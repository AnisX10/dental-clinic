# HKN Dentaire — Installation & User Guide Book
### The Complete Step-by-Step Guide for Dental Clinics

Welcome to **HKN Dentaire**! This guide is written in plain, simple language for dentists, clinic managers, and assistants. You do not need to be a software developer or IT expert to install and run this application.

---

## 📋 What You Need Before You Start

Everything runs **100% locally on your computer**. No internet connection is needed during normal clinic operations.

You only need:
1. **A Windows PC** (Windows 10 or 11) with at least 4 GB of RAM.
2. **Python 3.11** (the installer file `python-3.11.x-amd64.exe` is usually included on your installation USB drive).
3. **The Software Package** (`clinic-app-standalone-20261023.zip`).

---

## 🚀 Fast 1-Click Installation (Recommended)

Follow these **4 simple steps**:

### Step 1: Install Python (2 Minutes)
If Python is not already installed on your computer:
1. Double-click the Python installer file (`python-3.11.x-amd64.exe`).
2. ⚠️ **VERY IMPORTANT:** At the bottom of the first setup screen, check the box that says:
   ```
   [x] Add python.exe to PATH
   ```
3. Click **Install Now** and wait for it to finish.
4. Click **Close**.

---

### Step 2: Unzip the Software
1. Create a folder directly on your main drive: `C:\clinic`
2. Extract the contents of your software ZIP file into this `C:\clinic` folder.
   *(You should now see folders like `backend`, `frontend`, `scripts`, and a file named `install.bat`).*

---

### Step 3: Run the 1-Click Installer
1. Inside `C:\clinic`, double-click:
   👉 **`install.bat`**
2. A window will appear and handle the setup automatically:
   - It verifies that Python is ready.
   - It sets up the internal clinic system.
   - It will ask you for 3 quick details:
     - **Doctor's Name** *(e.g., `Dr. Benali Amine`)*
     - **Username for login** *(e.g., `dentiste`)*
     - **Password** *(e.g., your personal password)*
3. It will automatically create an **"HKN Dentaire"** icon on your Windows Desktop!

---

### Step 4: First-Time Activation (30 Seconds)
1. Double-click the new **HKN Dentaire** icon on your Desktop.
2. The application opens in its own window.
3. Because this is a new installation, you will see the **Licence inactive** screen displaying your unique:
   ```
   Installation ID: e.g. cf7a4f1b3c5049d1b82e8506f2e25cfb
   ```
4. Simply send or read this Installation ID to your software provider.
5. They will send you your clinic's license file (e.g., `cabinet-nom.lic`).
6. Click **"Installer la licence"** on the screen, select the file, and click Open.

🎉 **Congratulations!** Your clinic system is activated and ready for patients.

---

## 🖥️ Daily Clinic Routine

### How to Open the App
- Just double-click the **HKN Dentaire** shortcut on your Desktop.
- The app launches directly into its clean, distraction-free window.

### Connecting a Second Computer (Reception Desk)
If your clinic has a reception desk or a second computer in the treatment room:
1. Connect both computers to the clinic's local Wi-Fi or router network. *(Internet connection is NOT required, just local network).*
2. On the main server PC, open Command Prompt and type `ipconfig` to find its local IP (for example: `192.168.1.15`).
3. On the reception PC, open Chrome or Edge and go to:
   ```
   http://192.168.1.15:8000
   ```
4. The receptionist can log in using their own reception account!

### How to Close the App
- You can simply close the browser window when leaving.
- If you wish to shut down the background server completely at the end of the day, double-click:
  `C:\clinic\scripts\stop.bat`

---

## 💾 Backups & Safety (Protecting Patient Records)

Your clinic's data is precious. HKN Dentaire includes built-in automated protection:

### Automatic Daily Backup
- Every evening at **20:00 (8:00 PM)**, the application automatically creates a complete backup of all patients, treatments, notes, and financial records into:
  `C:\clinic\data\backups\`
- You can change the backup hour anytime in **Paramètres → Sauvegarde**.

### Manual Instant Backup (Before Leaving)
1. In the app menu, go to **Paramètres**.
2. Scroll to the **Sauvegarde** section.
3. Click **"Sauvegarder maintenant"**.
4. A confirmation message will appear with the date and file size.

> [!TIP]
> **Best Practice:** Keep an inexpensive USB flash drive plugged into your computer and copy the `C:\clinic\data\backups` folder onto it once a week. If your computer ever breaks or gets lost, your clinic records can be restored in 5 minutes!

---

## 🖨️ Printing Prescriptions & Documents

When printing ordonnances, medical certificates, or devis:
1. The first time you click **Imprimer**, a small reminder dialog will open.
2. In the Google Chrome / Microsoft Edge print window:
   - **Margins:** Select **"Default"** *(Par défaut)*.
   - **Options:** Make sure **"Background graphics"** *(Graphiques d'arrière-plan)* is **checked**.
3. This ensures clinic logos, watermarks, and header lines print crisp and centered on A4 paper.

---

## ❓ Troubleshooting & Frequently Asked Questions

#### Q1: When I double-click `install.bat`, it says Python is not detected.
- **Fix:** You need to install Python 3.11. Run the installer `python-3.11.x-amd64.exe` and make sure you check the box at the bottom: **[x] Add python.exe to PATH**. Then re-run `install.bat`.

#### Q2: The screen says "Port 8000 already in use".
- **Fix:** Another copy of the app is already running! Go into `C:\clinic\scripts\` and double-click **`stop.bat`**, then reopen your Desktop icon.

#### Q3: Can the clinic staff accidentally delete or overwrite files?
- **No.** The application stores all data in a safe, structured database. Staff can only add, view, or update patient files according to their role (Dentist vs Receptionist).

#### Q4: What happens if our clinic internet goes down?
- **Nothing!** The software does not use the internet. You can continue consulting patients, recording treatments, and printing ordonnances without any interruption.

---

## 📞 Support & License Re-issuance
If you move your clinic software to a brand-new computer:
1. Install following this guide.
2. Provide your new Installation ID to your software provider.
3. Your provider will issue an updated `.lic` file free of charge for your clinic.
