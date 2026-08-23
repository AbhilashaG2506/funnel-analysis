from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
import os
import joblib
from datetime import datetime

# =========================================================
# FLASK APP
# =========================================================

app = Flask(__name__)
CORS(app)

# =========================================================
# MYSQL CONFIGURATION
# =========================================================
#
# Local MySQL:
# Host     : localhost
# Port     : 3306
# Username : root
# Password : stored in environment variable
# Database : funnel_analysis
# For Render, environment variables can override these.
# =========================================================

MYSQL_HOST = os.getenv("MYSQL_HOST", "mysql-664df23-funnelanalytics.f.aivencloud.com")

MYSQL_PORT = int(os.getenv("MYSQL_PORT", "11586"))

MYSQL_USER = os.getenv("MYSQL_USER", "avnadmin")

MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")

MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "defaultdb")


# =========================================================
# MODEL
# =========================================================

MODEL_FILE = "models/dropout_model.pkl"

model = None

try:
    if os.path.exists(MODEL_FILE):
        model = joblib.load(MODEL_FILE)
        print("✅ Drop-off model loaded successfully")
    else:
        print("⚠️ Model file not found:", MODEL_FILE)
except Exception as e:
    print("⚠️ Could not load model:", e)


# =========================================================
# MYSQL CONNECTION
# =========================================================

def get_db_connection():
    try:

        connection = mysql.connector.connect(
    host=MYSQL_HOST,
    port=MYSQL_PORT,
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    database=MYSQL_DATABASE,
    ssl_disabled=False
)

        return connection

    except Error as e:

        print("❌ MySQL connection error:", e)

        return None


# =========================================================
# CREATE TABLE IF REQUIRED
# =========================================================

def initialize_database():

    # First connect without database
    try:

        connection = mysql.connector.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD
        )

        cursor = connection.cursor()

        cursor.execute(
            f"""
            CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}`
            """
        )

        connection.commit()

        cursor.close()
        connection.close()

        print("✅ MySQL database checked:", MYSQL_DATABASE)

    except Error as e:

        print("❌ Could not create/check database:", e)

        return

    # Now connect to database
    connection = get_db_connection()

    if connection is None:
        return

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_events (

                id INT AUTO_INCREMENT PRIMARY KEY,

                user_id VARCHAR(100),

                clicks INT DEFAULT 0,

                session_duration FLOAT DEFAULT 0,

                device VARCHAR(50),

                pages_visited INT DEFAULT 0,

                current_page VARCHAR(100),

                dropoff_probability FLOAT DEFAULT 0,

                risk VARCHAR(20),

                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP

            )
            """
        )

        connection.commit()

        cursor.close()
        connection.close()

        print("✅ user_events table checked successfully")

    except Error as e:

        print("❌ Could not create user_events table:", e)


# =========================================================
# DROP-OFF PREDICTION
# =========================================================

def predict_dropoff(
    age,
    pages_visited,
    session_duration,
    clicks,
    previous_visits
):

    # -----------------------------------------------------
    # Use trained ML model if available
    # -----------------------------------------------------

    if model is not None:

        try:

            import pandas as pd

            prediction_data = pd.DataFrame({

                "age": [float(age)],

                "pages_visited": [
                    float(pages_visited)
                ],

                "session_duration": [
                    float(session_duration)
                ],

                "clicks": [
                    float(clicks)
                ],

                "previous_visits": [
                    float(previous_visits)
                ]

            })

            features = [
                "age",
                "pages_visited",
                "session_duration",
                "clicks",
                "previous_visits"
            ]

            probability = float(
                model.predict_proba(
                    prediction_data[features]
                )[0][1]
            )

            if probability >= 0.70:

                risk = "HIGH"

            elif probability >= 0.40:

                risk = "MEDIUM"

            else:

                risk = "LOW"

            return probability, risk

        except Exception as e:

            print("⚠️ Model prediction error:", e)

    # -----------------------------------------------------
    # Fallback prediction
    # -----------------------------------------------------

    # This is only used if the ML model is unavailable.

    risk_score = 0.0

    if pages_visited <= 2:
        risk_score += 0.30

    elif pages_visited <= 4:
        risk_score += 0.15

    if session_duration < 10:
        risk_score += 0.30

    elif session_duration < 30:
        risk_score += 0.15

    if clicks <= 2:
        risk_score += 0.20

    elif clicks <= 4:
        risk_score += 0.10

    if previous_visits == 0:
        risk_score += 0.20

    elif previous_visits <= 2:
        risk_score += 0.10

    probability = min(risk_score, 0.99)

    if probability >= 0.70:

        risk = "HIGH"

    elif probability >= 0.40:

        risk = "MEDIUM"

    else:

        risk = "LOW"

    return probability, risk


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/")
def home():
    return render_template(
        "dashboard.html",
        site="Funnel Analysis"
    )


@app.route("/live")
def live():
    return render_template(
        "dashboard.html",
        site="Live Prediction"
    )

# =========================================================
# MYSQL HEALTH CHECK
# =========================================================

@app.route("/api/health")
def health():

    connection = get_db_connection()

    if connection is None:

        return jsonify({
            "status": "error",
            "mysql": "disconnected",
            "database": MYSQL_DATABASE
        }), 500

    try:

        cursor = connection.cursor()

        cursor.execute("SELECT 1")

        cursor.fetchone()

        cursor.close()
        connection.close()

        return jsonify({
            "status": "ok",
            "mysql": "connected",
            "database": MYSQL_DATABASE
        })

    except Exception as e:

        return jsonify({
            "status": "error",
            "mysql": "error",
            "message": str(e)
        }), 500


# =========================================================
# RECEIVE LIVE USER EVENT
# =========================================================

@app.route("/api/event", methods=["POST", "OPTIONS"])
def receive_event():

    # -----------------------------------------------------
    # Handle browser CORS preflight
    # -----------------------------------------------------

    if request.method == "OPTIONS":

        return jsonify({
            "status": "ok"
        })

    # -----------------------------------------------------
    # Get JSON
    # -----------------------------------------------------

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "success": False,
            "message": "No JSON data received"
        }), 400

    print("\n📡 LIVE EVENT RECEIVED")
    print(data)

    # -----------------------------------------------------
    # Extract values
    # -----------------------------------------------------

    user_id = str(
        data.get(
            "user_id",
            "UNKNOWN"
        )
    )

    clicks = int(
        data.get(
            "clicks",
            0
        ) or 0
    )

    session_duration = float(
        data.get(
            "session_duration",
            data.get(
                "session_time",
                0
            )
        ) or 0
    )

    device = str(
        data.get(
            "device",
            "Desktop"
        )
    )

    pages_visited = int(
        data.get(
            "pages_visited",
            0
        ) or 0
    )

    current_page = str(
        data.get(
            "current_page",
            data.get(
                "page",
                "Home"
            )
        )
    )

    age = float(
        data.get(
            "age",
            25
        ) or 25
    )

    previous_visits = int(
        data.get(
            "previous_visits",
            0
        ) or 0
    )

    # -----------------------------------------------------
    # Predict drop-off
    # -----------------------------------------------------

    probability, risk = predict_dropoff(
        age=age,
        pages_visited=pages_visited,
        session_duration=session_duration,
        clicks=clicks,
        previous_visits=previous_visits
    )

    # -----------------------------------------------------
    # Insert into MySQL
    # -----------------------------------------------------

    connection = get_db_connection()

    if connection is None:

        return jsonify({
            "success": False,
            "message": "Could not connect to MySQL"
        }), 500

    try:

        cursor = connection.cursor()

        sql = """
            INSERT INTO user_events
            (
                user_id,
                clicks,
                session_duration,
                device,
                pages_visited,
                current_page,
                dropoff_probability,
                risk,
                timestamp
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
                %s
            )
        """

        values = (
            user_id,
            clicks,
            session_duration,
            device,
            pages_visited,
            current_page,
            probability,
            risk,
            datetime.now()
        )

        cursor.execute(
            sql,
            values
        )

        connection.commit()

        inserted_id = cursor.lastrowid

        cursor.close()
        connection.close()

        print(
            f"✅ Event stored in MySQL | "
            f"ID={inserted_id} | "
            f"User={user_id} | "
            f"Page={current_page} | "
            f"Risk={risk}"
        )

        return jsonify({

            "success": True,

            "message": "Event stored successfully",

            "id": inserted_id,

            "user_id": user_id,

            "current_page": current_page,

            "dropoff_probability": round(
                probability,
                4
            ),

            "dropoff_percentage": round(
                probability * 100,
                2
            ),

            "risk": risk

        }), 201

    except Error as e:

        print(
            "❌ MySQL insert error:",
            e
        )

        try:
            connection.close()
        except:
            pass

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# GET LIVE EVENTS
# =========================================================

@app.route("/api/live", methods=["GET"])
def get_live_events():

    connection = get_db_connection()

    if connection is None:

        return jsonify({
            "success": False,
            "message": "Could not connect to MySQL",
            "data": []
        }), 500

    try:

        cursor = connection.cursor(
            dictionary=True
        )

        cursor.execute(
            """
            SELECT
                id AS event_id,
                user_id,
                clicks,
                session_duration,
                device,
                pages_visited,
                current_page,
                dropoff_probability,
                risk,
                timestamp
            FROM user_events
            ORDER BY timestamp DESC
            LIMIT 100
            """
        )

        rows = cursor.fetchall()

        cursor.close()
        connection.close()

        # Convert datetime to JSON-compatible string
        for row in rows:

            if row.get("timestamp"):

                row["timestamp"] = (
                    row["timestamp"]
                    .strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                )

            if row.get(
                "dropoff_probability"
            ) is not None:

                row[
                    "dropoff_probability"
                ] = float(
                    row[
                        "dropoff_probability"
                    ]
                )

            if row.get(
                "session_duration"
            ) is not None:

                row[
                    "session_duration"
                ] = float(
                    row[
                        "session_duration"
                    ]
                )

        return jsonify({

            "success": True,

            "count": len(rows),

            "data": rows

        })

    except Error as e:

        print(
            "❌ MySQL read error:",
            e
        )

        try:
            connection.close()
        except:
            pass

        return jsonify({

            "success": False,

            "message": str(e),

            "data": []

        }), 500


# =========================================================
# GET LIVE SUMMARY
# =========================================================

@app.route("/api/live/summary", methods=["GET"])
def live_summary():

    connection = get_db_connection()

    if connection is None:

        return jsonify({
            "success": False,
            "message": "MySQL unavailable"
        }), 500

    try:

        cursor = connection.cursor(
            dictionary=True
        )

        # -----------------------------------------------
        # Total events
        # -----------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS total_events
            FROM user_events
            """
        )

        total_events = cursor.fetchone()[
            "total_events"
        ]

        # -----------------------------------------------
        # Active / unique users
        # -----------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(DISTINCT user_id)
            AS active_users
            FROM user_events
            """
        )

        active_users = cursor.fetchone()[
            "active_users"
        ]

        # -----------------------------------------------
        # High-risk users
        # -----------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS high_risk
            FROM user_events
            WHERE UPPER(risk) = 'HIGH'
            """
        )

        high_risk = cursor.fetchone()[
            "high_risk"
        ]

        # -----------------------------------------------
        # Last event
        # -----------------------------------------------

        cursor.execute(
            """
            SELECT timestamp
            FROM user_events
            ORDER BY timestamp DESC
            LIMIT 1
            """
        )

        last_event = cursor.fetchone()

        cursor.close()
        connection.close()

        last_update = None

        if last_event and last_event.get(
            "timestamp"
        ):

            last_update = (
                last_event[
                    "timestamp"
                ].strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )

        return jsonify({

            "success": True,

            "live_events": int(
                total_events
            ),

            "active_users": int(
                active_users
            ),

            "high_risk_users": int(
                high_risk
            ),

            "last_update": last_update

        })

    except Error as e:

        return jsonify({

            "success": False,

            "message": str(e)

        }), 500


# =========================================================
# DELETE LIVE DATA
# =========================================================

@app.route("/api/live/clear", methods=["DELETE"])
def clear_live_data():

    connection = get_db_connection()

    if connection is None:

        return jsonify({
            "success": False,
            "message": "MySQL unavailable"
        }), 500

    try:

        cursor = connection.cursor()

        cursor.execute(
            "DELETE FROM user_events"
        )

        connection.commit()

        deleted = cursor.rowcount

        cursor.close()
        connection.close()

        return jsonify({

            "success": True,

            "message": "Live data cleared",

            "deleted_rows": deleted

        })

    except Error as e:

        return jsonify({

            "success": False,

            "message": str(e)

        }), 500


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    print("\n======================================")
    print("🚀 FUNNEL ANALYTICS API")
    print("======================================")

    print(
        "MySQL Host:",
        MYSQL_HOST
    )

    print(
        "MySQL Database:",
        MYSQL_DATABASE
    )

    print(
        "MySQL User:",
        MYSQL_USER
    )

    initialize_database()

    print(
        "\n🌐 API running on:"
    )

    print(
        "http://127.0.0.1:5000"
    )

    print(
        "\nEndpoints:"
    )

    print(
        "GET  /api/health"
    )

    print(
        "POST /api/event"
    )

    print(
        "GET  /api/live"
    )

    print(
        "GET  /api/live/summary"
    )

    app.run(host="0.0.0.0", port=5000, debug=True)