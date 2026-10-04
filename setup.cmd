@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    python -m venv .venv
) else (
    py -3 -m venv .venv
)
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo Installed. Double-click launch_gui.cmd to open the tool.
pause
exit /b 0
:fail
echo Setup failed. Install Python 3.10+ with Tcl/Tk and pip, then retry.
pause
exit /b 1
