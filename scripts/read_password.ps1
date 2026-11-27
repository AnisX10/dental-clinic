# HKN Dentaire - first-owner password + database initialisation (zip kit).
#
# Called by install.bat. The password never passes through cmd.exe (where
# characters such as " & ^ % ; would break or even execute part of it) and never
# appears on a command line: it is read here as a SecureString, typed twice,
# checked with the backend's own policy (cli.py check-password), then handed to
# cli.py init-prod through the CLINIC_INIT_PASSWORD environment variable.
#
# Username / full name come from install.bat through CLINIC_INIT_USERNAME and
# CLINIC_INIT_FULLNAME. Exit code: init-prod's exit code, or 3 after too many
# invalid attempts.
param(
    [Parameter(Mandatory = $true)]
    [string]$RootDir
)

$ErrorActionPreference = "Stop"
$py = Join-Path $RootDir "runtime\python.exe"
$cli = Join-Path $RootDir "backend\app\cli.py"

function Read-Secret([string]$label) {
    $secure = Read-Host $label -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}

$ok = $false
for ($try = 1; $try -le 5; $try++) {
    $p1 = Read-Secret "Mot de passe"
    if ([string]::IsNullOrEmpty($p1)) { Write-Host "[!] Le mot de passe ne peut pas etre vide."; continue }
    if ($p1 -eq $env:CLINIC_INIT_FULLNAME) { Write-Host "[!] Le mot de passe doit differer du nom complet."; continue }
    $p2 = Read-Secret "Confirmez le mot de passe"
    if ($p1 -ne $p2) { Write-Host "[!] Les deux mots de passe ne correspondent pas."; continue }

    $env:CLINIC_INIT_PASSWORD = $p1
    $msg = & $py $cli check-password 2>&1
    if ($LASTEXITCODE -eq 0) { $ok = $true; break }
    Write-Host ("[!] " + ($msg -join " "))
    Remove-Item Env:\CLINIC_INIT_PASSWORD -ErrorAction SilentlyContinue
}
$p1 = $null; $p2 = $null

if (-not $ok) {
    Write-Host "[ERREUR] Mot de passe invalide trop de fois."
    exit 3
}

Write-Host ""
Write-Host "Initialisation de la base de donnees et du catalogue dentaire..."
try {
    & $py $cli init-prod
    $rc = $LASTEXITCODE
}
finally {
    Remove-Item Env:\CLINIC_INIT_PASSWORD -ErrorAction SilentlyContinue
}
exit $rc
