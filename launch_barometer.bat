@echo off
setlocal
cd /d "%~dp0macro_barometer"
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.11 or newer, then try again.
  pause
  exit /b 1
)
python -m streamlit run app.py
if errorlevel 1 pause
