# DESIGN.md — Dental Clinic UI Design System

## 1. Design Goal

Create a **quiet, minimal, professional clinic interface** that feels trustworthy and effortless for two everyday users.

The visual language follows a design-spec structure inspired by the `awesome-design-md` approach:

- Visual Theme & Atmosphere
- Color Palette & Roles
- Typography Rules
- Component Styling
- Layout Principles
- Depth & Elevation
- Interaction/Feedback
- Do / Don't
- Responsive Behavior
- Agent Prompt Guide

This is a clinic operations product, not a consumer health app and not a medical dashboard full of metrics.

---

## 2. Visual Theme & Atmosphere

### Theme
**Quiet Clinical Minimalism**

Desired feeling:
- calm;
- clean;
- precise;
- trustworthy;
- warm enough for a small clinic;
- professional without looking corporate;
- modern without feeling experimental.

The interface should visually disappear behind the workflow.

### Avoid
- futuristic AI visuals;
- neon gradients;
- glassmorphism as a default;
- excessive shadows;
- excessive badges;
- large illustrations on operational screens;
- dense analytics dashboards;
- decorative motion;
- “hospital software” visual overload.

---

## 3. Color Palette & Roles

Use a restrained palette with semantic roles rather than color variety.

### Base

| Role | Token | Value | Purpose |
|---|---|---:|---|
| Background | `--color-bg` | `#F7F8FA` | Main application canvas |
| Surface | `--color-surface` | `#FFFFFF` | Panels, forms, tables |
| Text primary | `--color-text` | `#17212B` | Main content |
| Text secondary | `--color-text-muted` | `#66717D` | Supporting labels |
| Border | `--color-border` | `#E2E7EC` | Quiet separation |
| Primary | `--color-primary` | `#0040DC` | Main actions, active navigation (HKN brand blue) |
| Primary dark | `--color-primary-dark` | `#0033B0` | Hover/pressed states |
| Accent | `--color-accent` | `#0B64D8` | Small positive/clinical accent |
| Success | `--color-success` | `#2D7A5A` | Completed/success feedback |
| Warning | `--color-warning` | `#9A6A18` | Caution / attention |
| Danger | `--color-danger` | `#B34A4A` | Destructive/error states |

### Usage rules
- Most of the screen should remain neutral.
- Primary color is reserved for important actions and active states.
- Accent is used sparingly.
- Red is only for errors/destructive states.
- Do not encode every status as a loud colored badge.

### Money
Financial values should be readable through typography and grouping first, not through decorative colors.

Example:

```text
Total        12 000 DA
Payé          9 000 DA
Reste         3 000 DA
```

---

## 4. Typography Rules

### Primary type system
Use a clean sans-serif with strong French and Arabic support.

HKN brand fonts (commercial, see `branding/fonts/README.md`):

- Latin + documents: **PP Neue Montreal** (Pangram Pangram).
- Arabic: **Janah LT** (Linotype, Nadine Chahine).

They are wired via `@font-face` and activated automatically when licensed
`.woff2` files are placed in `frontend/app/assets/fonts/`. Until then the
bundled open-license fallbacks remain active:

```css
/* Latin stack (used by default) */
font-family: "PP Neue Montreal", Inter, "Segoe UI", Arial, sans-serif;
```

Arabic-capable stack (applied under `[lang="ar"]` / RTL):

```css
font-family: "Janah LT", "Noto Sans Arabic", Tahoma, Arial, sans-serif;
```

For a fully offline build, fonts must be bundled or available locally. Do not load them from a public CDN at runtime.

### Scale

| Level | Recommended size | Weight | Use |
|---|---:|---:|---|
| Page title | 24px | 650 | Main page heading |
| Section title | 18px | 600 | Section headers |
| Body | 14–15px | 400 | Main content |
| Label | 12–13px | 500 | Form/table labels |
| Small | 12px | 400 | Secondary metadata |
| Button | 13–14px | 550 | Actions |

### Typography rules
- Prefer sentence case.
- Avoid all-caps except small navigation section labels.
- Use weight before size to establish hierarchy.
- Do not use tiny text for important medical or financial data.
- Numeric values should be visually stable and easy to scan.

---

## 5. Layout Principles

### Desktop-first
The real workflow is two desktop PCs on a clinic LAN.

Primary target:
- 1280×800 and above.

Minimum supported practical layout:
- 1024px wide.

Mobile is not a V1 priority.

### Grid
Use generous whitespace and predictable alignment.

Recommended structure:

```text
┌─────────────────────────────────────────────────────┐
│ Sidebar │ Page header                               │
│         ├───────────────────────────────────────────┤
│         │ Main content                              │
│         │                                           │
│         │                                           │
└─────────────────────────────────────────────────────┘
```

### Sidebar
- Width expanded: ~240px.
- Width collapsed: ~72px.
- Persistent.
- Expanded by default.
- Section labels are subtle.
- Active item has a quiet background and primary accent.

### Content width
- Avoid full-bleed content where not needed.
- Forms should have a comfortable max width.
- Tables can use the available width.
- Patient pages may use a two-column desktop structure only when it improves scanning.

### Spacing
Use a consistent 4px/8px-derived scale.

Typical values:
- 8px compact gap;
- 12px field gap;
- 16px component gap;
- 24px section gap;
- 32px page section gap.

Generous whitespace is intentional.

---

## 6. Component Styling

### Buttons
Use three levels:

1. **Primary** — one main action per section.
2. **Secondary** — supportive actions.
3. **Tertiary/text** — low-priority actions.

Do not put five equally weighted buttons next to each other.

Primary action examples:
- Ajouter un patient
- Enregistrer
- Arrivé
- Ajouter un traitement
- Sauvegarder maintenant

### Inputs
- 40–44px height.
- Clear label above the field.
- Comfortable click area.
- Visible focus state.
- No placeholder-only labels for important fields.

### Search
Patient search is a high-priority interaction.

Use:
- one clear search field;
- name/surname as the default concept;
- optional phone search if useful;
- fast result feedback.

Avoid advanced filter drawers in V1.

### Tables
Patient list columns:
- Nom
- Prénom
- Téléphone

Do not show ten administrative columns by default.

### Cards
Use cards only where grouping is genuinely useful.

Do not turn every piece of information into a card.

### Tabs
Use tabs only for meaningful patient sections:
- Résumé
- Médical
- Traitements
- Paiements
- Documents

The default tab is **Résumé**.

### Status indicators
Prefer subtle text + small visual cue.

Primary appointment statuses:
- À venir
- Arrivé
- En cours
- Terminé

`Absent` should be a specific action/history event, not a fifth visually dominant status.

---

## 7. Page Definitions

### 7.1 Aujourd'hui

Header:
- `Aujourd'hui`
- date

Main:
- chronological appointment list;
- small financial summary.

Appointment row should show:
- time if provided;
- patient name;
- phone;
- treatment/context if useful;
- current status;
- remaining balance when useful;
- quick actions.

Do not show a calendar grid on the home page.

Empty state:

> Aucun rendez-vous aujourd'hui

Nothing else is required.

---

### 7.2 Tous les patients

Top:
- title;
- single dominant search field;
- add-patient action.

Main:
- simple table;
- Nom / Prénom / Téléphone only.

Row interaction:
- click opens the patient summary.

---

### 7.3 Patient

Recommended hierarchy:

```text
Patient name + phone

Dernière visite
[ Nouvelle note ] [ Ajouter un traitement ] [ Odontogramme ]

Résumé / Médical / Traitements / Paiements / Documents

Résumé:
  Dernière activité
  Total / Payé / Reste

Historique:
  older records
```

The page must feel like a **patient summary**, not a database record editor.

### 7.4 New patient

Keep first registration extremely short:

```text
Nom       [             ]
Prénom    [             ]
Téléphone [             ]

             [ Enregistrer ]
```

Medical information comes later.

---

## 8. Clinical Note Design

Clinical note is a compact form:

```text
Motif
[................................]

Diagnostic
[................................]

Traitement
[................................]

Remarques
[................................]

[ Enregistrer ]
```

Avoid forcing users to fill irrelevant fields.

---

## 9. Treatment Entry Design

Treatment creation should feel like a quick transaction.

Suggested flow:

```text
Traitement   [ select ]
Dent         [ facultatif ]
Prix         [       DA ]

[ Ajouter ]
```

Price editing controls are only visible/enabled for authorized owner-level accounts.

Do not expose tax/accounting complexity in the primary treatment form.

---

## 10. Financial UI

The financial screen should be calm and ledger-like.

Primary patient summary:

```text
Total        25 000 DA
Payé         15 000 DA
Reste        10 000 DA
```

Payment history should be a simple chronological list/table:
- date;
- amount;
- note if relevant.

Do not require users to choose a payment method because V1 is cash-only.

---

## 11. Medical UI

Medical information is intentionally simple.

Example:

```text
Diabète           □
Hypertension      □
Maladie cardiaque □
Grossesse         □
Anticoagulants    □
Asthme            □
Épilepsie         □
Allergies         □
Autre             [................]
```

Do not put warning banners on every page.

Medical warnings belong inside the Médical section.

---

## 12. Documents

Document UI should resemble a small print desk.

Actions:
- Aperçu
- Imprimer
- Enregistrer en PDF

V1 templates:
- Ordonnance
- Certificat médical
- Attestation

Header/footer configuration should be handled in settings, not repeated on every document screen.

---

## 13. Feedback and Interaction

### Loading
Use subtle progress indicators.

Avoid large animated loaders.

### Success
Use short confirmation text such as:
> Patient enregistré.

### Error
Explain the problem in normal language.

### Destructive actions
Appointment cancellation should require a clear confirmation.

Routine save actions should not trigger unnecessary confirmation dialogs.

### Animation
Use minimal motion:
- small state transition;
- drawer open/close;
- tooltip.

No animation should delay an operational task.

---

## 14. Depth & Elevation

Default surface model:
- flat surfaces;
- 1px borders;
- very soft shadows only when needed.

Recommended shadow:

```css
box-shadow: 0 4px 18px rgba(20, 35, 45, 0.06);
```

Use elevation to separate:
- dialogs;
- dropdowns;
- sticky areas.

Do not shadow every card.

---

## 15. Icons

Use a single consistent icon family.

Icons should be:
- simple;
- outline or restrained filled forms;
- 18–20px for standard actions;
- paired with text whenever the action is important.

Never make the user decode an icon-only critical action.

---

## 16. RTL / Arabic

When Arabic is selected:
- switch document direction to RTL;
- mirror sidebar/content relationships where appropriate;
- preserve natural numeric presentation;
- keep icons that communicate universal concepts visually consistent;
- do not hard-code left/right positioning.

The design must remain calm in Arabic, not merely translated.

---

## 17. Accessibility

Baseline:
- visible focus;
- keyboard-accessible buttons/forms;
- sufficient text contrast;
- descriptive labels;
- no color-only meaning;
- clickable areas large enough for mouse use;
- status should be understandable in text.

---

## 18. Do / Don't

### Do
- keep one primary action per area;
- use whitespace;
- make search prominent;
- make patient name and phone obvious;
- keep financial totals readable;
- use plain French;
- support RTL correctly;
- make the clinic workflow obvious without training.

### Don't
- add dashboards full of charts;
- add AI decorations;
- use huge badges;
- show internal IDs by default;
- expose every database field;
- create multi-step forms for simple actions;
- use cloud-only UI patterns;
- make users understand software architecture.

---

## 19. Responsive Behavior

### Desktop
Primary target for both clinic PCs.

### Narrow desktop
At ~1024px:
- sidebar may collapse automatically;
- two-column patient layouts stack;
- table remains readable;
- secondary metadata can be reduced.

### Mobile
Not a V1 optimization target.

Do not distort the desktop workflow just to imitate a mobile app.

---

## 20. Agent Prompt Guide

When an implementation agent creates or edits a screen, its internal design brief should follow this structure:

### Context
What clinic task does this screen support?

### User
Dentiste or Réception / Admin?

### Primary action
What should the user do here?

### Information hierarchy
What is essential, secondary, and hidden?

### Visual treatment
Apply Quiet Clinical Minimalism.

### Constraints
- French default.
- Arabic available.
- No English UI.
- No AI.
- No notifications.
- No unnecessary cards.
- No charts unless explicitly approved.
- Local/offline operation must remain possible.

### Interaction
Define:
- normal state;
- loading state;
- empty state;
- error state;
- success feedback;
- destructive confirmation where relevant.

### Accessibility
Keyboard, focus, contrast, labels, RTL.

### Final check
Ask:
> Can a non-technical clinic user understand what to do within 3 seconds?

---

## 21. Visual Acceptance Test

A screen passes design review when:

- the primary action is obvious;
- there is no unnecessary visual noise;
- the screen works without explanation;
- typography hierarchy is clear;
- French looks natural;
- Arabic layout is structurally correct;
- color is used sparingly;
- there are no unnecessary cards/charts/badges;
- the design feels like one coherent product.

---
