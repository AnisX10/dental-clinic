@echo off
rem =======================================================================
rem  HKN Dentaire - Automated 1-Click Installer for Windows
rem =======================================================================
call "%~dp0scripts\install.bat" %*
if errorlevel 1 (
    echo.
    echo [ERREUR] L'assistant d'installation s'est termine avec une erreur.
    pause
)
