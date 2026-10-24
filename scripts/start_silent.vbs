' HKN Dentaire - Silent Background Service Launcher
' Launches scripts\start.bat invisibly (window style 0) so the Command Prompt
' does not clutter the taskbar or risk accidental closure.
' When passed /app (or --app), also waits for the server to become ready
' and launches the application in clean, borderless app-window mode.

Option Explicit

Dim fso, shell, scriptDir, rootDir, batPath
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
rootDir = fso.GetParentFolderName(scriptDir)
batPath = fso.BuildPath(scriptDir, "start.bat")

Dim isAppMode, arg
isAppMode = False
For Each arg In WScript.Arguments
    If LCase(arg) = "/app" Or LCase(arg) = "--app" Then
        isAppMode = True
    End If
Next

Function IsServerReady()
    On Error Resume Next
    Dim http
    Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    http.setTimeouts 500, 500, 500, 500
    http.open "GET", "http://127.0.0.1:8000/api/health", False
    http.send
    If Err.Number = 0 Then
        IsServerReady = (http.status = 200)
    Else
        IsServerReady = False
    End If
    On Error GoTo 0
End Function

' Start the server if it is not already running
If Not IsServerReady() Then
    shell.CurrentDirectory = rootDir
    Dim comspec, extraArgs
    comspec = shell.ExpandEnvironmentStrings("%COMSPEC%")
    extraArgs = "--no-pause"
    If isAppMode Then
        extraArgs = extraArgs & " --no-browser"
    End If
    shell.Run """" & comspec & """ /c call """ & batPath & """ " & extraArgs, 0, False
End If

' In app mode, poll until server is ready and launch browser in app window
If isAppMode Then
    Dim attempts, ready
    ready = False
    For attempts = 1 To 60
        If IsServerReady() Then
            ready = True
            Exit For
        End If
        WScript.Sleep 1000
    Next

    If ready Then
        Dim browserPath
        browserPath = FindAppBrowser()

        If browserPath <> "" Then
            shell.Run """" & browserPath & """ --app=http://127.0.0.1:8000", 1, False
        Else
            shell.Run "http://127.0.0.1:8000", 1, False
        End If
    Else
        MsgBox "Le serveur HKN Dentaire n'a pas pu demarrer dans le delai imparti." & vbCrLf & vbCrLf & _
               "Veuillez d'abord executer 'install.bat' a la racine pour installer l'application, ou lancer 'scripts\start.bat' pour verifier les messages d'erreur.", _
               vbCritical, "HKN Dentaire"
    End If
End If

Function FindAppBrowser()
    On Error Resume Next
    Dim regVal

    ' Check Edge in registry
    regVal = shell.RegRead("HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe\")
    If Err.Number = 0 Then
        regVal = FindAppBrowserOrQuotes(regVal)
        If regVal <> "" Then
            FindAppBrowser = regVal
            On Error GoTo 0
            Exit Function
        End If
    End If
    Err.Clear

    regVal = shell.RegRead("HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe\")
    If Err.Number = 0 Then
        regVal = FindAppBrowserOrQuotes(regVal)
        If regVal <> "" Then
            FindAppBrowser = regVal
            On Error GoTo 0
            Exit Function
        End If
    End If
    Err.Clear

    ' Check Chrome in registry
    regVal = shell.RegRead("HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe\")
    If Err.Number = 0 Then
        regVal = FindAppBrowserOrQuotes(regVal)
        If regVal <> "" Then
            FindAppBrowser = regVal
            On Error GoTo 0
            Exit Function
        End If
    End If
    Err.Clear

    regVal = shell.RegRead("HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe\")
    If Err.Number = 0 Then
        regVal = FindAppBrowserOrQuotes(regVal)
        If regVal <> "" Then
            FindAppBrowser = regVal
            On Error GoTo 0
            Exit Function
        End If
    End If
    Err.Clear

    ' Check standard directory paths
    Dim paths(7)
    paths(0) = shell.ExpandEnvironmentStrings("%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe")
    paths(1) = shell.ExpandEnvironmentStrings("%ProgramFiles%\Microsoft\Edge\Application\msedge.exe")
    paths(2) = shell.ExpandEnvironmentStrings("%ProgramW6432%\Microsoft\Edge\Application\msedge.exe")
    paths(3) = shell.ExpandEnvironmentStrings("%ProgramFiles%\Google\Chrome\Application\chrome.exe")
    paths(4) = shell.ExpandEnvironmentStrings("%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe")
    paths(5) = shell.ExpandEnvironmentStrings("%ProgramW6432%\Google\Chrome\Application\chrome.exe")
    paths(6) = shell.ExpandEnvironmentStrings("%LocalAppData%\Microsoft\Edge\Application\msedge.exe")
    paths(7) = shell.ExpandEnvironmentStrings("%LocalAppData%\Google\Chrome\Application\chrome.exe")

    Dim p
    For Each p In paths
        If p <> "" And fso.FileExists(p) Then
            FindAppBrowser = p
            On Error GoTo 0
            Exit Function
        End If
    Next
    On Error GoTo 0

    FindAppBrowser = ""
End Function

Function FindAppBrowserOrQuotes(strVal)
    Dim cleaned
    cleaned = Replace(strVal, """", "")
    If fso.FileExists(cleaned) Then
        FindAppBrowserOrQuotes = cleaned
    Else
        FindAppBrowserOrQuotes = ""
    End If
End Function
