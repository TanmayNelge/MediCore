# app/db/session.py
# Dependencies that yield a pooled connection scoped to a DB role.
# The database itself - not just application code - refuses e.g. a
# receptionist's connection permission to SELECT * FROM diagnosis.
#
# current_schema = HCMS_ADMIN is set on every checkout: role users own no
# tables, and Oracle resolves unqualified names ("FROM patient") in the
# LOGIN user's schema unless current_schema says otherwise.

from fastapi import Depends, HTTPException, status

from app.auth.jwt import get_current_app_user
from app.db.pool import POOLS


def _acquire(role):
    pool = POOLS.get(role)
    if pool is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail=f"No database pool for role '{role}' - is Oracle running and the schema installed?")
    conn = pool.acquire()
    conn.current_schema = "HCMS_ADMIN"
    return conn


def connection_for(role):
    """Context-free helper (used by demos that need several roles at once)."""
    return _acquire(role)


async def get_connection(user=Depends(get_current_app_user)):
    conn = _acquire(user.role)
    try:
        yield conn
    finally:
        try:
            conn.rollback()      # never leave an open transaction in the pool
        except Exception:
            pass
        conn.close()             # returns the connection to the pool


async def get_readonly_connection(user=Depends(get_current_app_user)):
    """Always readonly1 (READONLY_ROLE: SELECT-only), whatever the caller's
    role. Backs Reports, Dashboard, ML insights and the SQL sandbox, so even
    a query that slipped past validation physically cannot change data."""
    conn = _acquire("READONLY")
    try:
        yield conn
    finally:
        conn.close()


async def get_admin_connection(user=Depends(get_current_app_user)):
    """admin1 connection - only for admin-only actions (retrain model,
    transaction demos). Callers must also use require_roles('ADMIN')."""
    conn = _acquire("ADMIN")
    try:
        yield conn
    finally:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
