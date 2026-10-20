# app/auth/jwt.py
# Issues/validates short-lived JWTs mapped to a DB role at each pooled
# connection checkout, so a compromised app session cannot silently
# escalate DB privileges beyond its mapped role (Phase 11.5).

from dataclasses import dataclass
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt as pyjwt
import os

SECRET_KEY = os.environ.get("JWT_SECRET", "change-me")
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


@dataclass
class AppUser:
    username: str
    role: str  # ADMIN, DOCTOR, NURSE, RECEPTIONIST, LAB, PHARMACY, BILLING


def get_current_app_user(token: str = Depends(oauth2_scheme)) -> AppUser:
    try:
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return AppUser(username=payload["sub"], role=payload["role"])
    except pyjwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
