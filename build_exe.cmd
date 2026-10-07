@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup.cmd first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m unittest discover -s tests -v
if errorlevel 1 goto fail
".venv\Scripts\python.exe" scripts\build_windows.py
if errorlevel 1 goto fail
".venv\Scripts\python.exe" scripts\smoke_binaries.py
if errorlevel 1 goto fail
".venv\Scripts\python.exe" scripts\package_release.py
if errorlevel 1 goto fail
".venv\Scripts\python.exe" scripts\test_frozen_updates.py
if errorlevel 1 goto fail
echo Built dist\PDF_Bookmarks.exe and dist\PDF_Bookmarks_CLI.exe
echo Portable GUI: dist\portable\PDF_Bookmarks\PDF_Bookmarks.exe
echo Validated release assets: artifacts\
pause
exit /b 0
:fail
echo Build failed. Review the output above.
pause
exit /b 1
