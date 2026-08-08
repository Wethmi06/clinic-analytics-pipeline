"""
train_noshowmodel.py

Day 9 of the clinic analytics pipeline project.

Trains a Random Forest classifier to predict no-show risk for upcoming
clinic appointments, using features derived from the fact_appointments
mart table built by dbt.

What this script does:
  1. Pulls historical appointments (attended/no_show) from Postgres
  2. Engineers features: lead time, day of week, age, department,
     past no-show count per patient
  3. Trains a Random Forest classifier and evaluates it on a test split
  4. Scores upcoming (scheduled) appointments with a risk probability
  5. Saves predictions to data/predictions/no_show_predictions.csv
     AND writes them back to Postgres as a mart_no_show_predictions table

Run from your project root:
  python scripts/train_noshow_model.py

Dependencies (already installed):
  pip install scikit-learn pandas sqlalchemy psycopg2-binary
"""

import os
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report,
    roc_auc_score,
    confusion_matrix,
)
from sklearn.preprocessing import LabelEncoder

OUTPUT_DIR = "data/predictions"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Database connection ─────────────────────────────────────────────────────
DB_HOST = os.environ.get("CLINIC_DB_HOST", "localhost")
DB_PORT = os.environ.get("CLINIC_DB_PORT", "5432")
DB_NAME = os.environ.get("CLINIC_DB_NAME", "clinic_db")
DB_USER = os.environ.get("CLINIC_DB_USER", "clinic_user")
DB_PASS = os.environ.get("CLINIC_DB_PASS", "clinic_pass")

ENGINE = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# ── Feature engineering ─────────────────────────────────────────────────────
def load_appointments():
    """Pull all resolved appointments (attended + no_show) and upcoming
    (scheduled) appointments from the fact/dim tables in dbt_dev schema."""

    query = """
        select
            a.appointment_id,
            a.patient_id,
            a.doctor_id,
            a.department_id,
            d.department_name,
            a.scheduled_date,
            a.lead_time_days,
            a.status,
            a.is_no_show,
            p.age,
            p.gender,
            p.district
        from dbt_dev.fact_appointments a
        left join dbt_dev.dim_patients p
            on a.patient_id = p.patient_id
        left join dbt_dev.dim_departments d
            on a.department_id = d.department_id
        order by a.scheduled_date
    """
    with ENGINE.connect() as conn:
        df = pd.read_sql(text(query), conn)
    return df


def engineer_features(df):
    """Build ML features from the raw appointment + patient columns.

    All features use only information available BEFORE the appointment
    happens -- no future leakage. past_no_show_count is the only one
    that needs careful handling: we compute it as a running count up to
    (but not including) the current appointment, using the sort order
    of scheduled_date.
    """
    df = df.copy()
    df["scheduled_date"] = pd.to_datetime(df["scheduled_date"])

    # Date-derived features
    df["day_of_week"] = df["scheduled_date"].dt.dayofweek   # 0=Mon, 6=Sun
    df["month"] = df["scheduled_date"].dt.month
    df["is_monday"] = (df["day_of_week"] == 0).astype(int)

    # Past no-show count per patient (rolling, excludes current row)
    # Sort by date first so the cumsum correctly captures history
    df = df.sort_values(["patient_id", "scheduled_date"]).reset_index(drop=True)
    df["is_no_show_int"] = df["is_no_show"].fillna(False).astype(int)
    df["past_no_show_count"] = (
        df.groupby("patient_id")["is_no_show_int"]
        .cumsum()
        .shift(1)
        .fillna(0)
        .astype(int)
    )

    # Encode categorical features
    le_dept = LabelEncoder()
    df["department_encoded"] = le_dept.fit_transform(
        df["department_name"].fillna("Unknown")
    )

    le_gender = LabelEncoder()
    df["gender_encoded"] = le_gender.fit_transform(
        df["gender"].fillna("Unknown")
    )

    return df, le_dept, le_gender


FEATURE_COLS = [
    "lead_time_days",
    "day_of_week",
    "month",
    "is_monday",
    "age",
    "past_no_show_count",
    "department_encoded",
    "gender_encoded",
]


# ── Training ────────────────────────────────────────────────────────────────
def train_model(df):
    """Train a Random Forest on historical (resolved) appointments."""

    # Only use resolved appointments for training
    resolved = df[df["status"].isin(["attended", "no_show"])].copy()
    resolved = resolved.dropna(subset=FEATURE_COLS + ["is_no_show"])

    X = resolved[FEATURE_COLS]
    y = resolved["is_no_show"].astype(int)

    print(f"\nTraining on {len(resolved)} resolved appointments")
    print(f"No-show rate in training data: {y.mean():.1%}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=8,
        min_samples_leaf=10,
        random_state=42,
        class_weight="balanced",  # handles the class imbalance (more attended than no_show)
    )
    model.fit(X_train, y_train)

    # ── Evaluation ──────────────────────────────────────────────────────────
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_prob)

    print(f"\n── Model Evaluation (test set: {len(X_test)} appointments) ──")
    print(f"AUC Score:  {auc:.3f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["Attended", "No-Show"]))
    print("Confusion Matrix (rows=actual, cols=predicted):")
    print(confusion_matrix(y_test, y_pred))

    # ── Feature importances ─────────────────────────────────────────────────
    print("\n── Feature Importances ──")
    importances = pd.Series(model.feature_importances_, index=FEATURE_COLS)
    for feat, imp in importances.sort_values(ascending=False).items():
        bar = "█" * int(imp * 40)
        print(f"  {feat:<25} {imp:.3f}  {bar}")

    return model, auc


# ── Scoring upcoming appointments ───────────────────────────────────────────
def score_upcoming(df, model):
    """Apply the trained model to appointments not yet happened."""
    upcoming = df[df["status"] == "scheduled"].copy()
    upcoming = upcoming.dropna(subset=["age", "lead_time_days"])

    if upcoming.empty:
        print("\nNo upcoming appointments to score.")
        return pd.DataFrame()

    X_upcoming = upcoming[FEATURE_COLS]
    upcoming["no_show_probability"] = model.predict_proba(X_upcoming)[:, 1]
    upcoming["risk_label"] = pd.cut(
        upcoming["no_show_probability"],
        bins=[0, 0.3, 0.6, 1.0],
        labels=["Low", "Medium", "High"],
    )

    print(f"\n── Upcoming Appointment Risk Summary ({len(upcoming)} appointments) ──")
    print(upcoming["risk_label"].value_counts().to_string())

    return upcoming[[
        "appointment_id",
        "patient_id",
        "doctor_id",
        "department_name",
        "scheduled_date",
        "lead_time_days",
        "age",
        "past_no_show_count",
        "no_show_probability",
        "risk_label",
    ]]


# ── Save predictions ────────────────────────────────────────────────────────
def save_predictions(predictions_df):
    """Save scored upcoming appointments to CSV and Postgres."""
    csv_path = os.path.join(OUTPUT_DIR, "no_show_predictions.csv")
    predictions_df.to_csv(csv_path, index=False)
    print(f"\nSaved predictions CSV -> {csv_path}")

    # Write to Postgres so the Streamlit dashboard can query it directly
    predictions_df["no_show_probability"] = predictions_df[
        "no_show_probability"
    ].round(4)
    predictions_df["risk_label"] = predictions_df["risk_label"].astype(str)
    predictions_df["scheduled_date"] = predictions_df["scheduled_date"].astype(str)

    with ENGINE.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS dbt_dev.mart_no_show_predictions"))
        predictions_df.to_sql(
            "mart_no_show_predictions",
            conn,
            schema="dbt_dev",
            if_exists="replace",
            index=False,
        )
    print("Saved predictions table -> dbt_dev.mart_no_show_predictions")


# ── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Loading appointments from Postgres...")
    df_raw = load_appointments()
    print(f"Loaded {len(df_raw)} total appointments")

    print("\nEngineering features...")
    df, le_dept, le_gender = engineer_features(df_raw)

    print("\nTraining model...")
    model, auc = train_model(df)

    print("\nScoring upcoming appointments...")
    predictions = score_upcoming(df, model)

    if not predictions.empty:
        save_predictions(predictions)

    print("\nDay 9 complete.")