@echo off
setlocal
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
    echo Run setup.cmd first, or use the packaged ZoteroPDFBookmarks.exe.
    pause
    exit /b 1
)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0gui_entry.py" %*
