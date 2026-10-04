# Start the clinic application (single port :8000, API + UI).
# Usage: bash scripts/start.sh   (or scripts\start.bat on Windows)
set -e
cd "$(dirname "$0")/.."

echo "[clinic] Starting server on http://127.0.0.1:8000 ..."
echo "[clinic] Data lives in ./data (database, backups, attachments)."
echo "[clinic] Keep this window open during clinic hours. Stop with Ctrl+C."

PY="${CLINIC_PYTHON:-.venv/Scripts/python}"
if [ ! -f "$PY" ]; then PY=python3; fi

cd backend
exec "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
