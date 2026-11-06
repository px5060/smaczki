@echo off
cd /d "%~dp0"
python -m smaczki dzis %*
if exist "site\index.html" start "" "site\index.html"
pause
