# Dental Clinic Local Management System — Strategy

## 1. Product North Star

Build a **very simple, fully local dental-clinic management system for one Algerian clinic**, optimized for two non-technical staff members and two PCs.

The product should feel like a focused desktop work tool rather than a hospital information system.

### North-star rule
> **Every screen should answer one operational question and make the next action obvious.**

Primary users:
- **Dentiste**: clinical work, patient records, treatments, odontogram when useful, financial visibility.
- **Réception / Admin**: patient registration, appointments, payments, debts, treatment catalog, basic settings.

There are only two logical roles. Account-level owner privileges may be used for sensitive configuration such as price editing without creating a third role.

---

## 2. Product Principles

### 2.1 Local first
- No cloud dependency for core operations.
- No hosted database.
- No external API required for normal clinic activity.
- The uncle's PC is the **local server + PostgreSQL host**.
- The wife's PC connects over the clinic LAN.
- The application must continue working when the internet is unavailable.

### 2.2 Simplicity over feature count
Do not recreate the whole DentalPin feature surface.

The target is a **small, deliberate subset** of DentalPin:
- Patients
- Appointments / Today
- Clinical notes
- Treatments
- Odontogram
- Payments / debt
- Basic documents
- Attachments
- Minimal settings
- Local backup

Everything else is optional until the clinic proves it needs it.

### 2.3 No AI in the product
The DentalPin AI/coplanilot direction is explicitly removed.

Do not add:
- AI copilot
- LLM chat
- AI suggestions
- AI summaries
- AI diagnosis
- AI automation
- cloud AI APIs
- AI-related navigation items

AI can be used by developers as a development tool, but **it is not a clinic feature**.

### 2.4 No in-app patient notifications in V1
Do not build SMS, WhatsApp, email, push notifications, or reminder automation into V1.

The clinic may continue using existing external/manual communication methods outside the application.

### 2.5 French + Arabic only
- Default UI: **French**.
- Secondary UI: **Arabic**.
- No English UI in V1.
- Arabic must use proper RTL layout.
- All user-visible text must be translatable.

### 2.6 Local Algerian context
The system should be localized for Algeria:
- Currency: **DZD**.
- Time zone: **Africa/Algiers**.
- Algerian clinic identity fields.
- Wilaya / commune where useful.
- Local document templates.
- Local cash/debt workflow.
- No unnecessary foreign accounting or payment concepts in the primary UI.

Tax behavior must remain configurable and should not hard-code assumptions about the clinic's exact fiscal treatment until verified with the clinic/accountant.

---

## 3. Source Strategy: Adapt DentalPin, Do Not Clone Its Complexity

DentalPin is the architectural reference and starting point, not the product specification.

The implementation strategy is:

1. **Pin a reviewed upstream DentalPin commit** before development.
2. Keep the parts that provide real value: API structure, authentication, database patterns, frontend shell, modularity, migrations, and proven domain patterns.
3. Remove or disable modules that do not belong in the local clinic product.
4. Simplify the remaining entities and workflows rather than exposing upstream complexity.
5. Keep the codebase modular enough that future features can be added without polluting the core.

### Important upstream discipline
Do not automatically follow the upstream `main` branch.

The inspected DentalPin repository contains a security/audit history with critical and high-priority findings. Before any production-like deployment, review the relevant findings, patch or remove affected code paths, and pin the exact version used by the clinic.

### Licensing checkpoint
DentalPin is source-available under its own license terms. Before redistribution, commercial use, or creating a product for multiple clinics, perform a formal license review. The initial target here is a private/local deployment for a single clinic.

---

## 4. V1 Scope

### Included

#### Patients
- Search by **Nom / Prénom**.
- Phone number mandatory.
- Internal patient number generated automatically but not used as the normal search key.
- Minimal registration: Nom, Prénom, Téléphone.
- Patient profile can later be completed.
- Summary-first patient page.
- Latest visit visible by default.
- Older information behind **Historique**.
- Medical section with common-condition checkboxes + Autre.
- Basic attachments: photos and PDFs.

#### Appointments
- Patient + day required.
- Time optional.
- Exact or approximate time can be represented.
- Main view: chronological list for the selected day, with **Aujourd'hui** as the primary landing page.
- Four visible workflow states:
  - À venir
  - Arrivé
  - En cours
  - Terminé
- **Absent** is an action/event, not one of the four primary statuses.
- Appointment can be modified or cancelled.
- Appointment history must remain visible.
- Quick actions: Arrivé / Ouvrir patient.

#### Clinical notes
- Mostly manual entry.
- Structured format:
  - Motif
  - Diagnostic
  - Traitement
  - Remarques
- No forced visit wizard.
- Main patient actions are direct:
  - Nouvelle note
  - Ajouter un traitement
  - Odontogramme

#### Treatments
- Predefined catalog.
- Categories such as:
  - Consultation
  - Soins
  - Chirurgie
  - Prothèse
  - Orthodontie
  - Parodontologie
  - Autre
- Price editable when authorized.
- Treatment can optionally be linked to a tooth.
- Without tooth selection, treatment is a general patient treatment record.
- With tooth selection, treatment can appear in odontogram/history context.

#### Payments
- Cash only.
- Patient-level payment ledger.
- Payments may be entered during a clinical workflow or independently.
- Primary financial summary:
  - Total
  - Payé
  - Reste
- Payment history.
- No banking, card gateway, online payment, or payment-method matrix.

#### Documents
V1 only:
- Ordonnance
- Certificat médical
- Attestation

Every document can:
- be printed directly;
- be saved as PDF;
- use clinic branding/header/footer;
- display clinic name, logo, doctor name, address, phone.

#### Odontogram
- Secondary tool, not the home screen.
- Simple and fast.
- Tooth selection optional for treatments.
- No attempt to become a complete dental imaging system.

#### Dashboard
Primary page: **Aujourd'hui**.

Show only:
- Current date.
- Today's appointments in chronological order.
- Small financial summary:
  - Recettes aujourd'hui
  - Nombre de paiements

Do not show:
- debt analytics;
- charts;
- complex KPI grids;
- AI insights;
- notification center.

If there are no appointments:
> **Aucun rendez-vous aujourd'hui**

No extra empty-state button is required.

#### Backup
- Automatic daily local backup.
- Manual **Sauvegarder maintenant** action.
- Backup belongs to the server PC.
- Backup status must be understandable to a non-technical user.

---

## 5. V1 Explicitly Excluded

Do not build unless a later product decision changes scope:

- AI / copilot
- patient portal
- mobile application
- WhatsApp integration
- SMS automation
- email reminder automation
- online booking
- cloud sync
- multi-clinic SaaS
- DICOM / radiology platform
- advanced inventory
- lab management
- complex accounting
- insurance processing
- bank integration
- online payments
- marketing/CRM automation
- advanced analytics
- complicated reporting builder
- appointment calendar grid as the primary workflow

---

## 6. Information Architecture

### Primary sidebar

**ACCUEIL**
- Aujourd'hui

**PATIENTS**
- Tous les patients

**PLANNING**
- Rendez-vous

**CLINIQUE**
- Traitements
- Odontogramme
- Documents

**FINANCES**
- Paiements

**PARAMÈTRES**

Sidebar behavior:
- Persistent.
- Expanded by default.
- Collapsible.
- Collapsed state shows icons with tooltips.

Do not add a large navigation tree.

---

## 7. Key User Flows

### 7.1 New patient, walk-in

1. Open Aujourd'hui.
2. Search patient by name.
3. No result -> create patient.
4. Enter Nom + Prénom + Téléphone.
5. Save.
6. Patient is immediately added to today's workflow.

### 7.2 Existing patient, walk-in

1. Search patient.
2. Open patient.
3. Add to today's workflow directly.

### 7.3 Normal clinical workflow

1. Find/open patient.
2. Add clinical note if needed.
3. Add treatment if needed.
4. Select tooth only when useful.
5. Record payment if received.
6. End without requiring a separate formal “visit” object in the UI.

### 7.4 Independent payment

1. Open patient or Payments.
2. Add cash payment.
3. Update Total / Payé / Reste.
4. Payment appears in patient ledger.

### 7.5 Appointment completion

À venir -> Arrivé -> En cours -> Terminé

Absent is recorded through a dedicated action, while preserving the appointment history.

---

## 8. Architecture Strategy

### Recommended baseline
Keep the proven DentalPin split:
- **FastAPI backend**
- **Nuxt frontend**
- **PostgreSQL**

Use the existing API/database/frontend conventions where they reduce risk, but aggressively simplify the exposed feature surface.

### Local topology

```text
                CLINIC LAN

   +---------------------------+
   | Uncle PC                  |
   |                           |
   | Nuxt / Web App            |
   | FastAPI API               |
   | PostgreSQL                |
   | Backup Scheduler          |
   +-------------+-------------+
                 |
                 | LAN
                 |
   +-------------v-------------+
   | Wife PC                   |
   | Browser / Clinic Client   |
   +---------------------------+
```

The application should be usable with the clinic internet connection disconnected.

### Server principle
The server PC must remain on during clinic hours because it hosts the database and application services.

### No hidden external dependencies
Do not call external services for:
- fonts;
- analytics;
- telemetry;
- error reporting;
- AI;
- remote document generation;
- cloud storage;
- authentication.

---

## 9. Data Model Direction

Prefer a small model set over an exhaustive ERP-style schema.

Core entities:
- User
- Patient
- MedicalProfile
- Appointment
- ClinicalNote
- TreatmentCatalogItem
- PatientTreatment
- ToothState / OdontogramEntry
- Payment
- Document
- Attachment
- AuditLog
- BackupRecord
- ClinicSettings

### Patient financial invariant

```text
Reste = Total patient charges - Total payments
```

The UI must never rely on handwritten debt values if they can be computed from transaction records.

### Auditability
Maintain enough history to answer:
- who changed a price;
- who edited/cancelled an appointment;
- who created/edited a clinical note;
- who recorded a payment;
- who changed patient administrative data.

Do not log sensitive medical content into application stdout or debug logs.

---

## 10. Security Strategy

Even though the system is local, patient data is sensitive.

Baseline controls:
- authenticated users;
- hashed passwords;
- role/account permission checks;
- server-side authorization on every protected action;
- no default production credentials;
- no demo seed users in production;
- rate-limited login;
- safe session/token handling;
- CSRF/XSS-safe frontend patterns;
- parameterized queries / ORM usage;
- database migrations under version control;
- audit logging for high-value changes;
- least privilege for database user;
- no medical PII in logs.

Do not treat LAN access as authentication.

---

## 11. Backup Strategy

### Automatic
Run once daily on the server PC.

Minimum backup artifact:
- PostgreSQL logical backup;
- metadata sufficient to identify timestamp/version.

### Manual
Provide a clearly labeled button:
> **Sauvegarder maintenant**

### Suggested retention
Use a simple rolling policy such as:
- 14 daily backups;
- 5 manual backups;
- never delete the newest valid backup.

Retention should be configurable later.

### Recovery
A recovery procedure must exist before deployment:
1. Stop clinic services.
2. Restore database into a known clean instance.
3. Verify patient count, appointment sample, payments, and documents.
4. Restart application.
5. Record the recovery event.

A backup that has never been restored is not considered validated.

---

## 12. Delivery Roadmap

### Phase 0 — Foundation
- Fork/pin DentalPin baseline.
- Establish local dev environment.
- Remove AI/copilot surface.
- Establish French/Arabic localization.
- Establish Algeria profile.
- Establish local-only configuration.

### Phase 1 — Daily clinic workflow
- Authentication.
- Patients.
- Today.
- Appointments.
- Clinical notes.
- Treatments.

### Phase 2 — Money and documents
- Payments.
- Patient debt summary.
- Document printing/PDF.
- Clinic branding.

### Phase 3 — Clinical extras
- Odontogram.
- Medical profile.
- Attachments.

### Phase 4 — Reliability
- Automated backup.
- Manual backup.
- Audit trail.
- Recovery test.
- LAN deployment hardening.
- Usability polish.

### Phase 5 — Pilot
Run the actual clinic workflow for a controlled pilot.

Measure:
- time to register a patient;
- time to find a patient;
- time to add a treatment;
- time to record a payment;
- number of operator mistakes;
- number of confusing screens;
- backup success;
- LAN reliability.

Do not add new features during the pilot unless they solve a blocking operational problem.

---

## 13. Definition of Done

A feature is done only when:

- It works on the server PC.
- It works from the second PC over LAN.
- It works without internet.
- French strings are complete.
- Arabic strings are present where the feature is user-visible.
- Permissions are enforced server-side.
- Validation and error states are understandable to non-technical staff.
- No unnecessary screen or navigation item was introduced.
- Data changes are covered by migrations and tests.
- The feature does not introduce cloud/AI/notification dependencies.

---

## 14. Product Quality Bar

The goal is not “maximum features”.

The goal is:

> **A dentist and receptionist should be able to operate the clinic all day without needing to understand the software.**

When a design decision is ambiguous, choose the option that reduces:
1. clicks;
2. visible concepts;
3. typing;
4. navigation;
5. technical vocabulary;
6. chances of data-entry mistakes.

---
