# app/main.py
# FastAPI entry point.
# v2: a global handler turns Oracle errors into readable HTTP responses.
# Before, any ORA- error (constraint violation, missing grant, trigger
# RAISE_APPLICATION_ERROR) surfaced as a bare "500 Internal Server Error",
# so the front end could never show WHY the database refused something -
# which is exactly what a DBMS demo needs to show.

import re

import oracledb
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import (
    auth, patients, appointments, admissions, clinical, pharmacy, lab,
    billing, queue, reports, dbms_lab, ml_insights, schema,
)

app = FastAPI(title="MediCore HCMS API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_FRIENDLY = {
    "ORA-00001": "Duplicate value - a UNIQUE / PRIMARY KEY constraint was violated",
    "ORA-02291": "Referenced record does not exist (FOREIGN KEY - parent key not found)",
    "ORA-02292": "Record is still referenced by other rows (FOREIGN KEY - child record found)",
    "ORA-02290": "A CHECK constraint was violated",
    "ORA-01400": "A mandatory (NOT NULL) value is missing",
    "ORA-00942": "Your database role has no privilege on this table/view",
    "ORA-01031": "Your database role has insufficient privileges for this operation",
    "ORA-06550": "PL/SQL call failed (procedure missing or no EXECUTE privilege)",
    "ORA-00054": "Row is locked by another session (NOWAIT)",
    "ORA-12899": "Value too large for the column",
    "ORA-01843": "Invalid date",
}


@app.exception_handler(oracledb.DatabaseError)
async def oracle_error_handler(request: Request, exc: oracledb.DatabaseError):
    raw = str(exc).strip()
    first = raw.splitlines()[0] if raw else "Database error"
    m = re.search(r"ORA-(\d{5})", first)
    code = f"ORA-{m.group(1)}" if m else None
    # business-rule errors raised by our PL/SQL: ORA-20000 .. ORA-20999
    if m and 20000 <= int(m.group(1)) <= 20999:
        msg = re.sub(r"^ORA-\d{5}:\s*", "", first)
        return JSONResponse(status_code=400, content={"detail": msg, "oracle_code": code})
    status = 403 if code in ("ORA-00942", "ORA-01031", "ORA-06550", "ORA-01924") else 400
    hint = _FRIENDLY.get(code)
    detail = f"{hint}: {first}" if hint else first
    return JSONResponse(status_code=status, content={"detail": detail, "oracle_code": code})


app.include_router(auth.router, tags=["auth"])
app.include_router(patients.router, tags=["patients"])
app.include_router(appointments.router, tags=["appointments"])
app.include_router(admissions.router, tags=["admissions"])
app.include_router(clinical.router, tags=["clinical"])
app.include_router(pharmacy.router, tags=["pharmacy"])
app.include_router(lab.router, tags=["lab"])
app.include_router(billing.router, tags=["billing"])
app.include_router(queue.router, tags=["queue"])
app.include_router(reports.router, tags=["reports"])
app.include_router(dbms_lab.router, tags=["dbms-lab"])
app.include_router(ml_insights.router, tags=["ml-insights"])
app.include_router(schema.router, tags=["schema"])


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0"}
