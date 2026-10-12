# Bouwt SMBConnect.exe (één bestand) met PyInstaller.
# Gebruik:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

if (-not (Test-Path .venv)) {
    Write-Host '> Virtuele omgeving aanmaken (.venv)'
    if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m venv .venv }
    else { & python -m venv .venv }
    if ($LASTEXITCODE -ne 0) { throw 'Python 3 niet gevonden. Installeer Python 3.10+ van python.org.' }
}
$venvPy = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'

Write-Host '> Afhankelijkheden installeren'
& $venvPy -m pip install --upgrade pip | Out-Null
& $venvPy -m pip install -r requirements-dev.txt

Write-Host '> Tests draaien'
& $venvPy -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Tests mislukt, build afgebroken.' }

Write-Host '> SMBConnect.exe bouwen'
& $venvPy -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name SMBConnect `
    --collect-submodules smbconnect `
    run.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller mislukt.' }

Write-Host ''
Write-Host "Klaar: $(Join-Path $PSScriptRoot 'dist\SMBConnect.exe')" -ForegroundColor Green
