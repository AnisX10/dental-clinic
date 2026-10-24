@echo off
rem =======================================================================
rem  HKN Dentaire - Arret du serveur local
rem =======================================================================
call "%~dp0scripts\stop.bat" %*
if errorlevel 1 (
    echo.
    echo [ERREUR] Impossible d'arreter le serveur.
    pause
)
