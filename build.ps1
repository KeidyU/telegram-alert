# Builds dist\BDVAlert.exe, a standalone exe for PCs without Python.
# Copy the whole dist\ folder (exe + .env + bancos.txt) to the target machine.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

venv\Scripts\pip install -r requirements.txt -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# --console: needed for the phone/code/2FA login prompts.
# --collect-all winrt/windows_toasts: windows-toasts loads winrt modules dynamically.
venv\Scripts\pyinstaller --noconfirm --onefile --console --name BDVAlert `
    --collect-all winrt --collect-all windows_toasts main.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Config files live next to the exe (see config.BASE_DIR). Never copy
# *.session: the other machine logs in with its own account.
Copy-Item bancos.txt, .env.example dist\
if (Test-Path .env) { Copy-Item .env dist\ }

Write-Host "`nBuilt dist\BDVAlert.exe -- copy the dist\ folder to the target PC."
