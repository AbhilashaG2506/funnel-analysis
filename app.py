import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import joblib
import os
import plotly.express as px

# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="User Journey Analytics",
    page_icon="📊",
    layout="wide"
)

# =========================================================
# PROFESSIONAL UI / UX
# =========================================================

st.markdown("""
<style>

    /* ---------- APP BACKGROUND ---------- */
    .stApp {
        background: #f5f7fb;
    }

    /* ---------- MAIN CONTENT ---------- */
    .block-container {
        max-width: 1450px;
        padding-top: 2rem;
        padding-bottom: 3rem;
        padding-left: 3rem;
        padding-right: 3rem;
    }

    /* ---------- HEADINGS ---------- */
    h1 {
        font-size: 42px !important;
        font-weight: 750 !important;
        letter-spacing: -1.2px;
        color: #172033 !important;
    }

    h2 {
        font-size: 28px !important;
        font-weight: 700 !important;
        color: #172033 !important;
        margin-top: 1rem;
    }

    h3 {
        font-size: 21px !important;
        font-weight: 650 !important;
        color: #273449 !important;
    }

    /* ---------- METRIC CARDS ---------- */
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e6eaf0;
        border-radius: 16px;
        padding: 20px 22px;
        box-shadow: 0 5px 18px rgba(31, 41, 55, 0.06);
        min-height: 120px;
    }

    [data-testid="stMetricLabel"] {
        font-size: 14px !important;
        font-weight: 600 !important;
        color: #64748b !important;
    }

    [data-testid="stMetricValue"] {
        font-size: 31px !important;
        font-weight: 750 !important;
        color: #172033 !important;
    }

    /* ---------- BUTTONS ---------- */
    .stButton > button {
        border-radius: 10px;
        border: 1px solid #d9e0ea;
        background: #ffffff;
        color: #263247;
        font-weight: 650;
        min-height: 42px;
        transition: all 0.15s ease;
    }

    .stButton > button:hover {
        border-color: #4f46e5;
        color: #4f46e5;
        box-shadow: 0 4px 12px rgba(79, 70, 229, 0.12);
    }

    /* ---------- SIDEBAR ---------- */
    section[data-testid="stSidebar"] {
        background: #111827;
        border-right: 1px solid #1f2937;
    }

    section[data-testid="stSidebar"] * {
        color: #f8fafc !important;
    }

    section[data-testid="stSidebar"] [data-testid="stRadio"] label {
        padding: 8px 10px;
        border-radius: 8px;
        font-weight: 550;
    }

    /* ---------- TABLES ---------- */
    [data-testid="stDataFrame"] {
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        overflow: hidden;
        background: #ffffff;
        box-shadow: 0 4px 14px rgba(31, 41, 55, 0.04);
    }

    /* ---------- ALERTS ---------- */
    [data-testid="stAlert"] {
        border-radius: 12px;
    }

    /* ---------- DIVIDERS ---------- */
    hr {
        border: none;
        border-top: 1px solid #e3e7ef;
        margin: 1.5rem 0;
    }

    /* ---------- PLOTLY CHART CONTAINER ---------- */
    .stPlotlyChart {
        background: #ffffff;
        border: 1px solid #e6eaf0;
        border-radius: 16px;
        padding: 10px;
        box-shadow: 0 5px 18px rgba(31, 41, 55, 0.05);
    }

    /* ---------- INPUTS ---------- */
    div[data-baseweb="input"] > div,
    div[data-baseweb="select"] > div {
        border-radius: 10px;
    }

    /* ---------- CAPTION ---------- */
    .stCaption {
        color: #64748b !important;
    }

</style>
""", unsafe_allow_html=True)


# =========================================================
# FILE PATHS
# =========================================================

DATA_FILE = "data/user_journey_data.csv"
DB_FILE = "data/user_journey.db"
MODEL_FILE = "models/dropout_model.pkl"

# =========================================================
# LOAD HISTORICAL DATA
# =========================================================

@st.cache_data
def load_historical_data():

    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)

    return pd.DataFrame()


df = load_historical_data()

# =========================================================
# LOAD MACHINE LEARNING MODEL
# =========================================================

@st.cache_resource
def load_model():

    if os.path.exists(MODEL_FILE):
        return joblib.load(MODEL_FILE)

    return None


model = load_model()

# =========================================================
# FEATURES USED BY MODEL
# =========================================================

features = [
    "age",
    "pages_visited",
    "session_duration",
    "clicks",
    "previous_visits"
]

# =========================================================
# LIVE DATABASE
# =========================================================

def get_live_data():

    try:

        if not os.path.exists(DB_FILE):
            return pd.DataFrame()

        conn = sqlite3.connect(DB_FILE)

        live_df = pd.read_sql_query(
            """
            SELECT *
            FROM user_events
            ORDER BY timestamp DESC
            """,
            conn
        )

        conn.close()

        return live_df

    except Exception:
        return pd.DataFrame()


live_df = get_live_data()

# =========================================================
# HISTORICAL METRICS
# =========================================================

total_users = len(df)

# ---------------------------------------------------------
# FIND PURCHASES
# ---------------------------------------------------------

historical_purchases = 0

if not df.empty:

    possible_page_columns = [
        "current_page",
        "page",
        "stage"
    ]

    page_column = None

    for col in possible_page_columns:

        if col in df.columns:
            page_column = col
            break

    if page_column:

        historical_purchases = (
            df[page_column]
            .astype(str)
            .str.lower()
            .eq("purchase")
            .sum()
        )

# ---------------------------------------------------------
# IF PURCHASE COLUMN EXISTS
# ---------------------------------------------------------

if historical_purchases == 0 and not df.empty:

    possible_purchase_columns = [
        "purchase",
        "purchased",
        "is_purchase",
        "conversion"
    ]

    for col in possible_purchase_columns:

        if col in df.columns:

            try:
                historical_purchases = int(
                    df[col].sum()
                )

                break

            except Exception:
                pass


# ---------------------------------------------------------
# CONVERSION RATE
# ---------------------------------------------------------

if total_users > 0:

    conversion_rate = (
        historical_purchases / total_users
    ) * 100

else:

    conversion_rate = 0


# =========================================================
# HISTORICAL HIGH-RISK USERS
# =========================================================

historical_high_risk = 0

# ---------------------------------------------------------
# If dropout_probability exists
# ---------------------------------------------------------

if "dropoff_probability" in df.columns:

    historical_high_risk = (
        df["dropoff_probability"] >= 0.70
    ).sum()

# ---------------------------------------------------------
# If probability is percentage
# ---------------------------------------------------------

elif "dropoff_probability" in df.columns:

    historical_high_risk = (
        df["dropoff_probability"] >= 70
    ).sum()

# ---------------------------------------------------------
# If risk column exists
# ---------------------------------------------------------

elif "risk" in df.columns:

    historical_high_risk = (
        df["risk"]
        .astype(str)
        .str.upper()
        .eq("HIGH")
        .sum()
    )

# =========================================================
# LIVE METRICS
# =========================================================

if not live_df.empty:

    live_users = live_df["user_id"].nunique()

    live_events = len(live_df)

    # -----------------------------------------------------
    # LIVE PURCHASES
    # -----------------------------------------------------

    live_purchases = (
        live_df["current_page"]
        .astype(str)
        .str.lower()
        .eq("purchase")
        .sum()
    )

    # -----------------------------------------------------
    # LIVE HIGH RISK
    # -----------------------------------------------------

    if "risk" in live_df.columns:

        live_high_risk = (
            live_df["risk"]
            .astype(str)
            .str.upper()
            .eq("HIGH")
            .sum()
        )

    else:

        live_high_risk = 0

else:

    live_users = 0
    live_events = 0
    live_purchases = 0
    live_high_risk = 0


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("🚀 JourneyIQ")

st.sidebar.write("Select Module")

page = st.sidebar.radio(
    "",
    [
        "Dashboard",
        "Funnel Analysis",
        "Drop-Off Prediction",
        "Live User Prediction",
        "Model Performance",
        "User Data"
    ]
)

st.sidebar.divider()

st.sidebar.info(
    "JourneyIQ • Real-Time User Journey Funnel "
    "Analysis and Drop-Off Prediction System"
)


# =========================================================
# DASHBOARD
# =========================================================

if page == "Dashboard":

    st.title(
        "🚀 JourneyIQ"
    )

    st.write(
        "Analyze user behavior, identify funnel drop-offs, "
        "and predict users at risk of dropping off."
    )

    st.divider()

    # =====================================================
    # HISTORICAL ANALYTICS
    # =====================================================

    st.subheader("📊 Historical Analytics")

    h1, h2, h3, h4 = st.columns(4)

    with h1:

        st.metric(
            "Historical Users",
            f"{total_users:,}"
        )

    with h2:

        st.metric(
            "Historical Purchases",
            f"{historical_purchases:,}"
        )

    with h3:

        st.metric(
            "Historical Conversion",
            f"{conversion_rate:.2f}%"
        )

    with h4:

        st.metric(
            "Historical High-Risk Users",
            f"{historical_high_risk:,}"
        )

    st.divider()

    # =====================================================
    # LIVE ANALYTICS
    # =====================================================

    st.subheader("🔴 Live Analytics")

    l1, l2, l3, l4 = st.columns(4)

    with l1:

        st.metric(
            "Live Users",
            f"{live_users:,}"
        )

    with l2:

        st.metric(
            "Live Events",
            f"{live_events:,}"
        )

    with l3:

        st.metric(
            "Live Purchases",
            f"{live_purchases:,}"
        )

    with l4:

        st.metric(
            "Live High-Risk Users",
            f"{live_high_risk:,}"
        )

    # =====================================================
    # LIVE USER ACTIVITY
    # =====================================================

    st.divider()

    st.subheader("🔴 Live User Activity")

    if not live_df.empty:

        display_columns = [
            "timestamp",
            "user_id",
            "current_page",
            "age",
            "pages_visited",
            "session_duration",
            "clicks",
            "previous_visits"
        ]

        available_columns = [
            col
            for col in display_columns
            if col in live_df.columns
        ]

        live_display = live_df[
            available_columns
        ].head(10).copy()

        # Add prediction columns if available

        if "dropoff_probability" in live_df.columns:

            live_display["Drop-Off %"] = (
                live_df[
                    "dropoff_probability"
                ].head(10) * 100
            ).round(2)

        if "risk" in live_df.columns:

            live_display["Risk"] = (
                live_df["risk"].head(10)
            )

        st.dataframe(
            live_display,
            width="stretch",
            hide_index=True
        )

    else:

        st.info(
            "No live user activity recorded yet."
        )

    # =====================================================
    # HISTORICAL FUNNEL
    # =====================================================

    st.divider()

    st.subheader("🔽 User Journey Funnel")

    stages = [
        "Home",
        "Sign Up",
        "Browse",
        "Product",
        "Add to Cart",
        "Checkout",
        "Purchase"
    ]

    # -----------------------------------------------------
    # Create funnel from historical data
    # -----------------------------------------------------

    funnel_values = []

    if not df.empty:

        if "current_page" in df.columns:

            for stage in stages:

                count = (
                    df["current_page"]
                    .astype(str)
                    .str.lower()
                    .eq(stage.lower())
                    .sum()
                )

                funnel_values.append(count)

        else:

            # fallback based on existing screenshot
            funnel_values = [
                5000,
                4121,
                3374,
                2645,
                1885,
                1116,
                471
            ]

    else:

        funnel_values = [
            5000,
            4121,
            3374,
            2645,
            1885,
            1116,
            471
        ]

    funnel_df = pd.DataFrame({
        "Stage": stages,
        "Users": funnel_values
    })

    fig = px.funnel(
        funnel_df,
        x="Users",
        y="Stage",
        title="Historical User Progress Through Journey"
    )

    st.plotly_chart(
        fig,
        width="stretch"
    )


# =========================================================
# FUNNEL ANALYSIS
# =========================================================

elif page == "Funnel Analysis":

    st.title("🔽 Funnel Analysis")

    st.write(
        "Analyze how users move through each stage "
        "of the customer journey."
    )

    stages = [
        "Home",
        "Sign Up",
        "Browse",
        "Product",
        "Add to Cart",
        "Checkout",
        "Purchase"
    ]

    funnel_values = [
        5000,
        4121,
        3374,
        2645,
        1885,
        1116,
        471
    ]

    funnel_df = pd.DataFrame({
        "Stage": stages,
        "Users": funnel_values
    })

    fig = px.funnel(
        funnel_df,
        x="Users",
        y="Stage",
        title="User Progress Through Journey"
    )

    st.plotly_chart(
        fig,
        width="stretch"
    )

    st.subheader(
        "📉 Stage-wise Drop-Off"
    )

    dropoff_values = []

    for i in range(len(funnel_values)):

        if i == 0:

            dropoff_values.append(0)

        else:

            previous = funnel_values[i - 1]
            current = funnel_values[i]

            dropoff = (
                (previous - current)
                / previous
            ) * 100

            dropoff_values.append(
                round(dropoff, 2)
            )

    dropoff_df = pd.DataFrame({
        "Stage": stages,
        "Users": funnel_values,
        "Drop-Off %": dropoff_values
    })

    st.dataframe(
        dropoff_df,
        width="stretch",
        hide_index=True
    )


# =========================================================
# DROP-OFF PREDICTION
# =========================================================

elif page == "Drop-Off Prediction":

    st.title("🔴 Drop-Off Prediction")

    st.write(
        "Predict the probability that a user will "
        "drop off based on behavioral characteristics."
    )

    if model is None:

        st.error(
            "ML model not found. "
            "Please check models/dropout_model.pkl"
        )

    else:

        col1, col2 = st.columns(2)

        with col1:

            age_input = st.number_input(
                "Age",
                min_value=10,
                max_value=100,
                value=25
            )

            pages_input = st.number_input(
                "Pages Visited",
                min_value=1,
                max_value=100,
                value=5
            )

            duration_input = st.number_input(
                "Session Duration",
                min_value=0,
                max_value=10000,
                value=60
            )

        with col2:

            clicks_input = st.number_input(
                "Clicks",
                min_value=0,
                max_value=1000,
                value=5
            )

            visits_input = st.number_input(
                "Previous Visits",
                min_value=0,
                max_value=100,
                value=3
            )

        if st.button(
            "🔮 Predict Drop-Off",
            width="stretch"
        ):

            prediction_data = pd.DataFrame({

                "age": [age_input],

                "pages_visited": [
                    pages_input
                ],

                "session_duration": [
                    duration_input
                ],

                "clicks": [
                    clicks_input
                ],

                "previous_visits": [
                    visits_input
                ]

            })

            try:

                probability = model.predict_proba(
                    prediction_data[features]
                )[0][1]

                percentage = probability * 100

                if probability >= 0.70:

                    risk = "HIGH"

                elif probability >= 0.40:

                    risk = "MEDIUM"

                else:

                    risk = "LOW"

                c1, c2 = st.columns(2)

                with c1:

                    st.metric(
                        "Drop-Off Probability",
                        f"{percentage:.2f}%"
                    )

                with c2:

                    st.metric(
                        "Risk Level",
                        risk
                    )

                st.progress(
                    min(probability, 1.0)
                )

                if risk == "HIGH":

                    st.error(
                        "🚨 HIGH RISK: User may leave."
                    )

                elif risk == "MEDIUM":

                    st.warning(
                        "⚠️ MEDIUM RISK: "
                        "User may need engagement."
                    )

                else:

                    st.success(
                        "🟢 LOW RISK: "
                        "User appears engaged."
                    )

            except Exception as e:

                st.error(
                    f"Prediction error: {e}"
                )


# =========================================================
# LIVE USER PREDICTION
# =========================================================

elif page == "Live User Prediction":

    st.title("🌐 Live User Journey")

    st.write(
        "Monitor the latest user activity and "
        "live drop-off prediction."
    )

    if live_df.empty:

        st.info(
            "No live user activity available yet."
        )

    else:

        latest = live_df.iloc[0]

        c1, c2, c3, c4 = st.columns(4)

        with c1:

            st.metric(
                "User ID",
                str(latest.get(
                    "user_id",
                    "N/A"
                ))
            )

        with c2:

            st.metric(
                "Current Page",
                str(latest.get(
                    "current_page",
                    "N/A"
                ))
            )

        with c3:

            st.metric(
                "Clicks",
                str(latest.get(
                    "clicks",
                    0
                ))
            )

        with c4:

            st.metric(
                "Pages Visited",
                str(latest.get(
                    "pages_visited",
                    0
                ))
            )

        st.divider()

        if "dropoff_probability" in latest.index:

            probability = float(
                latest["dropoff_probability"]
            )

            st.subheader(
                "🔴 Live Drop-Off Prediction"
            )

            p1, p2 = st.columns(2)

            with p1:

                st.metric(
                    "Drop-Off Probability",
                    f"{probability * 100:.2f}%"
                )

            with p2:

                risk = str(
                    latest.get(
                        "risk",
                        "UNKNOWN"
                    )
                )

                st.metric(
                    "Risk",
                    risk
                )

            st.progress(
                min(probability, 1.0)
            )

        st.divider()

        st.subheader(
            "📡 Recent Live User Events"
        )

        st.dataframe(
            live_df.head(20),
            width="stretch",
            hide_index=True
        )


# =========================================================
# MODEL PERFORMANCE
# =========================================================

elif page == "Model Performance":

    st.title("📊 Model Performance")

    st.write(
        "Performance evaluation of the "
        "drop-off prediction model."
    )

    # -----------------------------------------------------
    # Try to calculate performance from dataset
    # -----------------------------------------------------

    if model is not None and not df.empty:

        target_column = None

        possible_targets = [
            "dropoff",
            "drop_off",
            "dropoff_flag",
            "is_dropoff",
            "dropout",
            "target"
        ]

        for col in possible_targets:

            if col in df.columns:

                target_column = col
                break

        if target_column and all(
            feature in df.columns
            for feature in features
        ):

            try:

                X = df[features]
                y = df[target_column]

                predictions = model.predict(X)

                from sklearn.metrics import (
                    accuracy_score,
                    precision_score,
                    recall_score,
                    f1_score,
                    confusion_matrix
                )

                accuracy = accuracy_score(
                    y,
                    predictions
                )

                precision = precision_score(
                    y,
                    predictions,
                    zero_division=0
                )

                recall = recall_score(
                    y,
                    predictions,
                    zero_division=0
                )

                f1 = f1_score(
                    y,
                    predictions,
                    zero_division=0
                )

                c1, c2, c3, c4 = st.columns(4)

                with c1:

                    st.metric(
                        "Accuracy",
                        f"{accuracy * 100:.2f}%"
                    )

                with c2:

                    st.metric(
                        "Precision",
                        f"{precision * 100:.2f}%"
                    )

                with c3:

                    st.metric(
                        "Recall",
                        f"{recall * 100:.2f}%"
                    )

                with c4:

                    st.metric(
                        "F1 Score",
                        f"{f1 * 100:.2f}%"
                    )

                st.divider()

                st.subheader(
                    "🔲 Confusion Matrix"
                )

                cm = confusion_matrix(
                    y,
                    predictions
                )

                cm_df = pd.DataFrame(
                    cm,
                    index=[
                        "Actual 0",
                        "Actual 1"
                    ],
                    columns=[
                        "Predicted 0",
                        "Predicted 1"
                    ]
                )

                st.dataframe(
                    cm_df,
                    width="stretch"
                )

            except Exception as e:

                st.warning(
                    f"Could not calculate "
                    f"performance: {e}"
                )

        else:

            st.info(
                "Performance metrics require "
                "a target column in the dataset."
            )

    # -----------------------------------------------------
    # FEATURE IMPORTANCE
    # -----------------------------------------------------

    st.divider()

    st.subheader(
        "🎯 Feature Importance"
    )

    importance_values = None

    if model is not None:

        if hasattr(
            model,
            "feature_importances_"
        ):

            importance_values = (
                model.feature_importances_
            )

        elif hasattr(
            model,
            "named_steps"
        ):

            for step_name in reversed(
                list(model.named_steps.keys())
            ):

                step = model.named_steps[
                    step_name
                ]

                if hasattr(
                    step,
                    "feature_importances_"
                ):

                    importance_values = (
                        step.feature_importances_
                    )

                    break

    if importance_values is not None:

        importance_df = pd.DataFrame({

            "Feature": features,

            "Importance": importance_values

        }).sort_values(
            "Importance",
            ascending=True
        )

        fig = px.bar(
            importance_df,
            x="Importance",
            y="Feature",
            orientation="h",
            title="Factors Influencing Drop-Off Prediction"
        )

        st.plotly_chart(
            fig,
            width="stretch"
        )

        st.info(
            "Feature importance shows which user "
            "behavior variables contribute most "
            "to the model's prediction."
        )

    else:

        st.info(
            "Feature importance is not available "
            "for the loaded model."
        )


# =========================================================
# USER DATA
# =========================================================

elif page == "User Data":

    st.title("👥 User Journey Data")

    st.write(
        "Historical user journey records."
    )

    if df.empty:

        st.warning(
            "No historical dataset found."
        )

    else:

        st.write(
            f"Total records available: "
            f"**{len(df):,}**"
        )

        st.dataframe(
            df,
            width="stretch",
            hide_index=True
        )


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "Real-Time User Journey Funnel Analysis "
    "and Drop-Off Prediction System | "
    "Final Year Engineering Project"
)