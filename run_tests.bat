@echo off
echo Running /track endpoint tests...
cd /d %~dp0
call venv\Scripts\activate.bat
python test_track_endpoint.py
pause

