# app/routers/dbms_lab.py
# DBMS Concept Lab - every concept of the brief, each backed by a real
# query on the project data, plus LIVE demonstrations that run against
# Oracle and report every step:
#
#   GET  /dbms-lab/concepts             catalogue (theory + SQL; runnable ones flagged)
#   POST /dbms-lab/execute              SELECT-only SQL console (readonly1 connection)
#   POST /dbms-lab/explain              EXPLAIN PLAN + DBMS_XPLAN for a SELECT
#   POST /dbms-lab/demo/transaction     SAVEPOINT / ROLLBACK TO / statement-level atomicity
#   POST /dbms-lab/demo/atomic-procedure  failing stored procedure leaves no partial rows
#   POST /dbms-lab/demo/isolation       two sessions: no dirty read, lock wait, SKIP LOCKED
#   POST /dbms-lab/demo/rbac            every role x probe matrix (ORA-00942 / ORA-01031)
#
# Every demo ends with ROLLBACK - nothing is changed permanently.

import re
import time

import oracledb
from fastapi import APIRouter, Depends, HTTPException

from app.auth.jwt import AppUser, require_roles
from app.db.helpers import rows_to_dicts
from app.db.pool import _ROLE_USERS
from app.db.session import connection_for, get_admin_connection, get_readonly_connection

router = APIRouter()


def C(id, category, name, theory, sql, executable=True):
    return {"id": id, "category": category, "name": name, "theory": theory,
            "canonical_query": sql.strip(), "executable": executable}


CONCEPTS = [
    # ---------------- DDL / DML ----------------
    C("ddl", "DDL & DML", "DDL - CREATE / ALTER / DROP",
      "Defines the schema. In Oracle every DDL statement auto-commits (an implicit COMMIT before and after), "
      "so it cannot be rolled back. 01_schema.sql creates 27 tables with PK, FK, UNIQUE, CHECK and NOT NULL constraints.",
      """CREATE TABLE appointment (
    appointment_id NUMBER DEFAULT seq_appointment_id.NEXTVAL PRIMARY KEY,
    patient_id     NUMBER NOT NULL REFERENCES patient(patient_id),
    doctor_id      NUMBER NOT NULL REFERENCES doctor(doctor_id),
    appt_date      DATE   NOT NULL,
    appt_time      VARCHAR2(5) NOT NULL CHECK (REGEXP_LIKE(appt_time, '^([01][0-9]|2[0-3]):[0-5][0-9]$')),
    status         VARCHAR2(15) DEFAULT 'SCHEDULED' CHECK (status IN ('SCHEDULED','COMPLETED','CANCELLED','NO_SHOW')),
    CONSTRAINT uq_doctor_timeslot UNIQUE (doctor_id, appt_date, appt_time)
);
ALTER TABLE department ADD CONSTRAINT fk_dept_head FOREIGN KEY (head_doctor_id) REFERENCES doctor(doctor_id);""", False),
    C("dml", "DDL & DML", "DML - INSERT / UPDATE / DELETE / MERGE",
      "Changes rows; transactional (needs COMMIT, can be rolled back). Use the Patients page (INSERT/UPDATE/DELETE) "
      "and watch the SQL panel. MERGE is an upsert - the ML pipeline uses it to write ML_PREDICTION.",
      """INSERT INTO patient (first_name, last_name, dob, gender, phone) VALUES (:fn, :ln, :dob, :g, :ph);
UPDATE appointment SET status = 'COMPLETED' WHERE appointment_id = :id;
DELETE FROM appointment WHERE appointment_id = :id;   -- ORA-02292 if a bill/diagnosis references it
MERGE INTO ml_prediction mp USING (SELECT :appt AS appointment_id, :run AS run_id FROM dual) s
   ON (mp.appointment_id = s.appointment_id AND mp.run_id = s.run_id)
 WHEN MATCHED THEN UPDATE SET probability = :p
 WHEN NOT MATCHED THEN INSERT (appointment_id, run_id, prediction, probability) VALUES (:appt, :run, :pred, :p);""", False),
    C("constraints", "DDL & DML", "Integrity constraints (data dictionary)",
      "P = primary key, R = referential (foreign key), U = unique, C = check / not null. Read live from USER/ALL_CONSTRAINTS.",
      """SELECT constraint_type, COUNT(*) AS constraints
  FROM all_constraints WHERE owner = 'HCMS_ADMIN'
 GROUP BY constraint_type ORDER BY constraint_type"""),
    # ---------------- Joins ----------------
    C("inner_join", "Joins", "INNER JOIN (4 tables)",
      "Only rows with a match in every table. Today's appointments with patient, doctor and department.",
      """SELECT a.appointment_id, a.appt_time, p.first_name || ' ' || p.last_name AS patient,
       'Dr. ' || d.last_name AS doctor, dep.department_name, a.status
  FROM appointment a
  JOIN patient p      ON p.patient_id = a.patient_id
  JOIN doctor d       ON d.doctor_id = a.doctor_id
  JOIN department dep ON dep.department_id = d.department_id
 WHERE a.appt_date = TRUNC(SYSDATE)
 ORDER BY a.appt_time"""),
    C("left_join", "Joins", "LEFT OUTER JOIN",
      "Every patient, insured or not; unmatched insurance columns are NULL.",
      """SELECT p.patient_id, p.first_name || ' ' || p.last_name AS patient,
       NVL(ip.provider_name, '-- self pay --') AS insurer, ip.coverage_amount
  FROM patient p LEFT JOIN insurance_policy ip ON ip.patient_id = p.patient_id
 ORDER BY p.patient_id FETCH FIRST 20 ROWS ONLY"""),
    C("right_join", "Joins", "RIGHT OUTER JOIN",
      "Every bed (right table), with the patient currently in it if any.",
      """SELECT rb.room_no, rb.bed_no, rb.room_type, rb.status, p.first_name || ' ' || p.last_name AS current_patient
  FROM admission ad
  JOIN patient p ON p.patient_id = ad.patient_id AND ad.status = 'ADMITTED'
 RIGHT JOIN room_bed rb ON rb.room_bed_id = ad.room_bed_id
 ORDER BY rb.room_no, rb.bed_no"""),
    C("full_join", "Joins", "FULL OUTER JOIN",
      "Rows from both sides: medicines never prescribed in the last 30 days show 0.",
      """SELECT m.medicine_code, m.medicine_name, NVL(x.units, 0) AS units_last_30_days
  FROM medicine m
  FULL OUTER JOIN (SELECT pi.medicine_id, SUM(pi.quantity) AS units
                     FROM prescription_item pi JOIN prescription pr ON pr.prescription_id = pi.prescription_id
                    WHERE pr.prescribed_date >= TRUNC(SYSDATE) - 30 GROUP BY pi.medicine_id) x
    ON x.medicine_id = m.medicine_id
 ORDER BY units_last_30_days"""),
    C("self_join", "Joins", "SELF JOIN",
      "The DOCTOR table joined to itself: each department head and the colleagues in the same department.",
      """SELECT dep.department_name, 'Dr. ' || head.last_name AS head_of_department,
       'Dr. ' || c.first_name || ' ' || c.last_name AS colleague
  FROM department dep
  JOIN doctor head ON head.doctor_id = dep.head_doctor_id
  JOIN doctor c    ON c.department_id = head.department_id AND c.doctor_id != head.doctor_id
 ORDER BY dep.department_name"""),
    C("cross_join", "Joins", "CROSS JOIN (Cartesian product)",
      "Every combination of two sets: cardiologists x 3 weekdays (rows = 3 x n).",
      """SELECT d.last_name, w.weekday FROM doctor d
 CROSS JOIN (SELECT 'MON' weekday FROM dual UNION ALL SELECT 'TUE' FROM dual UNION ALL SELECT 'WED' FROM dual) w
 WHERE d.department_id = 2"""),
    C("anti_join", "Joins", "Anti-join (LEFT JOIN ... IS NULL)",
      "Patients who registered but never booked an appointment.",
      """SELECT p.patient_id, p.first_name, p.last_name, p.registered_date
  FROM patient p LEFT JOIN appointment a ON a.patient_id = p.patient_id
 WHERE a.appointment_id IS NULL"""),
    # ---------------- Sub-queries ----------------
    C("subquery_scalar", "Sub-queries", "Single-row sub-query",
      "Doctors whose fee is above the hospital average (inner query returns ONE value).",
      """SELECT first_name, last_name, specialization, consultation_fee FROM doctor
 WHERE consultation_fee > (SELECT AVG(consultation_fee) FROM doctor)
 ORDER BY consultation_fee DESC"""),
    C("subquery_in", "Sub-queries", "Multi-row sub-query (IN / NOT IN)",
      "Patients diagnosed with type-2 diabetes (ICD-10 E11.x).",
      """SELECT patient_id, first_name, last_name FROM patient
 WHERE patient_id IN (SELECT patient_id FROM diagnosis WHERE disease_code LIKE 'E11%')
 ORDER BY last_name"""),
    C("subquery_all", "Sub-queries", "ANY / ALL",
      "Doctors charging more than ALL pediatricians.",
      """SELECT last_name, specialization, consultation_fee FROM doctor
 WHERE consultation_fee > ALL (SELECT consultation_fee FROM doctor WHERE department_id = 4)"""),
    C("inline_view", "Sub-queries", "Inline view (sub-query in FROM)",
      "Top 5 diagnoses: aggregate inside, filter with ROWNUM outside.",
      """SELECT * FROM (SELECT ds.disease_name, dg.disease_code, COUNT(*) AS cases
                   FROM diagnosis dg JOIN disease ds ON ds.disease_code = dg.disease_code
                  GROUP BY ds.disease_name, dg.disease_code ORDER BY cases DESC)
 WHERE ROWNUM <= 5"""),
    C("cte", "Sub-queries", "WITH clause (CTE) + LAG",
      "Monthly collections and change vs the previous month.",
      """WITH monthly AS (SELECT TRUNC(paid_date, 'MM') AS month, SUM(amount_paid) AS collected
                   FROM payment GROUP BY TRUNC(paid_date, 'MM'))
SELECT TO_CHAR(month, 'YYYY-MM') AS month, collected,
       collected - LAG(collected) OVER (ORDER BY month) AS change_vs_last_month
  FROM monthly ORDER BY month"""),
    C("correlated", "Sub-queries", "Correlated sub-query",
      "The inner query references the OUTER row (d.department_id), so it is evaluated per doctor: "
      "doctors above the average fee of THEIR OWN department.",
      """SELECT d.first_name, d.last_name, d.department_id, d.consultation_fee
  FROM doctor d
 WHERE d.consultation_fee > (SELECT AVG(d2.consultation_fee) FROM doctor d2
                              WHERE d2.department_id = d.department_id)"""),
    C("exists", "Sub-queries", "EXISTS / NOT EXISTS (correlated)",
      "Patients with >= 5 completed visits who have NEVER missed one.",
      """SELECT p.patient_id, p.first_name, p.last_name FROM patient p
 WHERE NOT EXISTS (SELECT 1 FROM appointment a WHERE a.patient_id = p.patient_id AND a.status = 'NO_SHOW')
   AND (SELECT COUNT(*) FROM appointment a WHERE a.patient_id = p.patient_id AND a.status = 'COMPLETED') >= 5"""),
    # ---------------- Aggregation ----------------
    C("aggregates", "Aggregation", "Aggregate functions",
      "COUNT, SUM, AVG, MIN, MAX collapse many rows into one.",
      """SELECT COUNT(*) AS bill_items, SUM(amount) AS total_billed, ROUND(AVG(amount), 2) AS avg_item,
       MIN(amount) AS cheapest, MAX(amount) AS costliest FROM bill_item"""),
    C("group_by", "Aggregation", "GROUP BY + conditional aggregation",
      "Appointment outcomes per department.",
      """SELECT dep.department_name, COUNT(*) AS appointments,
       SUM(CASE WHEN a.status = 'COMPLETED' THEN 1 ELSE 0 END) AS completed,
       SUM(CASE WHEN a.status = 'NO_SHOW' THEN 1 ELSE 0 END) AS no_shows
  FROM appointment a JOIN doctor d ON d.doctor_id = a.doctor_id
  JOIN department dep ON dep.department_id = d.department_id
 GROUP BY dep.department_name ORDER BY appointments DESC"""),
    C("having", "Aggregation", "HAVING",
      "Filters GROUPS after aggregation (WHERE filters rows before). Diseases with more than 40 cases.",
      """SELECT ds.disease_name, COUNT(*) AS cases
  FROM diagnosis dg JOIN disease ds ON ds.disease_code = dg.disease_code
 GROUP BY ds.disease_name HAVING COUNT(*) > 40 ORDER BY cases DESC"""),
    C("rollup", "Aggregation", "ROLLUP / GROUPING",
      "Sub-totals per month and a grand total in one statement.",
      """SELECT CASE WHEN GROUPING(TRUNC(paid_date, 'MM')) = 1 THEN 'TOTAL' ELSE TO_CHAR(TRUNC(paid_date, 'MM'), 'YYYY-MM') END AS month,
       CASE WHEN GROUPING(payment_mode) = 1 THEN '(all)' ELSE payment_mode END AS mode, SUM(amount_paid) AS collected
  FROM payment WHERE paid_date >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -1)
 GROUP BY ROLLUP (TRUNC(paid_date, 'MM'), payment_mode)
 ORDER BY TRUNC(paid_date, 'MM') NULLS LAST, GROUPING(payment_mode)"""),
    C("window", "Aggregation", "Analytic / window functions",
      "DENSE_RANK() OVER (PARTITION BY ...) - busiest doctor of each department, without collapsing rows.",
      """SELECT * FROM (
  SELECT dep.department_name, d.last_name, COUNT(*) AS completed,
         DENSE_RANK() OVER (PARTITION BY dep.department_name ORDER BY COUNT(*) DESC) AS rnk
    FROM appointment a JOIN doctor d ON d.doctor_id = a.doctor_id
    JOIN department dep ON dep.department_id = d.department_id
   WHERE a.status = 'COMPLETED' GROUP BY dep.department_name, d.last_name)
 WHERE rnk = 1"""),
    C("pivot", "Aggregation", "PIVOT",
      "Rows to columns: patients per age band split by gender.",
      """SELECT * FROM (SELECT CASE WHEN MONTHS_BETWEEN(SYSDATE, dob)/12 < 18 THEN '0-17'
                            WHEN MONTHS_BETWEEN(SYSDATE, dob)/12 < 60 THEN '18-59' ELSE '60+' END AS band, gender FROM patient)
 PIVOT (COUNT(*) FOR gender IN ('M' AS male, 'F' AS female, 'O' AS other)) ORDER BY band"""),
    # ---------------- Set operations ----------------
    C("union", "Set operations", "UNION",
      "Everyone working in Emergency - doctors and nurses (duplicates removed).",
      """SELECT 'DOCTOR' AS staff_type, first_name, last_name FROM doctor WHERE department_id = 8
UNION
SELECT 'NURSE', first_name, last_name FROM nurse WHERE department_id = 8"""),
    C("intersect", "Set operations", "INTERSECT",
      "Patients who were BOTH admitted and seen in OPD.",
      """SELECT patient_id FROM admission INTERSECT SELECT patient_id FROM appointment WHERE status = 'COMPLETED'"""),
    C("minus", "Set operations", "MINUS",
      "Patients with an upcoming appointment but no insurance policy.",
      """SELECT patient_id FROM appointment WHERE status = 'SCHEDULED' AND appt_date > TRUNC(SYSDATE)
MINUS SELECT patient_id FROM insurance_policy"""),
    # ---------------- Views / indexes ----------------
    C("views", "Views & indexes", "Views",
      "Stored queries. vw_outstanding_bills is a view built on another view (vw_patient_billing_summary); "
      "vw_patient_directory restricts columns for lab/pharmacy/billing roles.",
      """SELECT * FROM vw_outstanding_bills ORDER BY days_outstanding DESC FETCH FIRST 15 ROWS ONLY"""),
    C("view_list", "Views & indexes", "All views in the schema",
      "Read from the data dictionary.",
      """SELECT view_name, text_length FROM all_views WHERE owner = 'HCMS_ADMIN' ORDER BY view_name"""),
    C("indexes", "Views & indexes", "Indexes (incl. function-based)",
      "B-tree indexes from the dictionary. IDX_PATIENT_UPPER_LNAME is function-based (UPPER(last_name)); "
      "UQ_ONE_ACTIVE_MODEL is a unique function-based index enforcing 'only one active ML model'. "
      "Use the Explain button on a query such as SELECT * FROM patient WHERE UPPER(last_name) LIKE 'PAT%'.",
      """SELECT i.index_name, i.table_name, i.uniqueness, i.index_type,
       LISTAGG(c.column_name, ', ') WITHIN GROUP (ORDER BY c.column_position) AS columns
  FROM all_indexes i JOIN all_ind_columns c ON c.index_owner = i.owner AND c.index_name = i.index_name
 WHERE i.owner = 'HCMS_ADMIN'
 GROUP BY i.index_name, i.table_name, i.uniqueness, i.index_type ORDER BY i.table_name, i.index_name"""),
    # ---------------- PL/SQL ----------------
    C("functions", "PL/SQL", "Stored functions in SQL",
      "calculate_age, fn_patient_no_show_rate and fn_bill_balance are PL/SQL functions callable inline.",
      """SELECT patient_id, first_name, calculate_age(dob) AS age, fn_patient_no_show_rate(patient_id) AS no_show_rate
  FROM patient WHERE ROWNUM <= 15"""),
    C("procedures", "PL/SQL", "Stored procedures",
      "book_appointment, admit_patient, transfer_bed, generate_bill, record_payment, update_patient, delete_patient, "
      "cancel_appointment, reschedule_appointment, add_prescription ... every one is a single transaction "
      "(COMMIT on success, ROLLBACK on error). Called from the UI through cursor.callproc().",
      """CREATE OR REPLACE PROCEDURE record_payment(p_bill_id IN NUMBER, p_amount IN NUMBER,
                                           p_mode IN VARCHAR2, p_payment_id OUT NUMBER) IS
    v_status bill.status%TYPE;
BEGIN
    SELECT status INTO v_status FROM bill WHERE bill_id = p_bill_id FOR UPDATE;   -- row lock
    IF p_amount > fn_bill_balance(p_bill_id) THEN
        RAISE_APPLICATION_ERROR(-20040, 'Payment exceeds outstanding balance');
    END IF;
    INSERT INTO payment (bill_id, amount_paid, payment_mode) VALUES (p_bill_id, p_amount, p_mode)
    RETURNING payment_id INTO p_payment_id;
    COMMIT;
EXCEPTION WHEN OTHERS THEN ROLLBACK; RAISE;
END;""", False),
    C("plsql_objects", "PL/SQL", "PL/SQL objects in the schema",
      "Procedures, functions, packages and triggers, read from the data dictionary.",
      """SELECT object_type, object_name, status FROM all_objects
 WHERE owner = 'HCMS_ADMIN' AND object_type IN ('PROCEDURE','FUNCTION','PACKAGE','TRIGGER')
 ORDER BY object_type, object_name"""),
    C("triggers", "PL/SQL", "Triggers",
      "trg_bill_status_update is a COMPOUND trigger (avoids ORA-04091 mutating table); trg_bed_status_update keeps "
      "bed status in sync; audit triggers write AUDIT_LOG with the real Oracle user; *_encounter_chk triggers keep "
      "redundant patient_id columns consistent.",
      """SELECT trigger_name, trigger_type, triggering_event, table_name, status
  FROM all_triggers WHERE owner = 'HCMS_ADMIN' ORDER BY table_name, trigger_name"""),
    C("cursors", "PL/SQL", "Cursors + FOR UPDATE SKIP LOCKED",
      "get_next_patient uses an explicit cursor with FOR UPDATE SKIP LOCKED: two nurses pressing 'call next' at the "
      "same moment never get the same patient. Try the isolation demo below.",
      """CURSOR c_next IS
  SELECT queue_id, patient_id FROM service_queue
   WHERE queue_type = p_queue_type AND status = 'WAITING' AND queue_date = TRUNC(SYSDATE)
   ORDER BY priority_level, arrival_time
   FOR UPDATE SKIP LOCKED;""", False),
    # ---------------- Transactions / security / design ----------------
    C("transactions", "Transactions & security", "Transactions & ACID",
      "Atomicity: book_appointment writes APPOINTMENT + SERVICE_QUEUE or nothing. Consistency: constraints + triggers. "
      "Isolation: READ COMMITTED + multiversion reads (no dirty reads). Durability: committed = in the redo log. "
      "Run the live demos below.",
      """SAVEPOINT sp_start;
INSERT INTO payment (bill_id, amount_paid, payment_mode) VALUES (:bill, 100, 'CASH');
SAVEPOINT sp_after_payment;
INSERT INTO payment (bill_id, amount_paid, payment_mode) VALUES (-1, 50, 'CASH');  -- ORA-02291
ROLLBACK TO sp_after_payment;   -- first payment still pending
ROLLBACK;                       -- undo everything""", False),
    C("security", "Transactions & security", "Roles & privileges",
      "8 Oracle users, 8 roles, least privilege, column-level UPDATE(status), view-based restriction, password "
      "profile. Run the RBAC matrix demo below to see Oracle refuse forbidden statements.",
      """SELECT grantee AS role, privilege, COUNT(*) AS objects
  FROM all_tab_privs WHERE table_schema = 'HCMS_ADMIN' AND grantee LIKE '%ROLE'
 GROUP BY grantee, privilege ORDER BY grantee, privilege"""),
    C("normalization", "Transactions & security", "Normalization (see Normalization page)",
      "Every table is in 3NF; most are in BCNF. v2 removed three violations: DIAGNOSIS.disease_name "
      "(disease_code -> disease_name, now table DISEASE), ML_PREDICTION.patient_id / model name+version "
      "(transitive via appointment / run), and the city hidden inside PATIENT.address (1NF). Controlled redundancy (patient_id in DIAGNOSIS, BILL, ...) "
      "is protected by consistency triggers. Full keys / FDs / decomposition on the Normalization page.",
      "-- structural property of the schema - see the Normalization page and docs/DBMS_Report.md", False),
]


@router.get("/dbms-lab/concepts")
def list_concepts():
    return {"concepts": CONCEPTS}


_SELECT_ONLY = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)
_FORBIDDEN = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|MERGE|EXEC|EXECUTE|CALL|BEGIN|DECLARE|LOCK)\b",
                        re.IGNORECASE)


def _clean(q):
    q = (q or "").strip().rstrip(";").strip()
    q = re.sub(r"--[^\n]*", "", q).strip()
    if not _SELECT_ONLY.match(q) or _FORBIDDEN.search(q):
        raise HTTPException(400, "Only a single SELECT (or WITH ... SELECT) statement is allowed in the sandbox. "
                                 "(Even if this check were bypassed, the readonly1 account has SELECT privileges only.)")
    if ";" in q:
        raise HTTPException(400, "Only one statement at a time.")
    return q


@router.post("/dbms-lab/execute")
def execute_readonly(query: str, conn=Depends(get_readonly_connection)):
    q = _clean(query)
    cur = conn.cursor()
    t0 = time.perf_counter()
    cur.execute(q)
    rows = cur.fetchmany(500)
    return {"sql_executed": q, "results": rows_to_dicts(cur, rows), "row_count": len(rows), "row_limit": 500,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1), "db_user": conn.username}


@router.post("/dbms-lab/explain")
def explain(query: str, conn=Depends(get_readonly_connection)):
    """EXPLAIN PLAN writes into the session's PLAN_TABLE (a global temporary
    table every user may use) - no application data is touched."""
    q = _clean(query)
    sid = f"lab{int(time.time() * 1000) % 10_000_000}"
    cur = conn.cursor()
    cur.execute(f"EXPLAIN PLAN SET STATEMENT_ID = '{sid}' FOR {q}")
    cur.execute("SELECT plan_table_output FROM TABLE(DBMS_XPLAN.DISPLAY('PLAN_TABLE', :sid, 'TYPICAL'))", sid=sid)
    plan = "\n".join(r[0] for r in cur.fetchall())
    conn.rollback()
    return {"sql_executed": f"EXPLAIN PLAN FOR {q};\nSELECT * FROM TABLE(DBMS_XPLAN.DISPLAY);", "plan": plan}


# --------------------------------------------------------------------------
# Live demos
# --------------------------------------------------------------------------
def _step(log, session, sql, fn):
    t0 = time.perf_counter()
    entry = {"step": len(log) + 1, "session": session, "sql": sql.strip()}
    try:
        entry["result"] = fn()
        entry["ok"] = True
    except oracledb.DatabaseError as e:
        entry["ok"] = False
        entry["error"] = str(e).splitlines()[0]
    entry["ms"] = round((time.perf_counter() - t0) * 1000, 1)
    log.append(entry)
    return entry


def _rows(cur, sql, **b):
    cur.execute(sql, **b)
    return [r[0] if len(r) == 1 else list(r) for r in cur.fetchall()]


def _scalar(cur, sql, **b):
    cur.execute(sql, **b)
    r = cur.fetchone()
    return r[0] if r and len(r) == 1 else (list(r) if r else None)


@router.post("/dbms-lab/demo/transaction")
def demo_transaction(conn=Depends(get_admin_connection), user: AppUser = Depends(require_roles("ADMIN"))):
    log = []
    cur = conn.cursor()
    bill = _scalar(cur, "SELECT MIN(bill_id) FROM bill WHERE status = 'UNPAID'")
    if bill is None:
        raise HTTPException(409, "No UNPAID bill to demonstrate with.")
    st = "SELECT status, fn_bill_balance(bill_id) AS balance FROM bill WHERE bill_id = :b"
    _step(log, "A", f"SELECT status, balance ... WHERE bill_id = {bill}", lambda: _scalar(cur, st, b=bill))
    _step(log, "A", "SAVEPOINT sp_start", lambda: cur.execute("SAVEPOINT sp_start") or "savepoint set")
    _step(log, "A", f"INSERT INTO payment (bill_id, amount_paid, payment_mode) VALUES ({bill}, 100, 'CASH')",
          lambda: cur.execute("INSERT INTO payment (bill_id, amount_paid, payment_mode) VALUES (:b, 100, 'CASH')", b=bill)
          or f"{cur.rowcount} row inserted")
    _step(log, "A", "-- compound trigger trg_bill_status_update already ran inside the transaction:\n" + st.replace(":b", str(bill)),
          lambda: _scalar(cur, st, b=bill))
    _step(log, "A", "SAVEPOINT sp_after_payment", lambda: cur.execute("SAVEPOINT sp_after_payment") or "savepoint set")
    _step(log, "A", "INSERT INTO payment (bill_id, amount_paid, payment_mode) VALUES (-1, 50, 'CASH')  -- bill -1 does not exist",
          lambda: cur.execute("INSERT INTO payment (bill_id, amount_paid, payment_mode) VALUES (-1, 50, 'CASH')") or "inserted")
    _step(log, "A", "-- statement-level atomicity: only the failed statement was undone\n"
                    f"SELECT COUNT(*) FROM payment WHERE bill_id = {bill}",
          lambda: _scalar(cur, "SELECT COUNT(*) FROM payment WHERE bill_id = :b", b=bill))
    _step(log, "A", "ROLLBACK TO sp_start", lambda: cur.execute("ROLLBACK TO sp_start") or "rolled back to savepoint")
    _step(log, "A", st.replace(":b", str(bill)), lambda: _scalar(cur, st, b=bill))
    _step(log, "A", "ROLLBACK", lambda: conn.rollback() or "transaction ended - database unchanged")
    return {"title": "SAVEPOINT / ROLLBACK TO / statement-level atomicity", "bill_id": bill, "steps": log}


@router.post("/dbms-lab/demo/atomic-procedure")
def demo_atomic_procedure(conn=Depends(get_admin_connection), user: AppUser = Depends(require_roles("ADMIN"))):
    """add_prescription inserts the header, then the item; the stock trigger
    rejects the item -> the procedure's ROLLBACK removes the header too."""
    log = []
    cur = conn.cursor()
    med = _scalar(cur, "SELECT medicine_id FROM medicine WHERE medicine_code = 'MED-046'") or 1
    cnt = "SELECT COUNT(*) FROM prescription"
    before = _step(log, "A", cnt, lambda: _scalar(cur, cnt))
    _step(log, "A", f"BEGIN add_prescription(1, 1, NULL, {med}, '10mg once daily', 5, 99999, :id); END;",
          lambda: (cur.callproc("add_prescription", [1, 1, None, med, "10mg once daily", 5, 99999, cur.var(int)]), "ok")[1])
    after = _step(log, "A", cnt, lambda: _scalar(cur, cnt))
    conn.rollback()
    return {"title": "Atomicity of a stored procedure (trigger rejects the 2nd INSERT)",
            "unchanged": before.get("result") == after.get("result"), "steps": log}


@router.post("/dbms-lab/demo/isolation")
def demo_isolation(conn=Depends(get_admin_connection), user: AppUser = Depends(require_roles("ADMIN"))):
    """Two real Oracle sessions (A = this request's connection, B = a second
    pooled admin1 connection)."""
    a, b = conn, connection_for("ADMIN")
    ca, cb = a.cursor(), b.cursor()
    log = []
    try:
        ids = _rows(ca, "SELECT medicine_id FROM medicine ORDER BY medicine_id FETCH FIRST 3 ROWS ONLY")
        m1 = ids[0]
        q = f"SELECT stock_quantity FROM medicine WHERE medicine_id = {m1}"
        _step(log, "A", q, lambda: _scalar(ca, q))
        _step(log, "A", f"UPDATE medicine SET stock_quantity = stock_quantity + 1000 WHERE medicine_id = {m1}  -- not committed",
              lambda: ca.execute("UPDATE medicine SET stock_quantity = stock_quantity + 1000 WHERE medicine_id = :m", m=m1)
              or f"{ca.rowcount} row updated (row now locked by A)")
        _step(log, "A", q + "   -- A sees its own change", lambda: _scalar(ca, q))
        _step(log, "B", q + "   -- B still sees the COMMITTED value: no dirty read", lambda: _scalar(cb, q))
        _step(log, "B", f"SELECT ... FROM medicine WHERE medicine_id = {m1} FOR UPDATE WAIT 2   -- row is locked by A",
              lambda: _rows(cb, "SELECT medicine_id FROM medicine WHERE medicine_id = :m FOR UPDATE WAIT 2", m=m1))
        _step(log, "B", f"SELECT medicine_id FROM medicine WHERE medicine_id IN {tuple(ids)} FOR UPDATE SKIP LOCKED",
              lambda: _rows(cb, f"SELECT medicine_id FROM medicine WHERE medicine_id IN ({','.join(map(str, ids))}) "
                                "FOR UPDATE SKIP LOCKED"))
        _step(log, "A", "ROLLBACK", lambda: a.rollback() or "A's change undone, lock released")
        _step(log, "B", "ROLLBACK", lambda: b.rollback() or "B's locks released")
        _step(log, "B", q + "   -- value unchanged", lambda: _scalar(cb, q))
    finally:
        try:
            a.rollback()
            b.rollback()
        finally:
            b.close()
    return {"title": "Isolation & locking with two concurrent sessions", "steps": log,
            "explanation": "Step 4: READ COMMITTED + multiversion read consistency -> B reads the old value. "
                           "Step 5: B cannot lock the row A is updating; WAIT 2 gives up with ORA-30006 instead of waiting forever. "
                           "Step 6: SKIP LOCKED returns only the rows nobody else holds - the queue's get_next_patient() "
                           "uses this so two nurses never call the same patient."}


_PROBES = [
    ("SELECT patient", "SELECT COUNT(*) FROM patient"),
    ("SELECT diagnosis", "SELECT COUNT(*) FROM diagnosis"),
    ("SELECT bill", "SELECT COUNT(*) FROM bill"),
    ("SELECT vw_patient_directory", "SELECT COUNT(*) FROM vw_patient_directory"),
    ("SELECT audit_log", "SELECT COUNT(*) FROM audit_log"),
    ("UPDATE appointment.status", "UPDATE appointment SET status = status WHERE 1 = 0"),
    ("UPDATE appointment.reason", "UPDATE appointment SET reason = reason WHERE 1 = 0"),
    ("DELETE patient", "DELETE FROM patient WHERE 1 = 0"),
    ("DELETE audit_log", "DELETE FROM audit_log WHERE 1 = 0"),
]


@router.post("/dbms-lab/demo/rbac")
def demo_rbac(user: AppUser = Depends(require_roles("ADMIN", "READONLY", "DOCTOR", "NURSE", "RECEPTIONIST",
                                                    "LAB", "PHARMACY", "BILLING"))):
    """Runs harmless probes (COUNT(*) or DML WHERE 1=0, then ROLLBACK) on
    EVERY role's own Oracle connection. Oracle checks privileges at parse
    time, so even a 0-row UPDATE is refused with ORA-01031 / ORA-00942."""
    matrix = []
    for role, (db_user, _pwd) in _ROLE_USERS.items():
        row = {"role": role, "db_user": db_user}
        try:
            c = connection_for(role)
        except Exception as e:  # pool unavailable
            row["error"] = str(getattr(e, "detail", e))
            matrix.append(row)
            continue
        try:
            cur = c.cursor()
            for label, sql in _PROBES:
                try:
                    cur.execute(sql)
                    row[label] = "ALLOWED"
                except oracledb.DatabaseError as e:
                    m = re.search(r"ORA-\d{5}", str(e))
                    row[label] = f"DENIED {m.group(0) if m else ''}".strip()
            c.rollback()
        finally:
            c.close()
        matrix.append(row)
    return {"probes": [p[0] for p in _PROBES], "probe_sql": dict(_PROBES), "matrix": matrix}
