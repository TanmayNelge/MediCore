# app/db/session.py
# Dependency that yields a connection scoped to the caller's DB role.
# The database itself — not just application code — refuses e.g. a
# receptionist's connection permission to SELECT * FROM diagnosis,
# satisfying "the database and backend enforce this" from the brief.
#
# FIX (session): oracledb.connect() does NOT accept a pool= keyword arg.
# Connections from a pool must be acquired via pool.acquire(), not via
# oracledb.connect(..., pool=pool).  The old code was silently ignoring
# the pool argument and opening a plain non-pooled connection on every
# request, defeating the purpose of the pool and exhausting OS sockets
# under any real load.  Replaced with pool.acquire() throughout.
#
# FIX (schema): role-mapped users (doctor1, receptionist1, ...) own no
# tables of their own -- every object lives in HCMS_ADMIN. Oracle resolves
# an UNQUALIFIED table name ("FROM patient") against the CONNECTING user's
# own schema first, not the schema that granted the privilege. Without
# setting current_schema, every query in the routers (all written as
# bare "FROM patient" etc., matching the blueprint's SQL) fails with
# ORA-00942 even though the GRANT is completely correct. Setting
# current_schema after acquire fixes this for every router at once,
# with no changes needed to the SQL text itself.

import oracledb
from fastapi import Depends

from app.auth.jwt import get_current_app_user
from app.auth import role_mapping
from app.db.pool import POOLS, _ROLE_USERS


async def get_connection(user=Depends(get_current_app_user)):
    db_user, _db_password = role_mapping.resolve(user.role)   # e.g. DOCTOR -> doctor1
    pool = POOLS.get(user.role)
    if pool is None:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No database pool for role '{user.role}' — check env vars.",
        )
    conn = pool.acquire()
    conn.current_schema = "HCMS_ADMIN"   # <-- unqualified names now resolve here
    try:
        yield conn
    finally:
        conn.close()   # returns connection to pool


async def get_readonly_connection(user=Depends(get_current_app_user)):
    """Always connects as readonly1 (READONLY_ROLE: SELECT-only on every
    table/view), regardless of the caller's own app role. Used exclusively
    by /dbms-lab/execute (Phase 13.4) so that endpoint's protection is a
    real DB-enforced grant set, not just the app-level regex filter --
    any authenticated app user can reach the sandbox, but the DB
    connection backing it can never INSERT/UPDATE/DELETE/DDL no matter
    what slips past the regex.
    """
    pool = POOLS.get("READONLY")
    if pool is None:
        pool = POOLS.get(user.role)
    if pool is None:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection pool unavailable — check Oracle connection.",
        )
    conn = pool.acquire()
    conn.current_schema = "HCMS_ADMIN"
    try:
        yield conn
    finally:
        conn.close()
