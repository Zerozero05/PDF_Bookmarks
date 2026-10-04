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
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --additional-hooks-dir=. --name ZoteroPDFBookmarks --distpath dist --workpath build\gui --specpath build gui_entry.py
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --console --additional-hooks-dir=. --name ZoteroPDFBookmarks-CLI --distpath dist --workpath build\cli --specpath build bookmarks.py
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onedir --windowed --additional-hooks-dir=. --name ZoteroPDFBookmarks --contents-directory _internal --distpath dist\portable --workpath build\portable --specpath build\portable gui_entry.py
if errorlevel 1 goto fail
".venv\Scripts\python.exe" scripts\smoke_binaries.py
if errorlevel 1 goto fail
echo Built dist\ZoteroPDFBookmarks.exe and dist\ZoteroPDFBookmarks-CLI.exe
echo Portable GUI: dist\portable\ZoteroPDFBookmarks\ZoteroPDFBookmarks.exe
pause
exit /b 0
:fail
echo Build failed. Review the output above.
pause
exit /b 1
