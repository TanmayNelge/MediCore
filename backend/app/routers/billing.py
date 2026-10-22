# app/routers/billing.py
# Bills and payments. Payments go through record_payment(), which locks
# the bill row (SELECT ... FOR UPDATE) and refuses over-payment; the bill
# status flip (UNPAID -> PARTIALLY_PAID -> PAID) is done by the compound
# trigger trg_bill_status_update, not by this code.

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.auth.jwt import AppUser, require_roles
from app.db.helpers import call_proc, query
from app.db.session import get_connection

router = APIRouter()
MODES = {"CASH", "CARD", "UPI", "INSURANCE", "NET_BANKING"}


@router.get("/billing/summary/{patient_id}")
def billing_summary(patient_id: int, conn=Depends(get_connection)):
    """vw_patient_billing_summary - aggregate view, not updatable."""
    return query(conn, "SELECT bill_id, TO_CHAR(bill_date, 'YYYY-MM-DD') AS bill_date, status, total_amount, "
                       "total_paid, balance_due FROM vw_patient_billing_summary WHERE patient_id = :pid "
                       "ORDER BY bill_date DESC", {"pid": patient_id})


@router.get("/billing/bills/{bill_id}/items")
def bill_items(bill_id: int, conn=Depends(get_connection)):
    return query(conn, "SELECT bill_item_id, item_description, item_category, amount FROM bill_item "
                       "WHERE bill_id = :bid ORDER BY bill_item_id", {"bid": bill_id})


@router.get("/billing/outstanding")
def outstanding(bucket: Optional[str] = None, conn=Depends(get_connection),
                user: AppUser = Depends(require_roles("ADMIN", "BILLING"))):
    """vw_outstanding_bills - ageing report (0-30 / 31-90 / 90+ days)."""
    if bucket:
        return query(conn, "SELECT bill_id, patient_id, patient_name, phone, TO_CHAR(bill_date,'YYYY-MM-DD') AS bill_date, "
                           "status, total_amount, total_paid, balance_due, days_outstanding, ageing_bucket "
                           "FROM vw_outstanding_bills WHERE ageing_bucket = :b ORDER BY days_outstanding DESC",
                     {"b": bucket})
    return query(conn, "SELECT bill_id, patient_id, patient_name, phone, TO_CHAR(bill_date,'YYYY-MM-DD') AS bill_date, "
                       "status, total_amount, total_paid, balance_due, days_outstanding, ageing_bucket "
                       "FROM vw_outstanding_bills ORDER BY days_outstanding DESC")


@router.post("/billing/generate/{appointment_id}")
def generate_bill(appointment_id: int, patient_id: int, conn=Depends(get_connection),
                  user: AppUser = Depends(require_roles("ADMIN", "BILLING"))):
    """generate_bill(): consultation fee + that visit's lab tests (INSERT ... SELECT)."""
    (bill_id,), meta = call_proc(conn, "generate_bill", [patient_id, appointment_id], (int,))
    return {"bill_id": bill_id, **meta}


@router.get("/billing/payments")
def list_payments(bill_id: Optional[int] = None, conn=Depends(get_connection)):
    base = ("SELECT payment_id, bill_id, amount_paid, payment_mode, TO_CHAR(paid_date, 'YYYY-MM-DD') AS paid_date "
            "FROM payment")
    if bill_id:
        return query(conn, base + " WHERE bill_id = :bid ORDER BY paid_date DESC", {"bid": bill_id})
    return query(conn, base + " ORDER BY paid_date DESC, payment_id DESC FETCH FIRST 50 ROWS ONLY")


@router.post("/billing/payments")
def record_payment(bill_id: int, amount_paid: float, payment_mode: str, conn=Depends(get_connection),
                   user: AppUser = Depends(require_roles("ADMIN", "BILLING"))):
    mode = payment_mode.upper()
    if mode not in MODES:
        raise HTTPException(422, f"payment_mode must be one of {sorted(MODES)}")
    if amount_paid <= 0:
        raise HTTPException(422, "amount_paid must be positive")
    (pid,), meta = call_proc(conn, "record_payment", [bill_id, amount_paid, mode], (int,))
    status = query(conn, "SELECT status, fn_bill_balance(bill_id) AS balance FROM bill WHERE bill_id = :b", {"b": bill_id})
    row = status["results"][0] if status["results"] else {}
    return {"payment_id": pid, "bill_status_after_trigger": row.get("status"), "balance": row.get("balance"), **meta}
