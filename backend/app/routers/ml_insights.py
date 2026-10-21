# app/routers/ml_insights.py
# Phase 13.5 / 16.2 -- read-only, reads only from ML_PREDICTION. Never
# triggers training or writes anything -- that's the offline/batch scripts
# in ml/ (extract.py, train.py, evaluate.py, predict_and_store.py).

import os
import joblib
from fastapi import APIRouter, Depends
from app.db.session import get_readonly_connection
from app.db.helpers import rows_to_dicts

router = APIRouter()


@router.get("/ml-insights/predictions")
def upcoming_predictions(conn=Depends(get_readonly_connection)):
    cursor = conn.cursor()
    sql = """SELECT p.first_name || ' ' || p.last_name AS patient,
                    TO_CHAR(a.appt_date, 'YYYY-MM-DD') AS appt_date,
                    a.appt_time,
                    d.first_name || ' ' || d.last_name AS doctor_name,
                    dep.department_name,
                    mp.prediction,
                    ROUND(mp.probability, 4) AS probability,
                    mp.model_name,
                    mp.model_version
             FROM ml_prediction mp
             JOIN patient p ON p.patient_id = mp.patient_id
             JOIN appointment a ON a.appointment_id = mp.appointment_id
             LEFT JOIN doctor d ON d.doctor_id = a.doctor_id
             LEFT JOIN department dep ON dep.department_id = d.department_id
             WHERE a.appt_date >= TRUNC(SYSDATE) OR a.status = 'SCHEDULED'
             ORDER BY mp.probability DESC"""
    cursor.execute(sql)
    return {
        "sql_executed": sql,
        "results": rows_to_dicts(cursor, cursor.fetchall()),
        "disclaimer": "Decision-support estimate only — not a medical diagnosis.",
    }


@router.get("/ml-insights/model-summary")
def model_summary():
    """Returns evaluation metrics and feature importance of the active persisted model."""
    candidate_paths = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "ml", "no_show_model.joblib")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ml", "no_show_model.joblib")),
        os.path.abspath(os.path.join(os.getcwd(), "ml", "no_show_model.joblib")),
        os.path.abspath(os.path.join(os.getcwd(), "..", "ml", "no_show_model.joblib")),
    ]
    model_path = next((p for p in candidate_paths if os.path.exists(p)), None)
    if model_path:
        try:
            bundle = joblib.load(model_path)
            return {
                "available": True,
                "model_name": bundle.get("model_name", "Classification Model"),
                "model_version": bundle.get("model_version", "1.0"),
                "metrics": bundle.get("metrics", {}),
                "features": bundle.get("feature_cols", []),
            }
        except Exception as e:
            return {"available": False, "message": str(e)}
    return {
        "available": False,
        "message": "No trained model found on disk. Run ml/run_pipeline.py to train and evaluate.",
    }

