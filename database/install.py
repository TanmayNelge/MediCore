#!/usr/bin/env python3
"""
MediCore HCMS - database installer (no SQL*Plus needed).

Runs the .sql files through python-oracledb, which parses statements itself,
so there are no SQL*Plus / Docker / PowerShell quoting problems.

Full install (drops and recreates the HCMS_ADMIN schema, ~1 minute):
    pip install oracledb
    python install.py --dsn localhost:1521/XEPDB1 --system-password <SYSTEM pwd>

Re-seed only (keep schema, users and grants; wipe + reload 04_sample_data.sql):
    python install.py --dsn localhost:1521/XEPDB1 --reseed
    (connects as hcms_admin; use --admin-password if you changed it)

Options:
    --admin-password   password of the hcms_admin schema owner (default HcmsAdmin_123)
    --with-bulk        also run 04b_bulk_data.sql (60 extra future appointments)
    --skip-security    skip creating the 8 app users / roles / grants
"""
import argparse
import os
import re
import sys
import time

import oracledb

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_FILES = ["03_sequences.sql", "01_schema.sql", "04_sample_data.sql",
                "05_views.sql", "06_indexes.sql", "07_functions.sql", "08_procedures.sql",
                "09_packages.sql", "10_triggers.sql", "14_bill_status_trigger.sql", "11_queue.sql"]
BULK_FILE = "04b_bulk_data.sql"
SEED_FILE = "04_sample_data.sql"
SECURITY_FILE = "12_security_roles.sql"
# user/role/profile already exists, or revoking something never granted
BENIGN = ("ORA-01927", "ORA-01920", "ORA-01921", "ORA-01918", "ORA-01919", "ORA-01952", "ORA-02379")

# child -> parent order for wiping data on --reseed
DELETE_ORDER = ["ml_prediction", "ml_model_run", "audit_log", "app_user", "service_queue", "payment",
                "bill_item", "bill", "insurance_policy", "lab_order", "prescription_item", "prescription",
                "clinical_note", "vital_sign", "diagnosis_symptom", "diagnosis", "disease", "admission", "appointment",
                "staff_schedule", "room_bed", "patient", "nurse", "lab_test_catalog", "medicine", "symptom"]
EXPECTED_TABLES = 28


def split_statements(text):
    """Split into (kind, sql). PL/SQL units end at a line with only '/';
    plain SQL ends at ';' at end of line. SQL*Plus-only commands are skipped."""
    out, buf, in_plsql = [], [], False
    for raw in text.splitlines():
        line = raw.rstrip()
        s = line.strip()
        if not buf:
            if not s or s.startswith("--"):
                continue
            up = s.upper()
            if up.startswith(("SET ", "PROMPT", "SPOOL", "EXIT", "@", "WHENEVER", "COMMIT;")):
                if up.startswith("COMMIT;"):
                    out.append(("sql", "COMMIT"))
                continue
            head = re.sub(r"\s+", " ", up)
            in_plsql = bool(re.match(r"(CREATE (OR REPLACE )?(EDITIONABLE )?(FUNCTION|PROCEDURE|PACKAGE|TRIGGER|TYPE)\b|DECLARE\b|BEGIN\b)", head))
        if not in_plsql:
            # drop a trailing "-- comment" so "stmt;   -- note" still ends at ';'
            line = re.sub(r"\s+--[^']*$", "", line)
            s = line.strip()
        if in_plsql:
            if s == "/":
                out.append(("plsql", "\n".join(buf).rstrip()))
                buf = []
                in_plsql = False
            else:
                buf.append(line)
        else:
            buf.append(line)
            if s.endswith(";"):
                stmt = "\n".join(buf).rstrip()
                out.append(("sql", stmt[:-1].rstrip()))
                buf = []
    if buf:
        out.append(("plsql" if in_plsql else "sql", "\n".join(buf).rstrip().rstrip(";")))
    return out


def ensure_seed_file():
    """04_sample_data.sql is GENERATED (and git-ignored). If it is missing,
    build it with generate_seed_data.py - deterministic, so every member of
    the team gets byte-identical data."""
    path = os.path.join(HERE, SEED_FILE)
    if not os.path.exists(path):
        import subprocess
        print(f"   {SEED_FILE} not found - generating it with generate_seed_data.py ...")
        subprocess.run([sys.executable, os.path.join(HERE, "generate_seed_data.py"), "--out", path], check=True)


def run_file(conn, path, ignore=()):
    name = os.path.basename(path)
    stmts = split_statements(open(path, encoding="utf-8").read())
    ok = bad = 0
    cur = conn.cursor()
    t0 = time.time()
    for kind, sql in stmts:
        try:
            cur.execute(sql)
            ok += 1
        except oracledb.DatabaseError as e:
            msg = str(e).strip()
            if any(code in msg for code in ignore):
                continue
            bad += 1
            first = sql.strip().splitlines()[0][:90]
            print(f"   ! {name}: {first}\n       {msg.splitlines()[0]}")
    conn.commit()
    print(f"   {name:<30} {ok:>6} ok, {bad} failed  ({time.time() - t0:.1f}s)")
    return bad


def report(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM user_tables")
    tables = cur.fetchone()[0]
    cur.execute("SELECT object_type, object_name FROM user_objects WHERE status = 'INVALID'")
    invalid = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM user_views")
    views = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM user_triggers")
    trg = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM user_objects WHERE object_type IN ('PROCEDURE','FUNCTION','PACKAGE')")
    plsql = cur.fetchone()[0]
    print(f"   tables={tables} (expect {EXPECTED_TABLES})  views={views}  triggers={trg}  "
          f"procedures/functions/packages={plsql}  invalid objects={len(invalid)} (expect 0)")
    for t, n in invalid:
        print(f"     INVALID {t} {n}  -> SELECT * FROM user_errors WHERE name = '{n}';")
    print("   row counts:")
    cur.execute("SELECT table_name FROM user_tables ORDER BY table_name")
    names = [r[0] for r in cur.fetchall()]
    line = []
    for n in names:
        cur.execute(f"SELECT COUNT(*) FROM {n}")
        line.append(f"{n.lower()}={cur.fetchone()[0]}")
    for i in range(0, len(line), 5):
        print("     " + "  ".join(line[i:i + 5]))


def reseed(a):
    print("Re-seeding data as HCMS_ADMIN (schema, users and grants are kept) ...")
    ensure_seed_file()
    conn = oracledb.connect(user="hcms_admin", password=a.admin_password, dsn=a.dsn)
    cur = conn.cursor()
    cur.execute("SELECT trigger_name FROM user_triggers")
    triggers = [r[0] for r in cur.fetchall()]
    for t in triggers:
        cur.execute(f"ALTER TRIGGER {t} DISABLE")
    cur.execute("UPDATE department SET head_doctor_id = NULL")
    for t in DELETE_ORDER + ["doctor", "department"]:
        cur.execute(f"DELETE FROM {t}")
    conn.commit()
    print(f"   wiped {len(DELETE_ORDER) + 2} tables, {len(triggers)} triggers disabled")
    failures = run_file(conn, os.path.join(HERE, SEED_FILE))
    for t in triggers:
        cur.execute(f"ALTER TRIGGER {t} ENABLE")
    print(f"   {len(triggers)} triggers re-enabled")
    report(conn)
    conn.close()
    print("\nDONE." if not failures else f"\nFinished with {failures} failed statement(s).")
    print("Next: retrain / re-score the ML model ->  .\\4_run_ml.ps1   (or: cd ml; python run_pipeline.py)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=os.environ.get("ORACLE_DSN", "localhost:1521/XEPDB1"))
    ap.add_argument("--system-password")
    ap.add_argument("--admin-password", default="HcmsAdmin_123")
    ap.add_argument("--with-bulk", action="store_true")
    ap.add_argument("--skip-security", action="store_true")
    ap.add_argument("--reseed", action="store_true", help="only wipe and reload the sample data")
    a = ap.parse_args()

    if a.reseed:
        return reseed(a)
    if not a.system_password:
        ap.error("--system-password is required for a full install (or use --reseed)")

    ensure_seed_file()
    print("1/3 Resetting schema owner HCMS_ADMIN as SYSTEM ...")
    sysc = oracledb.connect(user="system", password=a.system_password, dsn=a.dsn)
    c = sysc.cursor()
    try:
        c.execute("DROP USER hcms_admin CASCADE")
    except oracledb.DatabaseError as e:
        if "ORA-01918" not in str(e):
            raise
    c.execute(f'CREATE USER hcms_admin IDENTIFIED BY "{a.admin_password}"')
    c.execute("GRANT CONNECT, RESOURCE, CREATE VIEW, CREATE TRIGGER, CREATE PROCEDURE, "
              "CREATE SEQUENCE, UNLIMITED TABLESPACE TO hcms_admin")

    print("2/3 Building schema, loading data and compiling PL/SQL as HCMS_ADMIN ...")
    conn = oracledb.connect(user="hcms_admin", password=a.admin_password, dsn=a.dsn)
    failures = 0
    for f in SCHEMA_FILES:
        failures += run_file(conn, os.path.join(HERE, f))
    if a.with_bulk:
        failures += run_file(conn, os.path.join(HERE, BULK_FILE))
    # recompile anything that was created before a dependency existed
    conn.cursor().execute("BEGIN DBMS_UTILITY.COMPILE_SCHEMA(schema => 'HCMS_ADMIN', compile_all => FALSE); END;")
    report(conn)
    conn.close()

    if not a.skip_security:
        print("3/3 Creating app users, roles, profile and grants as SYSTEM ...")
        failures += run_file(sysc, os.path.join(HERE, SECURITY_FILE), ignore=BENIGN)
        for u in ["receptionist1", "doctor1", "labtech1", "pharmacist1", "billingclerk1", "admin1", "nurse1", "readonly1"]:
            try:
                sysc.cursor().execute(f'ALTER USER {u} IDENTIFIED BY "{u}" ACCOUNT UNLOCK')
            except oracledb.DatabaseError as e:
                print(f"   ! could not reset password of {u}: {str(e).splitlines()[0]}")
    sysc.close()
    print("\nDONE." if not failures else f"\nFinished with {failures} failed statement(s) - read the '!' lines above.")
    print("Next: .\\2_start_backend.ps1, .\\3_start_frontend.ps1, then .\\4_run_ml.ps1 to train/score the model.")


if __name__ == "__main__":
    sys.exit(main())
