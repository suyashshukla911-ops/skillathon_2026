@echo off
cd /d "%~dp0"
python ksisu_data_workbench.py
if errorlevel 1 pause
