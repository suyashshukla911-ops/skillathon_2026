@echo off
cd /d "%~dp0"
python self_test.py
echo.
echo Self-test finished. Close this window or press any key.
pause >nul
