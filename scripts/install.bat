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

echo [Etape 1/4] Detection de Python 3.11...

set "TARGET_PY="
set "WRONG_VER_PY="

rem Priority 1: Check Python 3.11 specifically via py launcher
where py >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%p in ('py -3.11 -c "import sys; print(sys.executable)" 2^>nul') do (
        if exist "%%p" set "TARGET_PY=%%p"
    )
)

rem Priority 2: Check standard Python 3.11 paths directly
if not defined TARGET_PY (
    for %%d in (
        "%LocalAppData%\Programs\Python\Python311\python.exe"
        "C:\Program Files\Python311\python.exe"
        "C:\Python311\python.exe"
    ) do (
        if not defined TARGET_PY if exist %%d set "TARGET_PY=%%~d"
    )
)

rem Priority 3: Check Registry for Python 3.11
if not defined TARGET_PY (
    for /f "tokens=2*" %%a in ('reg query "HKCU\Software\Python\PythonCore\3.11\InstallPath" /reg:64 /v "ExecutablePath" 2^>nul ^| findstr /i "ExecutablePath"') do (
        if exist "%%b" set "TARGET_PY=%%b"
    )
)
if not defined TARGET_PY (
    for /f "tokens=2*" %%a in ('reg query "HKLM\Software\Python\PythonCore\3.11\InstallPath" /reg:64 /v "ExecutablePath" 2^>nul ^| findstr /i "ExecutablePath"') do (
        if exist "%%b" set "TARGET_PY=%%b"
    )
)

rem If Python 3.11 is not found, check if a newer incompatible Python (3.12, 3.13) or older is present
if not defined TARGET_PY (
    where py >nul 2>&1
    if not errorlevel 1 (
        for /f "delims=" %%p in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do (
            if exist "%%p" set "WRONG_VER_PY=%%p"
        )
    )
    if not defined WRONG_VER_PY (
        for /d %%v in (
            "%LocalAppData%\Programs\Python\Python3*"
            "C:\Program Files\Python3*"
            "C:\Python3*"
        ) do (
            if exist "%%v\python.exe" set "WRONG_VER_PY=%%v\python.exe"
        )
    )
    if not defined WRONG_VER_PY (
        for /f "delims=" %%p in ('where python 2^>nul') do (
            echo "%%p" | findstr /i "WindowsApps" >nul
            if errorlevel 1 (
                if exist "%%p" set "WRONG_VER_PY=%%p"
            )
        )
    )
)

rem If an incompatible Python version is detected, warn the user clearly
if not defined TARGET_PY if defined WRONG_VER_PY (
    for /f "delims=" %%v in ('"!WRONG_VER_PY!" --version 2^>^&1') do set "DETECTED_VER=%%v"
    echo.
    echo =======================================================================
    echo  [ATTENTION] Version de Python incompatible detectee : !DETECTED_VER!
    echo =======================================================================
    echo.
    echo Ce PC possede !DETECTED_VER!, mais la base de donnees embarquee
    echo sans installation necessite imperativement Python 3.11.
    echo.
    echo Pour resoudre ce probleme simplement :
    echo   1. Telechargez ou lancez l'installateur 'python-3.11.9-amd64.exe'.
    echo   2. Installez Python 3.11 (en cochant "Add python.exe to PATH").
    echo   3. Relancez cet assistant d'installation.
    echo.
    echo Note : Vous pouvez conserver votre version actuelle de Python,
    echo Python 3.11 s'installe a cote sans aucun conflit.
    echo.
    pause
    exit /b 1
)

rem If nothing was detected at all
if not defined TARGET_PY (
    echo.
    echo =======================================================================
    echo  [ATTENTION] Python 3.11 n'a pas ete trouve sur cet ordinateur !
    echo =======================================================================
    echo.
    echo Pour continuer, veuillez installer Python 3.11 :
    echo   1. Lancez l'installateur 'python-3.11.9-amd64.exe'.
    echo   2. IMPORTANT : Sur le premier ecran, cochez la case en bas :
    echo      [x] "Add python.exe to PATH"
    echo   3. Cliquez sur "Install Now".
    echo   4. Relancez ensuite cet installateur.
    echo.
    pause
    exit /b 1
)

for /f "delims=" %%v in ('"!TARGET_PY!" --version 2^>^&1') do set "PY_VER=%%v"
echo  - Python 3.11 detecte : !TARGET_PY! (!PY_VER!)
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
