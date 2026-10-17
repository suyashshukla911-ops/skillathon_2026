# KSISU Skillathon 2026 — Final Project Position

## What this build is
A reproducible, source-driven manufacturing skill-alignment pilot for Karnataka. It is designed to answer: what can public data support today, what remains uncertain, and where KSISU should collect district evidence first.

## Scope
- Manufacturing only
- NCO groups 72 and 74
- FY 2022-23 reference
- 5,000 shared Monte Carlo draws, fixed seed
- Policy gate: proxy/partial actual -> NEEDS DATA; complete district-actual -> provisional interval call

## What is demonstrated with real public evidence
- 31 raw LGD district LGD-style matching
- ASI Karnataka manufacturing state base
- Karnataka Udyam district employment as a clearly labelled district allocator proxy
- DGT CTS-2026 provisional dynamic seat matrix: 1,734 Karnataka district×ITI×trade rows and 45,416 provisional seats; 39,984 seats map into the NCO 72/74 pilot
- Seats -> fill -> completion -> sector entry -> NCO crosswalk
- evidence update when partial/full district evidence replaces the proxy; partial rows are treated as floors and may legitimately widen the interval
- corruption/review queue
- provenance and audit log
- sensitivity and VOI priority

## What is intentionally not claimed
- No official Karnataka Skill Index formula
- DGT 2026 real supply is bundled, but the matrix is provisional, covers 58/60 analytical district-group pairs, and has 12.0% of published seats explicitly OUT_OF_SCOPE for the pilot; full policy eligibility therefore remains blocked. The DGT-share upgrade uses coverage-weighted shrinkage toward the historical 2022 ITI-count proxy, so missing districts such as Kodagu retain nonzero proxy allocation rather than collapsing to zero.
- No empirical occupation-by-industry prior until PLFS microdata is loaded
- No policy gap call from proxy or partial evidence

## Judge demo
Run `RUN_ALL.bat` to execute refresh QA, the baseline/DGT runs, all six scenarios, and public exports. Then launch `python ksisu_gui.py` for the interactive demo.


### Historical ITI weight verification update
All 30 positive historical analytical geography ITI counts (Government, Private, Total) were compared row by row with the official Rajya Sabha Q131 Annexure-IV table (PDF p.6) on 2026-10-17 and all match; the printed totals 275 + 1,227 = 1,502 are reproduced. The comparison runs against machine-extracted text of the official PDF (`raw/rajya_sabha_annexure_iv_official_text_extract.md`) and is reproducible with `python verify_iti_counts.py`. The PDF binary is not stored in the package; open the official URL, page 6, to confirm visually. The counts remain historical allocation weights only.


V13 demand allocator controls:
- --demand-allocation-method udyam_employment (default)
- --demand-allocation-method udyam_units
- --demand-allocation-method blend
- RUN_DEMAND_SCENARIOS.bat runs proxy and DGT-share modes under all three allocators.
- demand_allocator_rank_stability.csv reports rank range and top-5 robustness across allocators.
- scenario_robustness.csv combines all six supply×demand scenarios (proxy/DGT-share × employment/units/blend); six-scenario robustness is the stronger claim for judge-facing district priority.
- The 50/50 blend is an arbitrary midpoint sensitivity case, not an empirical estimator, because Udyam units and Udyam employment measure different underlying concepts.
- The demand lognormal sigma 0.35 is an explicit assumption with no district-level calibration yet.
