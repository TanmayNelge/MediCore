# app/routers/appointments.py
# Follows the pattern from patients.py (Phase 12.2): bind variables only,
# the executed SQL is echoed back for the frontend's "SQL Executed" panel.
#
# FIX: added GET /doctors endpoint — the frontend's LookupSelect components
# in AppointmentsPage, ClinicalPage, PharmacyPage, LabPage, and AdmissionsPage
# all call /api/doctors to populate the doctor dropdown. Without this endpoint
# every doctor lookup silently fell back to the free-text ID input.

from typing import Optional
from fastapi import APIRouter, Depends
from app.db.session import get_connection
from app.db.helpers import rows_to_dicts

router = APIRouter()


@router.get("/doctors")
def list_doctors(conn=Depends(get_connection)):
    """Return all doctors for use in LookupSelect dropdowns across the frontend."""
    cursor = conn.cursor()
    sql = "SELECT doctor_id, first_name, last_name, specialization, department_id FROM doctor ORDER BY last_name, first_name"
    cursor.execute(sql)
    return {"sql_executed": sql, "results": rows_to_dicts(cursor, cursor.fetchall())}


@router.get("/appointments/schedule")
def doctor_schedule(doctor_id: Optional[int] = None, conn=Depends(get_connection)):
    """vw_doctor_appointment_schedule (Phase 6.1.2), optionally filtered to one doctor."""
    cursor = conn.cursor()
    if doctor_id is not None:
        sql = "SELECT * FROM vw_doctor_appointment_schedule WHERE doctor_id = :did ORDER BY appt_date, appt_time"
        cursor.execute(sql, did=doctor_id)
        shown_sql = sql.replace(":did", str(doctor_id))
    else:
        sql = "SELECT * FROM vw_doctor_appointment_schedule ORDER BY appt_date, appt_time"
        cursor.execute(sql)
        shown_sql = sql
    return {"sql_executed": shown_sql, "results": rows_to_dicts(cursor, cursor.fetchall())}


@router.put("/appointments/{appointment_id}/status")
def update_appointment_status(appointment_id: int, status: str, conn=Depends(get_connection)):
    """Direct status update (e.g. mark COMPLETED / NO_SHOW). Booking itself
    goes through the book_appointment procedure in routers/patients.py so
    the queue-insert side effect stays atomic with it (Phase 10)."""
    cursor = conn.cursor()
    sql = "UPDATE appointment SET status = :st WHERE appointment_id = :aid"
    cursor.execute(sql, st=status, aid=appointment_id)
    conn.commit()
    return {
        "sql_executed": sql.replace(":st", f"'{status}'").replace(":aid", str(appointment_id)),
        "rows_updated": cursor.rowcount,
    }
