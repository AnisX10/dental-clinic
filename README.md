# Local Dental Clinic Management System (V1)

Minimal, local-first clinic management for a small dental practice in Algeria,
built from the spec in [`dental-clinic-spec/`](dental-clinic-spec/README.md).

- **Single-port deployment** — FastAPI serves both the API (`/api/*`) and the
  built Nuxt SPA on `http://127.0.0.1:8000`.
- **Bundled PostgreSQL 16** (pgserver — no installation, no admin rights);
  data lives in `data/pgdata`.
- **French default UI, Arabic (RTL) available** — fully offline, fonts bundled.
- **Cash-only payments** in DZD with per-patient ledger (Total / Payé / Reste).
- **Odontogramme** — anatomical chart inside the patient file with permanent and
  deciduous teeth: whole-tooth conditions (à traiter, couronne, bridge, absent)
  and per-surface carie/obturation marks.
- **Laboratoire** — work orders (envoyé → en fabrication → prêt → reçu, with
  cancellation) and supplier invoices with partial payments per lab.
- **Stock & matériaux** — append-only movement ledger (race-safe, never
  negative), inventory corrections, low-stock alerts, stock valuation, and
  consumables linked to catalogue treatments so stock is deducted
  automatically when a treatment is recorded.
- **Automatic daily backups** via `pg_dump` + manual one-click backup.

## Layout

```
backend/    FastAPI app (app/), Alembic migrations, pytest suite
frontend/   Nuxt 4 SPA (source + build in .output/public — see DEPLOY.md §5)
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

91 tests cover auth, patients, agenda transitions, clinical modules (including
odontogram conditions and surface marks), the concurrency-safe payments
ledger, documents, backups, lab orders/invoices, sterilization cycles,
DSP/CNAS and devis, and the stock ledger (including treatment
auto-deduction). Tests run against a separate disposable PostgreSQL instance
(`data/pgdata-test`).

## Security notes

- Argon2id password hashing; session tokens stored hashed (httpOnly cookie).
- Login rate-limited (8 attempts / 5 min / user+IP).
- Owner-only: settings, catalogue prices, manual backup, stock↔treatment links.
- All mutations audited in `audit_log` (actor, action, IP).
- No external services: no CDN fonts, no telemetry, no AI, no cloud.
