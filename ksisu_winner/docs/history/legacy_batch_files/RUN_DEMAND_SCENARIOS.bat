@echo off
setlocal
cd /d "%~dp0"
call .venv\Scripts\activate
python run_demand_scenarios.py
if errorlevel 1 exit /b %errorlevel%
echo.
echo SIX SCENARIOS COMPLETE: proxy and DGT-share under employment, units, and blend.
echo Combined output: out\scenario_robustness.csv
echo Detailed runs: out\scenarios\
pause
