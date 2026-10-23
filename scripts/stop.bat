@echo off
rem Gracefully stops any running uvicorn clinic process on port 8000.
setlocal enabledelayedexpansion
cd /d "%~dp0.."

echo [clinic] Stopping clinic server on port 8000...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$conns = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue; " ^
  "if (-not $conns) { Write-Host '[clinic] No running clinic server found on port 8000.'; exit 0 }; " ^
  "$pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique; " ^
  "foreach ($p in $pids) { " ^
  "  if ($p -le 0) { continue }; " ^
  "  try { " ^
  "    $proc = Get-CimInstance Win32_Process -Filter \"ProcessId = $p\"; " ^
  "    if ($proc -and $proc.ParentProcessId) { " ^
  "      $parent = Get-CimInstance Win32_Process -Filter \"ProcessId = $($proc.ParentProcessId)\"; " ^
  "      if ($parent -and ($parent.Name -match '^(cmd|python|powershell)\.exe$')) { " ^
  "        Write-Host ('[clinic] Stopping launcher process ' + $parent.ProcessId + ' (' + $parent.Name + ')...'); " ^
  "        Stop-Process -Id $parent.ProcessId -Force -ErrorAction SilentlyContinue; " ^
  "      } " ^
  "    } " ^
  "    Write-Host ('[clinic] Stopping server process ' + $p + ' (' + $proc.Name + ')...'); " ^
  "    Stop-Process -Id $p -Force -ErrorAction SilentlyContinue; " ^
  "  } catch { " ^
  "    taskkill /F /T /PID $p 2>$null; " ^
  "  } " ^
  "}; " ^
  "Start-Sleep -Seconds 1; " ^
  "$rem = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue; " ^
  "if ($rem) { Write-Host '[clinic] Warning: Port 8000 is still listening.'; exit 1 } else { Write-Host '[clinic] Clinic server stopped successfully.'; exit 0 }"

if %ERRORLEVEL% neq 0 (
    echo [clinic] Retrying with netstat fallback...
    for /f "tokens=5" %%a in ('netstat -ano -p tcp ^| findstr ":8000 " ^| findstr "LISTENING"') do (
        if not "%%a"=="0" (
            taskkill /f /t /pid %%a >nul 2>&1
        )
    )
)
