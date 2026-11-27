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
rem Files extracted from a downloaded ZIP carry the "downloaded from the
rem Internet" flag, which triggers security prompts on every launch.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -LiteralPath $env:ROOT_DIR -Recurse -File -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue" 1>nul 2>&1
echo.

rem --- Step 2/5: port check ------------------------------------------------
set "APP_PORT=8000"
for /f %%p in ('powershell -NoProfile -Command "$f=Join-Path $env:ROOT_DIR 'data\config.json'; $p=8000; if(Test-Path $f){try{$j=Get-Content $f -Raw|ConvertFrom-Json; if($j.port){$p=[int]$j.port}}catch{}}; Write-Output $p" 2^>nul') do set "APP_PORT=%%p"
echo [Etape 2/5] Verification du port d'ecoute (%APP_PORT%)...
set "PORT_STATE=FREE"
for /f %%s in ('powershell -NoProfile -Command "$c=Get-NetTCPConnection -LocalPort %APP_PORT% -State Listen -ErrorAction SilentlyContinue; if($c){$p=$c[0].OwningProcess; $cl=(Get-CimInstance Win32_Process -Filter \"ProcessId=$p\").CommandLine; if($cl -and $cl -match 'app\\launcher\.py'){Write-Output 'OURS'}else{Write-Output 'FOREIGN'}}else{Write-Output 'FREE'}" 2^>nul') do set "PORT_STATE=%%s"
if "%PORT_STATE%"=="FOREIGN" goto :port_foreign
if "%PORT_STATE%"=="FREE" goto :port_ok
echo  - L'application tourne deja. Arret propre pour l'installation...
call "%ROOT_DIR%\scripts\stop.bat"
powershell -NoProfile -Command "$c=Get-NetTCPConnection -LocalPort %APP_PORT% -State Listen -ErrorAction SilentlyContinue; if($c){Write-Output 'FOREIGN'}else{Write-Output 'FREE'}" 2>nul | findstr /x "FREE" >nul
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
if exist "%ROOT_DIR%\data\pgdata\PG_VERSION" goto :existing_db

rem ---- collect credentials (required, no default password) ----
echo.
echo Creation du compte principal de la clinique :
echo   (mot de passe : 10 caracteres ou plus, lettres et chiffres,
echo    avec au moins un symbole ! ? @ # - _ )
echo.
set "CRED_TRIES=0"
:cred_again
set /a CRED_TRIES+=1
if %CRED_TRIES% GTR 5 goto :cred_abandon
set "DOC_NAME="
set /p DOC_NAME="Nom complet du dentiste (ex: Dr. Benali Amine) : "
if not defined DOC_NAME goto :cred_again
set "DOC_USER="
set /p DOC_USER="Nom d'utilisateur (ex: dentiste) : "
if not defined DOC_USER goto :cred_again
echo.
setlocal EnableDelayedExpansion
echo Compte : !DOC_USER!  /  dentiste : !DOC_NAME!
endlocal
set "CONFIRM=O"
set /p CONFIRM="Confirmer ? (O/N) [O] : "
if /i not "%CONFIRM%"=="O" goto :cred_again
goto :ask_lan

:cred_abandon
echo.
echo [ERREUR] Saisie invalide trop de fois - installation annulee.
echo Relancez l'installation pour reessayer.
ping -n 6 127.0.0.1 >nul
exit /b 1

:existing_db
>"%ROOT_DIR%\data\.already_initialized" echo 1
echo.
echo [!] Une base de donnees existe deja dans ce dossier :
echo     mode mise a jour (vos donnees et votre compte sont conserves).
set "FIRST=N"
goto :run_steps

:ask_lan
echo.
echo Les autres ordinateurs du cabinet doivent-ils acceder a l'application
echo (reseau local) ? Repondez N si seul cet ordinateur l'utilise.
set "LAN=N"
set /p LAN="Acces reseau local ? (O/N) [N] : "
set "LAN_JSON=false"
if /i "%LAN%"=="O" set "LAN_JSON=true"
if not exist "%ROOT_DIR%\data" mkdir "%ROOT_DIR%\data" >nul 2>&1
>"%ROOT_DIR%\data\config.json" echo {"port": %APP_PORT%, "lan": %LAN_JSON%}
if "%LAN_JSON%"=="true" call :open_firewall
goto :run_init

:open_firewall
netsh advfirewall firewall delete rule name="HKN Dentaire LAN" >nul 2>&1
netsh advfirewall firewall add rule name="HKN Dentaire LAN" dir=in action=allow protocol=TCP localport=%APP_PORT% profile=private,domain program="%ROOT_DIR%\runtime\python.exe" >nul 2>&1
if errorlevel 1 (
    echo [ATTENTION] Pare-feu non configure ^(droits administrateur requis^).
    echo   Relancez install.bat en tant qu'administrateur, ou autorisez
    echo   "python.exe" quand Windows le demande au premier demarrage.
) else (
    echo  - Pare-feu : acces reseau local autorise sur le port %APP_PORT%.
)
exit /b 0

:update_mode
if exist "%ROOT_DIR%\data\pgdata\PG_VERSION" goto :update_ok
echo.
echo [!] Aucune base de donnees trouvee dans ce dossier : ce n'est pas une
echo     mise a jour. Relancez l'installation et repondez O (premiere installation).
ping -n 8 127.0.0.1 >nul
exit /b 1
:update_ok
>"%ROOT_DIR%\data\.already_initialized" echo 1
echo.
echo Mode mise a jour : vos donnees et votre compte sont conserves.
goto :run_steps

:run_init
echo.
echo Cle de licence (fournie par votre revendeur, commence par HKN1.)
set "LIC_KEY="
set /p LIC_KEY="Collez la cle ici (ENTREE pour passer) : "
if not "%LIC_KEY%"=="" call :save_key "%LIC_KEY%"
echo.
rem The password is typed, confirmed, checked and passed to init-prod inside
rem PowerShell only (never through cmd variables or a command line).
set "CLINIC_INIT_USERNAME=%DOC_USER%"
set "CLINIC_INIT_FULLNAME=%DOC_NAME%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT_DIR%\scripts\read_password.ps1" -RootDir "%ROOT_DIR%"
set "INIT_RC=%ERRORLEVEL%"
set "CLINIC_INIT_USERNAME="
set "CLINIC_INIT_FULLNAME="
if not "%INIT_RC%"=="0" goto :init_failed
rem Mark as initialised only once the database and owner really exist.
>"%ROOT_DIR%\data\.already_initialized" echo 1

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
setlocal EnableDelayedExpansion
echo   - Nom d'utilisateur : !DOC_USER!
endlocal
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
if defined LIC_KEY set "LIC_KEY="
if defined CLINIC_KEY set "CLINIC_KEY="
endlocal
exit /b 0

:save_key
set "CLINIC_KEY=%~1"
set "CLINIC_ROOT_DIR=%ROOT_DIR%"
powershell -NoProfile -Command "$k=($env:CLINIC_KEY -replace '\s',''); $d=Join-Path $env:CLINIC_ROOT_DIR 'data'; New-Item -ItemType Directory -Force $d | Out-Null; if($k.StartsWith('HKN1.')){ [IO.File]::WriteAllText((Join-Path $d 'clinic.key'), $k + [Environment]::NewLine); Write-Output ' - Cle de licence enregistree.' } else { Write-Output ' [!] Cle ignoree (doit commencer par HKN1.) - vous pourrez la coller dans l application.' }"
if defined CLINIC_KEY set "CLINIC_KEY="
if defined CLINIC_ROOT_DIR set "CLINIC_ROOT_DIR="
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
echo  [BLOQUE] Le port %APP_PORT% est utilise par une autre application.
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
