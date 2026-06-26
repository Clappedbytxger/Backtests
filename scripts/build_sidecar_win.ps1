<#
.SYNOPSIS
    Build the Quant-OS API as a standalone Windows .exe sidecar for the Tauri app.

.DESCRIPTION
    Run this ON WINDOWS, inside the project's Python venv, from anywhere in the repo:

        .\.venv\Scripts\Activate.ps1            # the Windows venv
        powershell -ExecutionPolicy Bypass -File scripts\build_sidecar_win.ps1

    Output: apps\web\src-tauri\binaries\quant-os-api-<triple>.exe
    where <triple> is the host Rust target (almost always x86_64-pc-windows-msvc).
    Tauri's `externalBin` resolves the sidecar for the build target by that exact
    triple + ".exe", so the name must match.

    The binary is large (pandas/scipy/scikit-learn/lightgbm get bundled). Torch and the
    LLM-inference backends are intentionally excluded (the agent routes don't work frozen
    anyway). If freezing fails on a missing module, adjust the --collect/--exclude flags.
#>

$ErrorActionPreference = "Stop"

# repo root = parent of this script's folder
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Name = "quant-os-api"
$OutDir = Join-Path $Root "apps\web\src-tauri\binaries"

# Resolve the host Rust target triple so the sidecar name matches Tauri's expectation.
$Triple = "x86_64-pc-windows-msvc"
try {
    $rustcInfo = & rustc -Vv 2>$null
    $hostLine = $rustcInfo | Where-Object { $_ -like "host:*" }
    if ($hostLine) { $Triple = ($hostLine -replace "host:\s*", "").Trim() }
} catch {
    Write-Host "==> rustc not found; assuming triple $Triple"
}

Write-Host "==> repo root : $Root"
Write-Host "==> python    : $((Get-Command python).Source)"
Write-Host "==> triple    : $Triple"
Write-Host "==> installing pyinstaller (no-op if present)..."
python -m pip install --quiet pyinstaller
if ($LASTEXITCODE -ne 0) { throw "pip install pyinstaller failed" }

Write-Host "==> freezing the API (this takes a few minutes)..."
python -m PyInstaller `
    --noconfirm --clean --onefile `
    --name $Name `
    --distpath (Join-Path $Root "build\sidecar\dist") `
    --workpath (Join-Path $Root "build\sidecar\work") `
    --specpath (Join-Path $Root "build\sidecar") `
    --paths (Join-Path $Root "src") --paths $Root `
    --collect-submodules quantlab `
    --collect-submodules apps `
    --collect-all fastapi --collect-all starlette --collect-all uvicorn `
    --collect-all pydantic --collect-all pydantic_settings `
    --collect-all pandas --collect-all numpy `
    --collect-all scipy --collect-all sklearn --collect-all lightgbm `
    --collect-all yfinance --collect-all yaml `
    --hidden-import apps.api.main `
    --exclude-module torch --exclude-module torchvision `
    --exclude-module transformers --exclude-module llama_cpp `
    --exclude-module mlx --exclude-module mlx_lm `
    (Join-Path $Root "apps\api\sidecar_entry.py")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$Dest = Join-Path $OutDir "$Name-$Triple.exe"
Copy-Item -Force (Join-Path $Root "build\sidecar\dist\$Name.exe") $Dest

Write-Host ""
Write-Host "==> OK sidecar built:"
Write-Host "    $Dest"
Write-Host ""
Write-Host "    Quick self-test (Ctrl-C to stop, then open http://127.0.0.1:8000/health):"
Write-Host "    & `"$Dest`""
