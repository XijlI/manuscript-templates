@echo off
rem Windows launcher: double-click this, or let a VS Code task call it.
rem All real work is in build.py (python, latexmk and pandoc must be on PATH).
setlocal
cd /d "%~dp0"
where python >nul 2>nul && (python "%~dp0build.py" %* & exit /b %errorlevel%)
where py >nul 2>nul && (py "%~dp0build.py" %* & exit /b %errorlevel%)
echo python not found on PATH - install Python 3 or add it to PATH.
exit /b 1
