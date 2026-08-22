from flask import Flask, render_template, jsonify, request
import pandas as pd
import mysql.connector
import joblib
import math
from pathlib import Path
from datetime import datetime


app = Flask(__name__)

BASE = Path(__file__).resolve().parent


# =========================================================
# FILE PATHS
# =========================================================

DATA_FILE = BASE / "data" / "user_journey_data.csv"
MODEL_FILE = BASE / "models" / "dropout_model.pkl"
METRICS_FILE = BASE / "models" / "model_metrics.pkl"


# =========================================================
# MYSQL CONNECTION
# =========================================================

def get_mysql_connection():

    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Abhilasha@123",
        database="funnel_analysis"
    )


# =========================================================
# ML FEATURES
# =========================================================

FEATURES = [
    "age",
    "pages_visited",
    "session_duration",
    "clicks",
    "previous_visits"
]


# =========================================================
# FUNNEL STAGES
# =========================================================

STAGES = [
    "Home",
    "Sign Up",
    "Browse",
    "Product",
    "Add to Cart",
    "Checkout",
    "Purchase"
]


# =========================================================
# LOAD MACHINE LEARNING MODEL
# =========================================================

model = (
    joblib.load(MODEL_FILE)
    if MODEL_FILE.exists()
    else None
)


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
# HISTORICAL DATA
# =========================================================

def load_data():

    if not DATA_FILE.exists():

        return pd.DataFrame()

    try:

        return pd.read_csv(DATA_FILE)

    except Exception as e:

        print("CSV read error:", e)

        return pd.DataFrame()


# =========================================================
# MODEL METRICS
# =========================================================

def load_metrics():

    if not METRICS_FILE.exists():

        return {}

    try:

        return joblib.load(METRICS_FILE)

    except Exception as e:

        print("Metrics read error:", e)

        return {}


# =========================================================
# CREATE MYSQL LIVE TABLE
#
# SQLite is completely removed.
#
# MySQL database:
#
# funnel_analysis
#       |
#       |---- funnel_data
#       |
#       |---- live_events
#
# =========================================================

def ensure_mysql_tables():

    connection = None
    cursor = None

    try:

        connection = get_mysql_connection()

        cursor = connection.cursor()

        # -------------------------------------------------
        # LIVE EVENTS TABLE
        # -------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS live_events (

                id INT AUTO_INCREMENT PRIMARY KEY,

                timestamp DATETIME NOT NULL,

                user_id INT NOT NULL,

                current_page VARCHAR(100),

                age INT,

                pages_visited INT,

                session_duration INT,

                clicks INT,

                previous_visits INT,

                device VARCHAR(50),

                dropout_probability DECIMAL(10,8),

                risk VARCHAR(20)

            )
        """)

        connection.commit()

        print("MySQL live_events table ready.")

    except Exception as e:

        print("MySQL table error:", e)

    finally:

        if cursor is not None:

            cursor.close()

        if connection is not None:

            connection.close()


# =========================================================
# LOAD LIVE EVENTS FROM MYSQL
# =========================================================

def load_live_events():

    connection = None
    cursor = None

    try:

        connection = get_mysql_connection()

        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                id,
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
            FROM live_events
            ORDER BY timestamp DESC, id DESC
        """)

        rows = cursor.fetchall()

        if not rows:

            return pd.DataFrame()

        df = pd.DataFrame(rows)

        return df

    except Exception as e:

        print("MySQL live event read error:", e)

        return pd.DataFrame()

    finally:

        if cursor is not None:

            cursor.close()

        if connection is not None:

            connection.close()


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
# NEXT USER ID
#
# Checks both:
#
# 1. funnel_data
# 2. live_events
#
# Then generates:
#
# U1001
# U1002
# U1003
#
# =========================================================

def next_user_id():

    connection = None
    cursor = None

    try:

        connection = get_mysql_connection()

        cursor = connection.cursor()

        # -------------------------------------------------
        # Highest user ID in funnel_data
        # -------------------------------------------------

        cursor.execute("""
            SELECT COALESCE(MAX(user_id), 1000)
            FROM funnel_data
        """)

        funnel_result = cursor.fetchone()

        funnel_max = (
            int(funnel_result[0])
            if funnel_result and funnel_result[0] is not None
            else 1000
        )

        # -------------------------------------------------
        # Highest user ID in live_events
        # -------------------------------------------------

        cursor.execute("""
            SELECT COALESCE(MAX(user_id), 1000)
            FROM live_events
        """)

        live_result = cursor.fetchone()

        live_max = (
            int(live_result[0])
            if live_result and live_result[0] is not None
            else 1000
        )

        # -------------------------------------------------
        # Select highest ID
        # -------------------------------------------------

        maximum = max(
            funnel_max,
            live_max
        )

        return f"U{maximum + 1}"

    except Exception as e:

        print("Next user ID error:", e)

        return "U1001"

    finally:

        if cursor is not None:

            cursor.close()

        if connection is not None:

            connection.close()


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
    # PURCHASE = COMPLETED JOURNEY
    # -----------------------------------------------------

    if (
        str(page)
        .strip()
        .lower()
        == "purchase"
    ):

        return 0.0, "LOW"

    # -----------------------------------------------------
    # MODEL NOT AVAILABLE
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

        # -------------------------------------------------
        # Check valid number
        # -------------------------------------------------

        if not math.isfinite(
            probability
        ):

            probability = 0.0

        # -------------------------------------------------
        # Keep between 0 and 1
        # -------------------------------------------------

        probability = max(
            0.0,
            min(
                probability,
                1.0
            )
        )

    except Exception as e:

        print(
            "Prediction error:",
            e
        )

        probability = 0.0

    # -----------------------------------------------------
    # RISK LEVEL
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
# SAVE LIVE EVENT TO MYSQL
# =========================================================

def save_live_event(user):

    connection = None
    cursor = None

    try:

        connection = get_mysql_connection()

        cursor = connection.cursor()

        # -------------------------------------------------
        # Convert U1001 -> 1001
        # -------------------------------------------------

        raw_user_id = str(
            user["user_id"]
        )

        if raw_user_id.startswith("U"):

            mysql_user_id = int(
                raw_user_id[1:]
            )

        else:

            mysql_user_id = int(
                raw_user_id
            )

        # -------------------------------------------------
        # INSERT LIVE EVENT
        # -------------------------------------------------

        query = """
            INSERT INTO live_events
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
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
        """

        values = (

            datetime.now(),

            mysql_user_id,

            user["current_page"],

            user["age"],

            user["pages_visited"],

            user["session_duration"],

            user["clicks"],

            user["previous_visits"],

            user["device"],

            user["dropout_probability"],

            user["risk"]

        )

        cursor.execute(
            query,
            values
        )

        connection.commit()

        print(
            "Live event saved to MySQL:",
            mysql_user_id,
            user["current_page"]
        )

    except Exception as e:

        print(
            "MySQL live event save error:",
            e
        )

    finally:

        if cursor is not None:

            cursor.close()

        if connection is not None:

            connection.close()


# =========================================================
# SAVE SHOP EASY EVENT TO FUNNEL_DATA
#
# Existing MySQL table:
#
# funnel_analysis
#       |
#       └── funnel_data
#
# =========================================================

def save_event_to_mysql(data, user):

    connection = None
    cursor = None

    try:

        connection = get_mysql_connection()

        cursor = connection.cursor()

        # -------------------------------------------------
        # USER ID
        #
        # Website:
        # U1001
        #
        # MySQL:
        # 1001
        # -------------------------------------------------

        raw_user_id = str(
            user["user_id"]
        )

        if raw_user_id.startswith("U"):

            mysql_user_id = int(
                raw_user_id[1:]
            )

        else:

            mysql_user_id = int(
                raw_user_id
            )

        # -------------------------------------------------
        # CURRENT PAGE
        # -------------------------------------------------

        current_page = str(
            user["current_page"]
        ).strip()

        # -------------------------------------------------
        # TRAFFIC SOURCE
        # -------------------------------------------------

        traffic_source = str(
            data.get(
                "traffic_source",
                "Direct"
            )
        )

        # -------------------------------------------------
        # LANDING PAGE
        # -------------------------------------------------

        landing_page = str(
            data.get(
                "landing_page",
                "Home"
            )
        )

        # -------------------------------------------------
        # PRODUCT
        # -------------------------------------------------

        product_viewed = data.get(
            "product_viewed",
            None
        )

        if (
            product_viewed is None
            and current_page.lower()
            == "product"
        ):

            product_viewed = "Product Page"

        # -------------------------------------------------
        # ADD TO CART
        # -------------------------------------------------

        added_to_cart = int(
            data.get(
                "added_to_cart",
                1
                if current_page.lower()
                == "add to cart"
                else 0
            )
        )

        # -------------------------------------------------
        # CHECKOUT
        # -------------------------------------------------

        checkout_started = int(
            data.get(
                "checkout_started",
                1
                if current_page.lower()
                == "checkout"
                else 0
            )
        )

        # -------------------------------------------------
        # PURCHASE
        # -------------------------------------------------

        purchase_completed = int(
            data.get(
                "purchase_completed",
                1
                if current_page.lower()
                == "purchase"
                else 0
            )
        )

        # -------------------------------------------------
        # PURCHASE AMOUNT
        # -------------------------------------------------

        purchase_amount = float(
            data.get(
                "purchase_amount",
                0
            ) or 0
        )

        # -------------------------------------------------
        # INSERT INTO FUNNEL_DATA
        # -------------------------------------------------

        query = """
            INSERT INTO funnel_data
            (
                user_id,
                visit_date,
                traffic_source,
                device,
                landing_page,
                product_viewed,
                added_to_cart,
                checkout_started,
                purchase_completed,
                purchase_amount
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
        """

        values = (

            mysql_user_id,

            datetime.now().date(),

            traffic_source,

            user["device"],

            landing_page,

            product_viewed,

            added_to_cart,

            checkout_started,

            purchase_completed,

            purchase_amount

        )

        cursor.execute(
            query,
            values
        )

        connection.commit()

        print(
            "Funnel event saved successfully:",
            mysql_user_id,
            current_page
        )

    except Exception as e:

        print(
            "MySQL funnel save error:",
            e
        )

    finally:

        if cursor is not None:

            cursor.close()

        if connection is not None:

            connection.close()


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

        "total":
            total,

        "dropped":
            dropped,

        "not_dropped":
            not_dropped,

        "dropoff_rate":
            round(
                rate,
                2
            )

    })


# =========================================================
# LIVE EVENTS API
#
# IMPORTANT:
# ONE ROW PER USER IS DISPLAYED
#
# All events remain stored in MySQL.
# The dashboard only displays the latest
# event for each user.
# =========================================================

@app.route("/api/live")
def api_live():

    live_df = load_live_events()

    # -----------------------------------------------------
    # NO LIVE EVENTS
    # -----------------------------------------------------

    if live_df.empty:

        return jsonify({

            "events": [],

            "count": 0

        })

    # -----------------------------------------------------
    # TIMESTAMP
    # -----------------------------------------------------

    live_df["timestamp"] = pd.to_datetime(
        live_df["timestamp"],
        errors="coerce"
    )

    # -----------------------------------------------------
    # NEWEST FIRST
    # -----------------------------------------------------

    live_df = live_df.sort_values(

        [
            "timestamp",
            "id"
        ],

        ascending=[
            False,
            False
        ]

    )

    # -----------------------------------------------------
    # ONLY LATEST EVENT FOR EACH USER
    #
    # Example:
    #
    # U1001 -> Home
    # U1001 -> Browse
    # U1001 -> Product
    #
    # Dashboard displays:
    #
    # U1001 -> Product
    #
    # But all 3 records remain in MySQL.
    # -----------------------------------------------------

    live_df = live_df.drop_duplicates(

        subset=[
            "user_id"
        ],

        keep="first"

    )

    # -----------------------------------------------------
    # MAXIMUM 50 CURRENT USERS
    # -----------------------------------------------------

    live_df = live_df.head(50)

    # -----------------------------------------------------
    # CONVERT USER ID
    #
    # MySQL:
    # 1001
    #
    # Dashboard:
    # U1001
    # -----------------------------------------------------

    live_df["user_id"] = live_df[
        "user_id"
    ].apply(
        lambda x: f"U{int(x)}"
        if str(x).isdigit()
        else str(x)
    )

    # -----------------------------------------------------
    # FORMAT TIMESTAMP
    # -----------------------------------------------------

    live_df["timestamp"] = (
        live_df["timestamp"]
        .dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    # -----------------------------------------------------
    # JSON RECORDS
    # -----------------------------------------------------

    records = (
        live_df
        .fillna("")
        .to_dict(
            orient="records"
        )
    )

    return jsonify({

        "events":
            records,

        "count":
            len(records)

    })


# =========================================================
# NEXT USER API
# =========================================================

@app.route("/api/next-user")
def api_next_user():

    return jsonify({

        "user_id":
            next_user_id()

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
    # CURRENT PAGE
    # -----------------------------------------------------

    current_page = str(
        data.get(
            "current_page",
            "Home"
        )
    )

    # -----------------------------------------------------
    # USER ID
    # -----------------------------------------------------

    user_id = str(
        data.get(
            "user_id",
            next_user_id()
        )
    )

    # -----------------------------------------------------
    # USER INFORMATION
    # -----------------------------------------------------

    age = int(
        data.get(
            "age",
            25
        )
    )

    pages_visited = int(
        data.get(
            "pages_visited",
            1
        )
    )

    session_duration = int(
        data.get(
            "session_duration",
            0
        )
    )

    clicks = int(
        data.get(
            "clicks",
            0
        )
    )

    previous_visits = int(
        data.get(
            "previous_visits",
            0
        )
    )

    # -----------------------------------------------------
    # ML PREDICTION
    # -----------------------------------------------------

    probability, risk = calculate_prediction(

        age,

        pages_visited,

        session_duration,

        clicks,

        previous_visits,

        current_page

    )

    # -----------------------------------------------------
    # CREATE USER EVENT
    # -----------------------------------------------------

    user = {

        "user_id":
            user_id,

        "current_page":
            current_page,

        "age":
            age,

        "pages_visited":
            pages_visited,

        "session_duration":
            session_duration,

        "clicks":
            clicks,

        "previous_visits":
            previous_visits,

        "device":
            device,

        "dropout_probability":
            probability,

        "risk":
            risk

    }

    # -----------------------------------------------------
    # SAVE LIVE PREDICTION EVENT TO MYSQL
    # -----------------------------------------------------

    save_live_event(user)

    # -----------------------------------------------------
    # SAVE SHOP EASY FUNNEL EVENT TO MYSQL
    # -----------------------------------------------------

    save_event_to_mysql(
        data,
        user
    )

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return jsonify({

        "ok":
            True,

        "user":
            user,

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

    # -----------------------------------------------------
    # Make sure MySQL live_events table exists
    # -----------------------------------------------------

    ensure_mysql_tables()

    # -----------------------------------------------------
    # START FLASK
    # -----------------------------------------------------

    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True

    )