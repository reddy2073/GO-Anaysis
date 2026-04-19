@echo off
REM LegalDebateAI Auto-Resume Startup Script
REM This script activates the virtual environment and runs the auto-resume check

cd /d "C:\Users\vemul\LegalDebateAI"

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Run auto-resume script
python scripts\auto_resume.py

REM Keep window open briefly to see output
timeout /t 10