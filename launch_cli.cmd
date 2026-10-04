@echo off
setlocal
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo Run setup.cmd first.
    exit /b 1
)
"%~dp0.venv\Scripts\python.exe" "%~dp0bookmarks.py" %*
exit /b %errorlevel%
