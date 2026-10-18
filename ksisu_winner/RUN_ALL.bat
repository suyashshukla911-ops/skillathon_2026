@echo off
setlocal
cd /d "%~dp0"
python verify_iti_counts.py
if errorlevel 1 goto :fail
python refresh_pipeline.py
if errorlevel 1 goto :fail
python run_gap.py --out out\proxy_baseline
if errorlevel 1 goto :fail
python run_gap.py --actual-supply clean\dgt_cts_2026_karnataka_supply_nco.csv --out out\dgt_run
if errorlevel 1 goto :fail
python run_gap.py --actual-supply clean\dgt_cts_2026_karnataka_supply_nco.csv --proxy-allocation-method dgt_2026_seat_share --out out\dgt_share_run
if errorlevel 1 goto :fail
python run_demand_scenarios.py
if errorlevel 1 goto :fail
python public_export.py
if errorlevel 1 goto :fail
python policy_layer.py .
if errorlevel 1 goto :fail
echo.
echo KSISU JUDGE PACKAGE READY
echo Public exports: public_export\
echo Policy layer: out\policy_actions.csv + out\district_evidence_levels.csv
echo DSDP triangulation: out\dsdp_benchmark_comparison.csv
echo Policy summary: out\policy_summary.json
echo Robustness summary: out\run_summary.json
echo To open the GUI separately: python ksisu_gui.py
exit /b 0
:fail
echo.
echo A command failed. Read the message above.
pause
exit /b 1
