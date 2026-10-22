# app/db/helpers.py
# Shared helpers so every router serialises results the same way and
# returns the same "transparency" metadata to the front end's SQL panel:
#   sql_executed  - the statement with bind values shown inline (display only;
#                   the database always receives bind variables, never this text)
#   results       - list of row dicts
#   row_count, elapsed_ms, db_user - which Oracle account actually ran it
import datetime as _dt
import decimal
import re
import time


def _jsonable(v):
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.isoformat(sep=" ") if isinstance(v, _dt.datetime) else v.isoformat()
    if hasattr(v, "read"):            # CLOB / LOB
        try:
            return v.read()
        except Exception:
            return str(v)
    return v


def rows_to_dicts(cursor, rows):
    cols = [c[0].lower() for c in cursor.description]
    return [{c: _jsonable(v) for c, v in zip(cols, r)} for r in rows]


def show_sql(sql, binds=None):
    """Render bind values into the SQL text FOR DISPLAY ONLY."""
    if not binds:
        return sql.strip()

    def lit(v):
        if v is None:
            return "NULL"
        if isinstance(v, (int, float, decimal.Decimal)):
            return str(v)
        if isinstance(v, (_dt.date, _dt.datetime)):
            return f"DATE '{v:%Y-%m-%d}'"
        return "'" + str(v).replace("'", "''") + "'"

    out = sql
    for k in sorted(binds, key=len, reverse=True):
        out = re.sub(rf":{re.escape(k)}\b", lambda _m, v=binds[k]: lit(v), out)
    return out.strip()


def query(conn, sql, binds=None, limit=None):
    """Execute a SELECT and return the standard response dict."""
    cur = conn.cursor()
    t0 = time.perf_counter()
    cur.execute(sql, binds or {})
    rows = cur.fetchmany(limit) if limit else cur.fetchall()
    return {
        "sql_executed": show_sql(sql, binds),
        "results": rows_to_dicts(cur, rows),
        "row_count": len(rows),
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
        "db_user": getattr(conn, "username", None),
    }


def execute(conn, sql, binds=None, commit=True):
    """Execute DML and return rows affected + metadata."""
    cur = conn.cursor()
    t0 = time.perf_counter()
    cur.execute(sql, binds or {})
    n = cur.rowcount
    if commit:
        conn.commit()
    return {"sql_executed": show_sql(sql, binds), "rows_affected": n,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1), "db_user": getattr(conn, "username", None)}


def call_proc(conn, name, args, out_types=(), shown_args=None):
    """Call a stored procedure. out_types: python types of trailing OUT params.
    Returns (out_values, meta)."""
    cur = conn.cursor()
    outs = [cur.var(t) for t in out_types]
    t0 = time.perf_counter()
    cur.callproc(name, list(args) + outs)
    vals = []
    for o in outs:
        v = o.getvalue()
        vals.append(v[0] if isinstance(v, list) else v)
    shown = ", ".join(shown_args if shown_args is not None else
                      [("NULL" if a is None else (f"'{a}'" if isinstance(a, str) else str(a))) for a in args]
                      + [":out"] * len(outs))
    return vals, {"sql_executed": f"BEGIN {name}({shown}); END;",
                  "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
                  "db_user": getattr(conn, "username", None)}
