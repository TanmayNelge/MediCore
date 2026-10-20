# app/routers/pharmacy.py
#
# FIX: added GET /pharmacy/medicines endpoint — PharmacyPage's LookupSelect
# for medicines called /api/pharmacy/medicines which didn't exist, causing
# every medicine picker to fall back to the free-text ID input.
# Also: add_prescription was missing conn.commit() (the stored procedure
# performs inserts that were never committed).

from typing import Optional
from fastapi import APIRouter, Depends
from app.db.session import get_connection
from app.db.helpers import rows_to_dicts

router = APIRouter()


@router.get("/pharmacy/medicines")
def list_medicines(conn=Depends(get_connection)):
    """Return the medicine catalogue for use in the prescription LookupSelect."""
    cursor = conn.cursor()
    sql = "SELECT medicine_id, medicine_name, category, unit_price, stock_quantity FROM medicine ORDER BY medicine_name"
    cursor.execute(sql)
    return {"sql_executed": sql, "results": rows_to_dicts(cursor, cursor.fetchall())}


@router.get("/pharmacy/inventory")
def inventory_status(conn=Depends(get_connection)):
    """vw_medicine_inventory_status (Phase 6.1.6)."""
    cursor = conn.cursor()
    sql = "SELECT * FROM vw_medicine_inventory_status ORDER BY stock_status, medicine_name"
    cursor.execute(sql)
    return {"sql_executed": sql, "results": rows_to_dicts(cursor, cursor.fetchall())}


@router.get("/pharmacy/prescriptions")
def list_prescriptions(patient_id: Optional[int] = None, conn=Depends(get_connection)):
    cursor = conn.cursor()
    if patient_id:
        sql = """SELECT p.prescription_id, p.patient_id, p.doctor_id, pi.medicine_id,
                        m.medicine_name, pi.dosage, pi.quantity,
                        TO_CHAR(p.prescribed_date, 'YYYY-MM-DD') AS prescribed_date
                 FROM prescription p
                 JOIN prescription_item pi ON pi.prescription_id = p.prescription_id
                 JOIN medicine m ON m.medicine_id = pi.medicine_id
                 WHERE p.patient_id = :pid
                 ORDER BY p.prescribed_date DESC"""
        cursor.execute(sql, pid=patient_id)
        shown_sql = sql.replace(":pid", str(patient_id))
    else:
        sql = """SELECT p.prescription_id, p.patient_id, p.doctor_id, pi.medicine_id,
                        m.medicine_name, pi.dosage, pi.quantity,
                        TO_CHAR(p.prescribed_date, 'YYYY-MM-DD') AS prescribed_date
                 FROM prescription p
                 JOIN prescription_item pi ON pi.prescription_id = p.prescription_id
                 JOIN medicine m ON m.medicine_id = pi.medicine_id
                 ORDER BY p.prescribed_date DESC
                 FETCH FIRST 50 ROWS ONLY"""
        cursor.execute(sql)
        shown_sql = sql
    return {"sql_executed": shown_sql, "results": rows_to_dicts(cursor, cursor.fetchall())}


@router.post("/pharmacy/prescriptions")
def add_prescription(
    patient_id: int, doctor_id: int, medicine_id: int,
    dosage: str, duration_days: int, quantity: int,
    appointment_id: Optional[int] = None,
    conn=Depends(get_connection),
):
    """Calls the add_prescription procedure (Phase 7.3) -- stock check
    happens in trg_prescription_stock_check, not duplicated here.
    FIX: added conn.commit() so the prescription row is actually persisted."""
    cursor = conn.cursor()
    out_id = cursor.var(int)
    cursor.callproc("add_prescription", [
        patient_id, doctor_id, appointment_id, medicine_id, dosage, duration_days, quantity, out_id,
    ])
    conn.commit()
    return {"sql_executed": "CALL add_prescription(...)", "prescription_id": out_id.getvalue()}


@router.put("/pharmacy/medicine/{medicine_id}/stock")
def adjust_stock(medicine_id: int, stock_quantity: int, conn=Depends(get_connection)):
    """Direct stock correction (e.g. after a supplier delivery not modeled
    via the prescription-fulfillment path)."""
    cursor = conn.cursor()
    sql = "UPDATE medicine SET stock_quantity = :qty WHERE medicine_id = :mid"
    cursor.execute(sql, qty=stock_quantity, mid=medicine_id)
    conn.commit()
    return {
        "sql_executed": sql.replace(":qty", str(stock_quantity)).replace(":mid", str(medicine_id)),
        "rows_updated": cursor.rowcount,
    }
