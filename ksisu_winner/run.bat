@echo off
cd /d "%~dp0"
python ksisu_gui.py
if errorlevel 1 pause
