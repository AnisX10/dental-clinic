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

## 3. Upstream licence review (recorded 2026-10-21)

**Upstream identified and pinned for review:** https://github.com/dentalpin/dentalpin
(read-only shallow clone at `reference/dentalpin/`, git-ignored; re-clone and
re-check at every major release until the Change Date).

**Terms read from the pinned `LICENSE`:**
- Licensor: Dentared Odontology Services S.L. (`(c)` 2026).
- Business Source License 1.1 → converts to Apache-2.0 at the Change Date
  (4 years from publication, ≈ 2030).
- **Additional Use Grant:** production use is *allowed*, provided it is not
  "a commercial Software-as-a-Service (SaaS) offering for dental clinic
  management where the primary value is substantially derived from the
  Licensed Work".

**Verdict:**
- ✅ **Single-clinic private local deployment (current target) — permitted.**
  It is plain production use on the clinic's own PC; not a SaaS.
- ⚠️ **Multi-clinic perpetual-licence sales (runbook §2) — permitted in
  principle** (we distribute self-hosted copies; we do not host them), but
  get a short legal confirmation before this becomes the core business.
- ❌ **Never offer hosted/cloud SaaS derived from it before the Change
  Date** or without written permission from Dentared.
- Our codebase does not vendor upstream source files (pattern-adapted, not
  copied); when delivering copies to clinics, still preserve upstream
  LICENSE/copyright notices and third-party notices.
- The upstream optional `verifactu` module carries a Spanish tax-compliance
  duty ("productor del SIF") on whoever operates real invoicing in Spain —
  irrelevant to the Algerian single-clinic target, important if Spain is
  ever targeted.
- Upstream audit: no formal public audit report ships in the repo; SECURITY
  policy and CHANGELOG document an external-audit fix lineage. Our own
  production gates remain DEPLOY.md §7 checklist, `docs/qa-report.md` and
  the e2e suite.
