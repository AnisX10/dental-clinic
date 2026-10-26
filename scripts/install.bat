@echo off
rem =======================================================================
rem  HKN Dentaire - Installation / mise a jour (Windows)
rem  - Aucun accès Internet requis
rem  - Donnees conservees lors des mises a jour
rem =======================================================================
setlocal DisableDelayedExpansion
title HKN Dentaire - Assistant d'installation

rem --- resolve project root (works from scripts\ or repo root) ------------
set "SCRIPT_DIR=%~dp0"
if exist "%SCRIPT_DIR%backend\app\main.py" goto :root_scripts
if exist "%SCRIPT_DIR%..\backend\app\main.py" goto :root_parent
echo [ERREUR] Dossier d'installation incomplet (backend\app absent).
echo Verifiez que le ZIP a ete extrait entierement.
pause
exit /b 1

:root_scripts
set "ROOT_DIR=%SCRIPT_DIR:~0,-1%"
goto :root_done

:root_parent
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"

:root_done
cd /d "%ROOT_DIR%"

echo =======================================================================
echo         HKN Dentaire - Installation automatique du cabinet
echo =======================================================================
echo.
echo Ce programme configure l'application sur cet ordinateur.
echo Aucun acces a Internet n'est requis.
echo.

rem --- Step 1/5: runtime integrity ----------------------------------------
echo [Etape 1/5] Verification de l'environnement d'execution...
set "PY=%ROOT_DIR%\runtime\python.exe"
if not exist "%PY%" goto :runtime_missing
"%PY%" -c "import fastapi, uvicorn, psycopg, alembic, sqlalchemy, pydantic" 1>nul 2>&1
if errorlevel 1 goto :runtime_corrupt
echo  - Environnement autonome portable: OK.
echo.

rem --- Step 2/5: port check ------------------------------------------------
echo [Etape 2/5] Verification du port d'ecoute (8000)...
set "PORT_STATE=FREE"
for /f %%s in ('powershell -NoProfile -Command "$c=Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue; if($c){$p=$c[0].OwningProcess; $cl=(Get-CimInstance Win32_Process -Filter \"ProcessId=$p\").CommandLine; if($cl -and $cl -match 'app\\launcher\.py'){Write-Output 'OURS'}else{Write-Output 'FOREIGN'}}else{Write-Output 'FREE'}" 2^>nul') do set "PORT_STATE=%%s"
if "%PORT_STATE%"=="FOREIGN" goto :port_foreign
if "%PORT_STATE%"=="FREE" goto :port_ok
echo  - L'application tourne deja. Arret propre pour l'installation...
call "%ROOT_DIR%\scripts\stop.bat"
powershell -NoProfile -Command "$c=Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue; if($c){Write-Output 'FOREIGN'}else{Write-Output 'FREE'}" 2>nul | findstr /x "FREE" >nul
if errorlevel 1 goto :port_foreign
:port_ok
echo  - Port libre.
echo.

rem --- Step 3/5: first install or update -----------------------------------
echo [Etape 3/5] Configuration du cabinet...
echo.
set "FIRST=Y"
set /p FIRST="Premiere installation (O) ou mise a jour (N) ? [O] : "
if "%FIRST%"=="" set "FIRST=Y"
if /i "%FIRST%"=="O" set "FIRST=Y"
if /i "%FIRST%"=="N" set "FIRST=N"
if "%FIRST%"=="N" goto :update_mode

rem ---- collect credentials (required, no default password) ----
echo.
echo Creation du compte principal de la clinique :
echo   (mot de passe : 10 caracteres ou plus, lettres et chiffres,
echo    avec au moins un symbole ! ? @ # - _ )
echo.
set "DOC_NAME="
set /p DOC_NAME="Nom complet du dentiste (ex: Dr. Benali Amine) : "
if "%DOC_NAME%"=="" goto :cred_retry_name
set "DOC_USER="
set /p DOC_USER="Nom d'utilisateur (ex: dentiste) : "
if "%DOC_USER%"=="" goto :cred_retry_user
set "DOC_PASS="
set /p DOC_PASS="Mot de passe : "
if "%DOC_PASS%"=="" goto :cred_retry_pass
if "%DOC_PASS%"=="%DOC_NAME%" goto :cred_same
echo.
echo Compte : %DOC_USER%  /  clinique : %DOC_NAME%
set /p CONFIRM="Confirmer ? (O/N) [O] : "
if "%CONFIRM%"=="" set "CONFIRM=O"
if /i not "%CONFIRM%"=="O" goto :cred_retry_name
goto :run_init

:cred_retry_name
echo [!] Saisissez le nom complet du dentiste.
goto :cred_name_again
:cred_name_again
set /a CRED_TRIES+=1
if %CRED_TRIES% GTR 5 goto :cred_abandon
set "DOC_NAME="
set /p DOC_NAME="Nom complet du dentiste : "
if "%DOC_NAME%"=="" goto :cred_name_again
set "DOC_USER="
set /p DOC_USER="Nom d'utilisateur : "
if "%DOC_USER%"=="" goto :cred_name_again
set "DOC_PASS="
set /p DOC_PASS="Mot de passe : "
if "%DOC_PASS%"=="" goto :cred_name_again
if "%DOC_PASS%"=="%DOC_NAME%" goto :cred_same
goto :run_init

:cred_abandon
echo.
echo [ERREUR] Saisie invalide trop de fois - installation annulee.
echo Relancez l'installation pour reessayer.
ping -n 6 127.0.0.1 >nul
exit /b 1

:cred_retry_user
echo [!] Saisissez le nom d'utilisateur.
goto :cred_name_again

:cred_retry_pass
echo [!] Le mot de passe ne peut pas etre vide.
goto :cred_name_again

:cred_same
echo [!] Le mot de passe doit differer du nom de la clinique.
goto :cred_name_again

:update_mode
echo.
echo Mode mise a jour : vos donnees et votre compte sont conserves.
goto :run_steps

:run_init
echo.
echo Initialisation de la base de donnees et du catalogue dentaire...
set "CLINIC_INIT_USERNAME=%DOC_USER%"
set "CLINIC_INIT_PASSWORD=%DOC_PASS%"
set "CLINIC_INIT_FULLNAME=%DOC_NAME%"
"%PY%" "%ROOT_DIR%\backend\app\cli.py" init-prod
set "INIT_RC=%ERRORLEVEL%"
set "CLINIC_INIT_USERNAME="
set "CLINIC_INIT_PASSWORD="
set "CLINIC_INIT_FULLNAME="
if not "%INIT_RC%"=="0" goto :init_failed

rem --- Step 4/5: shortcuts --------------------------------------------------
:run_steps
echo.
echo [Etape 4/5] Creation des raccourcis (Bureau + Menu Demarrer)...
if not exist "%ROOT_DIR%\scripts\make_shortcuts.ps1" goto :shortcut_failed
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT_DIR%\scripts\make_shortcuts.ps1" -RootDir "%ROOT_DIR%" 1>nul 2>&1
if not "%ERRORLEVEL%"=="0" goto :shortcut_failed
echo  - Raccourcis crees.
goto :step5

:shortcut_missing
echo [INFO] Raccourci natif absent ^(exe non livre^) - raccourci en mode compatibilite...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT_DIR%\scripts\make_shortcuts.ps1" -RootDir "%ROOT_DIR%" -Fallback 1>nul 2>&1
echo  - Raccourcis crees (mode compatibilite).
goto :step5

:shortcut_failed
echo [ATTENTION] Raccourcis non crees - vous pouvez lancer via scripts\start.bat
goto :step5

rem --- Step 5/5: done -------------------------------------------------------
:step5
echo.
echo =======================================================================
echo          Installation terminee avec succes !
echo =======================================================================
echo.
if "%FIRST%"=="Y" goto :show_creds
echo Mise a jour terminee. Vos identifiants sont inchanges.
goto :launch_q

:show_creds
echo Vos identifiants de connexion :
echo   - Nom d'utilisateur : %DOC_USER%
echo   - Mot de passe : celui que vous avez saisi
echo.

:launch_q
set "LAUNCH_NOW=O"
set /p LAUNCH_NOW="Lancer HKN Dentaire maintenant ? (O/N) [O] : "
if "%LAUNCH_NOW%"=="" set "LAUNCH_NOW=O"
if /i "%LAUNCH_NOW%"=="N" goto :end_ok
if exist "%ROOT_DIR%\scripts\HKN Dentaire.exe" goto :launch_native
start "" "%ROOT_DIR%\scripts\start.bat"
goto :end_ok

:launch_native
start "" "%ROOT_DIR%\scripts\HKN Dentaire.exe"

:end_ok
echo.
echo Fermeture automatique dans 10 secondes...
ping -n 11 127.0.0.1 >nul
endlocal
exit /b 0

:runtime_missing
echo.
echo =======================================================================
echo  [ERREUR] Le dossier "runtime" est absent.
echo =======================================================================
echo.
echo L'environnement Python integre n'a pas ete extrait.
echo Re-extrayez le fichier ZIP en totalite (clic droit - Extraire tout),
echo puis relancez cette installation.
echo.
pause
exit /b 1

:runtime_corrupt
echo.
echo =======================================================================
echo  [ERREUR] Environnement Python integre incomplet.
echo =======================================================================
echo.
echo Des composants sont manquants ou corrompus (extraction partielle,
echo antivirus bloque des fichiers, ou transfert USB interrompu).
echo Re-extrayez le ZIP entierement puis relancez l'installation.
echo.
pause
exit /b 1

:port_foreign
echo.
echo =======================================================================
echo  [BLOQUE] Le port 8000 est utilise par une autre application.
echo =======================================================================
echo.
echo Fermez cette application puis relancez l'installation.
echo (Diagnostic : lancez scripts\stop.bat pour plus de details.)
echo.
pause
exit /b 1

:init_failed
echo.
echo =======================================================================
echo  [ERREUR] L'initialisation de la base de donnees a echoue (code %INIT_RC%).
echo =======================================================================
echo.
echo Reessayez ou contactez le support avec une capture d'ecran de ce message.
echo.
pause
exit /b 1
