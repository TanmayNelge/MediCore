# app/routers/billing.py
#
# FIX: generate_bill was missing conn.commit(). The procedure writes a
# bill row and line items but neither was ever committed, so the data
# disappeared on connection close.

from typing import Optional
from fastapi import APIRouter, Depends
from app.db.session import get_connection
from app.db.helpers import rows_to_dicts

router = APIRouter()


@router.get("/billing/summary/{patient_id}")
def billing_summary(patient_id: int, conn=Depends(get_connection)):
    """vw_patient_billing_summary (Phase 6.1.3) -- aggregate view, not updatable."""
    cursor = conn.cursor()
    sql = "SELECT * FROM vw_patient_billing_summary WHERE patient_id = :pid ORDER BY bill_date DESC"
    cursor.execute(sql, pid=patient_id)
    return {"sql_executed": sql.replace(":pid", str(patient_id)),
            "results": rows_to_dicts(cursor, cursor.fetchall())}


@router.post("/billing/generate/{appointment_id}")
def generate_bill(appointment_id: int, patient_id: int, conn=Depends(get_connection)):
    """Calls the generate_bill procedure (Phase 7.3) -- consultation fee
    line item derived from the doctor's fee via a join, not duplicated here.
    FIX: added conn.commit() so the bill and bill_item rows are persisted."""
    cursor = conn.cursor()
    out_id = cursor.var(int)
    cursor.callproc("generate_bill", [patient_id, appointment_id, out_id])
    conn.commit()
    raw = out_id.getvalue()
    new_id = raw[0] if isinstance(raw, list) else raw
    return {"sql_executed": "CALL generate_bill(...)", "bill_id": new_id}


@router.get("/billing/payments")
def list_payments(bill_id: Optional[int] = None, conn=Depends(get_connection)):
    cursor = conn.cursor()
    if bill_id:
        sql = "SELECT payment_id, bill_id, amount_paid, payment_mode, TO_CHAR(paid_date, 'YYYY-MM-DD') AS paid_date FROM payment WHERE bill_id = :bid ORDER BY paid_date DESC"
        cursor.execute(sql, bid=bill_id)
        shown_sql = sql.replace(":bid", str(bill_id))
    else:
        sql = "SELECT payment_id, bill_id, amount_paid, payment_mode, TO_CHAR(paid_date, 'YYYY-MM-DD') AS paid_date FROM payment ORDER BY paid_date DESC FETCH FIRST 50 ROWS ONLY"
        cursor.execute(sql)
        shown_sql = sql
    return {"sql_executed": shown_sql, "results": rows_to_dicts(cursor, cursor.fetchall())}


@router.post("/billing/payments")
def record_payment(bill_id: int, amount_paid: float, payment_mode: str, conn=Depends(get_connection)):
    """Insert only -- bill.status flip to PAID/PARTIALLY_PAID happens in
    trg_bill_status_update (Phase 8), not duplicated here."""
    cursor = conn.cursor()
    out_id = cursor.var(int)
    sql = """INSERT INTO payment (bill_id, amount_paid, payment_mode)
             VALUES (:bid, :amt, :mode) RETURNING payment_id INTO :out_id"""
    cursor.execute(sql, bid=bill_id, amt=amount_paid, mode=payment_mode, out_id=out_id)
    conn.commit()
    return {"sql_executed": "INSERT INTO payment (...)", "payment_id": out_id.getvalue()[0]}
