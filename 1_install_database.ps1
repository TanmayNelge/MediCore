# Step 1 - build the Oracle schema (works with your running Docker container, no sqlplus needed)
# Usage:  .\1_install_database.ps1 -SystemPassword Tejas04
param([Parameter(Mandatory=$true)][string]$SystemPassword)
python -m pip install oracledb
python database\install.py --dsn localhost:1521/XEPDB1 --system-password $SystemPassword
