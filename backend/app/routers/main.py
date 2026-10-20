# app/main.py
# FIX: added CORSMiddleware. Without it, the browser blocks every API
# request from the Vite dev server (localhost:5173) to the FastAPI server
# (localhost:8000) with a CORS preflight failure.  In production, tighten
# allow_origins to your actual domain.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import (
    auth, patients, appointments, admissions, clinical, pharmacy, lab,
    billing, queue, reports, dbms_lab, ml_insights, schema,
)

app = FastAPI(title="MediCore HCMS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return {"status": "ok"}
