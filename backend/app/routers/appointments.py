# app/routers/appointments.py
# Appointment SELECT / UPDATE / DELETE (+ booking lives in patients.py).
#   * status update  -> plain UPDATE, allowed by the COLUMN-LEVEL grant
#                       GRANT UPDATE (status) ON appointment TO ..._role
#   * cancel         -> cancel_appointment()      (also cancels the queue token)
#   * reschedule     -> reschedule_appointment()  (SAVEPOINT demo)
#   * delete         -> DELETE, ADMIN only; Oracle refuses with ORA-02292 if
#                       a diagnosis / bill / prescription references the visit

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.auth.jwt import AppUser, require_roles
from app.db.helpers import call_proc, execute, query
from app.db.session import get_connection

router = APIRouter()

VALID_STATUS = {"SCHEDULED", "COMPLETED", "CANCELLED", "NO_SHOW"}


@router.get("/doctors")
def list_doctors(conn=Depends(get_connection)):
    sql = """SELECT d.doctor_id, d.first_name, d.last_name, d.specialization, d.department_id,
                    dep.department_name, d.consultation_fee
               FROM doctor d JOIN department dep ON dep.department_id = d.department_id
              ORDER BY dep.department_name, d.last_name"""
    return query(conn, sql)


@router.get("/appointments/schedule")
def doctor_schedule(doctor_id: Optional[int] = None, date_from: Optional[str] = None, date_to: Optional[str] = None,
                    status: Optional[str] = None, patient_id: Optional[int] = None, limit: int = 300,
                    conn=Depends(get_connection)):
    """vw_doctor_appointment_schedule with optional filters. Default window:
    today .. +14 days."""
    where, binds = [], {}
    df = date_from or datetime.date.today().isoformat()
    dt_ = date_to or (datetime.date.today() + datetime.timedelta(days=14)).isoformat()
    where.append("appt_date BETWEEN TO_DATE(:dfrom, 'YYYY-MM-DD') AND TO_DATE(:dto, 'YYYY-MM-DD')")
    binds.update(dfrom=df, dto=dt_)
    if doctor_id:
        where.append("doctor_id = :did")
        binds["did"] = doctor_id
    if patient_id:
        where.append("patient_id = :pid")
        binds["pid"] = patient_id
    if status and status.upper() in VALID_STATUS:
        where.append("status = :st")
        binds["st"] = status.upper()
    binds["lim"] = max(1, min(limit, 1000))
    sql = ("SELECT appointment_id, TO_CHAR(appt_date, 'YYYY-MM-DD') AS appt_date, appt_time, doctor_name, "
           "patient_id, patient_name, appt_type, status, reason FROM vw_doctor_appointment_schedule WHERE "
           + " AND ".join(where) + " ORDER BY appt_date, appt_time FETCH FIRST :lim ROWS ONLY")
    return query(conn, sql, binds)


@router.put("/appointments/{appointment_id}/status")
def update_appointment_status(appointment_id: int, status: str, conn=Depends(get_connection),
                              user: AppUser = Depends(require_roles("ADMIN", "DOCTOR", "NURSE", "RECEPTIONIST"))):
    st = status.upper()
    if st not in VALID_STATUS:
        raise HTTPException(422, f"status must be one of {sorted(VALID_STATUS)}")
    res = execute(conn, "UPDATE appointment SET status = :st WHERE appointment_id = :aid",
                  {"st": st, "aid": appointment_id})
    if res["rows_affected"] == 0:
        raise HTTPException(404, f"Appointment {appointment_id} not found")
    return res


@router.post("/appointments/{appointment_id}/cancel")
def cancel(appointment_id: int, conn=Depends(get_connection),
           user: AppUser = Depends(require_roles("ADMIN", "DOCTOR", "RECEPTIONIST"))):
    _, meta = call_proc(conn, "cancel_appointment", [appointment_id])
    return {"status": "cancelled", **meta}


@router.post("/appointments/{appointment_id}/reschedule")
def reschedule(appointment_id: int, new_date: str, new_time: str, conn=Depends(get_connection),
               user: AppUser = Depends(require_roles("ADMIN", "RECEPTIONIST"))):
    try:
        d_val = datetime.date.fromisoformat(new_date[:10])
    except ValueError:
        raise HTTPException(422, "new_date must be YYYY-MM-DD")
    _, meta = call_proc(conn, "reschedule_appointment", [appointment_id, d_val, new_time[:5]],
                        shown_args=[str(appointment_id), f"DATE '{d_val}'", f"'{new_time[:5]}'"])
    return {"status": "rescheduled", **meta}


@router.delete("/appointments/{appointment_id}")
def delete_appointment(appointment_id: int, conn=Depends(get_connection),
                       user: AppUser = Depends(require_roles("ADMIN"))):
    """Physical DELETE. Works for a mistaken booking; for a visit that already
    has a diagnosis / bill Oracle raises ORA-02292 (child record found) -
    the error handler shows that message in the UI. The OPD queue token of
    the same day is removed in the same transaction."""
    cur = conn.cursor()
    cur.execute("""DELETE FROM service_queue q
                    WHERE q.queue_type = 'OPD' AND q.status IN ('WAITING','CANCELLED')
                      AND (q.patient_id, q.doctor_id, q.queue_date) IN
                          (SELECT patient_id, doctor_id, appt_date FROM appointment WHERE appointment_id = :aid)""",
                aid=appointment_id)
    res = execute(conn, "DELETE FROM appointment WHERE appointment_id = :aid", {"aid": appointment_id}, commit=False)
    if res["rows_affected"] == 0:
        conn.rollback()
        raise HTTPException(404, f"Appointment {appointment_id} not found")
    conn.commit()
    return res
