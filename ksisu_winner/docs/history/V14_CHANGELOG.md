# V14 Change Log

## Six-scenario robustness

V14 adds `out/scenario_robustness.csv`, combining six judge-checkable scenarios:

- proxy supply × Udyam employment demand
- proxy supply × Udyam enterprise-unit demand
- proxy supply × blended demand
- DGT-share supply × Udyam employment demand
- DGT-share supply × Udyam enterprise-unit demand
- DGT-share supply × blended demand

The combined table reports each district's rank in all six scenarios, the rank range, top-five appearances and a `top5_all_six` robustness flag.

The current documentation now states plainly that the 50/50 blend is an arbitrary midpoint sensitivity case and that the demand lognormal sigma of 0.35 is an explicit analyst assumption with no district calibration.
