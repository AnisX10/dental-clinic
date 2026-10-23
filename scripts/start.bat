@echo off
rem Start the clinic application (single port :8000, API + UI).
cd /d "%~dp0.."

echo [clinic] Starting server on http://127.0.0.1:8000 ...
echo [clinic] Data lives in the data folder (database, backups, attachments).
echo [clinic] Close this window to stop. Keep it running during clinic hours.

set PY=%cd%\.venv\Scripts\python.exe
if not exist "%PY%" set PY=python

"%PY%" -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
if /i "%1" neq "--no-pause" if /i "%1" neq "/nopause" pause
