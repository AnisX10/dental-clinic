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
