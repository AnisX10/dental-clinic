# Local Dental Clinic Management System (V1)

Minimal, local-first clinic management for a small dental practice in Algeria,
built from the spec in [`dental-clinic-spec/`](dental-clinic-spec/README.md).

- **Single-port deployment** — FastAPI serves both the API (`/api/*`) and the
  built Nuxt SPA on `http://127.0.0.1:8000`.
- **Bundled PostgreSQL 16** — no installation, no admin rights; data lives in
  `data/pgdata`.
- **French default UI, Arabic (RTL) available** — fully offline, fonts bundled.
- **Cash-only payments** in DZD with per-patient ledger (Total / Payé / Reste).
- **Automatic daily backups** via `pg_dump` + manual one-click backup.

## Layout

```
backend/    FastAPI app (app/), Alembic migrations, pytest suite
frontend/   Nuxt 4 SPA (source + ready-made build in .output/public)
data/       pgdata, backups, attachments (created at runtime)
scripts/    start.bat / start.sh
```

## Quick start

See [DEPLOY.md](DEPLOY.md). Short version:

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements.txt
.venv\Scripts\python backend\app\cli.py create-user --username dentiste --role dentiste --owner --full-name "Dr Nom"
scripts\start.bat
```

Development mode (hot reload frontend + API proxy):

```bat
:: terminal 1
cd backend && ..\.venv\Scripts\python -m uvicorn app.main:app --port 8000
:: terminal 2
cd frontend && npm run dev
```

## Tests

```bat
cd backend
..\.venv\Scripts\python -m pytest tests\ -q
..\.venv\Scripts\python -m ruff check .
```

49 tests cover auth, patients, agenda transitions, clinical modules, the
concurrency-safe payments ledger, documents, and backups. Tests run against a
separate disposable PostgreSQL instance (`data/pgdata-test`).

## Security notes

- Argon2id password hashing; session tokens stored hashed (httpOnly cookie).
- Login rate-limited (8 attempts / 5 min / user+IP).
- Owner-only: settings, catalogue prices, manual backup.
- All mutations audited in `audit_log` (actor, action, IP).
- No external services: no CDN fonts, no telemetry, no AI, no cloud.
