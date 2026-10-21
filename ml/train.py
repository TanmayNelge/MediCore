# ml/train.py
# Phase 15.4 (feature engineering) + 15.5 (training).
#
# Class imbalance note: with a ~12% no-show rate (see 04_sample_data.sql /
# 04b_bulk_data.sql), plain accuracy is misleading (predicting "always
# attends" scores ~88% accuracy while catching zero no-shows) — this is
# why evaluate.py leads with recall/F1/ROC-AUC, not accuracy.

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier


def prepare_features(df: pd.DataFrame):
    df = df.copy()
    # Normalize column names to lowercase
    df.columns = [str(c).lower() for c in df.columns]

    # Handle appointment weekday
    df["appt_weekday"] = pd.to_datetime(df["appt_date"], errors="coerce").dt.dayofweek.fillna(0).astype(int)

    # Safely convert numeric fields
    prior_appts = pd.to_numeric(df.get("prior_appt_count", 0), errors="coerce").fillna(0)
    prior_no_shows = pd.to_numeric(df.get("prior_no_show_count", 0), errors="coerce").fillna(0)
    df["prior_appt_count"] = prior_appts
    df["prior_no_show_count"] = prior_no_shows
    df["prior_no_show_rate"] = prior_no_shows / prior_appts.replace(0, 1)
    df["is_new_patient"] = (prior_appts == 0).astype(int)
    
    appt_types = df.get("appt_type", "").astype(str).str.upper()
    df["appt_type_new"] = (appt_types == "NEW").astype(int)

    df["patient_age"] = pd.to_numeric(df.get("patient_age", 30), errors="coerce").fillna(30).clip(lower=0)
    df["lead_time_days"] = pd.to_numeric(df.get("lead_time_days", 0), errors="coerce").fillna(0).clip(lower=0)
    df["department_id"] = pd.to_numeric(df.get("department_id", 1), errors="coerce").fillna(1).astype(int)

    if "status" in df.columns:
        df["label"] = (df["status"].astype(str).str.upper() == "NO_SHOW").astype(int)
    else:
        df["label"] = 0

    feature_cols = ["patient_age", "prior_appt_count", "prior_no_show_rate",
                     "is_new_patient", "appt_type_new", "appt_weekday",
                     "lead_time_days", "department_id"]
    X = df[feature_cols].fillna(0)
    y = df["label"]
    return X, y, feature_cols


def split_and_scale(X, y):
    has_both_classes = (y.nunique() > 1) and (y.value_counts().min() >= 2) and (len(y) >= 5)
    stratify = y if has_both_classes else None
    test_size = 0.2 if len(y) >= 10 else 0.25
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42, stratify=stratify
    )
    scaler = StandardScaler().fit(X_train)
    return scaler.transform(X_train), scaler.transform(X_test), y_train, y_test, scaler


def train_models(X_train, y_train):
    log_reg = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
    log_reg.fit(X_train, y_train)

    rf = RandomForestClassifier(n_estimators=200, max_depth=6, class_weight="balanced", random_state=42)
    rf.fit(X_train, y_train)

    return {"logistic_regression": log_reg, "random_forest": rf}


if __name__ == "__main__":
    import oracledb
    from extract import extract_training_data

    conn = oracledb.connect(user="hcms_admin", password="...", dsn="localhost/XEPDB1")
    df = extract_training_data(conn)
    X, y, feature_cols = prepare_features(df)
    X_train, X_test, y_train, y_test, scaler = split_and_scale(X, y)
    models = train_models(X_train, y_train)
    print("Trained:", list(models.keys()))
