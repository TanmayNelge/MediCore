# app/routers/patients.py
# Demonstrates the parameterized-query pattern used across every endpoint
# (Phase 12.2): bind variables only, never f-string/concatenate user
# input into SQL. The already-bound, injection-safe SQL text is echoed
# back for the frontend's "SQL Executed" transparency panel.
#
# FIX: this file previously had no way to create a new patient at all --
# only /patients/search existed. That breaks the Phase 17.1 functional
# test ("Submit valid patient form -> New row in PATIENT") and the
# Patient Management module generally. POST /patients below fills that
# gap using the same RETURNING-INTO bind-variable pattern already used
# by book_appointment_endpoint.
#
# FIX: book_appointment_endpoint was missing conn.commit() — the procedure
# writes to both appointment and service_queue but neither was ever
# committed, so the rows would vanish on connection close.

from typing import Optional

from fastapi import APIRouter, Depends
from app.db.session import get_connection

router = APIRouter()


@router.get("/patients/search")
def search_patients(last_name: str, conn=Depends(get_connection)):
    cursor = conn.cursor()
    # Bind variable ":ln" — never f-string/concatenate user input into SQL
    sql = "SELECT patient_id, first_name, last_name, phone FROM patient WHERE last_name LIKE :ln"
    cursor.execute(sql, ln=f"{last_name}%")
    rows = cursor.fetchall()
    return {
        "sql_executed": sql.replace(":ln", f"'{last_name}%'"),  # shown to frontend for transparency
        "results": [dict(zip([c[0].lower() for c in cursor.description], r)) for r in rows],
    }


@router.get("/patients")
def list_patients(limit: int = 50, conn=Depends(get_connection)):
    """List recent patients (supports GET /patients)."""
    cursor = conn.cursor()
    sql = "SELECT patient_id, first_name, last_name, TO_CHAR(dob, 'YYYY-MM-DD') AS dob, gender, phone, email FROM patient ORDER BY patient_id DESC FETCH FIRST :lim ROWS ONLY"
    cursor.execute(sql, lim=limit)
    rows = cursor.fetchall()
    return {
        "sql_executed": sql.replace(":lim", str(limit)),
        "results": [dict(zip([c[0].lower() for c in cursor.description], r)) for r in rows],
    }


@router.post("/patients")
def register_patient(
    first_name: str,
    last_name: str,
    dob: str,              # ISO 'YYYY-MM-DD'; oracledb binds this to DATE via TO_DATE below
    gender: str,            # 'M' | 'F' | 'O' — matches the CHECK constraint on patient.gender
    phone: str,
    blood_group: Optional[str] = None,
    email: Optional[str] = None,
    address: Optional[str] = None,
    emergency_contact_name: Optional[str] = None,
    emergency_contact_phone: Optional[str] = None,
    conn=Depends(get_connection),
):
    """Registers a new patient (Phase 3/17.1). CHECK constraints on
    gender/blood_group and the UNIQUE constraint on email are the last
    line of defense if a caller bypasses the frontend's own validation."""
    cursor = conn.cursor()
    sql = """
        INSERT INTO patient (
            first_name, last_name, dob, gender, blood_group, phone, email,
            address, emergency_contact_name, emergency_contact_phone
        ) VALUES (
            :first_name, :last_name, TO_DATE(:dob, 'YYYY-MM-DD'), :gender, :blood_group, :phone, :email,
            :address, :ec_name, :ec_phone
        )
        RETURNING patient_id INTO :out_id
    """
    out_id = cursor.var(int)
    cursor.execute(
        sql,
        first_name=first_name, last_name=last_name, dob=dob, gender=gender,
        blood_group=blood_group, phone=phone, email=email, address=address,
        ec_name=emergency_contact_name, ec_phone=emergency_contact_phone,
        out_id=out_id,
    )
    conn.commit()
    raw = out_id.getvalue()
    new_id = raw[0] if isinstance(raw, list) else raw
    return {
        "patient_id": new_id,
        "sql_executed": sql,
    }


@router.post("/appointments/book")
def book_appointment_endpoint(
    patient_id: int, doctor_id: int, appt_date: str, appt_time: str, reason: str,
    conn=Depends(get_connection),
):
    """Executes the book_appointment PL/SQL procedure from Python (Phase 12.4).
    FIX: added conn.commit() — without it the INSERT into appointment and
    service_queue done inside the procedure are never persisted."""
    import datetime
    cursor = conn.cursor()
    out_id = cursor.var(int)
    try:
        d_val = datetime.date.fromisoformat(str(appt_date)[:10])
    except Exception:
        d_val = appt_date
    cursor.callproc("book_appointment", [patient_id, doctor_id, d_val, appt_time, reason, out_id])
    conn.commit()
    raw = out_id.getvalue()
    new_id = raw[0] if isinstance(raw, list) else raw
    return {"appointment_id": new_id}

