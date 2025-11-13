@echo off
echo Running event simulation...
cd /d %~dp0
call venv\Scripts\activate.bat
python scripts/simulate_clicks.py
pause

