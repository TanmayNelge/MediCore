# app/routers/patients.py
# Patient CRUD - INSERT / SELECT (search) / UPDATE / DELETE.
# Bind variables only, never string-concatenated user input; the bound SQL
# is echoed back (display only) for the front end's "SQL executed" panel.
#
# Roles without direct access to PATIENT (LAB, PHARMACY, BILLING) search
# through vw_patient_directory - same endpoint, different object, and the
# database enforces it (column-level security through a view).

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.auth.jwt import AppUser, get_current_app_user, require_roles
from app.db.helpers import call_proc, query, show_sql
from app.db.session import get_connection

router = APIRouter()

_DIRECTORY_ROLES = {"LAB", "PHARMACY", "BILLING", "READONLY"}


def _source(user: AppUser):
    return "vw_patient_directory" if user.role in _DIRECTORY_ROLES else "patient"


@router.get("/patients")
def list_patients(q: Optional[str] = None, limit: int = 50, offset: int = 0,
                  user: AppUser = Depends(get_current_app_user), conn=Depends(get_connection)):
    """Search by name, phone or patient id (case-insensitive; uses the
    function-based index idx_patient_upper_lname for last-name prefixes)."""
    limit = max(1, min(limit, 500))
    src = _source(user)
    extra = "" if src != "patient" else ", TO_CHAR(dob, 'YYYY-MM-DD') AS dob, blood_group, city, email"
    base = f"SELECT patient_id, first_name, last_name, gender, phone{extra} FROM {src}"
    if q and q.strip():
        qs = q.strip()
        sql = (base + " WHERE UPPER(last_name) LIKE UPPER(:q) || '%' OR UPPER(first_name) LIKE UPPER(:q) || '%'"
                      " OR phone LIKE :q || '%' OR TO_CHAR(patient_id) = :q"
                      " ORDER BY last_name, first_name OFFSET :off ROWS FETCH NEXT :lim ROWS ONLY")
        return query(conn, sql, {"q": qs, "off": offset, "lim": limit})
    sql = base + " ORDER BY patient_id DESC OFFSET :off ROWS FETCH NEXT :lim ROWS ONLY"
    return query(conn, sql, {"off": offset, "lim": limit})


@router.get("/patients/search")
def search_patients(last_name: str = "", user: AppUser = Depends(get_current_app_user), conn=Depends(get_connection)):
    """Back-compatible lookup used by the LookupSelect drop-downs."""
    sql = (f"SELECT patient_id, first_name, last_name, phone FROM {_source(user)} "
           "WHERE UPPER(last_name) LIKE UPPER(:ln) || '%' ORDER BY last_name, first_name FETCH FIRST 500 ROWS ONLY")
    return query(conn, sql, {"ln": last_name})


@router.get("/patients/{patient_id}")
def patient_detail(patient_id: int, conn=Depends(get_connection),
                   user: AppUser = Depends(require_roles("ADMIN", "DOCTOR", "NURSE", "RECEPTIONIST"))):
    """One patient + insurance (LEFT JOIN) + visit counters (scalar sub-queries)."""
    sql = """SELECT p.patient_id, p.first_name, p.last_name, TO_CHAR(p.dob, 'YYYY-MM-DD') AS dob,
                    TRUNC(MONTHS_BETWEEN(SYSDATE, p.dob) / 12) AS age, p.gender, p.blood_group, p.phone, p.email,
                    p.address, p.city, p.emergency_contact_name, p.emergency_contact_phone,
                    TO_CHAR(p.registered_date, 'YYYY-MM-DD') AS registered_date,
                    ip.provider_name AS insurer, ip.policy_no, TO_CHAR(ip.valid_until, 'YYYY-MM-DD') AS policy_valid_until,
                    (SELECT COUNT(*) FROM appointment a WHERE a.patient_id = p.patient_id) AS appointments,
                    (SELECT COUNT(*) FROM appointment a WHERE a.patient_id = p.patient_id AND a.status = 'NO_SHOW') AS no_shows,
                    (SELECT COUNT(*) FROM admission ad WHERE ad.patient_id = p.patient_id) AS admissions
               FROM patient p LEFT JOIN insurance_policy ip ON ip.patient_id = p.patient_id
              WHERE p.patient_id = :pid"""
    res = query(conn, sql, {"pid": patient_id})
    if not res["results"]:
        raise HTTPException(404, f"Patient {patient_id} not found")
    return res


@router.post("/patients")
def register_patient(
    first_name: str, last_name: str, dob: str, gender: str, phone: str,
    blood_group: Optional[str] = None, email: Optional[str] = None, address: Optional[str] = None,
    city: Optional[str] = None,
    emergency_contact_name: Optional[str] = None, emergency_contact_phone: Optional[str] = None,
    conn=Depends(get_connection), user: AppUser = Depends(require_roles("ADMIN", "RECEPTIONIST")),
):
    """INSERT ... RETURNING. CHECK constraints (gender, blood group) and the
    UNIQUE constraint on email are the last line of defence."""
    try:
        datetime.date.fromisoformat(dob)
    except ValueError:
        raise HTTPException(422, "dob must be YYYY-MM-DD")
    cursor = conn.cursor()
    sql = """INSERT INTO patient (first_name, last_name, dob, gender, blood_group, phone, email,
                                  address, city, emergency_contact_name, emergency_contact_phone)
             VALUES (:first_name, :last_name, TO_DATE(:dob, 'YYYY-MM-DD'), :gender, :blood_group, :phone, :email,
                     :address, :city, :ec_name, :ec_phone)
             RETURNING patient_id INTO :out_id"""
    out_id = cursor.var(int)
    binds = dict(first_name=first_name.strip(), last_name=last_name.strip(), dob=dob, gender=gender,
                 blood_group=blood_group or None, phone=phone.strip(), email=email or None, address=address or None,
                 city=(city or "").strip() or None, ec_name=emergency_contact_name or None, ec_phone=emergency_contact_phone or None)
    cursor.execute(sql, **binds, out_id=out_id)
    conn.commit()
    raw = out_id.getvalue()
    return {"patient_id": raw[0] if isinstance(raw, list) else raw,
            "sql_executed": show_sql(sql.replace("RETURNING patient_id INTO :out_id", "RETURNING patient_id INTO :new_id"), binds),
            "db_user": conn.username}


@router.put("/patients/{patient_id}")
def update_patient(
    patient_id: int, first_name: Optional[str] = None, last_name: Optional[str] = None,
    phone: Optional[str] = None, email: Optional[str] = None, address: Optional[str] = None,
    city: Optional[str] = None, blood_group: Optional[str] = None, emergency_contact_name: Optional[str] = None,
    emergency_contact_phone: Optional[str] = None,
    conn=Depends(get_connection), user: AppUser = Depends(require_roles("ADMIN", "RECEPTIONIST")),
):
    """Calls update_patient (NVL semantics: only supplied fields change).
    trg_patient_audit writes the before/after values to AUDIT_LOG."""
    args = [patient_id, first_name or None, last_name or None, phone or None, email or None, address or None,
            city or None, blood_group or None, emergency_contact_name or None, emergency_contact_phone or None]
    _, meta = call_proc(conn, "update_patient", args)
    return {"status": "updated", "patient_id": patient_id, **meta}


@router.delete("/patients/{patient_id}")
def delete_patient(patient_id: int, conn=Depends(get_connection), user: AppUser = Depends(require_roles("ADMIN"))):
    """Calls delete_patient: refuses (ORA-20031) when the patient has any
    appointments / bills / admissions - referential integrity + medical
    record retention. Try it on a freshly registered patient."""
    _, meta = call_proc(conn, "delete_patient", [patient_id])
    return {"status": "deleted", "patient_id": patient_id, **meta}


@router.post("/appointments/book")
def book_appointment_endpoint(
    patient_id: int, doctor_id: int, appt_date: str, appt_time: str, reason: str = "",
    conn=Depends(get_connection), user: AppUser = Depends(require_roles("ADMIN", "DOCTOR", "RECEPTIONIST")),
):
    """book_appointment inserts APPOINTMENT + SERVICE_QUEUE atomically."""
    try:
        d_val = datetime.date.fromisoformat(str(appt_date)[:10])
    except ValueError:
        raise HTTPException(422, "appt_date must be YYYY-MM-DD")
    (new_id,), meta = call_proc(conn, "book_appointment",
                                [patient_id, doctor_id, d_val, appt_time[:5], reason or None], (int,),
                                shown_args=[str(patient_id), str(doctor_id), f"DATE '{d_val}'", f"'{appt_time[:5]}'",
                                            f"'{reason}'", ":new_appointment_id"])
    return {"appointment_id": new_id, **meta}
