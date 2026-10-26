# HKN Dentaire - create Desktop + Start Menu shortcuts (no admin needed)
param(
    [Parameter(Mandatory = $true)]
    [string]$RootDir,
    [switch]$Fallback
)

$ErrorActionPreference = "Stop"

$scriptsDir = Join-Path $RootDir "scripts"
$icon = Join-Path $RootDir "branding\app.ico"

$target = Join-Path $scriptsDir "HKN Dentaire.exe"
if (-not (Test-Path -LiteralPath $target)) {
    $target = Join-Path $RootDir "scripts\start.bat"
    if (-not (Test-Path -LiteralPath $target)) { exit 1 }
    $cmdExtra = ""
} else {
    $cmdExtra = ""
}

$shell = New-Object -ComObject WScript.Shell

function New-Shortcut {
    param([string]$Path, [string]$Target, [string]$WorkDir, [string]$IconPath)
    $sc = $shell.CreateShortcut($Path)
    $sc.TargetPath = $Target
    $sc.WorkingDirectory = $WorkDir
    if ($IconPath -and (Test-Path -LiteralPath $IconPath)) { $sc.IconLocation = "$IconPath,0" }
    $sc.Description = "Application de gestion de clinique dentaire"
    $sc.Save()
}

$desktop = [Environment]::GetFolderPath("DesktopDirectory")
New-Shortcut -Path (Join-Path $desktop "HKN Dentaire.lnk") -Target $target -WorkDir $scriptsDir -IconPath $icon

$smDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
New-Shortcut -Path (Join-Path $smDir "HKN Dentaire.lnk") -Target $target -WorkDir $scriptsDir -IconPath $icon

# uninstall registry entry (HKCU, shown in Windows "Applications" settings)
try {
    $key = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\HKN Dentaire"
    if (-not (Test-Path $key)) { New-Item -Path $key -Force | Out-Null }
    $exePath = Join-Path $scriptsDir "HKN Dentaire.exe"
    if (Test-Path -LiteralPath $exePath) {
        Set-ItemProperty -Path $key -Name "DisplayName" -Value "HKN Dentaire"
        Set-ItemProperty -Path $key -Name "DisplayVersion" -Value "1.0.0"
        Set-ItemProperty -Path $key -Name "Publisher" -Value "HKN Dentaire"
        Set-ItemProperty -Path $key -Name "InstallLocation" -Value $RootDir
        Set-ItemProperty -Path $key -Name "DisplayIcon" -Value $exePath
        Set-ItemProperty -Path $key -Name "UninstallString" -Value ('"{0}" /uninstall' -f $exePath)
        Set-ItemProperty -Path $key -Name "NoModify" -Value 1 -Type DWord
        Set-ItemProperty -Path $key -Name "NoRepair" -Value 1 -Type DWord
        Set-ItemProperty -Path $key -Name "EstimatedSize" -Value 204800 -Type DWord
    }
} catch { }

exit 0
