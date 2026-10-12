# scripts/run_ui.ps1
# Запуск Streamlit UI.
# Использование: pwsh -File .\scripts\run_ui.ps1

$ErrorActionPreference = "Stop"
Set-Location -Path (Join-Path $PSScriptRoot "..")

streamlit run src/supplier_bonus/ui/app.py