# ml/extract.py
# Phase 15.3 — pulls training data straight from Oracle. Reuses the
# database's own calculate_age() function (Phase 7) inside the SQL so the
# app and the ML pipeline share one canonical age calculation.

import oracledb
import pandas as pd


def extract_training_data(conn):
    query = """
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
        FROM appointment a
        JOIN patient p ON p.patient_id = a.patient_id
        JOIN doctor d ON d.doctor_id = a.doctor_id
        WHERE a.status IN ('COMPLETED','NO_SHOW')    -- only resolved appointments have a ground-truth label
    """
    df = pd.read_sql(query, conn)
    # FIX: Oracle returns column names in UPPERCASE in cursor description.
    # Convert to lowercase to match prepare_features expectations.
    df.columns = [c.lower() for c in df.columns]
    return df
