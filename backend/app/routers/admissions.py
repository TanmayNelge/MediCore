# app/routers/admissions.py
#
# FIX: 08_procedures.sql defines admit_patient(p_patient_id, p_room_bed_id,
# p_doctor_id, p_reason, p_admission_id OUT) and the schema/trigger layer
# fully supports admitting a patient (trg_bed_status_update flips the bed
# to OCCUPIED automatically). But no router anywhere called it, and the
# frontend's AdmissionsPage could only list current admissions and
# discharge -- there was no way to admit a new patient through the app at
# all. This router closes that gap; app/main.py registers it and
# AdmissionsPage.jsx now has an "Admit patient" form that calls it.
#
# FIX: out_id.getvalue() normalised via _scalar() to handle both list and
# scalar return from the oracledb OUT variable depending on driver version.

from fastapi import APIRouter, Depends
from app.db.session import get_connection
from app.db.helpers import rows_to_dicts

router = APIRouter()


def _scalar(var):
    """Return the scalar value from an oracledb OUT variable regardless of
    whether the driver wrapped it in a list or not."""
    v = var.getvalue()
    return v[0] if isinstance(v, list) else v


@router.get("/admissions/available-beds")
def available_beds(conn=Depends(get_connection)):
    """Beds a receptionist/admin can pick from when admitting a patient."""
    cursor = conn.cursor()
    sql = """SELECT room_bed_id, room_no, bed_no, department_id, room_type, daily_rate
             FROM room_bed WHERE status = 'AVAILABLE' ORDER BY room_no, bed_no"""
    cursor.execute(sql)
    return {"sql_executed": sql, "results": rows_to_dicts(cursor, cursor.fetchall())}


@router.post("/admissions/admit")
def admit_patient_endpoint(
    patient_id: int, room_bed_id: int, doctor_id: int, reason: str,
    conn=Depends(get_connection),
):
    """Calls the admit_patient PL/SQL procedure (Phase 7). The bed's
    status flips to OCCUPIED via trg_bed_status_update -- not duplicated
    here, same pattern as discharge_patient in clinical.py."""
    cursor = conn.cursor()
    out_id = cursor.var(int)
    cursor.callproc("admit_patient", [patient_id, room_bed_id, doctor_id, reason, out_id])
    conn.commit()
    return {
        "sql_executed": f"CALL admit_patient({patient_id}, {room_bed_id}, {doctor_id}, '{reason}', :out)",
        "admission_id": _scalar(out_id),
    }
