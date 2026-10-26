@echo off
rem =====================================================================
rem  HKN Dentaire - Safe shutdown for the local server.
rem  1) Stops our own server process on port 8000 (never a foreign app).
rem  2) Gracefully shuts the embedded PostgreSQL down (pg_ctl -m fast),
rem     so the medical database is never force-killed.
rem =====================================================================
setlocal DisableDelayedExpansion
cd /d "%~dp0.."
set "ROOT_DIR=%cd%"

set "PY_RUNTIME=%ROOT_DIR%\runtime\python.exe"
set "PY_VENV=%ROOT_DIR%\.venv\Scripts\python.exe"
if exist "%PY_RUNTIME%" (set "PY=%PY_RUNTIME%") else (set "PY=%PY_VENV%")

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$conns = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue; " ^
  "if ($conns) { " ^
  "  $root = '%ROOT_DIR%'; " ^
  "  foreach ($p in ($conns | Select-Object -ExpandProperty OwningProcess -Unique)) { " ^
  "    if ($p -le 0) { continue } " ^
  "    $cmdline = (Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $p)).CommandLine; " ^
  "    if ($cmdline -and ($cmdline.ToLower().Contains($root.ToLower()) -or $cmdline.ToLower().Contains('app\launcher.py'))) { " ^
  "      Write-Host ('[clinic] Stopping HKN Dentaire server (PID ' + $p + ')...'); " ^
  "      Stop-Process -Id $p -Force -ErrorAction SilentlyContinue; " ^
  "    } else { " ^
  "      Write-Host ('[clinic] Port 8000 is used by another program (PID ' + $p + ') - left untouched.'); " ^
  "    } " ^
  "  } " ^
  "} else { Write-Host '[clinic] No server running on port 8000.' }"
if errorlevel 1 echo [clinic] Warning: could not inspect port 8000.

if exist "%PY%" (
    if exist "%ROOT_DIR%\backend\app\cli.py" (
        echo [clinic] Closing the database cleanly...
        "%PY%" "%ROOT_DIR%\backend\app\cli.py" stop-server
    )
) else (
    echo [clinic] Runtime not found - database could not be closed via pg_ctl.
    echo [clinic] If PostgreSQL is still running, it will close gracefully on next clean stop.
)

echo [clinic] Shutdown complete.
endlocal
exit /b 0
