@echo off
rem =======================================================================
rem  HKN Dentaire - Reinitialisation du compte principal (mot de passe oublie)
rem =======================================================================
setlocal DisableDelayedExpansion
title HKN Dentaire - Reinitialisation du mot de passe

set "SCRIPT_DIR=%~dp0"
if exist "%SCRIPT_DIR%backend\app\main.py" goto :root_scripts
if exist "%SCRIPT_DIR%..\backend\app\main.py" goto :root_parent
echo [ERREUR] Installation incomplete.
pause
exit /b 1

:root_scripts
set "ROOT_DIR=%SCRIPT_DIR:~0,-1%"
goto :root_done

:root_parent
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"

:root_done
cd /d "%ROOT_DIR%"

set "PY=%ROOT_DIR%\runtime\python.exe"
if not exist "%PY%" set "PY=%ROOT_DIR%\.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo [ERREUR] Environnement Python introuvable.
    pause
    exit /b 1
)

echo.
echo Cette operation remplace le nom d'utilisateur et le mot de passe du
echo compte principal. Les donnees patients ne sont PAS modifiees.
echo.
set "NEW_USER=dentiste"
set /p NEW_USER="Nom d'utilisateur [dentiste] : "
if "%NEW_USER%"=="" set "NEW_USER=dentiste"
set "NEW_PASS="
set /p NEW_PASS="Nouveau mot de passe (10+ caracteres, lettres+chiffres+symbole) : "
if "%NEW_PASS%"=="" goto :need_pass
goto :confirm

:need_pass
echo [!] Le mot de passe ne peut pas etre vide.
set /a PASS_TRIES+=1
if %PASS_TRIES% GTR 5 goto :too_many_pass
set "NEW_PASS="
set /p NEW_PASS="Nouveau mot de passe : "
if "%NEW_PASS%"=="" goto :need_pass
goto :confirm_name

:too_many_pass
echo [ERREUR] Trop de tentatives - operation annulee.
ping -n 6 127.0.0.1 >nul
exit /b 1

:confirm_name
set "NEW_NAME="
set /p NEW_NAME="Nom complet du dentiste [Dr. Dentiste] : "
if "%NEW_NAME%"=="" set "NEW_NAME=Dr. Dentiste"

:confirm
echo.
echo Remplacement du compte principal par : %NEW_USER% (%NEW_NAME%)
set /p GO="Confirmer la reinitialisation ? (O/N) [N] : "
if /i not "%GO%"=="O" goto :aborted

set "CLINIC_INIT_USERNAME=%NEW_USER%"
set "CLINIC_INIT_PASSWORD=%NEW_PASS%"
set "CLINIC_INIT_FULLNAME=%NEW_NAME%"
"%PY%" "%ROOT_DIR%\backend\app\cli.py" init-prod --force
if errorlevel 1 goto :failed
set "CLINIC_INIT_USERNAME="
set "CLINIC_INIT_PASSWORD="
set "CLINIC_INIT_FULLNAME="
echo.
echo Reinitialisation terminee. Connectez-vous avec le nouveau mot de passe.
echo.
pause
exit /b 0

:aborted
echo Annule. Aucune modification effectuee.
echo.
pause
exit /b 0

:failed
set "CLINIC_INIT_USERNAME="
set "CLINIC_INIT_PASSWORD="
set "CLINIC_INIT_FULLNAME="
echo [ERREUR] La reinitialisation a echoue. Contactez le support.
echo.
pause
exit /b 1
