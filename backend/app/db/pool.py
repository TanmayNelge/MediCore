# app/db/pool.py
# oracledb connection pool, one pool per DB role — as referenced in the
# project's backend structure (Phase 12.1). Fill in DSN for your Oracle
# XE instance (e.g. "localhost/XEPDB1").

import os
import logging
import oracledb

logger = logging.getLogger("uvicorn.error")

def _load_env():
    candidates = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")),
    ]
    for env_path in candidates:
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip('"').strip("'")
                            if k:
                                os.environ[k] = v
            except Exception:
                pass

_load_env()

DSN = os.environ.get("ORACLE_DSN", "localhost:1521/XEPDB1")

# Passwords come from .env / environment; default to username for simplicity
_ROLE_USERS = {
    "ADMIN":        ("admin1", os.environ.get("ADMIN1_PWD", "admin1")),
    "DOCTOR":       ("doctor1", os.environ.get("DOCTOR1_PWD", "doctor1")),
    "NURSE":        ("nurse1", os.environ.get("NURSE1_PWD", "nurse1")),
    "RECEPTIONIST": ("receptionist1", os.environ.get("RECEPTIONIST1_PWD", "receptionist1")),
    "LAB":          ("labtech1", os.environ.get("LABTECH1_PWD", "labtech1")),
    "PHARMACY":     ("pharmacist1", os.environ.get("PHARMACIST1_PWD", "pharmacist1")),
    "BILLING":      ("billingclerk1", os.environ.get("BILLINGCLERK1_PWD", "billingclerk1")),
    "READONLY":     ("readonly1", os.environ.get("READONLY1_PWD", "readonly1")),
}

_POOLS = {}

def get_pool(role: str):
    if role in _POOLS:
        return _POOLS[role]
    if role not in _ROLE_USERS:
        return None
    user, pwd = _ROLE_USERS[role]
    if not pwd:
        return None
    try:
        pool = oracledb.create_pool(user=user, password=pwd, dsn=DSN, min=1, max=5, increment=1)
        _POOLS[role] = pool
        return pool
    except Exception as e:
        logger.warning(f"Could not initialize connection pool for role '{role}': {e}")
        return None

class _PoolDict(dict):
    def get(self, key, default=None):
        pool = get_pool(key)
        return pool if pool is not None else default

    def __getitem__(self, key):
        pool = get_pool(key)
        if pool is None:
            raise KeyError(key)
        return pool

    def __contains__(self, key):
        return key in _ROLE_USERS

POOLS = _PoolDict()

