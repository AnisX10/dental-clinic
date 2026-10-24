@echo off
rem =======================================================================
rem  HKN Dentaire - Automated 1-Click Installer for Windows
rem =======================================================================
setlocal enabledelayedexpansion
title HKN Dentaire - Assistant d'installation

rem Anchor to project root whether run from root or from scripts folder
set "SCRIPT_DIR=%~dp0"
if exist "%SCRIPT_DIR%backend" (
    set "ROOT_DIR=%SCRIPT_DIR%"
) else (
    set "ROOT_DIR=%SCRIPT_DIR%..\"
)
cd /d "%ROOT_DIR%"

echo =======================================================================
echo          HKN Dentaire - Installation automatique du cabinet
echo =======================================================================
echo.
echo Ce programme va configurer l'application sur cet ordinateur.
echo Aucun acces a Internet n'est requis si le dossier est complet.
echo.

echo [Etape 1/4] Detection automatique de Python...

set "TARGET_PY="

rem Check 1: Python launcher py
where py >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%p in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do (
        if exist "%%p" (
            "%%p" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
            if not errorlevel 1 set "TARGET_PY=%%p"
        )
    )
)

rem Check 2: Registry HKCU (CurrentUser installs)
if not defined TARGET_PY (
    for /f "tokens=2*" %%a in ('reg query "HKCU\Software\Python\PythonCore" /reg:64 /s /v "ExecutablePath" 2^>nul ^| findstr /i "ExecutablePath"') do (
        if exist "%%b" (
            "%%b" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
            if not errorlevel 1 if not defined TARGET_PY set "TARGET_PY=%%b"
        )
    )
)

rem Check 3: Registry HKLM (AllUsers installs)
if not defined TARGET_PY (
    for /f "tokens=2*" %%a in ('reg query "HKLM\Software\Python\PythonCore" /reg:64 /s /v "ExecutablePath" 2^>nul ^| findstr /i "ExecutablePath"') do (
        if exist "%%b" (
            "%%b" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
            if not errorlevel 1 if not defined TARGET_PY set "TARGET_PY=%%b"
        )
    )
)

rem Check 4: Standard user & program files folders
if not defined TARGET_PY (
    for /d %%v in (
        "%LocalAppData%\Programs\Python\Python3*"
        "C:\Program Files\Python3*"
        "C:\Python3*"
    ) do (
        if exist "%%v\python.exe" (
            "%%v\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
            if not errorlevel 1 if not defined TARGET_PY set "TARGET_PY=%%v\python.exe"
        )
    )
)

rem Check 5: Anaconda / Conda environments
if not defined TARGET_PY (
    for %%c in (
        "%USERPROFILE%\anaconda3\python.exe"
        "%USERPROFILE%\miniconda3\python.exe"
        "C:\ProgramData\Anaconda3\python.exe"
    ) do (
        if exist %%c (
            %%c -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
            if not errorlevel 1 if not defined TARGET_PY set "TARGET_PY=%%~c"
        )
    )
)

rem Check 6: PATH command (excluding Microsoft Store dummy stub)
if not defined TARGET_PY (
    for /f "delims=" %%p in ('where python 2^>nul') do (
        echo "%%p" | findstr /i "WindowsApps" >nul
        if errorlevel 1 (
            if exist "%%p" (
                "%%p" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
                if not errorlevel 1 if not defined TARGET_PY set "TARGET_PY=%%p"
            )
        )
    )
)

rem Check 7: Manual input if still not found
if not defined TARGET_PY (
    echo.
    echo Python n'a pas ete trouve automatiquement dans les dossiers standards.
    echo Si Python est installe dans un autre dossier, glissez-deposez
    echo le fichier python.exe dans cette fenetre ou tapez son chemin complet.
    set /p "CUSTOM_PY=[Chemin complet vers python.exe, ou appuyez sur Entree] : "
    if defined CUSTOM_PY (
        set "CUSTOM_PY=!CUSTOM_PY:"=!"
        if exist "!CUSTOM_PY!" (
            "!CUSTOM_PY!" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
            if not errorlevel 1 set "TARGET_PY=!CUSTOM_PY!"
        )
    )
)

if not defined TARGET_PY (
    echo.
    echo =======================================================================
    echo  [ATTENTION] Impossible de localiser Python sur cet ordinateur !
    echo =======================================================================
    echo.
    echo Pour continuer, installez Python ou ajoutez-le a PATH :
    echo   1. Si Python est deja installe : relancez son installateur,
    echo      choisissez "Modify", puis cochez "Add Python to environment variables".
    echo   2. Si vous installez un nouveau Python 3.11 :
    echo      IMPORTANT : Sur le premier ecran, cochez la case en bas :
    echo      [x] "Add python.exe to PATH"
    echo   3. Relancez ensuite cet installateur.
    echo.
    pause
    exit /b 1
)

for /f "delims=" %%v in ('"!TARGET_PY!" --version 2^>^&1') do set "PY_VER=%%v"
echo  - Python localise : !TARGET_PY! (!PY_VER!)
echo.

rem Step 2: Virtual environment
echo [Etape 2/4] Preparation de l'environnement virtuel (.venv)...
if not exist ".venv\Scripts\python.exe" (
    "!TARGET_PY!" -m venv .venv
    if errorlevel 1 (
        echo [ERREUR] Impossible de creer l'environnement virtuel.
        pause
        exit /b 1
    )
)
echo  - Installation des composants internes...
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt --no-warn-script-location >nul 2>&1
if errorlevel 1 (
    echo  - Installation detaillee...
    .venv\Scripts\python.exe -m pip install -r backend\requirements.txt
)
echo  - Environnement pret.
echo.

rem Step 3: Database & Doctor Account setup
echo [Etape 3/4] Configuration du cabinet et compte administrateur...
echo.
echo Veuillez saisir les informations du medecin responsable :
echo.
set /p DOC_NAME="Nom complet du medecin (ex: Dr. Benali Amine) : "
if "%DOC_NAME%"=="" set "DOC_NAME=Dr. Dentiste"

set /p DOC_USER="Identifiant de connexion (ex: dentiste) : "
if "%DOC_USER%"=="" set "DOC_USER=dentiste"

set /p DOC_PASS="Mot de passe de securite (au moins 8 caracteres) : "
if "%DOC_PASS%"=="" set "DOC_PASS=Cabinet2026!"

echo.
echo Initialisation de la base de donnees et du catalogue dentaire...
.venv\Scripts\python.exe backend\app\cli.py init-prod --username "%DOC_USER%" --password "%DOC_PASS%" --full-name "%DOC_NAME%"
if errorlevel 1 (
    echo.
    echo [NOTE] La base semble deja initialisee ou une erreur est survenue.
    echo Les donnees existantes sont conservees.
)
echo.

rem Step 4: Create Desktop shortcut
echo [Etape 4/4] Creation du raccourci sur le Bureau Windows...
if exist "scripts\create_desktop_shortcut.bat" (
    call "scripts\create_desktop_shortcut.bat"
)
echo.

echo =======================================================================
echo          Installation terminee avec succes !
echo =======================================================================
echo.
echo Pour demarrer :
echo   - Double-cliquez sur l'icone "HKN Dentaire" sur votre Bureau.
echo   - Identifiant : %DOC_USER%
echo   - Mot de passe : (celui saisi ci-dessus)
echo.
echo Si l'application vous demande une licence lors de la premiere ouverture,
echo transmettez simplement le "Numero d'installation" affiche a l'ecran.
echo.
pause
