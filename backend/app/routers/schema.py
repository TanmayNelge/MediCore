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
