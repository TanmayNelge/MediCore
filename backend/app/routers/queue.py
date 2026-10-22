# app/routers/queue.py
# Mirrors Phase 9's core queue operations exactly.
#
# FIX: add_to_queue and prioritize_emergency were missing conn.commit().
# The stored procedures INSERT into service_queue but neither was ever
# committed, so rows vanished on connection close.

from fastapi import APIRouter, Depends
from app.db.session import get_connection
from app.db.helpers import rows_to_dicts

router = APIRouter()


def _scalar(var):
    v = var.getvalue()
    return v[0] if isinstance(v, list) else v


@router.post("/queue/add")
def add_to_queue(
    queue_type: str, patient_id: int,
    doctor_id: int = None, department_id: int = None,
    conn=Depends(get_connection),
):
    """queue_type: OPD | EMERGENCY | LAB | PHARMACY (Phase 9.1)."""
    cursor = conn.cursor()
    out_id = cursor.var(int)
    cursor.callproc("add_to_queue", [queue_type, patient_id, doctor_id, department_id, out_id])
    conn.commit()
    return {"sql_executed": "CALL add_to_queue(...)", "queue_id": _scalar(out_id)}


@router.post("/queue/next")
def get_next_patient(queue_type: str, conn=Depends(get_connection)):
    """Priority-then-FIFO, concurrency-safe via FOR UPDATE SKIP LOCKED (Phase 9.2)."""
    cursor = conn.cursor()
    out_qid, out_pid = cursor.var(int), cursor.var(int)
    cursor.callproc("get_next_patient", [queue_type, out_qid, out_pid])
    conn.commit()
    qid, pid = _scalar(out_qid), _scalar(out_pid)
    return {
        "sql_executed": "CALL get_next_patient(...)",
        "queue_id": qid, "patient_id": pid,
        "message": "No waiting patients." if qid is None else "Patient called.",
    }


@router.post("/queue/emergency")
def prioritize_emergency(patient_id: int, conn=Depends(get_connection)):
    cursor = conn.cursor()
    out_id = cursor.var(int)
    cursor.callproc("prioritize_emergency", [patient_id, out_id])
    conn.commit()
    return {"sql_executed": "CALL prioritize_emergency(...)", "queue_id": _scalar(out_id)}


@router.post("/queue/{queue_id}/complete")
def complete(queue_id: int, conn=Depends(get_connection)):
    cursor = conn.cursor()
    cursor.callproc("mark_queue_completed", [queue_id])
    conn.commit()
    return {"sql_executed": f"CALL mark_queue_completed({queue_id})", "status": "completed"}


@router.post("/queue/{queue_id}/cancel")
def cancel(queue_id: int, conn=Depends(get_connection)):
    cursor = conn.cursor()
    cursor.callproc("cancel_queue_entry", [queue_id])
    conn.commit()
    return {"sql_executed": f"CALL cancel_queue_entry({queue_id})", "status": "cancelled"}


@router.get("/queue/emergency-list")
def emergency_queue(conn=Depends(get_connection)):
    """vw_emergency_queue (Phase 6.1.7)."""
    cursor = conn.cursor()
    sql = "SELECT * FROM vw_emergency_queue"
    cursor.execute(sql)
    return {"sql_executed": sql, "results": rows_to_dicts(cursor, cursor.fetchall())}


@router.get("/queue/wait-estimate")
def opd_wait_estimate(conn=Depends(get_connection)):
    """Position + rough ETA for today's waiting OPD queue (Phase 9.3) --
    computed on read, never stored, since it would go stale immediately."""
    cursor = conn.cursor()
    sql = """SELECT queue_id, patient_id, priority_level,
                     ROW_NUMBER() OVER (ORDER BY priority_level, arrival_time) AS position_in_line,
                     (ROW_NUMBER() OVER (ORDER BY priority_level, arrival_time) - 1) * 12 AS est_wait_minutes
              FROM service_queue
              WHERE queue_type = 'OPD' AND status = 'WAITING' AND queue_date = TRUNC(SYSDATE)"""
    cursor.execute(sql)
    return {"sql_executed": sql, "results": rows_to_dicts(cursor, cursor.fetchall())}


@router.get("/queue/today")
def queue_today(queue_type: str = None, conn=Depends(get_connection)):
    """All of today's tokens, priority-then-FIFO order (the order get_next_patient uses)."""
    from app.db.helpers import query
    sql = """SELECT q.queue_id, q.queue_type, q.queue_number, q.patient_id, q.priority_level, q.status,
                    TO_CHAR(q.arrival_time, 'HH24:MI') AS arrived, TO_CHAR(q.called_time, 'HH24:MI') AS called,
                    ROUND((CAST(NVL(q.called_time, SYSTIMESTAMP) AS DATE) - CAST(q.arrival_time AS DATE)) * 1440) AS wait_minutes
               FROM service_queue q
              WHERE q.queue_date = TRUNC(SYSDATE) AND (:qt IS NULL OR q.queue_type = :qt)
              ORDER BY CASE q.status WHEN 'WAITING' THEN 0 WHEN 'CALLED' THEN 1 ELSE 2 END,
                       q.priority_level, q.arrival_time"""
    return query(conn, sql, {"qt": queue_type})
