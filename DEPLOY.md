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
- Node.js is only needed if you rebuild the frontend; the repository ships
  with a ready-made build in `frontend/.output/public`.

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
start. The database (PostgreSQL 16) is bundled and initializes itself in
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
- Retention: last 14 automatic + 5 manual backups; the most recent backup
  is never deleted.
- Restore drill (recommended once before go-live):

```bat
:: stop the app, then
.venv\Scripts\python backend\app\cli.py restore --backup data\backups\<file>.dump
```

Copy the whole `data\backups` folder to a USB drive regularly.

---

## 5. Updating the frontend (optional)

Only if the UI was modified:

```bat
cd frontend
npm install
npm run generate
```

Then restart the server; it serves the new build automatically.

---

## 6. Pre-launch checklist

- [ ] Unique passwords set; demo accounts removed or renamed
- [ ] `create-user` for every real staff member, owner flag only for the dentist
- [ ] Clinic name/doctor filled in **Paramètres**
- [ ] Backup hour confirmed, one manual backup run, restore drill done
- [ ] Second PC can open the app over the LAN
- [ ] `data\backups` reachable and included in the USB copy routine
- [ ] Server PC set to never sleep during clinic hours
