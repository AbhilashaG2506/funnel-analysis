from flask import Flask, render_template, jsonify, request
import pandas as pd
import sqlite3
import joblib
import math
from pathlib import Path
from datetime import datetime

app = Flask(__name__)

BASE = Path(__file__).resolve().parent

DATA_FILE = BASE / "data" / "user_journey_data.csv"
DB_FILE = BASE / "data" / "user_journey.db"
MODEL_FILE = BASE / "models" / "dropout_model.pkl"
METRICS_FILE = BASE / "models" / "model_metrics.pkl"

FEATURES = [
    "age",
    "pages_visited",
    "session_duration",
    "clicks",
    "previous_visits"
]

STAGES = [
    "Home",
    "Sign Up",
    "Browse",
    "Product",
    "Add to Cart",
    "Checkout",
    "Purchase"
]

model = joblib.load(MODEL_FILE) if MODEL_FILE.exists() else None


# =========================================================
# CORS
# =========================================================

@app.after_request
def add_cors_headers(response):

    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"

    return response


# =========================================================
# DATA
# =========================================================

def load_data():

    return (
        pd.read_csv(DATA_FILE)
        if DATA_FILE.exists()
        else pd.DataFrame()
    )


def load_metrics():

    return (
        joblib.load(METRICS_FILE)
        if METRICS_FILE.exists()
        else {}
    )


def load_live_events():

    if not DB_FILE.exists():
        return pd.DataFrame()

    try:

        with sqlite3.connect(DB_FILE) as conn:

            return pd.read_sql_query(
                """
                SELECT *
                FROM user_events
                ORDER BY timestamp DESC
                """,
                conn
            )

    except Exception:

        return pd.DataFrame()


# =========================================================
# HISTORICAL STATISTICS
# =========================================================

def stats(df):

    if df.empty:

        return 0, 0, 0, 0.0

    total = len(df)

    dropped = int(
        pd.to_numeric(
            df.get("dropped_off", 0),
            errors="coerce"
        )
        .fillna(0)
        .sum()
    )

    not_dropped = total - dropped

    rate = (
        dropped / total * 100
        if total
        else 0
    )

    return (
        total,
        dropped,
        not_dropped,
        rate
    )


# =========================================================
# USER ID
# =========================================================

def next_user_id():

    live = load_live_events()

    if (
        live.empty
        or "user_id" not in live.columns
    ):

        return "U1001"

    nums = []

    for value in live["user_id"].dropna().astype(str):

        if value.startswith("U"):

            try:

                nums.append(
                    int(value[1:])
                )

            except ValueError:

                pass

    return (
        f"U{max(nums) + 1}"
        if nums
        else "U1001"
    )


# =========================================================
# DATABASE
# =========================================================

def ensure_table():

    DB_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with sqlite3.connect(DB_FILE) as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_events (

                timestamp TEXT,

                user_id TEXT,

                current_page TEXT,

                age INTEGER,

                pages_visited INTEGER,

                session_duration INTEGER,

                clicks INTEGER,

                previous_visits INTEGER,

                device TEXT,

                dropout_probability REAL,

                risk TEXT

            )
        """)

        # -------------------------------------------------
        # Check whether device column already exists
        # -------------------------------------------------

        columns = [
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(user_events)"
            ).fetchall()
        ]

        if "device" not in columns:

            conn.execute(
                """
                ALTER TABLE user_events
                ADD COLUMN device TEXT
                """
            )

        conn.commit()


# =========================================================
# DEVICE DETECTION
# =========================================================

def detect_device():

    user_agent = request.headers.get(
        "User-Agent",
        ""
    ).lower()

    if (
        "ipad" in user_agent
        or "tablet" in user_agent
    ):

        return "Tablet"

    if (
        "mobile" in user_agent
        or "iphone" in user_agent
        or "android" in user_agent
    ):

        return "Mobile"

    return "Desktop"


# =========================================================
# PREDICTION
# =========================================================

def calculate_prediction(
    age,
    pages,
    duration,
    clicks,
    previous_visits,
    page
):

    # -----------------------------------------------------
    # Purchase means completed journey
    # -----------------------------------------------------

    if (
        str(page)
        .strip()
        .lower()
        == "purchase"
    ):

        return 0.0, "LOW"

    # -----------------------------------------------------
    # If model is unavailable
    # -----------------------------------------------------

    if model is None:

        return 0.0, "LOW"

    data = pd.DataFrame([{

        "age": age,

        "pages_visited": pages,

        "session_duration": duration,

        "clicks": clicks,

        "previous_visits": previous_visits

    }])

    try:

        probability = float(
            model.predict_proba(
                data[FEATURES]
            )[0][1]
        )

        if not math.isfinite(
            probability
        ):

            probability = 0.0

        probability = max(
            0.0,
            min(
                probability,
                1.0
            )
        )

    except Exception:

        probability = 0.0

    # -----------------------------------------------------
    # Risk classification
    # -----------------------------------------------------

    if probability >= 0.70:

        risk = "HIGH"

    elif probability >= 0.40:

        risk = "MEDIUM"

    else:

        risk = "LOW"

    return (
        probability,
        risk
    )


# =========================================================
# SAVE EVENT
# =========================================================

def save_event(user):

    ensure_table()

    with sqlite3.connect(DB_FILE) as conn:

        conn.execute("""
            INSERT INTO user_events
            (
                timestamp,
                user_id,
                current_page,
                age,
                pages_visited,
                session_duration,
                clicks,
                previous_visits,
                device,
                dropout_probability,
                risk
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (

            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

            user["user_id"],

            user["current_page"],

            user["age"],

            user["pages_visited"],

            user["session_duration"],

            user["clicks"],

            user["previous_visits"],

            user["device"],

            user["dropout_probability"],

            user["risk"]

        ))

        conn.commit()


# =========================================================
# MAIN DASHBOARD
# =========================================================

@app.route("/")
def funnel():

    df = load_data()

    (
        total,
        dropped,
        not_dropped,
        rate
    ) = stats(df)

    return render_template(

        "dashboard.html",

        site="Funnel Analysis",

        page="Funnel Analysis",

        total=total,

        dropped=dropped,

        not_dropped=not_dropped,

        rate=rate,

        metrics=load_metrics()

    )


# =========================================================
# LIVE PREDICTION PAGE
# =========================================================

@app.route("/live")
def live():

    return render_template(

        "dashboard.html",

        site="Live Prediction",

        page="Live Prediction",

        next_user=next_user_id()

    )


# =========================================================
# HISTORICAL API
# =========================================================

@app.route("/api/historical")
def historical():

    df = load_data()

    (
        total,
        dropped,
        not_dropped,
        rate
    ) = stats(df)

    return jsonify({

        "total": total,

        "dropped": dropped,

        "not_dropped": not_dropped,

        "dropoff_rate": round(
            rate,
            2
        )

    })


# =========================================================
# LIVE EVENTS API
# ONE ROW PER USER
# =========================================================

@app.route("/api/live")
def api_live():

    live_df = load_live_events()

    # -----------------------------------------------------
    # No events
    # -----------------------------------------------------

    if live_df.empty:

        return jsonify({

            "events": [],

            "count": 0

        })

    # -----------------------------------------------------
    # IMPORTANT:
    #
    # load_live_events() already sorts by:
    #
    # timestamp DESC
    #
    # Therefore the FIRST record for each user
    # is their latest/current activity.
    # -----------------------------------------------------

    live_df = live_df.drop_duplicates(
        subset=["user_id"],
        keep="first"
    )

    # -----------------------------------------------------
    # Show maximum 50 current users
    # -----------------------------------------------------

    live_df = live_df.head(50)

    # -----------------------------------------------------
    # Convert to JSON records
    # -----------------------------------------------------

    records = (
        live_df
        .fillna("")
        .to_dict(
            orient="records"
        )
    )

    return jsonify({

        "events": records,

        "count": len(records)

    })


# =========================================================
# NEXT USER
# =========================================================

@app.route("/api/next-user")
def api_next_user():

    return jsonify({

        "user_id": next_user_id()

    })


# =========================================================
# PREDICTION API
# =========================================================

@app.route(
    "/api/predict",
    methods=["POST"]
)
def api_predict():

    data = request.get_json(
        force=True
    )

    probability, risk = calculate_prediction(

        int(
            data.get(
                "age",
                25
            )
        ),

        int(
            data.get(
                "pages_visited",
                1
            )
        ),

        int(
            data.get(
                "session_duration",
                0
            )
        ),

        int(
            data.get(
                "clicks",
                0
            )
        ),

        int(
            data.get(
                "previous_visits",
                0
            )
        ),

        data.get(
            "current_page",
            "Home"
        )

    )

    return jsonify({

        "probability":
            probability,

        "percentage":
            round(
                probability * 100,
                2
            ),

        "risk":
            risk

    })


# =========================================================
# SHOP EASY EVENT API
# =========================================================

@app.route(
    "/api/event",
    methods=["POST"]
)
def api_event():

    data = request.get_json(
        force=True
    )

    # -----------------------------------------------------
    # DEVICE
    # -----------------------------------------------------

    device = str(
        data.get(
            "device",
            detect_device()
        )
    )

    # -----------------------------------------------------
    # PREDICTION
    # -----------------------------------------------------

    probability, risk = calculate_prediction(

        int(
            data.get(
                "age",
                25
            )
        ),

        int(
            data.get(
                "pages_visited",
                1
            )
        ),

        int(
            data.get(
                "session_duration",
                0
            )
        ),

        int(
            data.get(
                "clicks",
                0
            )
        ),

        int(
            data.get(
                "previous_visits",
                0
            )
        ),

        data.get(
            "current_page",
            "Home"
        )

    )

    # -----------------------------------------------------
    # USER EVENT
    # -----------------------------------------------------

    user = {

        "user_id": str(
            data.get(
                "user_id",
                next_user_id()
            )
        ),

        "current_page": str(
            data.get(
                "current_page",
                "Home"
            )
        ),

        "age": int(
            data.get(
                "age",
                25
            )
        ),

        "pages_visited": int(
            data.get(
                "pages_visited",
                1
            )
        ),

        "session_duration": int(
            data.get(
                "session_duration",
                0
            )
        ),

        "clicks": int(
            data.get(
                "clicks",
                0
            )
        ),

        "previous_visits": int(
            data.get(
                "previous_visits",
                0
            )
        ),

        "device": device,

        "dropout_probability":
            probability,

        "risk":
            risk

    }

    # -----------------------------------------------------
    # SAVE EVENT
    #
    # Every event is still saved.
    # The dashboard simply displays one latest row
    # per user.
    # -----------------------------------------------------

    save_event(user)

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return jsonify({

        "ok": True,

        "user": user,

        "percentage":
            round(
                probability * 100,
                2
            )

    })


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":

    ensure_table()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )