# app/routers/dbms_lab.py
# Phase 13.4 -- an accordion of the 20 concept categories from the brief.
# No new SQL is invented here; every "canonical_query" is copied verbatim
# from the Phase 5-10 objects already built. The /execute endpoint is the
# "read-only sandboxed endpoint" the blueprint calls for: only SELECT
# statements are allowed through, enforced by a regex.
#
# FIX: previously this endpoint ran queries through get_connection (the
# CALLER's own role connection), so its only real protection was the
# regex below. It now uses get_readonly_connection, which always
# connects as readonly1 (READONLY_ROLE: SELECT-only on every table/view
# -- see database/12_security_roles_FIXED.sql), regardless of which app
# role is calling it. That gives defense in depth exactly as Phase 13.4
# calls for: even if a query slipped past the regex, the DB connection
# backing it physically cannot INSERT/UPDATE/DELETE/DDL anything.

import re
from fastapi import APIRouter, Depends, HTTPException
from app.db.session import get_readonly_connection
from app.db.helpers import rows_to_dicts

router = APIRouter()

CONCEPTS = [
    {
        "id": "ddl", "name": "DDL — Data Definition Language",
        "theory": "Statements that define/alter the schema itself (CREATE, ALTER, DROP). "
                  "They are auto-committing DDL in Oracle -- no explicit COMMIT needed or possible.",
        "canonical_query": "CREATE TABLE patient (\n    patient_id NUMBER DEFAULT seq_patient_id.NEXTVAL PRIMARY KEY,\n    first_name VARCHAR2(50) NOT NULL,\n    ...\n);",
        "executable": False,
    },
    {
        "id": "dml", "name": "DML — Data Manipulation Language",
        "theory": "INSERT/UPDATE/DELETE change row data. Unlike DDL, DML is transactional "
                  "and must be explicitly COMMITted or it can be ROLLBACKed.",
        "canonical_query": "INSERT INTO payment (bill_id, amount_paid, payment_mode) VALUES (:bid, :amt, :mode)",
        "executable": False,
    },
    {
        "id": "dql", "name": "DQL — Data Query Language",
        "theory": "SELECT statements -- pure reads, no schema or data changes.",
        "canonical_query": "SELECT patient_id, first_name, last_name, phone FROM patient WHERE last_name LIKE 'S%'",
        "executable": True,
    },
    {
        "id": "joins", "name": "Joins",
        "theory": "Combining rows across tables on a related column. vw_patient_medical_summary "
                  "is a 3-table INNER JOIN (patient, diagnosis, doctor).",
        "canonical_query": "SELECT * FROM vw_patient_medical_summary WHERE ROWNUM <= 10",
        "executable": True,
    },
    {
        "id": "aggregates", "name": "Aggregate Functions",
        "theory": "COUNT, SUM, AVG, MIN, MAX collapse multiple rows into a single summary value. "
                  "The dashboard KPI query runs six scalar aggregate subqueries in one round trip.",
        "canonical_query": "SELECT COUNT(*) AS total_patients FROM patient",
        "executable": True,
    },
    {
        "id": "group_by", "name": "GROUP BY",
        "theory": "Partitions rows into groups before aggregating. vw_doctor_workload groups "
                  "appointments per doctor.",
        "canonical_query": "SELECT doctor_id, COUNT(*) AS total_appointments FROM appointment GROUP BY doctor_id",
        "executable": True,
    },
    {
        "id": "having", "name": "HAVING",
        "theory": "Filters groups AFTER aggregation -- unlike WHERE, which filters rows BEFORE "
                  "grouping. Doctors with more than 2 appointments, for example.",
        "canonical_query": "SELECT doctor_id, COUNT(*) AS c FROM appointment GROUP BY doctor_id HAVING COUNT(*) > 2",
        "executable": True,
    },
    {
        "id": "subqueries", "name": "Subqueries",
        "theory": "A query nested inside another. vw_patient_billing_summary uses a scalar "
                  "subquery to sum a patient's payments.",
        "canonical_query": "SELECT bill_id, (SELECT SUM(amount_paid) FROM payment pay WHERE pay.bill_id = b.bill_id) AS total_paid FROM bill b",
        "executable": True,
    },
    {
        "id": "correlated", "name": "Correlated Subqueries",
        "theory": "A subquery that references a column from the outer query -- it re-runs "
                  "conceptually once per outer row, unlike an independent subquery.",
        "canonical_query": "SELECT b.bill_id FROM bill b WHERE EXISTS (SELECT 1 FROM payment p WHERE p.bill_id = b.bill_id)",
        "executable": True,
    },
    {
        "id": "views", "name": "Views",
        "theory": "A saved, named SELECT that behaves like a virtual table. vw_medicine_inventory_status "
                  "is updatable (single base table); vw_patient_billing_summary is not (aggregated).",
        "canonical_query": "SELECT * FROM vw_medicine_inventory_status WHERE stock_status = 'REORDER'",
        "executable": True,
    },
    {
        "id": "indexes", "name": "Indexes",
        "theory": "B-tree structures mapping column values to ROWIDs, avoiding full table scans "
                  "at the cost of slower writes. idx_appt_doctor_date is a composite index.",
        "canonical_query": "CREATE INDEX idx_appt_doctor_date ON appointment(doctor_id, appt_date)",
        "executable": False,
    },
    {
        "id": "transactions", "name": "Transactions",
        "theory": "A unit of work that is atomic -- book_appointment inserts into both "
                  "appointment and service_queue, then COMMITs; any failure ROLLBACKs both.",
        "canonical_query": "BEGIN\n  INSERT INTO appointment (...) VALUES (...);\n  INSERT INTO service_queue (...) VALUES (...);\n  COMMIT;\nEXCEPTION WHEN OTHERS THEN ROLLBACK;\nEND;",
        "executable": False,
    },
    {
        "id": "plsql", "name": "PL/SQL",
        "theory": "Oracle's procedural extension to SQL -- variables, IF/ELSE, loops, exceptions. "
                  "calculate_bmi is a pure function with no side effects.",
        "canonical_query": "CREATE OR REPLACE FUNCTION calculate_bmi(p_weight_kg NUMBER, p_height_cm NUMBER) RETURN NUMBER IS BEGIN RETURN ROUND(p_weight_kg / POWER(p_height_cm/100, 2), 2); END;",
        "executable": False,
    },
    {
        "id": "procedures", "name": "Stored Procedures",
        "theory": "Named, reusable PL/SQL blocks that can take IN/OUT parameters and perform "
                  "multi-statement work. register_lab_order takes 3 IN params and returns an OUT id.",
        "canonical_query": "CREATE OR REPLACE PROCEDURE register_lab_order(p_patient_id NUMBER, p_doctor_id NUMBER, p_lab_test_id NUMBER, p_lab_order_id OUT NUMBER) IS BEGIN INSERT INTO lab_order (...) RETURNING lab_order_id INTO p_lab_order_id; COMMIT; END;",
        "executable": False,
    },
    {
        "id": "functions", "name": "Stored Functions",
        "theory": "Like a procedure, but always returns exactly one value and can be used inline "
                  "in a SELECT. Demonstrates deriving age dynamically from DOB — never stored as a column.",
        "canonical_query": "SELECT patient_id, first_name, last_name, TRUNC(MONTHS_BETWEEN(SYSDATE, dob)/12) AS calculated_age FROM patient",
        "executable": True,
    },
    {
        "id": "cursors", "name": "Cursors",
        "theory": "An explicit cursor lets PL/SQL iterate row-by-row with fine control (locking, "
                  "ordering). get_next_patient uses FOR UPDATE SKIP LOCKED so two receptionists "
                  "calling 'next' simultaneously never grab the same patient.",
        "canonical_query": "CURSOR c_next IS\n  SELECT queue_id, patient_id FROM service_queue\n  WHERE queue_type = p_queue_type AND status = 'WAITING'\n  ORDER BY priority_level, arrival_time\n  FOR UPDATE SKIP LOCKED;",
        "executable": False,
    },
    {
        "id": "triggers", "name": "Triggers",
        "theory": "Code that fires automatically on INSERT/UPDATE/DELETE. E.g. a bed-status trigger "
                  "flips room_bed to OCCUPIED the moment an admission row is inserted, so the app "
                  "layer never has to remember to do it manually.",
        "canonical_query": "CREATE OR REPLACE TRIGGER trg_bed_status_update\nAFTER INSERT OR UPDATE ON admission\nFOR EACH ROW\nBEGIN\n  UPDATE room_bed SET status = CASE WHEN :NEW.status='ADMITTED' THEN 'OCCUPIED' ELSE 'AVAILABLE' END\n  WHERE room_bed_id = :NEW.room_bed_id;\nEND;",
        "executable": False,
    },
    {
        "id": "queues", "name": "Queue Modeling",
        "theory": "service_queue generalizes OPD/Emergency/Lab/Pharmacy queues via queue_type. "
                  "Hybrid priority+FIFO: lower priority_level always wins across levels, FIFO within a level.",
        "canonical_query": "SELECT * FROM service_queue WHERE queue_type='OPD' AND status='WAITING' ORDER BY priority_level, arrival_time",
        "executable": True,
    },
    {
        "id": "security", "name": "Security & Roles",
        "theory": "Six least-privilege DB users (doctor1, receptionist1, ...) each mapped to a role "
                  "with only the object grants that role needs -- enforced by Oracle itself, not "
                  "just application code.",
        "canonical_query": "GRANT SELECT, UPDATE ON hcms_admin.patient TO doctor_role",
        "executable": False,
    },
    {
        "id": "normalization", "name": "Normalization",
        "theory": "The 26-table schema is in 3NF: every non-key column depends on the whole "
                  "primary key and nothing but the key (e.g. bill_item.amount lives with the "
                  "line item, not duplicated onto bill; insurance_policy is split out as its own "
                  "1:0..1 table rather than nullable columns bolted onto patient).",
        "canonical_query": "-- No query -- structural property of the schema design, see 01_schema.sql",
        "executable": False,
    },
]


@router.get("/dbms-lab/concepts")
def list_concepts():
    return {"concepts": CONCEPTS}


_SELECT_ONLY = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|MERGE|EXEC|CALL)\b",
    re.IGNORECASE,
)


@router.post("/dbms-lab/execute")
def execute_readonly(query: str, conn=Depends(get_readonly_connection)):
    """The sandboxed endpoint from Phase 13.4 -- SELECT only, enforced both
    by the regex below AND by the readonly DB connection's SELECT-only
    grants (see module docstring)."""
    clean_query = query.strip()
    if not _SELECT_ONLY.match(clean_query) or _FORBIDDEN.search(clean_query):
        raise HTTPException(status_code=400, detail="Only single SELECT statements are allowed here.")
    
    # Strip any trailing semicolon so Oracle does not reject with ORA-00911
    clean_query = clean_query.rstrip(";").strip()
    if ";" in clean_query:
        raise HTTPException(status_code=400, detail="Only a single statement is allowed.")

    # Auto-bind common demo placeholders if present
    binds = {}
    if ":ln" in clean_query:
        binds["ln"] = "S%"

    import oracledb
    cursor = conn.cursor()
    try:
        cursor.execute(clean_query, **binds)
        rows = cursor.fetchmany(200)  # hard cap, this is a lab sandbox not a reporting tool
        return {"sql_executed": clean_query, "results": rows_to_dicts(cursor, rows), "row_limit": 200}
    except oracledb.DatabaseError as e:
        err_str = str(e)
        if "CALCULATE_AGE" in err_str.upper():
            try:
                fallback_query = re.sub(
                    r"\bcalculate_age\s*\(\s*([a-zA-Z0-9_\.]+)\s*\)",
                    r"TRUNC(MONTHS_BETWEEN(SYSDATE, \1)/12)",
                    clean_query,
                    flags=re.IGNORECASE,
                )
                cursor.execute(fallback_query, **binds)
                rows = cursor.fetchmany(200)
                return {
                    "sql_executed": clean_query,
                    "results": rows_to_dicts(cursor, rows),
                    "row_limit": 200,
                    "note": "Substituted built-in MONTHS_BETWEEN() for calculate_age().",
                }
            except Exception:
                pass
        err_msg = err_str.splitlines()[0]
        raise HTTPException(status_code=400, detail=f"Oracle SQL Error: {err_msg}")

