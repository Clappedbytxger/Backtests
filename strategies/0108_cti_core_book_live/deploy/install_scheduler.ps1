<#
Registers (or replaces) the Windows scheduled task that runs the CTI CORE-book bot
once per day. Run this in an elevated PowerShell on the VPS, from anywhere:

    powershell -ExecutionPolicy Bypass -File install_scheduler.ps1

Parameters:
  -At        Trigger time in the VPS's LOCAL timezone. Set it to ~30 min after the
             US close. Easiest: set the VPS timezone to US Eastern, then use 16:35.
             Default 22:35 assumes a CET VPS (16:35 ET in winter).
  -TaskArgs  Args passed to run_cti_daily.py. Default "--ibkr --arm" = forward-track
             AND place FX orders armed. Use "" for tracker-only, "--ibkr" for dry-run.
  -TaskName  Scheduled-task name.

The task runs in the interactive logon session (IB Gateway / MT5 need a desktop),
catches up if a run was missed, and retries twice on failure.
#>
param(
    [string]$At = "22:35",
    [string]$TaskArgs = "--ibkr --arm",
    [string]$TaskName = "CTI CORE Book Daily"
)

$ErrorActionPreference = "Stop"
$bat = Join-Path $PSScriptRoot "run_daily.bat"
if (-not (Test-Path $bat)) { throw "run_daily.bat not found next to this script: $bat" }

$action  = New-ScheduledTaskAction -Execute $bat -Argument $TaskArgs -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -DontStopOnIdleEnd

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -RunLevel Highest -Force | Out-Null

Write-Host "Registered task '$TaskName':"
Write-Host "  runs: $bat $TaskArgs"
Write-Host "  daily at: $At (VPS local time)"
Write-Host ""
Write-Host "Test it now with:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Inspect last run:  Get-ScheduledTaskInfo -TaskName '$TaskName'"
Write-Host "Remove it:         Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
