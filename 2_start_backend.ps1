# Step 2 - start the API on http://127.0.0.1:8000   (leave this window open)
$env:ORACLE_DSN        = "localhost:1521/XEPDB1"
$env:JWT_SECRET        = "change-this-to-a-long-random-string"
$env:RECEPTIONIST1_PWD = "receptionist1"
$env:DOCTOR1_PWD       = "doctor1"
$env:LABTECH1_PWD      = "labtech1"
$env:PHARMACIST1_PWD   = "pharmacist1"
$env:BILLINGCLERK1_PWD = "billingclerk1"
$env:ADMIN1_PWD        = "admin1"
$env:NURSE1_PWD        = "nurse1"
$env:READONLY1_PWD     = "readonly1"
Set-Location backend
if (-not (Test-Path venv)) { python -m venv venv }
.\venv\Scripts\python -m pip install -r requirements.txt
.\venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
