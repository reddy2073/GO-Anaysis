@echo off
cd /d C:\Users\vemul\LegalDebateAI
echo ========================================
echo  LegalDebateAI - Migrate + Fetch
echo ========================================
echo.
echo Step 1: Migrating old court_verdicts_chunks...
venv\Scripts\python.exe scripts\migrate_court_verdicts.py
echo.
echo Step 2: Fetching all SC judgments (all 76 parquet files)...
venv\Scripts\python.exe scrapers\verdicts_hf_scraper.py --sc-only
echo.
echo Done! Press any key to close.
pause
