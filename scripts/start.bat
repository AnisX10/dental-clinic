@echo off
rem Start the clinic application (single port :8000, API + UI).
setlocal enabledelayedexpansion
cd /d "%~dp0.."
set "ROOT_DIR=%cd%"

rem Priority 1: Isolated portable runtime (zero prerequisite)
if exist "%ROOT_DIR%\runtime\python.exe" (
    set "PY=%ROOT_DIR%\runtime\python.exe"
) else if exist "%ROOT_DIR%\.venv\Scripts\python.exe" (
    set "PY=%ROOT_DIR%\.venv\Scripts\python.exe"
) else (
    echo =======================================================================
    echo  [ERREUR] Environnement d'execution introuvable !
    echo =======================================================================
    echo.
    echo Le dossier 'runtime' ou '.venv' n'a pas ete trouve dans :
    echo %ROOT_DIR%
    echo.
    echo Si vous venez de telecharger l'archive, verifiez que tous les fichiers
    echo ont bien ete extraits.
    echo.
    if /i "%~1" neq "--no-pause" pause
    exit /b 1
)

echo =======================================================================
echo          HKN Dentaire - Demarrage de l'application
echo =======================================================================
echo.
echo Initialisation et verification de l'environnement...
echo.

"%PY%" "%ROOT_DIR%\backend\app\launcher.py" %*
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
