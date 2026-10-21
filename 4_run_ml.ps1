# Step 4 - train the no-show model and score upcoming appointments (run after the DB is built)
$env:ORACLE_DSN = "localhost:1521/XEPDB1"
$env:ADMIN1_PWD = "admin1"

$venvPython = Join-Path $PSScriptRoot "backend\venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

Set-Location (Join-Path $PSScriptRoot "ml")
& $python run_pipeline.py $args

