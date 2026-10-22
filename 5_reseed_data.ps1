# Step 5 (optional) - wipe and reload ONLY the sample data (schema, users and grants are kept).
# Use it when the demo data got messy, or a few weeks after installing so "today" is fresh again.
#   .\5_reseed_data.ps1
#   .\5_reseed_data.ps1 -AdminPassword MyOtherPwd
param([string]$AdminPassword = "HcmsAdmin_123")
python -m pip install -q oracledb
python database\install.py --dsn localhost:1521/XEPDB1 --reseed --admin-password $AdminPassword
Write-Host "Now re-score the ML model:  .\4_run_ml.ps1"
