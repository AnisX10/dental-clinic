@echo off
rem Create an "HKN Dentaire" shortcut on the current user's Windows Desktop
rem that starts the service and opens the application in a clean, borderless app-window mode.
setlocal enabledelayedexpansion

cd /d "%~dp0.."
set "ROOT_DIR=%cd%"
set "VBS_SCRIPT=%ROOT_DIR%\scripts\start_silent.vbs"

echo [clinic] Creating "HKN Dentaire" shortcut on Desktop...

if not exist "%VBS_SCRIPT%" (
    echo [clinic] ERROR: Cannot find "%VBS_SCRIPT%".
    exit /b 1
)

set "SHORTCUT_VBS=%TEMP%\clinic_create_sc_%RANDOM%.vbs"
(
echo Option Explicit
echo Dim ws, fso, desktop, sc, rootDir, vbsScript
echo Set ws = CreateObject("WScript.Shell"^)
echo Set fso = CreateObject("Scripting.FileSystemObject"^)
echo desktop = ws.SpecialFolders("Desktop"^)
echo Set sc = ws.CreateShortcut(fso.BuildPath(desktop, "HKN Dentaire.lnk"^)^)
echo sc.TargetPath = ws.ExpandEnvironmentStrings("%%SystemRoot%%\System32\wscript.exe"^)
echo sc.Arguments = """" ^& "%VBS_SCRIPT%" ^& """ /app"
echo sc.WorkingDirectory = "%ROOT_DIR%"
echo sc.Description = "HKN Dentaire - Application de gestion de cabinet dentaire"
echo Dim browser, p, candidates(9^)
echo On Error Resume Next
echo candidates(0^) = ws.RegRead("HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe\"^)
echo candidates(1^) = ws.RegRead("HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe\"^)
echo candidates(2^) = ws.RegRead("HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe\"^)
echo candidates(3^) = ws.RegRead("HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe\"^)
echo candidates(4^) = ws.ExpandEnvironmentStrings("%%ProgramFiles(x86)%%\Microsoft\Edge\Application\msedge.exe"^)
echo candidates(5^) = ws.ExpandEnvironmentStrings("%%ProgramFiles%%\Microsoft\Edge\Application\msedge.exe"^)
echo candidates(6^) = ws.ExpandEnvironmentStrings("%%ProgramFiles%%\Google\Chrome\Application\chrome.exe"^)
echo candidates(7^) = ws.ExpandEnvironmentStrings("%%ProgramFiles(x86)%%\Google\Chrome\Application\chrome.exe"^)
echo candidates(8^) = ws.ExpandEnvironmentStrings("%%LocalAppData%%\Microsoft\Edge\Application\msedge.exe"^)
echo candidates(9^) = ws.ExpandEnvironmentStrings("%%LocalAppData%%\Google\Chrome\Application\chrome.exe"^)
echo For Each p In candidates
echo   If p ^<^> "" Then
echo     p = Replace(p, """", ""^)
echo     If fso.FileExists(p^) Then
echo       sc.IconLocation = p ^& ",0"
echo       Exit For
echo     End If
echo   End If
echo Next
echo On Error GoTo 0
echo sc.Save
echo WScript.Echo "[clinic] OK: Shortcut created at " ^& sc.FullName
) > "%SHORTCUT_VBS%"

cscript //nologo "%SHORTCUT_VBS%"
set "ERR=%ERRORLEVEL%"
if exist "%SHORTCUT_VBS%" del "%SHORTCUT_VBS%"

if %ERR% equ 0 (
    echo [clinic] Setup complete. Double-click the "HKN Dentaire" shortcut on your Desktop to use the app.
) else (
    echo [clinic] Failed to create desktop shortcut.
    exit /b %ERR%
)
