# app/routers/auth.py
# /auth/login - the database IS the identity store: credentials are the
# Oracle user/password of one of the role accounts created in
# 12_security_roles.sql. We verify by actually opening an Oracle
# connection with what was submitted; if Oracle accepts it, the person is
# who they say they are. We then map the DB user to an application role
# and issue a JWT (with expiry) so later requests reuse the role's pool.
#
# v2 SECURITY FIX: the previous version accepted ANY login whose password
# equalled the username WITHOUT asking Oracle ("Simple login" shortcut).
# That bypassed the database's own authentication, the password profile
# (lock-out after failed attempts) and would keep working even after a
# DBA changed a password. Every login is now checked by Oracle.

import oracledb
from fastapi import APIRouter, HTTPException, Request, status

from app.auth import role_mapping
from app.auth.jwt import issue_token
from app.db.pool import DSN

router = APIRouter()

ALIASES = {
    "admin": "admin1", "doctor": "doctor1", "nurse": "nurse1", "receptionist": "receptionist1",
    "lab": "labtech1", "labtech": "labtech1", "pharmacist": "pharmacist1", "pharmacy": "pharmacist1",
    "billing": "billingclerk1", "billingclerk": "billingclerk1", "readonly": "readonly1",
}


async def _read_credentials(request: Request):
    ctype = request.headers.get("content-type", "").lower()
    data = {}
    try:
        if "form" in ctype:
            data = dict(await request.form())
        else:
            data = await request.json()
    except Exception:
        try:
            data = dict(await request.form())
        except Exception:
            data = {}
    if not isinstance(data, dict):
        data = {}
    return data.get("username"), data.get("password")


@router.post("/auth/login")
async def login(request: Request):
    username, password = await _read_credentials(request)
    if not username or not password:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing username or password")
    canonical_user = ALIASES.get(str(username).strip().lower(), str(username).strip().lower())

    try:
        role = role_mapping.reverse_resolve(canonical_user)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"'{canonical_user}' is not an application account.")

    try:
        test_conn = oracledb.connect(user=canonical_user, password=str(password), dsn=DSN)
        test_conn.close()
    except oracledb.DatabaseError as e:
        msg = str(e)
        if "ORA-28000" in msg:
            detail = "Account is locked after too many failed attempts (password profile). Try again in 15 minutes or ask the DBA: ALTER USER ... ACCOUNT UNLOCK."
        elif "ORA-01017" in msg:
            detail = "Incorrect username or password. (Demo accounts: password = username, e.g. doctor1 / doctor1.)"
        else:
            detail = f"Database not reachable: {msg.splitlines()[0]}"
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)

    return {"access_token": issue_token(canonical_user, role), "token_type": "bearer",
            "role": role, "username": canonical_user}
