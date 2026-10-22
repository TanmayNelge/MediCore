# app/routers/clinical.py
#
# FIX: out_id.getvalue() for an oracledb OUT variable with a single
# RETURNING INTO clause returns a list on some driver versions and a
# scalar on others. Normalised with a helper so the code works in both
# cases without crashing with a TypeError when [0] is applied to an int.

from fastapi import APIRouter, Depends
from app.db.session import get_connection
from app.db.helpers import rows_to_dicts

router = APIRouter()


def _scalar(var):
    """Return the scalar value from an oracledb OUT variable regardless of
    whether the driver wrapped it in a list (older behaviour) or not."""
    v = var.getvalue()
    return v[0] if isinstance(v, list) else v


@router.get("/clinical/patient-summary/{patient_id}")
def patient_summary(patient_id: int, conn=Depends(get_connection)):
    """vw_patient_medical_summary (Phase 6.1.1) -- diagnosis history, no billing exposed."""
    cursor = conn.cursor()
    sql = "SELECT * FROM vw_patient_medical_summary WHERE patient_id = :pid ORDER BY diagnosis_date DESC"
    cursor.execute(sql, pid=patient_id)
    return {
        "sql_executed": sql.replace(":pid", str(patient_id)),
        "results": rows_to_dicts(cursor, cursor.fetchall()),
    }


@router.get("/clinical/diseases")
def list_diseases(conn=Depends(get_connection)):
    """DISEASE reference table (ICD-10 code -> name)."""
    sql = "SELECT disease_code, disease_name, is_chronic FROM disease ORDER BY disease_name"
    cursor = conn.cursor()
    cursor.execute(sql)
    return {"sql_executed": sql, "results": rows_to_dicts(cursor, cursor.fetchall())}


@router.post("/clinical/diagnosis")
def add_diagnosis(
    patient_id: int, doctor_id: int, disease_code: str,
    appointment_id: int = None, admission_id: int = None, severity: str = None,
    conn=Depends(get_connection),
):
    """Exactly one of appointment_id / admission_id (chk_diag_one_encounter);
    disease_code must exist in DISEASE (FK); trg_diagnosis_encounter_chk
    rejects an encounter that belongs to another patient."""
    cursor = conn.cursor()
    out_id = cursor.var(int)
    sql = """INSERT INTO diagnosis (patient_id, doctor_id, appointment_id, admission_id, disease_code, severity)
             VALUES (:pid, :did, :aid, :adm, :dcode, :sev)
             RETURNING diagnosis_id INTO :out_id"""
    cursor.execute(sql, pid=patient_id, did=doctor_id, aid=appointment_id, adm=admission_id,
                   dcode=disease_code.strip().upper(), sev=severity, out_id=out_id)
    conn.commit()
    return {"sql_executed": sql, "diagnosis_id": _scalar(out_id)}


@router.get("/clinical/notes")
def list_clinical_notes(patient_id: int, conn=Depends(get_connection)):
    cursor = conn.cursor()
    sql = "SELECT note_id, patient_id, doctor_id, note_text, created_at FROM clinical_note WHERE patient_id = :pid ORDER BY created_at DESC"
    cursor.execute(sql, pid=patient_id)
    return {"sql_executed": sql.replace(":pid", str(patient_id)), "results": rows_to_dicts(cursor, cursor.fetchall())}


@router.post("/clinical/notes")
def add_clinical_note(
    patient_id: int, doctor_id: int, note_text: str,
    appointment_id: int = None, admission_id: int = None,
    conn=Depends(get_connection),
):
    cursor = conn.cursor()
    out_id = cursor.var(int)
    sql = """INSERT INTO clinical_note (patient_id, doctor_id, appointment_id, admission_id, note_text)
             VALUES (:pid, :did, :aid, :adm, :note)
             RETURNING note_id INTO :out_id"""
    cursor.execute(sql, pid=patient_id, did=doctor_id, aid=appointment_id, adm=admission_id,
                    note=note_text, out_id=out_id)
    conn.commit()
    return {"sql_executed": "INSERT INTO clinical_note (...)", "note_id": _scalar(out_id)}


@router.get("/clinical/vitals")
def list_vitals(patient_id: int, conn=Depends(get_connection)):
    cursor = conn.cursor()
    sql = "SELECT vital_id, patient_id, temperature_c, pulse_rate, systolic_bp, diastolic_bp, TO_CHAR(recorded_at, 'YYYY-MM-DD HH24:MI:SS') AS recorded_at FROM vital_sign WHERE patient_id = :pid ORDER BY recorded_at DESC"
    cursor.execute(sql, pid=patient_id)
    return {"sql_executed": sql.replace(":pid", str(patient_id)), "results": rows_to_dicts(cursor, cursor.fetchall())}


@router.post("/clinical/vitals")
def add_vitals(
    patient_id: int, temperature_c: float = None, pulse_rate: int = None,
    systolic_bp: int = None, diastolic_bp: int = None, spo2_percent: float = None,
    height_cm: float = None, weight_kg: float = None,
    appointment_id: int = None, admission_id: int = None,
    conn=Depends(get_connection),
):
    cursor = conn.cursor()
    out_id = cursor.var(int)
    sql = """INSERT INTO vital_sign (patient_id, appointment_id, admission_id,
                                      temperature_c, pulse_rate, systolic_bp, diastolic_bp,
                                      spo2_percent, height_cm, weight_kg)
             VALUES (:pid, :aid, :adm, :temp, :pulse, :sbp, :dbp, :spo2, :ht, :wt)
             RETURNING vital_id INTO :out_id"""
    cursor.execute(sql, pid=patient_id, aid=appointment_id, adm=admission_id, temp=temperature_c,
                    pulse=pulse_rate, sbp=systolic_bp, dbp=diastolic_bp, spo2=spo2_percent,
                    ht=height_cm, wt=weight_kg, out_id=out_id)
    conn.commit()
    return {"sql_executed": "INSERT INTO vital_sign (...)", "vital_id": _scalar(out_id)}


@router.post("/clinical/discharge/{admission_id}")
def discharge_patient(admission_id: int, conn=Depends(get_connection)):
    """Calls pkg_clinical_ops.discharge_patient (Phase 7.4) -- bed freed via
    trg_bed_status_update, not duplicated here."""
    cursor = conn.cursor()
    cursor.callproc("pkg_clinical_ops.discharge_patient", [admission_id])
    conn.commit()
    return {"sql_executed": f"CALL pkg_clinical_ops.discharge_patient({admission_id})", "status": "discharged"}
