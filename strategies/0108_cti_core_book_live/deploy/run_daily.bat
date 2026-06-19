@echo off
REM Wrapper the Windows scheduled task calls. Resolves the repo root relative to
REM this file (deploy\ -> 0108 -> strategies -> repo), so it is portable across VPS
REM paths. Passes any args through (e.g. --ibkr --arm).
setlocal
set "REPO=%~dp0..\..\.."
pushd "%REPO%"
".\.venv\Scripts\python.exe" "strategies\0108_cti_core_book_live\run_cti_daily.py" %*
set "RC=%ERRORLEVEL%"
popd
endlocal & exit /b %RC%
