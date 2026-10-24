@echo off
rem Start the clinic application (single port :8000, API + UI).
setlocal enabledelayedexpansion
cd /d "%~dp0.."

set "PY=%cd%\.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo =======================================================================
    echo  [ERREUR] L'application n'est pas encore installee sur ce PC !
    echo =======================================================================
    echo.
    echo Le dossier d'environnement virtuel .venv n'a pas ete trouve.
    echo Veuillez executer install.bat a la racine du dossier pour l'installer.
    echo.
    pause
    exit /b 1
)

rem Pre-flight: Check if server is already running on port 8000
call :CheckPort8000
if "!PORT_8000_ALREADY_ACTIVE!"=="1" (
    echo =======================================================================
    echo  [INFO] Le serveur HKN Dentaire est DEJA en cours d'execution !
    echo =======================================================================
    echo.
    echo L'application est deja active sur : http://127.0.0.1:8000
    echo Ouverture de l'application dans votre navigateur...
    start http://127.0.0.1:8000
    echo.
    echo Pour arreter ou redemarrer le serveur :
    echo   - Double-cliquez sur "stop.bat"
    echo.
    if /i "%~1" neq "--no-pause" pause
    exit /b 0
)

echo =======================================================================
echo          HKN Dentaire - Demarrage du serveur local
echo =======================================================================
echo.
echo Serveur actif sur : http://127.0.0.1:8000
echo Base de donnees et fichiers stockes dans le dossier "data".
echo.
echo Gardez cette fenetre ouverte pendant l'utilisation du cabinet.
echo Fermez cette fenetre pour arreter le serveur.
echo.

"%PY%" -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
set "EXIT_CODE=%ERRORLEVEL%"
if %EXIT_CODE% neq 0 (
    echo.
    echo =======================================================================
    echo  [ERREUR] Le serveur s'est arrete avec le code d'erreur %EXIT_CODE%.
    echo =======================================================================
    echo.
    if /i "%~1" neq "--no-pause" pause
)
exit /b %EXIT_CODE%

:CheckPort8000
set "PORT_8000_ALREADY_ACTIVE=0"
"%PY%" -c "import socket; s = socket.socket(); s.settimeout(0.3); res = s.connect_ex(('127.0.0.1', 8000)); s.close(); exit(0 if res == 0 else 1)" >nul 2>&1
if errorlevel 1 exit /b 0

rem Port 8000 is open. Check if health check responds.
"%PY%" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=1)" >nul 2>&1
if not errorlevel 1 (
    set "PORT_8000_ALREADY_ACTIVE=1"
    exit /b 0
)

rem Port 8000 is occupied but not responding, kill stale process
echo [INFO] Port 8000 occupe par un ancien processus. Nettoyage en cours...
call "%~dp0stop.bat" >nul 2>&1
ping -n 2 127.0.0.1 >nul 2>&1
exit /b 0
