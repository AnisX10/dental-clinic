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

Create the first account (owner = the dentist). The command also creates the
database schema, the treatment catalogue and prints a pre-launch security
audit at the end:

```bat
.venv\Scripts\python backend\app\cli.py init-prod
```

Passwords must be at least 10 characters and mix letters, digits and a symbol.

### Licence activation (seller step)

The application starts **locked** until a signed licence file is installed.
Perpetual per-clinic licence; validation is fully offline (no internet needed).

1. Start the app once (`scripts\start.bat`); the log prints the
   **installation ID**, and the licence screen (shown instead of the login)
   displays it as well.
2. From the seller machine, issue the licence:

   ```bat
   .venv\Scripts\python tools\license.py issue --clinic "Clinique X" --dentist "Dr Y" --installation <installation-id>
   ```

3. Copy the produced `.lic` file into the clinic's `data\` folder (restart)
   or upload it from the licence screen — the app unlocks immediately.

The signing private key (`tools\license\private.pem`) never leaves the seller
and must never be committed. Each installation has a different ID, so a
licence file only works on that one database.

Then create the other accounts (owner flag only for the dentist):

```bat
.venv\Scripts\python backend\app\cli.py create-user --username reception --role reception --full-name "Réception"
```

You will be prompted for a password for each. Keep them private — these are
the only ways into patient data.

The treatment catalogue (21 entries, 7 categories) seeds itself on first
start. The database (PostgreSQL 16, bundled launcher) initializes itself in
`data\pgdata` — nothing to install.

---

## 3. Daily start & Desktop integration

### Option A: Desktop Shortcut (recommended for daily clinic use)

Run **`scripts\create_desktop_shortcut.bat`** once on the server PC.

- Creates an **HKN Dentaire** shortcut directly on the current user's Windows Desktop.
- Double-clicking the shortcut:
  1. Starts the clinic service silently in the background (if not already running).
  2. Opens the application in a clean, borderless app-window mode (`msedge.exe --app=http://127.0.0.1:8000` or `chrome.exe --app=http://127.0.0.1:8000`).
- If the server is already running, clicking the shortcut opens the app window immediately without spawning duplicate processes.

### Option B: Silent Background Start

Double-click **`scripts\start_silent.vbs`**.

- Launches `scripts\start.bat` invisibly (window style 0) so the Command Prompt does not clutter the clinic taskbar or risk accidental closure.

### Stopping the Server

Double-click **`scripts\stop.bat`**.

- Gracefully stops any running uvicorn clinic process on port 8000 and terminates launcher processes.

### Option C: Console Start (diagnostics)

Double-click **`scripts\start.bat`**.

- Starts the application with a visible Command Prompt window showing server logs.
- Close the window to stop the app.

---

### LAN Access (other PCs)

- The application listens on **http://127.0.0.1:8000** on the server PC.
- Other PCs on the LAN open **http://SERVER-PC-IP:8000** in the browser
  (find the IP with `ipconfig` — e.g. `http://192.168.1.20:8000`).
- Allow the app through the Windows firewall when prompted (private
  networks only), or run once as admin:
  `netsh advfirewall firewall add rule name="Clinic 8000" dir=in action=allow protocol=TCP localport=8000`

The database survives restarts.

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

### Off-site copy (strongly recommended)

A backup on the same disk dies with the disk. Point `backend\.env` at a
second location (second disk, USB auto-mount path, network share or a
cloud-sync folder), then restart the app:

```ini
CLINIC_BACKUP_OFFSITE_DIR=E:\ClinicBackups
```

Every successful backup (automatic or manual) is copied there immediately
with the same retention counts. The app never fails a backup because the
off-site copy failed — it just logs a warning — check the folder after the
first nightly backup to confirm it fills up.

### Automated monthly drill (throwaway restore test)

```bat
schtasks /Create /TN "ClinicBackupDrill" /SC MONTHLY /D 1 /ST 07:30 ^
  /TR "C:\path\to\dental-clinic-software\.venv\Scripts\python.exe C:\path\to\dental-clinic-software\backend\app\cli.py drill"
```

`cli.py drill` restores the newest backup into a throwaway `clinic_drill`
database, prints row counts (patients, treatments, payments, ...) and drops
it afterwards. Production data is never touched — safe to run while the app
is up. Run `... cli.py drill --keep` to inspect the scratch database manually.

### Full restore drill (recommended once before go-live, then once a year)

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

## 6. Upgrading to a new version

```bat
:: 1) stop the app (close the server window)
:: 2) replace the code (new copy of the repo folder, or `git pull` if using git)
::    reinstall backend deps only if requirements.txt changed:
::    .venv\Scripts\pip install -r backend\requirements.txt
:: 3) from backend\, run the safe upgrade (backup -> migrate -> frontend build):
::    .venv\Scripts\python app\cli.py upgrade
:: 4) start the app again (start.bat)
:: 5) verify: Paramètres shows the new Version; open a patient file
```

`cli.py upgrade` takes a pre-upgrade safety dump automatically, applies schema
migrations and rebuilds the frontend bundle. The installed version is visible
at the bottom of the **Paramètres** page and via `cli.py version`.

If `upgrade` skipped the frontend build because Node.js is missing, run
section 5 manually before restarting the app.

---

## 7. Pre-launch checklist

- [ ] `init-prod` run once (first owner created, security audit all `[OK]` or TODOs resolved)
- [ ] Unique passwords set; demo accounts removed or renamed
- [ ] Do **not** run the demo seeder (`backend\seed_demo_tmp.py`) against the
      production database — it creates demo patients and generates one-time
      random logins printed only once
- [ ] `create-user` for every real staff member, owner flag only for the dentist
- [ ] Clinic name/doctor filled in **Paramètres**
- [ ] Backup hour confirmed, one manual backup run, restore drill done
- [ ] Second PC can open the app over the LAN
- [ ] Desktop shortcut created via `scripts\create_desktop_shortcut.bat` on the server PC
- [ ] Verified `scripts\stop.bat` stops the service cleanly
- [ ] `data\backups` reachable and included in the USB copy routine
- [ ] Server PC set to never sleep during clinic hours
