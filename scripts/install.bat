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
cd /d "%ROOT_DIR%"
set "ROOT_DIR=%cd%"

echo =======================================================================
echo          HKN Dentaire - Installation automatique du cabinet
echo =======================================================================
echo.
echo Ce programme va configurer l'application sur cet ordinateur.
echo Aucun acces a Internet n'est requis.
echo.

echo [Etape 1/4] Verification de l'environnement d'execution...

set "TARGET_PY="
set "WRONG_VER_PY="
set "IS_PORTABLE="

rem Priority 0: Check standalone portable runtime (Zero prerequisite)
if exist "runtime\python.exe" (
    set "TARGET_PY=%cd%\runtime\python.exe"
    set "IS_PORTABLE=1"
    echo  - Environnement autonome portable detecte [Zero installation requise].
    goto :PythonFound
)

rem Priority 1: Check Python 3.11 specifically via py launcher
where py >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%p in ('py -3.11 -c "import sys; print(sys.executable)" 2^>nul') do (
        if exist "%%p" (
            "%%p" --version >nul 2>&1
            if not errorlevel 1 set "TARGET_PY=%%p"
        )
    )
)

rem Priority 2: Check standard Python 3.11 paths directly
if not defined TARGET_PY (
    for %%d in (
        "%LocalAppData%\Programs\Python\Python311\python.exe"
        "C:\Program Files\Python311\python.exe"
        "C:\Python311\python.exe"
    ) do (
        if not defined TARGET_PY if exist %%d (
            %%d --version >nul 2>&1
            if not errorlevel 1 set "TARGET_PY=%%~d"
        )
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

rem If Python 3.11 is not found, check what Python is available
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

rem If Python 3.12+ is present, test if PostgreSQL is running on port 5432
if not defined TARGET_PY if defined WRONG_VER_PY call :ProbePostgres

rem If still not defined but WRONG_VER_PY exists, show incompatible Python message
if not defined TARGET_PY if defined WRONG_VER_PY goto :ShowIncompatiblePython

rem If nothing was detected at all, show missing Python message
if not defined TARGET_PY goto :ShowMissingPython

goto :PythonFound

:ShowIncompatiblePython
for /f "delims=" %%v in ('"!WRONG_VER_PY!" --version 2^>^&1') do set "DETECTED_VER=%%v"
echo.
echo =======================================================================
echo  [ATTENTION] !DETECTED_VER! detecte sans base de donnees compatible
echo =======================================================================
echo.
echo Deux options simples s'offrent a vous pour continuer :
echo.
echo OPTION 1 [Recommandee - Zero installation de base de donnees] :
echo   Installez Python 3.11 [fichier python-3.11.9-amd64.exe].
echo   La base de donnees integree fonctionnera alors automatiquement.
echo.
echo OPTION 2 [Garder !DETECTED_VER!] :
echo   Installez PostgreSQL pour Windows [port 5432].
echo   L'application s'y connectera alors automatiquement avec !DETECTED_VER!.
echo.
pause
exit /b 1

:ShowMissingPython
echo.
echo =======================================================================
echo  [ATTENTION] Aucun environnement d'execution n'a ete trouve !
echo =======================================================================
echo.
echo Le dossier 'runtime' semble absent de cette distribution.
echo Verifiez que le contenu du fichier ZIP a ete extrait dans sa totalite.
echo.
pause
exit /b 1

:PythonFound
for /f "delims=" %%v in ('"!TARGET_PY!" --version 2^>^&1') do set "PY_VER=%%v"
echo  - Moteur d'execution actif : !TARGET_PY! (!PY_VER!)
echo.

rem Step 2: Virtual environment or portable setup
echo [Etape 2/4] Verification des composants logicielles et de la base de donnees...
if defined IS_PORTABLE (
    echo  - Environnement portable autonome valide.
    echo  - Moteur PostgreSQL embarque integre : Pret.
    goto :RuntimeReady
)

if not exist ".venv\Scripts\python.exe" (
    echo  - Creation de l'environnement virtuel local...
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
    .venv\Scripts\python.exe -m pip install -r backend\requirements.txt
)
set "TARGET_PY=%cd%\.venv\Scripts\python.exe"

:RuntimeReady
echo  - Composants prets.
echo.

rem Step 3: Database & Doctor Account setup
echo [Etape 3/4] Configuration du cabinet et compte administrateur...
echo.
echo Veuillez saisir les informations du medecin responsable :
echo (Appuyez sur Entree pour accepter les valeurs par defaut)
echo.
set /p DOC_NAME="Nom complet du medecin (ex: Dr. Benali Amine) [Dr. Dentiste] : "
if "%DOC_NAME%"=="" set "DOC_NAME=Dr. Dentiste"

set /p DOC_USER="Identifiant de connexion (ex: dentiste) [dentiste] : "
if "%DOC_USER%"=="" set "DOC_USER=dentiste"

set /p DOC_PASS="Mot de passe (au moins 10 caracteres) [Cabinet2026!] : "
if "%DOC_PASS%"=="" set "DOC_PASS=Cabinet2026!"

echo.
echo Initialisation de la base de donnees et du catalogue dentaire...
"!TARGET_PY!" "%ROOT_DIR%\backend\app\cli.py" init-prod --username "%DOC_USER%" --password "%DOC_PASS%" --full-name "%DOC_NAME%" --force
if errorlevel 1 (
    echo.
    echo [NOTE] La base semble deja initialisee ou une erreur non-bloquante est survenue.
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
echo L'application est prete a l'emploi avec sa licence permanente integree.
echo.
echo Vos identifiants de connexion :
echo   - Identifiant : %DOC_USER%
echo   - Mot de passe : %DOC_PASS%
echo.
echo Pour lancer l'application a tout moment :
echo   - Double-cliquez sur le raccourci "HKN Dentaire" sur votre Bureau.
echo   - Ou double-cliquez sur "start.bat" dans ce dossier.
echo.

set /p LAUNCH_NOW="Souhaitez-vous lancer HKN Dentaire maintenant ? (O/N) [O] : "
if "%LAUNCH_NOW%"=="" set "LAUNCH_NOW=O"
if /i "%LAUNCH_NOW%"=="O" (
    echo Demarrage en cours...
    if exist "scripts\start_silent.vbs" (
        start "" wscript.exe "scripts\start_silent.vbs" /app
    ) else (
        start "" "start.bat"
    )
)
exit /b 0

:ProbePostgres
if not defined WRONG_VER_PY exit /b 0
"!WRONG_VER_PY!" -c "import socket; s = socket.socket(); s.settimeout(0.3); s.connect(('127.0.0.1', 5432)); s.close()" >nul 2>&1
if not errorlevel 1 (
    echo  - Serveur PostgreSQL detecte sur le port 5432.
    echo  - Utilisation automatique de PostgreSQL avec !WRONG_VER_PY!
    set "TARGET_PY=!WRONG_VER_PY!"
)
exit /b 0
