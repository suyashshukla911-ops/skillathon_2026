@echo off
cd /d "%~dp0"
python run_gap.py
if errorlevel 1 pause
