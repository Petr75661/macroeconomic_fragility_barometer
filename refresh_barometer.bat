@echo off
setlocal
cd /d "%~dp0macro_barometer"
python main.py --refresh
