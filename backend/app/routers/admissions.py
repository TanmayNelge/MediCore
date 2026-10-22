# app/routers/admissions.py
# Admit (admit_patient: bed row-lock FOR UPDATE), transfer (transfer_bed:
# both beds locked in id order -> no deadlock) and bed listings. Bed status
# changes are made by trg_bed_status_update, not by this code.

from fastapi import APIRouter, Depends

from app.auth.jwt import AppUser, require_roles
from app.db.helpers import call_proc, query
from app.db.session import get_connection

router = APIRouter()


@router.get("/admissions/available-beds")
def available_beds(conn=Depends(get_connection)):
    return query(conn, """SELECT rb.room_bed_id, rb.room_no, rb.bed_no, dep.department_name, rb.room_type, rb.daily_rate
                            FROM room_bed rb JOIN department dep ON dep.department_id = rb.department_id
                           WHERE rb.status = 'AVAILABLE' ORDER BY rb.room_no, rb.bed_no""")


@router.get("/admissions/bed-board")
def bed_board(conn=Depends(get_connection)):
    """Every bed with its current occupant (outer join)."""
    return query(conn, """SELECT rb.room_bed_id, rb.room_no, rb.bed_no, rb.room_type, rb.status,
                                 p.first_name || ' ' || p.last_name AS patient, ad.admission_id,
                                 TO_CHAR(ad.admit_date, 'YYYY-MM-DD') AS admit_date
                            FROM room_bed rb
                            LEFT JOIN admission ad ON ad.room_bed_id = rb.room_bed_id AND ad.status = 'ADMITTED'
                            LEFT JOIN patient p ON p.patient_id = ad.patient_id
                           ORDER BY rb.room_no, rb.bed_no""")


@router.post("/admissions/admit")
def admit_patient_endpoint(patient_id: int, room_bed_id: int, doctor_id: int, reason: str,
                           conn=Depends(get_connection),
                           user: AppUser = Depends(require_roles("ADMIN", "DOCTOR", "NURSE", "RECEPTIONIST"))):
    (adm_id,), meta = call_proc(conn, "admit_patient", [patient_id, room_bed_id, doctor_id, reason], (int,))
    return {"admission_id": adm_id, **meta}


@router.post("/admissions/{admission_id}/transfer")
def transfer(admission_id: int, new_bed_id: int, conn=Depends(get_connection),
             user: AppUser = Depends(require_roles("ADMIN", "DOCTOR", "NURSE"))):
    _, meta = call_proc(conn, "transfer_bed", [admission_id, new_bed_id])
    return {"status": "transferred", **meta}
