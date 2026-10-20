# app/routers/lab.py
#
# FIX: added GET /lab/tests endpoint — LabPage's LookupSelect for lab tests
# called /api/lab/tests which didn't exist, causing every test picker to
# silently fall back to the free-text ID input.
# Also: register_lab_order was missing conn.commit() (the stored procedure
# performs an INSERT that was never committed).

from typing import Optional
from fastapi import APIRouter, Depends
from app.db.session import get_connection
from app.db.helpers import rows_to_dicts

router = APIRouter()


@router.get("/lab/tests")
def list_lab_tests(conn=Depends(get_connection)):
    """Return the lab test catalogue for use in the order LookupSelect."""
    cursor = conn.cursor()
    sql = "SELECT lab_test_id, test_code, test_name, normal_range, price FROM lab_test_catalog ORDER BY test_name"
    cursor.execute(sql)
    return {"sql_executed": sql, "results": rows_to_dicts(cursor, cursor.fetchall())}


@router.get("/lab/pending")
def pending_reports(conn=Depends(get_connection)):
    """vw_pending_lab_reports (Phase 6.1.4) -- ORDERED or SAMPLE_COLLECTED only."""
    cursor = conn.cursor()
    sql = "SELECT * FROM vw_pending_lab_reports ORDER BY order_date"
    cursor.execute(sql)
    return {"sql_executed": sql, "results": rows_to_dicts(cursor, cursor.fetchall())}


@router.get("/lab/orders")
def list_lab_orders(patient_id: Optional[int] = None, conn=Depends(get_connection)):
    cursor = conn.cursor()
    if patient_id:
        sql = """SELECT lo.lab_order_id, lo.patient_id, lo.doctor_id, ltc.test_name,
                        TO_CHAR(lo.order_date, 'YYYY-MM-DD') AS order_date, lo.status, lo.result_value
                 FROM lab_order lo
                 JOIN lab_test_catalog ltc ON ltc.lab_test_id = lo.lab_test_id
                 WHERE lo.patient_id = :pid
                 ORDER BY lo.order_date DESC"""
        cursor.execute(sql, pid=patient_id)
        shown_sql = sql.replace(":pid", str(patient_id))
    else:
        sql = """SELECT lo.lab_order_id, lo.patient_id, lo.doctor_id, ltc.test_name,
                        TO_CHAR(lo.order_date, 'YYYY-MM-DD') AS order_date, lo.status, lo.result_value
                 FROM lab_order lo
                 JOIN lab_test_catalog ltc ON ltc.lab_test_id = lo.lab_test_id
                 ORDER BY lo.order_date DESC
                 FETCH FIRST 50 ROWS ONLY"""
        cursor.execute(sql)
        shown_sql = sql
    return {"sql_executed": shown_sql, "results": rows_to_dicts(cursor, cursor.fetchall())}


@router.post("/lab/orders")
def register_order(patient_id: int, doctor_id: int, lab_test_id: int, conn=Depends(get_connection)):
    """Calls the register_lab_order procedure (Phase 7.3).
    FIX: added conn.commit() so the lab_order row is actually persisted."""
    cursor = conn.cursor()
    out_id = cursor.var(int)
    cursor.callproc("register_lab_order", [patient_id, doctor_id, lab_test_id, out_id])
    conn.commit()
    raw = out_id.getvalue()
    new_id = raw[0] if isinstance(raw, list) else raw
    return {"sql_executed": "CALL register_lab_order(...)", "lab_order_id": new_id}


@router.put("/lab/orders/{lab_order_id}/collect")
def mark_sample_collected(lab_order_id: int, conn=Depends(get_connection)):
    cursor = conn.cursor()
    sql = "UPDATE lab_order SET status = 'SAMPLE_COLLECTED' WHERE lab_order_id = :id AND status = 'ORDERED'"
    cursor.execute(sql, id=lab_order_id)
    conn.commit()
    return {"sql_executed": sql.replace(":id", str(lab_order_id)), "rows_updated": cursor.rowcount}


@router.put("/lab/orders/{lab_order_id}/result")
def record_result(lab_order_id: int, result_value: str, conn=Depends(get_connection)):
    """chk_result_after_order (Phase 4.3) requires result_date >= order_date;
    SYSDATE always satisfies that since order_date can't be in the future."""
    cursor = conn.cursor()
    sql = """UPDATE lab_order SET result_value = :val, result_date = SYSDATE, status = 'RESULT_READY'
             WHERE lab_order_id = :id"""
    cursor.execute(sql, val=result_value, id=lab_order_id)
    conn.commit()
    return {
        "sql_executed": sql.replace(":val", f"'{result_value}'").replace(":id", str(lab_order_id)),
        "rows_updated": cursor.rowcount,
    }
