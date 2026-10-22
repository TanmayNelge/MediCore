# app/auth/jwt.py
# Issues/validates short-lived JWTs mapped to a DB role at each pooled
# connection checkout, so a compromised app session cannot silently
# escalate DB privileges beyond its mapped role.
#
# v2: tokens now carry an expiry (exp, 8 hours) - AuthContext.jsx already
# checked `exp` but the backend never set it, so tokens lived forever.
# require_roles() gives endpoints an app-level role check IN ADDITION to
# the database grants (defence in depth).

import datetime as dt
import os
from dataclasses import dataclass

import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.db import pool as _pool  # noqa: F401  (importing it loads .env before JWT_SECRET is read)

SECRET_KEY = os.environ.get("JWT_SECRET", "change-me")
ALGORITHM = "HS256"
TOKEN_HOURS = 8

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


@dataclass
class AppUser:
    username: str
    role: str  # ADMIN, DOCTOR, NURSE, RECEPTIONIST, LAB, PHARMACY, BILLING, READONLY


def issue_token(username: str, role: str) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    return pyjwt.encode({"sub": username, "role": role, "iat": now,
                         "exp": now + dt.timedelta(hours=TOKEN_HOURS)}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_app_user(token: str = Depends(oauth2_scheme)) -> AppUser:
    try:
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return AppUser(username=payload["sub"], role=payload["role"])
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired - please log in again")
    except pyjwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")


def require_roles(*roles):
    """FastAPI dependency: allow only the given application roles."""
    allowed = {r.upper() for r in roles}

    def checker(user: AppUser = Depends(get_current_app_user)) -> AppUser:
        if user.role.upper() not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"Role {user.role} may not perform this action (allowed: {', '.join(sorted(allowed))}).")
        return user
    return checker
