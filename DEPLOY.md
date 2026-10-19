# DEPLOY.md — Clinic installation guide

This guide installs the complete application on the clinic's **server PC**
(the uncle's PC). The second PC only needs a browser.

Everything runs locally: application, database, and daily backups. **No
internet is required** for normal clinic work.

---

## 1. What you need

- The server PC (Windows), left powered on during clinic hours.
- This project folder copied onto it (e.g. `C:\clinic`).
- Python **3.11** installed (3.12+ is not supported by the bundled
  PostgreSQL launcher).
- Node.js is only needed to build the frontend; generate the build once with
  `npm run generate` (section 5) before the first deployment.

---

## 2. One-time setup (server PC)

Open *Command Prompt* in the project folder and run:

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements.txt
```

Create the two clinic accounts (owner = the dentist):

```bat
.venv\Scripts\python backend\app\cli.py create-user --username dentiste --role dentiste --owner --full-name "Dr Nom"
.venv\Scripts\python backend\app\cli.py create-user --username reception --role reception --full-name "Réception"
```

You will be prompted for a password for each. Keep them private — these are
the only ways into patient data.

The treatment catalogue (21 entries, 7 categories) seeds itself on first
start. The database (PostgreSQL 16, bundled launcher) initializes itself in
`data\pgdata` — nothing to install.

---

## 3. Daily start

Double-click **`scripts\start.bat`**.

- The application listens on **http://127.0.0.1:8000** on the server PC.
- Other PCs on the LAN open **http://SERVER-PC-IP:8000** in the browser
  (find the IP with `ipconfig` — e.g. `http://192.168.1.20:8000`).
- Allow the app through the Windows firewall when prompted (private
  networks only), or run once as admin:
  `netsh advfirewall firewall add rule name="Clinic 8000" dir=in action=allow protocol=TCP localport=8000`

Close the window to stop the app. The database survives restarts.

---

## 4. Backups

- Automatic daily backup of the database at the hour configured in
  **Paramètres** (default 20:00) while the app is running.
- Manual backup: **Paramètres → Sauvegarder maintenant**.
- Files land in `data\backups\clinic_YYYYMMDD_HHMMSS.dump` (compressed).
- Backups cover the whole database, so the laboratoire (work orders,
  supplier invoices) and stock (articles, movements, treatment links)
  tables are included automatically — nothing extra to configure.
- Retention: last 14 automatic + 5 manual backups; the most recent backup
  is never deleted.
- Restore drill (recommended once before go-live, then once a year):

```bat
:: 1) stop the app (close the start.bat window)
:: 2) copy the dump you want to test with, e.g.
::    copy data\backups\clinic_manual_SOMEDAY.dump data\backups\drill.dump
:: 3) restore
.venv\Scripts\python backend\app\cli.py restore --backup data\backups\drill.dump --yes
:: 4) start the app again and verify:
::    - a real or demo user can log in (sessions are reset by the restore)
::    - patients exist and patient_nr spot-check matches the day of the backup
::    - Paramètres shows the backup time recorded before the restore
:: 5) delete drill.dump after the drill passes
```

Copy the whole `data\backups` folder to a USB drive regularly.

---

## 5. Building the frontend (required before first deployment)

```bat
cd frontend
npm install
npm run generate
```

The build lands in `frontend\.output\public`; restart the server and it
serves the new build automatically. Re-run both commands only when the UI
was modified.

---

## 6. Pre-launch checklist

- [ ] Unique passwords set; demo accounts removed or renamed
- [ ] Do **not** run the demo seeder (`backend\seed_demo_tmp.py`) against the
      production database — it creates demo patients and generates one-time
      random logins printed only once
- [ ] `create-user` for every real staff member, owner flag only for the dentist
- [ ] Clinic name/doctor filled in **Paramètres**
- [ ] Backup hour confirmed, one manual backup run, restore drill done
- [ ] Second PC can open the app over the LAN
- [ ] `data\backups` reachable and included in the USB copy routine
- [ ] Server PC set to never sleep during clinic hours
