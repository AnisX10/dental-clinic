# QA Report — Frontend + Backend full audit (2026-10-12)

**Scope:** every backend module exercised live (curl, both roles), every frontend page walked in
the browser as a real clinician. Dataset: existing demo DB (17 patients, treatments, payments).

## Baseline before QA
- pytest: 72 tests ✅ · ruff clean ✅ · `npm run typecheck` ✅
- Dev servers restarted after session restart (uvicorn :8000 + Nuxt :52490).

---

## Bugs found → fixed during the audit

### BUG#1 (major) — duplicate patient → HTTP 500
- **Repro:** `POST /api/patients` twice with same nom+prenom+téléphone → `IntegrityError` on
  `uq_patient_identity` bubbled up as `500 / errors.internal`.
- **Impact:** reception double-clicking "Save" gets a scary internal error instead of guidance.
- **Root cause:** unique constraint exists but the API never translated it to a business error.
- **Fix:** [backend/app/patients/service.py](../backend/app/patients/service.py) — catch
  `IntegrityError` on flush → `400 patient_exists` (`errors.patient_exists`, new i18n key in
  fr + ar: "Un patient avec ce nom, prénom et téléphone existe déjà.").
- **Regression test:** `test_duplicate_patient_returns_400` in `test_patients.py` ✅ (72 passed).

### BUG#2 (minor, UX) — patient page error banner persists forever
- **Repro:** any transient tab-load failure (e.g. stale auth cookie against a restarted server)
  sets `errorMsg`; switching tabs or retrying never cleared it, even when the retry succeeded.
- **Fix:** [frontend/app/pages/patients/[id].vue](../frontend/app/pages/patients/[id].vue) —
  `loadTab` clears `errorMsg` on entry, so a successful reload removes the banner.
- Verified via reload: banner gone, odontogram + history panel render.

### Observations logged (not bugs, deliberate design confirmed in code)
- Appointment status **skips are allowed** (a_venir → termine directly). Events table records the
  real transition chain; frontend only offers sensible next steps. No change made.
- Settings save shows no confirmation toast (data persists; verified via API + document header
  picked it up). Candidate micro-polish.

---

## Module-by-module results (live API, both roles)

| Module | Checks run | Result |
|---|---|---|
| Auth | login ok/bad-pass/missing-field, `/me`, logout, rate-limit fields, HttpOnly cookie | ✅ 401/422/200 as designed |
| Patients | create, duplicate identity (now clean 400), bad phone, blank name, future birthdate, search, birthdate update | ✅ (after BUG#1 fix) |
| Attachments | upload (pdf ok, wrong mime 400), download 200 both roles, delete 204, re-download 404 | ✅ |
| Agenda | create, arrive→(skip termine allowed)→en_cours 400 from termine→absent, cancel; bad date 400, bad time 400, unknown patient 404; today/day lists; upcoming-count; patient appointments; event log written | ✅ |
| Clinical notes | create 201, latest, list (reception allowed) | ✅ |
| Catalog | reception create 403 ✅, owner create 201, duplicate name 400, bad category 400, price update 200 (audited) | ✅ |
| Treatments | create with tooth; catalog-category casing enforced | ✅ |
| Odontogram | surface set, whole-tooth set, clear; history endpoint with actor name; invalid tooth 400 | ✅ |
| Payments | zero 400, negative 400, unknown patient 404, valid 201; **ledger math verified** (total = payé + reste); day summary counts | ✅ |
| Documents | ordonnance / certificat / attestation all 201; document detail view shows clinic header ( freshly saved settings!) | ✅ |
| Labs | lab create, duplicate 400; order lifecycle envoye→en_fabrication→recu, bad status 404; invoice create, partial payment, overpay 400 | ✅ |
| Stock | item create (category/cost required), duplicate name 400, reception adjust allowed, over-consume 400 (clamped), inventory correction, movements list, valuation | ✅ |
| Settings | GET both roles, PUT reception 403, owner update persists (used for document header test) | ✅ |
| Backup | status 200 both, run manual 201 (owner), reception run 403 | ✅ |
| Role matrix | all read endpoints 200 for reception; owner-only writes 403 (catalog, settings, backup, users mgmt UI); anonymous 401 everywhere | ✅ |

---

## Browser walkthrough (as the clinician)
1. **Login** → dashboard: today's RDV with statuses, recettes du jour (600 DA / 2 paiements), alerts + relance card. ✅
2. **Create patient via UI dialog** (Djazaïr Lina) → appears in list. ✅
3. **Paramètres** → changed clinic name & doctor → persisted API-side; document header reflected it. ✅
4. **Paiements** page → day filter, list with amounts. ✅
5. **Documents** → patient search → ordonnance wizard (add line "Amoxicilline…") → saved, openable in printable view. ✅
6. **Stock** → items with quantities, low-stock threshold column, action buttons. ✅
7. **Laboratoire** → order list with status counts + pipeline badges. ✅
8. **Odontogramme** (standalone launcher + patient tab) → tooth chart both arches, legend, condition panel; tooth-history panel under the chart. ✅

## Backend gaps vs DentalPin reference (from docs/dentalpin-workflows.md)
Unchanged conclusion: devis/facture module absent (by design for now), odontogram v2 (planned ×
performed distinction) not yet scheduled — these are the two "Modules" items on the backlog.

## Recommendations (small, non-blocking)
1. Settings "Enregistrer" could flash a success toast.
2. Appointment skip (a_venir → termine) is currently permitted; if the clinic wants strict
   sequencing, add a guard in `set_status` (service already keeps an event audit trail).
3. `seed_qa_tmp.py` / `seed_demo_tmp.py` are dev-only conveniences in the repo root of `backend/` —
   keep out of production deploys.

## Final state
- Backend: **72/72 tests**, ruff clean.
- Frontend: typecheck clean; all 12 pages exercised.
- Dev servers running: API :8000, Nuxt :52490 (registered in Preview).
