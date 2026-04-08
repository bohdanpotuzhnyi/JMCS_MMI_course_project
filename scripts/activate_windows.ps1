$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot

& "$ProjectRoot\.venv\Scripts\Activate.ps1"
. "$ProjectRoot\.project-env.ps1"

Write-Host "Activated multimodal toolkit environment."
Write-Host "Python: $((Get-Command python).Source)"
