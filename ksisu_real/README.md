# KSISU Real-Data Prototype

This is the real-data research prototype for Skillathon 2026. It replaces the earlier synthetic district workbench with a source-driven pipeline and an uncertainty-aware demand/supply method.

## Pipeline
Ingest -> Registry -> Harmonise (LGD/NIC/NCO) -> Demand model -> Supply model -> Ratio with 80% interval -> Confidence -> VOI priority -> Human review -> Outputs

## Run
```bash
python run_gap.py
```

The script re-runs the method from `raw/` and `clean/` and writes to `out/`.

## Real data vs assumptions
REAL: district Udyam employment (Karnataka Economic Survey 2022-23), Karnataka manufacturing worker share from PLFS 2022-23, DGT/DITE division-level ITI training counts, district Udyam employment shares (2023) for a sanity check, June 2026 Udyam district totals as contextual reconciliation.

ESTIMATES: district manufacturing employment proxy, district ITI seats proxy, occupation mix prior, course-to-NCO crosswalk, openings rate and sector-entry rate. These are all labeled in output files and the submission draft.

## Core outputs
- `out/traffic_light.csv` - source readiness check
- `out/demand_estimates.csv` - district/occupation demand range
- `out/supply_estimates.csv` - district/occupation supply range
- `out/ratio_intervals.csv` - 5000-draw Monte Carlo ratio and classification
- `out/district_priority.csv` - SCI + VOI ranking
- `out/focus_districts.csv` - Tumakuru vs Kalaburagi worked comparison
- `out/corruption_test_summary.csv` - linkage recovery result
- `out/sanity_summary.csv` - temporal district-share consistency check
- `out/unmatched.csv` - human review queue
- `raw/file_registry.csv` - source lineage metadata

## Important limitations
1. PLFS district-level estimates are not used. The official/public documentation indicates reliable district estimates are not available; PLFS is used at state level.
2. Udyam is a registered-enterprise employment proxy, not a complete district workforce census.
3. District ITI seats were not verified directly; real DGT/DITE division-level seat totals are allocated within each division to districts using a transparent Udyam-employment share proxy.
4. The occupation mix and course/NCO crosswalk are analyst priors until PLFS microdata and district MIS/DSDP records are onboarded.
5. LGD codes should be re-validated against a fresh live LGD Download Directory export before the competition submission.

## Competition use
Use the included PDF only as a draft method note. Do not present the estimated numbers as official statistics or claim an official KSI formula. The key contribution is the linkage method, uncertainty interval, reproducibility, and onboarding priority.
