#!/usr/bin/env python3
"""
MediCore HCMS - database installer (no SQL*Plus needed).

Runs the .sql files through python-oracledb, which parses statements itself,
so there are no SQL*Plus / Docker / PowerShell quoting problems.

Usage (from the database/ folder):
    pip install oracledb
    python install.py --dsn localhost:1521/XEPDB1 --system-password <SYSTEM pwd>

Optional:
    --admin-password   password for the hcms_admin schema owner (default HcmsAdmin_123)
    --skip-bulk        skip 04b_bulk_data.sql (200 random appointments)
    --skip-security    skip creating the 8 app users / roles
"""
import argparse, os, re, sys
import oracledb

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_FILES = ["03_sequences.sql", "01_schema.sql", "04_sample_data.sql",
                "04b_bulk_data.sql", "05_views.sql", "06_indexes.sql",
                "07_functions.sql", "08_procedures.sql", "09_packages.sql",
                "10_triggers.sql", "14_bill_status_trigger.sql", "11_queue.sql"]
SECURITY_FILE = "12_security_roles.sql"
BENIGN = ("ORA-01927", "ORA-01920", "ORA-01921", "ORA-01918", "ORA-01919", "ORA-01952")  # user/role exists / not found


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
            if up.startswith(("SET ", "PROMPT", "SPOOL", "EXIT", "@", "WHENEVER", "COMMIT;")) :
                if up.startswith("COMMIT;"):
                    out.append(("sql", "COMMIT"))
                continue
            head = re.sub(r"\s+", " ", up)
            in_plsql = bool(re.match(r"(CREATE (OR REPLACE )?(EDITIONABLE )?(FUNCTION|PROCEDURE|PACKAGE|TRIGGER|TYPE)\b|DECLARE\b|BEGIN\b)", head))
        if in_plsql:
            if s == "/":
                out.append(("plsql", "\n".join(buf).rstrip())); buf = []; in_plsql = False
            else:
                buf.append(line)
        else:
            buf.append(line)
            if s.endswith(";"):
                stmt = "\n".join(buf).rstrip()
                out.append(("sql", stmt[:-1].rstrip())); buf = []
    if buf:
        out.append(("plsql" if in_plsql else "sql", "\n".join(buf).rstrip().rstrip(";")))
    return out


def run_file(conn, path, ignore=()):
    name = os.path.basename(path)
    stmts = split_statements(open(path, encoding="utf-8").read())
    ok = bad = 0
    cur = conn.cursor()
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
    print(f"   {name}: {ok} ok, {bad} failed")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=os.environ.get("ORACLE_DSN", "localhost:1521/XEPDB1"))
    ap.add_argument("--system-password", required=True)
    ap.add_argument("--admin-password", default="HcmsAdmin_123")
    ap.add_argument("--skip-bulk", action="store_true")
    ap.add_argument("--skip-security", action="store_true")
    a = ap.parse_args()

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

    print("2/3 Building schema as HCMS_ADMIN ...")
    conn = oracledb.connect(user="hcms_admin", password=a.admin_password, dsn=a.dsn)
    failures = 0
    for f in SCHEMA_FILES:
        if a.skip_bulk and f.startswith("04b"):
            continue
        failures += run_file(conn, os.path.join(HERE, f))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM user_tables"); tables = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM user_objects WHERE status='INVALID'"); invalid = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM patient"); pats = cur.fetchone()[0]
    print(f"   tables={tables} (expect 26)  invalid objects={invalid} (expect 0)  patients={pats}")
    conn.close()

    if not a.skip_security:
        print("3/3 Creating app users, roles and grants as SYSTEM ...")
        failures += run_file(sysc, os.path.join(HERE, SECURITY_FILE), ignore=BENIGN)
        for u in ["receptionist1", "doctor1", "labtech1", "pharmacist1", "billingclerk1", "admin1", "nurse1", "readonly1"]:
            sysc.cursor().execute(f'ALTER USER {u} IDENTIFIED BY "{u}"')
    sysc.close()
    print("\nDONE." if not failures else f"\nFinished with {failures} failed statement(s) - read the '!' lines above.")


if __name__ == "__main__":
    main()
