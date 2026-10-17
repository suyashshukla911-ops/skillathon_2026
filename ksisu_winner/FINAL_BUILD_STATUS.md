# V15 Final Build Status

- Version: V15
- Default demand allocator: `udyam_employment`
- Alternative demand allocators: `udyam_units`, `blend`
- Six-scenario robustness: `out/scenario_robustness.csv`
- Six-scenario summary: `out/run_summary.json`
- Public machine-readable exports: `public_export/`
- Public suppression threshold: `min_count_suppression = 5`
- Refresh QA: `refresh_pipeline.py` writes `out/data_quality_report.csv` and `out/review_queue.csv` and stops when review is required
- Primary public district view: `out/dgt_share_run/` (coverage-weighted DGT-share scenario, still policy-gated)
- Policy gate: all modeled policy cells remain `NEEDS DATA`
- Six-scenario robust priority: generated from all six supply × demand combinations; `out/run_summary.json` records the robust district(s) and the number with rank range above 5
- Package entry point: `RUN_ALL.bat`
- Interactive GUI: `python ksisu_gui.py`
