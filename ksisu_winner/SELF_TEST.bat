@echo off
cd /d "%~dp0"
python self_test.py
if errorlevel 1 pause
