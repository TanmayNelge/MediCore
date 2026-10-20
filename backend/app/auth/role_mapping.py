# app/auth/role_mapping.py
# Maps an authenticated application role (from the JWT) to the Oracle
# DB user that should be used for that session's connection, and back.

from app.db.pool import _ROLE_USERS


def resolve(app_role: str):
    """Return (db_user, db_password) for a given application role, e.g.
    resolve('DOCTOR') -> ('doctor1', '<password>')."""
    try:
        return _ROLE_USERS[app_role.upper()]
    except KeyError:
        raise ValueError(f"No DB user mapped for role '{app_role}'")


def reverse_resolve(db_username: str):
    """Return the application role for a given DB username, e.g.
    reverse_resolve('doctor1') -> 'DOCTOR'. Used by /auth/login, where the
    person logs in with the DB username itself (the DB *is* the identity
    store here -- see auth/jwt.py header comment)."""
    db_username = db_username.lower()
    for role, (user, _pwd) in _ROLE_USERS.items():
        if user.lower() == db_username:
            return role
    raise ValueError(f"'{db_username}' is not a recognized application DB user")
