# AGENTS.md — Engineering and Coding-Agent Rules

## 1. Mission

You are working on a **local Algerian dental clinic application**, adapted from DentalPin.

The application is intentionally simpler than DentalPin.

Your job is to improve the clinic workflow without expanding the product into an ERP, hospital suite, SaaS platform, or AI product.

---

## 2. Mandatory Reading Order

Before changing code, read:

1. `README.md`
2. `STRATEGY.md`
3. `DESIGN.md`
4. relevant upstream DentalPin documentation/module code

Never implement a feature from a task title alone when the files above define a constraint.

---

## 3. Non-Negotiable Product Rules

### Must remain local
Never add a runtime dependency on:
- cloud databases;
- hosted auth;
- cloud storage;
- remote fonts;
- analytics;
- telemetry;
- remote AI APIs;
- online document generation;
- third-party notification services.

Internet access may exist for development, updates, or package installation, but the installed clinic application must not need internet for normal operation.

### No AI in the application
Do not create or restore:
- Copilot UI;
- AI chat;
- AI diagnosis;
- AI summary;
- AI recommendation;
- prompt fields;
- model/provider settings.

Remove dead AI UI, routes, feature flags, imports, and navigation entries when they are no longer needed.

### No notification system in V1
Do not implement SMS, WhatsApp, email, push, or automated reminders unless the product scope is explicitly changed later.

---

## 4. UX Rules

The clinic team is not expected to be technical.

### One screen = one job
Avoid dashboards that look like analytics products.

### Prefer direct actions
The patient page should expose the three useful actions directly:
- Nouvelle note
- Ajouter un traitement
- Odontogramme

Do not force users through artificial “visit” wizards.

### Use normal clinic language
Prefer:
- Patient
- Rendez-vous
- Arrivé
- En cours
- Terminé
- Paiement
- Reste
- Historique

Avoid unnecessary technical terms such as:
- entity;
- workflow state;
- orchestration;
- queue;
- payload;
- pipeline;
- synchronization.

### Minimize visible information
Do not add a field simply because the database can store it.

---

## 5. Navigation Rules

Primary navigation is:

```text
ACCUEIL
  Aujourd'hui

PATIENTS
  Tous les patients

PLANNING
  Rendez-vous

CLINIQUE
  Traitements
  Odontogramme
  Documents

FINANCES
  Paiements

PARAMÈTRES
```

Do not create additional top-level navigation items without updating `STRATEGY.md` and `DESIGN.md`.

Sidebar:
- expanded by default;
- persistent;
- collapsible;
- icon + tooltip when collapsed.

---

## 6. Language and Localization

### UI languages
- French is default.
- Arabic is available.
- English is not a V1 UI language.

### Rules
Every new visible string must:
- live in translation resources;
- have French text;
- have Arabic text;
- avoid sentence fragments where possible;
- use the same medical terminology throughout the product.

Never hard-code user-visible language in a component when localization infrastructure exists.

Arabic:
- use RTL at layout level;
- mirror directional UI appropriately;
- do not simply translate strings while keeping a broken LTR composition.

---

## 7. Algeria Rules

Default profile:
- Currency: DZD.
- Time zone: Africa/Algiers.
- Local clinic identity information.

Do not assume a tax regime in code without an explicit configuration source.

Do not add foreign country/payment concepts to the main clinic workflow.

---

## 8. Roles and Permissions

There are only two logical roles:

### Dentiste
Can:
- manage clinical notes;
- manage treatments;
- use odontogram;
- access patients;
- view payments/debt.

### Réception / Admin
Can:
- manage patients;
- manage appointments;
- record payments;
- view patient debt;
- manage treatment catalog;
- manage basic clinic settings according to assigned account privileges.

### Owner-level account privileges
Use account-level permissions/flags for sensitive actions such as:
- edit treatment prices;
- change critical clinic settings.

Do not create a third role merely to solve this permission edge case.

Server-side authorization is mandatory.

---

## 9. Domain Rules

### Patient
Required at minimum:
- Nom
- Prénom
- Téléphone

Internal patient number may exist but should not dominate the UI.

### Appointment
- Patient is required.
- Day is required.
- Time is optional.
- Four primary statuses:
  - À venir
  - Arrivé
  - En cours
  - Terminé
- Absent is a separate action/event.
- Modification and cancellation history must remain visible.

### Treatment
- Comes from catalog or a valid manually defined treatment path.
- Price is editable only for authorized owner-level accounts.
- Tooth selection is optional.

### Payment
- Cash only.
- Independent patient-level ledger.
- Never delete financial records silently.

### Clinical note
Structured fields:
- Motif
- Diagnostic
- Traitement
- Remarques

### Medical profile
Use simple checkboxes for common conditions plus Autre.

Examples:
- Diabète
- Hypertension
- Maladie cardiaque
- Grossesse
- Anticoagulants
- Asthme
- Épilepsie
- Allergies
- Autre

Medical alerts are shown inside the Médical section; do not create disruptive warning banners across the application.

---

## 10. Data Integrity

Never rely on frontend-only validation for important operations.

Validate server-side:
- required fields;
- allowed status transitions;
- money values;
- payment amounts;
- price permissions;
- ownership/role permissions;
- attachment types/size;
- appointment dates;
- document generation inputs.

Use database constraints where appropriate.

For financial values:
- use decimal-safe types;
- never use floating-point arithmetic for currency.

For history:
- prefer append-only transaction records where appropriate;
- preserve auditability of edits/cancellations;
- avoid destructive deletes for clinical/financial history.

---

## 11. API Rules

The backend is the source of truth.

For every mutating endpoint:
1. authenticate;
2. authorize;
3. validate;
4. execute transactionally;
5. emit/record the necessary audit information;
6. return a clear result.

Do not trust:
- client-side hidden fields;
- disabled buttons;
- role labels from the browser;
- request headers for identity or authorization.

Avoid check-then-act race conditions for:
- invoice/payment operations;
- refunds/financial mutations;
- unique identifiers;
- concurrent updates.

Use database transactions and constraints as the final integrity layer.

---

## 12. Database and Migrations

Any schema change requires a migration.

Migration rules:
- descriptive migration name;
- reversible when practical;
- no destructive data migration without an explicit plan;
- seed data must be deterministic;
- do not seed production demo credentials.

Never edit production data through ad-hoc startup code.

---

## 13. Module Strategy

Keep modules small and purposeful.

Likely V1 modules:
- auth/core
- patients
- agenda
- clinical_notes
- treatment_plan/treatments
- odontogram
- medical profile
- payments
- documents
- attachments
- settings
- backup
- audit

Likely excluded or disabled:
- copilot
- notifications
- integrations
- advanced inventory
- lab orders
- treasury/advanced accounting
- advanced reports
- patient portal
- marketing

Do not delete upstream code blindly. Prefer:
1. disable/remove registration;
2. remove navigation;
3. remove frontend exposure;
4. remove migrations/models only when dependencies are understood.

---

## 14. Frontend Rules

Primary stack remains the DentalPin-aligned frontend architecture unless a justified change is documented.

Do:
- keep components small;
- use consistent spacing tokens;
- use reusable form fields;
- make primary actions obvious;
- support keyboard navigation;
- preserve focus states;
- support 1024px+ desktop layouts;
- handle RTL correctly;
- provide clear loading/empty/error states.

Do not:
- introduce dense card grids;
- add animated dashboards;
- add decorative gradients everywhere;
- hide critical actions in overflow menus;
- create mobile-first compromises for a desktop-only clinic workflow;
- use confirmation modals for trivial actions.

---

## 15. Patient Page Rules

The patient page is summary-first.

Recommended hierarchy:
1. Identity + phone.
2. Last visit / latest clinical information.
3. Direct actions: Nouvelle note / Ajouter un traitement / Odontogramme.
4. Financial summary: Total / Payé / Reste.
5. Lightweight tab/section navigation:
   - Résumé
   - Médical
   - Traitements
   - Paiements
   - Documents
6. Historique for older activity.

Do not dump every historical record onto the first screen.

---

## 16. Today Page Rules

Today is the operational home screen.

Show:
- date;
- chronological appointments;
- patient name;
- phone;
- treatment if relevant;
- time when available;
- status;
- quick payment state such as `Reste: 3 000 DA`;
- quick action `Arrivé`;
- quick action `Ouvrir patient`.

Financial summary is intentionally tiny:
- Recettes aujourd'hui;
- Nombre de paiements.

No charting.

---

## 17. Error Handling

Error messages should tell the user what to do next.

Bad:
> `ValidationError: appointment_time must be null`

Better:
> `Impossible d'enregistrer le rendez-vous. Vérifiez la date.`

Technical details belong in logs, not the clinic UI.

For network/database outages on the wife PC, show a simple state such as:
> `Le serveur de la clinique est momentanément inaccessible.`

Avoid stack traces in the UI.

---

## 18. Backups

The server PC owns backups.

Required UI:
- last successful backup date/time;
- status;
- `Sauvegarder maintenant`.

Do not expose shell commands to the clinic staff.

Do not report “backup successful” unless the backup process has actually completed and produced a valid artifact.

---

## 19. Testing Requirements

Minimum test layers:

### Unit tests
- patient validation;
- appointment status rules;
- payment/debt calculations;
- permissions;
- localization keys;
- document data mapping.

### Integration tests
- create patient;
- create appointment;
- record treatment;
- record payment;
- update patient debt;
- generate document;
- backup trigger.

### End-to-end critical flows
1. Create a patient.
2. Add an existing patient to today.
3. Move an appointment through statuses.
4. Add a treatment.
5. Record a cash payment.
6. View remaining balance.
7. Print/save a document.
8. Create a backup.
9. Access the app from the second PC over LAN.

---

## 20. Change Discipline

Before coding:
- identify the smallest affected module;
- check existing upstream patterns;
- confirm whether the behavior is already implemented elsewhere;
- avoid creating duplicate domain concepts.

After coding:
- update tests;
- update translations;
- update documentation when behavior changes;
- verify desktop layout;
- verify French + Arabic;
- verify local-only operation when relevant.

Do not refactor unrelated code during feature work unless required for correctness.

---

## 21. Agent Workflow

### Product/UX Agent
Owns:
- screen hierarchy;
- flows;
- labels;
- empty/error states;
- consistency with `DESIGN.md`.

Must not expand scope.

### Backend Agent
Owns:
- API;
- validation;
- authorization;
- transactions;
- migrations;
- auditability.

Must not decide UX independently.

### Frontend Agent
Owns:
- components;
- forms;
- navigation;
- responsive desktop layout;
- RTL;
- loading/error states.

Must follow `DESIGN.md`.

### Data/Security Agent
Owns:
- backup/recovery;
- audit logs;
- secrets;
- permission checks;
- database constraints;
- deployment hardening.

### QA Agent
Owns:
- critical workflow verification;
- regression tests;
- LAN validation;
- backup verification;
- bilingual UI checks.

No agent may silently add AI, cloud, notification, or SaaS behavior.

---

## 22. Final Agent Check

Before submitting a change, ask internally:

> Does this make the clinic easier to operate, or does it merely make the software more sophisticated?

If it only makes the software more sophisticated, do not add it.
