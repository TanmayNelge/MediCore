# app/routers/schema.py
# Phase 14.2 / 14.3 -- live schema browser fetched from Oracle's data
# dictionary rather than hardcoded, so it never drifts from 01_schema.sql.
# Queries copied verbatim from database/schema_viewer_queries.sql.
#
# FIX: the original queries used USER_TAB_COLUMNS and USER_CONS_COLUMNS.
# Those views only show objects owned BY the connecting user (doctor1,
# receptionist1, etc.), which own nothing -- all tables live in
# HCMS_ADMIN. Even though current_schema is set to HCMS_ADMIN in
# session.py, the USER_ views are always scoped to the session's LOGIN
# user, not current_schema. Switch to ALL_TAB_COLUMNS / ALL_CONS_COLUMNS
# and filter by owner = 'HCMS_ADMIN' so the schema viewer actually shows
# the tables that exist.

from fastapi import APIRouter, Depends
from app.db.session import get_connection
from app.db.helpers import rows_to_dicts

router = APIRouter()

_OWNER = "HCMS_ADMIN"


@router.get("/schema/columns")
def schema_columns(conn=Depends(get_connection)):
    cursor = conn.cursor()
    sql = f"""SELECT atc.table_name, atc.column_name, atc.data_type, atc.nullable,
       (SELECT 'PK' FROM all_cons_columns ucc JOIN all_constraints uc
          ON uc.constraint_name = ucc.constraint_name
          AND uc.owner = '{_OWNER}'
        WHERE uc.constraint_type='P'
          AND ucc.table_name = atc.table_name
          AND ucc.column_name = atc.column_name
          AND ucc.owner = '{_OWNER}'
          AND ROWNUM=1) AS is_pk,
       (SELECT 'FK' FROM all_cons_columns ucc JOIN all_constraints uc
          ON uc.constraint_name = ucc.constraint_name
          AND uc.owner = '{_OWNER}'
        WHERE uc.constraint_type='R'
          AND ucc.table_name = atc.table_name
          AND ucc.column_name = atc.column_name
          AND ucc.owner = '{_OWNER}'
          AND ROWNUM=1) AS is_fk
    FROM all_tab_columns atc
    WHERE atc.owner = '{_OWNER}'
    ORDER BY atc.table_name, atc.column_id"""
    cursor.execute(sql)
    return {"sql_executed": sql, "results": rows_to_dicts(cursor, cursor.fetchall())}


@router.get("/schema/relationships")
def schema_relationships(conn=Depends(get_connection)):
    """Used to draw the FK arrows on the schema viewer automatically (Phase 14.3)."""
    cursor = conn.cursor()
    sql = f"""SELECT a.table_name AS child_table, a.column_name AS fk_column,
       c_pk.table_name AS parent_table
    FROM all_cons_columns a
    JOIN all_constraints c ON a.constraint_name = c.constraint_name AND c.owner = '{_OWNER}'
    JOIN all_constraints c_pk ON c.r_constraint_name = c_pk.constraint_name AND c_pk.owner = '{_OWNER}'
    WHERE c.constraint_type = 'R' AND a.owner = '{_OWNER}'"""
    cursor.execute(sql)
    return {"sql_executed": sql, "results": rows_to_dicts(cursor, cursor.fetchall())}


@router.get("/schema/objects")
def schema_objects(conn=Depends(get_connection)):
    """Views, indexes, triggers, PL/SQL units, sequences and constraint
    counts - all from Oracle's data dictionary (what YOUR role can see)."""
    from app.db.helpers import rows_to_dicts
    cur = conn.cursor()
    out = {}
    queries = {
        "views": "SELECT view_name AS name, text_length FROM all_views WHERE owner = :o ORDER BY view_name",
        "indexes": """SELECT i.index_name AS name, i.table_name, i.uniqueness, i.index_type,
                             LISTAGG(c.column_name, ', ') WITHIN GROUP (ORDER BY c.column_position) AS columns
                        FROM all_indexes i JOIN all_ind_columns c ON c.index_owner = i.owner AND c.index_name = i.index_name
                       WHERE i.owner = :o GROUP BY i.index_name, i.table_name, i.uniqueness, i.index_type
                       ORDER BY i.table_name, i.index_name""",
        "triggers": """SELECT trigger_name AS name, table_name, trigger_type, triggering_event, status
                         FROM all_triggers WHERE owner = :o ORDER BY table_name, trigger_name""",
        "plsql": """SELECT object_name AS name, object_type, status FROM all_objects
                     WHERE owner = :o AND object_type IN ('PROCEDURE','FUNCTION','PACKAGE') ORDER BY object_type, object_name""",
        "sequences": "SELECT sequence_name AS name, last_number FROM all_sequences WHERE sequence_owner = :o ORDER BY sequence_name",
        "constraints": """SELECT table_name, constraint_type, COUNT(*) AS n FROM all_constraints
                           WHERE owner = :o AND constraint_name NOT LIKE 'BIN$%' GROUP BY table_name, constraint_type
                           ORDER BY table_name, constraint_type""",
    }
    for key, sql in queries.items():
        cur.execute(sql, o=_OWNER)
        out[key] = rows_to_dicts(cur, cur.fetchall())
    return {"sql_executed": "\n\n".join(q.replace(":o", f"'{_OWNER}'") for q in queries.values()),
            "db_user": conn.username, **out}
