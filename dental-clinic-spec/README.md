# Local Dental Clinic Management System

A **minimal, local-first dental clinic management system for Algeria**, designed for a small clinic running on two PCs.

This project uses DentalPin as an architectural starting point but deliberately removes unnecessary complexity for the actual clinic workflow.

---

## Product Summary

### Users
- **Dentiste**
- **Réception / Admin**

### Environment
- 2 computers.
- Uncle's PC = local server + database host.
- Wife's PC = client connected over LAN.
- Internet is not required for day-to-day clinic operation.

### Languages
- French by default.
- Arabic available.
- English not included in V1.

### Currency / Locale
- DZD.
- `Africa/Algiers`.

### Communication
- No in-app SMS automation.
- No WhatsApp automation.
- No email notification system in V1.

### AI
- No AI features in the product.

---

## What the App Does

### Today
The home screen shows:
- today's date;
- today's appointments in chronological order;
- small revenue summary;
- number of payments.

Appointment workflow:
- À venir
- Arrivé
- En cours
- Terminé

Absent is recorded separately.

### Patients
Search primarily by name/surname.

Patient creation starts with:
- Nom
- Prénom
- Téléphone

Phone is mandatory.

An internal patient number is generated in the background but is not the primary search concept.

### Patient file
The patient page is summary-first.

Main actions:
- Nouvelle note
- Ajouter un traitement
- Odontogramme

Sections:
- Résumé
- Médical
- Traitements
- Paiements
- Documents

Older activity is accessible through Historique.

### Clinical notes
Structured as:
- Motif
- Diagnostic
- Traitement
- Remarques

### Treatments
Catalog categories include:
- Consultation
- Soins
- Chirurgie
- Prothèse
- Orthodontie
- Parodontologie
- Autre

Tooth selection is optional.

### Payments
Cash only.

Patient-level summary:

```text
Total
Payé
Reste
```

Payments can be entered independently from the clinical note/treatment flow.

### Documents
V1 includes:
- Ordonnance
- Certificat médical
- Attestation

Documents can be printed and saved as PDF with clinic branding.

### Medical
Simple checklist for common conditions, plus `Autre`.

### Attachments
Photos and PDFs only.

### Backup
- automatic daily local backup;
- manual `Sauvegarder maintenant` button.

---

## What the App Does NOT Do

V1 intentionally excludes:

- AI / LLM / Copilot
- patient portal
- cloud synchronization
- hosted database
- WhatsApp/SMS automation
- email reminders
- online booking
- DICOM/radiology
- complex accounting
- bank/card integrations
- online payments
- advanced inventory
- lab management
- advanced analytics
- multi-clinic SaaS features

This is a feature, not a limitation by accident: the goal is ease of use.

---

## Architecture

The recommended baseline follows the DentalPin architecture:

- FastAPI backend
- Nuxt frontend
- PostgreSQL database

### Local topology

```text
                CLINIC LAN

+----------------------------------+
| Uncle PC                         |
|                                  |
| Frontend + API + PostgreSQL      |
| Backup service                   |
+----------------+-----------------+
                 |
                 | Local network
                 |
+----------------v-----------------+
| Wife PC                          |
| Browser / Clinic client          |
+----------------------------------+
```

The server PC must stay powered on during clinic hours.

---

## Project Documents

### `STRATEGY.md`
Product strategy, scope, architecture direction, rollout phases, security, backup, and definition of done.

### `AGENTS.md`
Rules for developers and coding agents. It is the engineering guardrail for all implementation work.

### `DESIGN.md`
UI/UX design system based on quiet clinical minimalism and the structured design-spec approach from `awesome-design-md`.

### `README.md`
Project overview and operational orientation.

When these documents disagree, update the documents first and then implement against the newly agreed specification.

---

## Development Philosophy

### 1. Start from proven code
Use DentalPin as a code/architecture reference.

### 2. Remove complexity aggressively
A smaller number of well-designed workflows is more valuable than exposing every upstream feature.

### 3. Keep the user model simple
Only two roles are visible.

### 4. Keep the interface minimal
One screen = one job.

### 5. Keep the server local
No runtime cloud dependency.

### 6. Make every important action reversible/auditable where appropriate
Especially:
- payments;
- price changes;
- appointment changes;
- clinical record edits.

---

## Suggested Project Structure

```text
project/
├── README.md
├── STRATEGY.md
├── AGENTS.md
├── DESIGN.md
│
├── backend/
│   ├── app/
│   │   ├── core/
│   │   ├── patients/
│   │   ├── agenda/
│   │   ├── clinical_notes/
│   │   ├── treatments/
│   │   ├── odontogram/
│   │   ├── medical/
│   │   ├── payments/
│   │   ├── documents/
│   │   ├── attachments/
│   │   ├── settings/
│   │   ├── backup/
│   │   └── audit/
│   └── migrations/
│
└── frontend/
    ├── pages/
    ├── components/
    ├── layouts/
    ├── composables/
    └── i18n/
```

Actual directories may follow the upstream DentalPin conventions when that reduces migration and maintenance risk.

---

## First Development Milestone

The first complete usable slice should be:

```text
Login
  ↓
Aujourd'hui
  ↓
Search patient
  ↓
Create patient or open existing
  ↓
Add to today's workflow
  ↓
Open patient
  ↓
Add clinical note / treatment
  ↓
Record cash payment
  ↓
See Total / Payé / Reste
```

Only after this loop feels effortless should secondary modules receive significant attention.

---

## Deployment Goal

The final clinic installation should feel like one local application, even though it is technically a client/server system.

Target experience:

1. Uncle starts/keeps the clinic server running on his PC.
2. Wife opens the clinic app on her PC.
3. Both use the same database over the LAN.
4. Daily backup runs automatically.
5. A manual backup can be triggered with one button.
6. No internet is required for normal work.

---

## Operational Safety

Before real patient data is loaded:

- disable demo credentials;
- configure unique user passwords;
- confirm server-only database access;
- verify LAN firewall rules;
- test backup;
- perform a restore test;
- verify role permissions;
- verify no medical PII appears in logs;
- pin the exact software version deployed.

The upstream DentalPin repository has documented security/audit findings. Do not assume that upstream code is automatically safe for a real clinic deployment without review.

---

## License / Upstream Note

DentalPin is the architectural starting point for this project and has its own source-available license terms.

Before distributing this application beyond the intended private clinic deployment, review the upstream license and all third-party licenses and preserve required notices.

---

## Success Definition

The project is successful when:

> The dentist and receptionist can run a normal clinic day without needing to think about the software.

The software should be quiet, fast, local, predictable, and easy to understand.
