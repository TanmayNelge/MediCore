# ml/predict_and_store.py
# Phase 16.1 — scores upcoming SCHEDULED appointments and MERGEs the
# results into ML_PREDICTION. Reuses the exact MERGE pattern already used
# for pharmacy stock upserts (Phase 5.2) — ML integration doesn't require
# any new database concepts beyond what's already in the schema/DML.
#
# The frontend's "AI/ML Insights" page (Phase 13.5 / 16.2) only ever runs
# a read-only SELECT against ML_PREDICTION — it never triggers training or
# writes from the frontend, keeping the ML write path offline/batch.

import pandas as pd
from train import prepare_features


def predict_and_store(conn, model, scaler, feature_cols, model_name, model_version):
    upcoming = pd.read_sql("""
        SELECT a.appointment_id, a.patient_id, a.doctor_id, a.appt_date, a.appt_time,
               a.appt_type, a.status,
               d.department_id,
               calculate_age(p.dob) AS patient_age,
               (SELECT COUNT(*) FROM appointment a2
                WHERE a2.patient_id = a.patient_id AND a2.appt_date < a.appt_date) AS prior_appt_count,
               (SELECT COUNT(*) FROM appointment a3
                WHERE a3.patient_id = a.patient_id AND a3.appt_date < a.appt_date
                  AND a3.status = 'NO_SHOW') AS prior_no_show_count,
               (a.appt_date - TRUNC(a.created_at)) AS lead_time_days
        FROM appointment a JOIN patient p ON p.patient_id=a.patient_id
        JOIN doctor d ON d.doctor_id=a.doctor_id
        WHERE a.status = 'SCHEDULED' AND a.appt_date >= TRUNC(SYSDATE)
    """, conn)

    # Normalize Oracle column names to lowercase
    upcoming.columns = [str(c).lower() for c in upcoming.columns]

    if upcoming.empty:
        print("  Notice: No upcoming SCHEDULED appointments found to predict (status='SCHEDULED' and appt_date >= SYSDATE).")
        return 0

    X_raw, _, _ = prepare_features(upcoming.assign(status='SCHEDULED'))  # label column unused here
    X = scaler.transform(X_raw[feature_cols])       # same transform as training
    probs = model.predict_proba(X)[:, 1]
    preds = ["NO_SHOW" if p >= 0.5 else "ATTENDED" for p in probs]

    cursor = conn.cursor()
    saved_count = 0
    for (_, row), pred, prob in zip(upcoming.iterrows(), preds, probs):
        prob_val = round(float(prob), 4)
        cursor.execute("""
            MERGE INTO ml_prediction mp
            USING (SELECT :appt_id AS appointment_id FROM dual) src
            ON (mp.appointment_id = src.appointment_id AND mp.model_name = :mname AND mp.model_version = :mver)
            WHEN MATCHED THEN
                UPDATE SET prediction = :pred, probability = :prob, prediction_date = SYSDATE
            WHEN NOT MATCHED THEN
                INSERT (patient_id, appointment_id, model_name, model_version, prediction, probability)
                VALUES (:pid, :appt_id, :mname, :mver, :pred, :prob)
        """, appt_id=int(row["appointment_id"]), pid=int(row["patient_id"]),
             mname=str(model_name), mver=str(model_version), pred=str(pred), prob=prob_val)
        saved_count += 1
    conn.commit()
    print(f"  Successfully scored and saved {saved_count} appointments into ML_PREDICTION.")
    return saved_count


# Frontend consumption (Phase 16.2) — read-only, run directly by the
# "AI/ML Insights" page, never by this script:
#
# SELECT p.first_name || ' ' || p.last_name AS patient, a.appt_date, a.appt_time,
#        mp.prediction, mp.probability
# FROM ml_prediction mp
# JOIN patient p ON p.patient_id = mp.patient_id
# JOIN appointment a ON a.appointment_id = mp.appointment_id
# WHERE a.appt_date >= TRUNC(SYSDATE)
# ORDER BY mp.probability DESC;
