<#
.SYNOPSIS
    Populate the Tauri resources\ folder with the data the desktop app ships.

.DESCRIPTION
    Windows (PowerShell) port of scripts/bundle_data.sh. Copies:
      * strategies.db               (registry -> dashboard table + strategy detail pages)
      * strategies\*\results\*.png  (the plots shown on each strategy detail page)

    Run BEFORE `npm run desktop:build:win`. Tauri bundles resources\ into the installer;
    the sidecar seeds it into a writable dir on first launch, so the shipped app starts
    self-contained with data.

        powershell -ExecutionPolicy Bypass -File scripts\bundle_data.ps1
#>

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Res = Join-Path $Root "apps\web\src-tauri\resources"

Write-Host "==> populating $Res"
if (Test-Path (Join-Path $Res "strategies")) { Remove-Item -Recurse -Force (Join-Path $Res "strategies") }
if (Test-Path (Join-Path $Res "strategies.db")) { Remove-Item -Force (Join-Path $Res "strategies.db") }
New-Item -ItemType Directory -Force -Path $Res | Out-Null

$db = Join-Path $Root "strategies.db"
if (Test-Path $db) {
    Copy-Item -Force $db (Join-Path $Res "strategies.db")
    $sizeKb = [math]::Round((Get-Item $db).Length / 1KB)
    Write-Host "    + strategies.db ($sizeKb KB)"
} else {
    Write-Host "    ! strategies.db missing - build it first:"
    Write-Host "        .\.venv\Scripts\python.exe scripts\build_registry.py"
}

$count = 0
Get-ChildItem -Path (Join-Path $Root "strategies") -Recurse -Directory -Filter "results" | ForEach-Object {
    $rel = $_.FullName.Substring($Root.Length + 1)
    $destDir = Join-Path $Res $rel
    New-Item -ItemType Directory -Force -Path $destDir | Out-Null
    Get-ChildItem -Path $_.FullName -Filter "*.png" -File | ForEach-Object {
        Copy-Item -Force $_.FullName $destDir
        $count++
    }
}

Write-Host "==> bundled $count result plots"
Write-Host "==> done - now build: cd apps\web; npm run desktop:build:win"
