@echo off
rem =====================================================================
rem  HKN Dentaire - Safe shutdown for the local server.
rem  1) Stops our own server process on its port (data\config.json, default 8000;
rem     never a foreign app).
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
  "$root = [IO.Path]::GetFullPath($env:ROOT_DIR); " ^
  "$port = 8000; $cfg = Join-Path $root 'data\config.json'; " ^
  "if (Test-Path $cfg) { try { $j = Get-Content $cfg -Raw | ConvertFrom-Json; if ($j.port) { $port = [int]$j.port } } catch {} } " ^
  "$conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue; " ^
  "if ($conns) { " ^
  "  $launcher = [IO.Path]::GetFullPath((Join-Path $root 'backendpp\launcher.py')); " ^
  "  foreach ($p in ($conns | Select-Object -ExpandProperty OwningProcess -Unique)) { " ^
  "    if ($p -le 0) { continue } " ^
  "    $cmdline = (Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $p)).CommandLine; " ^
  "    if ($cmdline -and $cmdline.IndexOf($launcher, [StringComparison]::OrdinalIgnoreCase) -ge 0) { " ^
  "      Write-Host ('[clinic] Stopping HKN Dentaire server (PID ' + $p + ')...'); " ^
  "      Stop-Process -Id $p -Force -ErrorAction SilentlyContinue; " ^
  "    } else { " ^
  "      Write-Host ('[clinic] Port ' + $port + ' is used by another program (PID ' + $p + ') - left untouched.'); " ^
  "    } " ^
  "  } " ^
  "} else { Write-Host ('[clinic] No server running on port ' + $port + '.') }"
if errorlevel 1 echo [clinic] Warning: could not inspect the server port.

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
