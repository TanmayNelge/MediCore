# app/routers/reports.py

from fastapi import APIRouter, Depends
from app.db.session import get_readonly_connection
from app.db.helpers import rows_to_dicts

router = APIRouter()


@router.get("/reports/dashboard")
def dashboard_kpis(conn=Depends(get_readonly_connection)):
    """Powers the dashboard cards in one round trip (Phase 13.2)."""
    cursor = conn.cursor()
    sql = """SELECT
      (SELECT COUNT(*) FROM patient) AS total_patients,
      (SELECT COUNT(*) FROM appointment WHERE appt_date = TRUNC(SYSDATE)) AS todays_appointments,
      (SELECT COUNT(*) FROM service_queue WHERE status='WAITING' AND queue_date=TRUNC(SYSDATE)) AS current_queue,
      (SELECT COUNT(*) FROM room_bed WHERE status='AVAILABLE') AS available_beds,
      (SELECT COUNT(*) FROM lab_order WHERE status IN ('ORDERED','SAMPLE_COLLECTED')) AS pending_labs,
      (SELECT NVL(SUM(amount_paid),0) FROM payment WHERE paid_date=TRUNC(SYSDATE)) AS revenue_today
    FROM dual"""
    cursor.execute(sql)
    return {"sql_executed": sql, "results": rows_to_dicts(cursor, cursor.fetchall())}


@router.get("/reports/doctor-workload")
def doctor_workload(conn=Depends(get_readonly_connection)):
    """vw_doctor_workload (Phase 6.1.8)."""
    cursor = conn.cursor()
    sql = "SELECT * FROM vw_doctor_workload ORDER BY total_appointments DESC"
    cursor.execute(sql)
    return {"sql_executed": sql, "results": rows_to_dicts(cursor, cursor.fetchall())}


@router.get("/reports/admitted-patients")
def admitted_patients(conn=Depends(get_readonly_connection)):
    """vw_current_admitted_patients (Phase 6.1.5)."""
    cursor = conn.cursor()
    sql = "SELECT * FROM vw_current_admitted_patients ORDER BY admit_date"
    cursor.execute(sql)
    return {"sql_executed": sql, "results": rows_to_dicts(cursor, cursor.fetchall())}
