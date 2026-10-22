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

## 4. Next sales steps (plan dated 2026-10-22)

### 4.1 Product claims we can honestly sell today

- Local-first: the database and licence live in the clinic; works fully offline,
  nothing patient-related leaves the cabinet PC.
- Print output: A4 ordonnances/certificats/attestations with a proper letterhead,
  multi-page ordonnances with repeated patient line, devis with signature blocks,
  CNAS/DSP sheets ready to hand to the caisse.
- Perpetual licence (per installation), no hosted service, no yearly lock-in.
- FR + AR (RTL) interface.

### 4.2 Demo kit — build once, reuse every meeting

1. **Demo machine**: run the e2e bootstrap (`backend/e2e_bootstrap.py`) +
   `scratch/seed_print_lab.py` + `scratch/seed_devis_dsp.py` against a demo DB —
   gives realistic patients (e.g. Meziane Yasmine), an ordonnance, a certificat,
   a 2-page ordonnance, a devis sent for accord, and a CNAS DSP with acts.
2. **20-minute script**: patients → today's agenda → consultation → odontogramme
   → print an ordonnance (show the print-quality + the settings reminder) →
   devis "Envoyer/Imprimer" → DSP & CNAS sheet → agenda absent/cancel flow →
   documents archive.
3. **One-pager** (FR + AR): the claims of §4.1 + a screenshot of the ordonnance
   print + licence/pourtour terms in one line.
4. **Contract template**: one page — perpetual right of use per installation,
   installation & training are separate services, updates optionally included,
   no hosting, upstream notices preserved (see §3).
5. **Pricing sheet** (perpetual model, owner fills the numbers):
   - Licence perpétuelle par installation : ____ DA
   - Installation + PostgreSQL + audit sécurité (DEPLOY.md §1–7) : ____ DA
   - Formation équipe (2 h) : ____ DA
   - Mise à jour optionnelle : ____ DA/an (≈15–20 % du licence)

### 4.3 First 5 pilot cabinets (Alger), then decide scale-up

Target profile: 1–2 chair cabinets, dentist-owner present during demo, has a
spare PC or accepts the one we install. Sequence per cabinet: demo (20 min) →
1-week pilot on his own patients → conversion.

Success criteria for the pilot batch (2+ conversions needed): pilot used ≥2 weeks
in real consultations; at least ordonnance + devis printed; explicit quote or
won/lost reason recorded. Pilot cabinets sign nothing commercial; ask for a
one-line testimonial + permission to name-drop.

### 4.4 Channels (in order)

1. Warm & local: the dentist-owners already known to the founder; ortho/general
   colleagues of the first pilots.
2. Dental supply shops and the informaticiens who install cabinets' PCs —
   referral commission (one-time, fixed).
3. Professional/regional gatherings (associations dentaires, faculté d'Alger
   graduates' groups), case courante Facebook groups of dentistes.

### 4.5 Weekly operating loop

- Monday: 10 outbound touches (visit or called demo), log in the pipeline sheet
  (cabinet, date, stage, next action, won/lost reason).
- Demos within 48 h of interest; pilot installs scheduled the same week as demo.
- Friday: update funnel numbers (touches → demos → pilots → paid installs) and
  the top-3 product asks heard this week (feeds the roadmap).

### 4.6 Legal/ops guardrails (from §3)

- Never sell a hosted SaaS read of the Install — per-deployment licences only.
- Keep upstream LICENSE + third-party notices intact in every delivered build.
- New-server move = free re-issue with the new Installation ID (goodwill item —
  say it explicitly during the sale).

### 4.7 4-week launch plan

| Week | Focus |
|---|---|
| 1 | Demo kit built (§4.2), pricing sheet decided, contract template ready, 2 demo machines |
| 2 | 10 visits / 3–5 demos done; 2 pilots scheduled |
| 3 | 2 + pilots installed and live; first objections log |
| 4 | Pilot reviews → adjust pricing/version priority; public testimonial; scale to 10 visits/week |
