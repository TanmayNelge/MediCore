# ml/run_pipeline.py
#
# FIX: extract.py, train.py, evaluate.py and predict_and_store.py each
# existed as clean, correct pieces, but nothing tied them together into a
# single runnable script, and no model was ever persisted to disk. As
# written, predict_and_store.predict_and_store() takes `model, scaler,
# feature_cols` as parameters that nothing supplied — you'd have had to
# re-run training in the same Python process just to score new
# appointments, every single time (Phase 16.1's "run this daily/on a
# schedule" intent was impossible). This script is the missing entry
# point: run it once to train + evaluate + persist, then again (with
# --predict-only) as a fast recurring job that just loads the saved
# model and scores upcoming appointments.
#
# Usage:
#   python run_pipeline.py                 # full retrain + evaluate + predict
#   python run_pipeline.py --predict-only   # skip training, reuse saved model
#
# Configure the connection via environment variables (matches the
# backend's own convention in app/db/pool.py):
#   ORACLE_DSN      e.g. "localhost/XEPDB1"   (default shown)
#   ADMIN1_PWD      password for hcms_admin   (ML reads/writes need admin_role)

import argparse
import os
import sys

import joblib
import oracledb

from extract import extract_training_data
from train import prepare_features, split_and_scale, train_models
from evaluate import select_best_model
from predict_and_store import predict_and_store

MODEL_PATH = os.path.join(os.path.dirname(__file__), "no_show_model.joblib")
MODEL_VERSION = "1.0"


def connect(dsn=None, user="admin1", pwd=None):
    dsn = dsn or os.environ.get("ORACLE_DSN", "localhost:1521/XEPDB1")
    pwd = pwd or os.environ.get("ADMIN1_PWD", "admin1")
    try:
        conn = oracledb.connect(user=user, password=pwd, dsn=dsn)
        conn.current_schema = "HCMS_ADMIN"
        return conn
    except oracledb.Error as e:
        print(f"\n[Error] Unable to connect to Oracle database at {dsn} as {user}: {e}")
        print("Tip: Check if Oracle service is running, or verify credentials in 2_start_backend.ps1.")
        print("Tip: You can also run with '--demo' to test training & evaluation on synthetic hospital data without live Oracle.\n")
        sys.exit(1)


def generate_synthetic_data(n=250):
    """Generates synthetic patient appointment data for offline demonstration or testing."""
    import numpy as np
    import pandas as pd
    np.random.seed(42)
    
    ages = np.random.randint(18, 85, size=n)
    dept_ids = np.random.randint(1, 9, size=n)
    prior_appts = np.random.poisson(lam=3, size=n)
    # Higher prior no-show count correlates with future no-show
    prior_no_shows = np.array([np.random.binomial(n=max(1, p), p=0.15) for p in prior_appts])
    lead_time = np.random.exponential(scale=10, size=n).astype(int)
    appt_types = np.random.choice(["NEW", "FOLLOW_UP"], size=n, p=[0.4, 0.6])
    
    # Calculate realistic no-show probability
    logits = -2.2 + 0.04 * (lead_time > 14) + 1.2 * (prior_no_shows > 0) + 0.3 * (appt_types == "NEW") - 0.01 * (ages > 50)
    probs = 1 / (1 + np.exp(-logits))
    statuses = ["NO_SHOW" if p > np.random.rand() else "COMPLETED" for p in probs]

    df = pd.DataFrame({
        "appointment_id": range(1001, 1001 + n),
        "patient_id": range(1, 1 + n),
        "doctor_id": np.random.randint(1, 16, size=n),
        "appt_date": pd.date_range(end=pd.Timestamp.now(), periods=n, freq="4h"),
        "appt_time": ["10:00"] * n,
        "appt_type": appt_types,
        "status": statuses,
        "department_id": dept_ids,
        "patient_age": ages,
        "prior_appt_count": prior_appts,
        "prior_no_show_count": prior_no_shows,
        "lead_time_days": lead_time,
    })
    return df


def train_and_persist(conn=None, df=None):
    if df is None:
        print("Extracting training data (resolved COMPLETED/NO_SHOW appointments)...")
        df = extract_training_data(conn)
        print(f"  {len(df)} labeled rows extracted from Oracle.")

    if len(df) < 5:
        sys.exit(f"Insufficient training data ({len(df)} rows). Please run 04_sample_data.sql and 04b_bulk_data.sql first.")

    X, y, feature_cols = prepare_features(df)
    X_train, X_test, y_train, y_test, scaler = split_and_scale(X, y)

    print(f"Training Logistic Regression and Random Forest on {len(X_train)} samples...")
    models = train_models(X_train, y_train)

    print("Evaluating models on held-out test set (selecting by recall, then F1)...")
    best_name, best_model, scored = select_best_model(models, X_test, y_test)
    for name, metrics in scored.items():
        marker = " <-- [BEST MODEL SELECTED]" if name == best_name else ""
        print(f"  {name:20s}: recall={metrics['recall']:.3f} | f1={metrics['f1']:.3f} | "
              f"roc_auc={metrics['roc_auc']:.3f} | accuracy={metrics['accuracy']:.3f}{marker}")

    joblib.dump(
        {"model": best_model, "scaler": scaler, "feature_cols": feature_cols,
         "model_name": best_name, "model_version": MODEL_VERSION, "metrics": scored[best_name]},
        MODEL_PATH,
    )
    print(f"\nSaved optimal model ({best_name}) to {MODEL_PATH}")
    return best_model, scaler, feature_cols, best_name


def load_persisted():
    if not os.path.exists(MODEL_PATH):
        sys.exit(f"No saved model found at {MODEL_PATH} -- run without --predict-only first.")
    bundle = joblib.load(MODEL_PATH)
    return bundle["model"], bundle["scaler"], bundle["feature_cols"], bundle["model_name"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MediCore HCMS no-show prediction pipeline")
    parser.add_argument("--predict-only", action="store_true",
                         help="Skip training; load the last saved model and just score upcoming appointments.")
    parser.add_argument("--demo", action="store_true",
                         help="Train and evaluate on synthetic clinic data without requiring live Oracle DB.")
    parser.add_argument("--dsn", default=None, help="Oracle DSN (e.g. localhost/XEPDB1)")
    parser.add_argument("--user", default="admin1", help="Oracle user (default: admin1)")
    parser.add_argument("--password", default=None, help="Oracle password (default: Str0ng_Pwd!28)")
    args = parser.parse_args()

    if args.demo:
        print("\n--- Running in DEMO mode with synthetic patient appointments ---")
        demo_df = generate_synthetic_data(n=300)
        model, scaler, feature_cols, model_name = train_and_persist(df=demo_df)
        print("Demo completed successfully. Model is trained and verified.")
        sys.exit(0)

    conn = connect(dsn=args.dsn, user=args.user, pwd=args.password)
    try:
        if args.predict_only:
            model, scaler, feature_cols, model_name = load_persisted()
        else:
            model, scaler, feature_cols, model_name = train_and_persist(conn=conn)

        print("Scoring upcoming SCHEDULED appointments and MERGEing into ML_PREDICTION...")
        scored = predict_and_store(conn, model, scaler, feature_cols, model_name, MODEL_VERSION)
        print("ML Pipeline run finished successfully.")
    finally:
        conn.close()

