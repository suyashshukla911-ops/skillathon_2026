@echo off
setlocal
cd /d "%~dp0"
python run_gap.py --out out\proxy_baseline
if errorlevel 1 goto :fail
python run_gap.py --actual-supply clean\dgt_cts_2026_karnataka_supply_nco.csv --out out\dgt_run
if errorlevel 1 goto :fail
python run_gap.py --actual-supply clean\dgt_cts_2026_karnataka_supply_nco.csv --proxy-allocation-method dgt_2026_seat_share --out out\dgt_share_run
if errorlevel 1 goto :fail
echo.
echo PROXY + DGT ACTUAL EVIDENCE + DGT SHARE RUNS COMPLETE
exit /b 0
:fail
echo.
echo A command failed. Read the message above.
pause
exit /b 1
