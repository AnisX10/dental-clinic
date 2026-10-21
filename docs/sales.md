# Sales runbook — selling the clinic application

Workflow for the seller (one machine), from empty PC to an unlocked clinic.
Complements `DEPLOY.md` (technical installation).

## 0. One-time seller setup

```bat
.venv\Scripts\python tools\license.py keygen
```

- Creates `tools\license\private.pem` (NEVER commit, NEVER share) and
  `backend\app\licensing\public_key.pem` (committed, embedded in the app).
- Losing the private key = no new licenses can be issued; keep a copy on a
  personal USB/backup.

## 1. Per-client sale steps

1. Install the application at the clinic (DEPLOY.md sections 1–2):
   venv + requirements, frontend build, PostgreSQL data folder.
2. `cli.py init-prod` — schema, catalog, first owner account, security audit.
3. Start the app once; read the **Installation ID** (licence screen or log).
4. Issue the licence:

   ```bat
   .venv\Scripts\python tools\license.py issue --clinic "Clinique X" --dentist "Dr Y" --installation <id>
   ```

5. Deliver the `.lic`: copy to `data\` (restart) or give the file to the
   clinic to upload from the licence screen.
6. Create staff accounts (`cli.py create-user`), owner flag only for the
   dentist. Complete DEPLOY.md section 7 checklist with the client.

## 2. Pricing / contract basics (perpetual model)

- One purchase per installation (per database). Moving to a new server PC
  = new Installation ID = new licence file (free of charge for the same
  clinic: re-issue with the new ID).
- Updates: seller-supplied app updates use `cli.py upgrade` at the clinic;
  licence survives (it lives in `data\` and binds to the database).

## 3. Known open risk (blocker for scale)

`STRATEGY.md` section 3: the DentalPin upstream is source-available under its
own terms. **Before selling to multiple clinics, a formal upstream licence
review is required.** Until then, sales should remain limited to the
initial target (private deployment for a single clinic). The upstream repo
location must be identified and pinned (no local checkout exists today).
