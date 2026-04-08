$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "python is required but was not found in PATH."
}

python scripts/bootstrap_project.py @args

Write-Host ""
Write-Host "Next step:"
Write-Host "  . .\scripts\activate_windows.ps1"
