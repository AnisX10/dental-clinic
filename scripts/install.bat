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

rem Step 1: Check Python
echo [Etape 1/4] Verification de Python...
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo =======================================================================
    echo  [ATTENTION] Python 3.11 ou superieur n'est pas detecte sur ce PC !
    echo =======================================================================
    echo.
    echo Pour continuer, veuillez installer Python :
    echo   1. Lancez l'installateur 'python-3.11.x-amd64.exe'.
    echo   2. IMPORTANT : Cochez imperativement la case en bas :
    echo      [x] "Add python.exe to PATH"
    echo   3. Cliquez sur "Install Now".
    echo   4. Relancez cet assistant d'installation.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version') do set "PY_VER=%%v"
echo  - %PY_VER% detecte avec succes.
echo.

rem Step 2: Virtual environment
echo [Etape 2/4] Preparation de l'environnement virtuel (.venv)...
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 (
        echo [ERREUR] Impossible de creer l'environnement virtuel.
        pause
        exit /b 1
    )
)
echo  - Installation des composants internes...
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt --no-warn-script-location >nul 2>&1
if errorlevel 1 (
    echo  - Tentative sans options avancees...
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
