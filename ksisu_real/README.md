# KSISU Real-Data Manufacturing Pilot

This is the **competition-facing research prototype**. It is deliberately not a synthetic district dashboard.

## Core question
Can public data support a defensible district-level view of **ITI trade supply versus manufacturing occupation openings** for NCO groups **72, 74 and 81**, and, when it cannot, **which district should KSISU onboard first for better data?**

The prototype treats the second question - data acquisition priority - as the safer policy output until district-actual supply arrives.

## Pipeline

Ingest -> Registry -> District Harmonisation (LGD / aliases / fuzzy review) -> State manufacturing base -> District proxy allocation -> Occupation prior / NCO crosswalk -> ITI trade supply -> 5,000 shared-draw Monte Carlo -> Alignment ratio -> SCI -> Confidence -> VOI -> Human review

## Real public inputs included

- LGD district register (31 Karnataka districts; verify against a fresh live LGD export before final submission).
- Karnataka district Udyam employment up to Nov 2022 (district proxy allocator).
- MoSPI ASI 2022-23 Karnataka selected-manufacturing persons engaged = 1,166,555 (state manufacturing base).
- NCVT MIS 2022 Karnataka state ITI count / seats = 1,467 ITIs and 216,772 seats (state supply magnitude).
- DGT/DITE 2020-21 division training counts (historical fill/completion calibration only).
- Udyam 2023 district employment shares (temporal consistency check).

Official NCVT MIS also exposes district/trade/seat fields in downloadable ITI extracts; the GUI therefore accepts a district/trade CSV to replace the supply proxy for the demo. The public search result shows fields for Karnataka, district, trade and seats. Do not use a company name paired with fabricated metrics.

## What is estimated

- District manufacturing employment is **not observed**. It is allocated from the state manufacturing base using district Udyam employment shares as a transparent proxy.
- NCO 72/74/81 occupation mix is an **analyst prior** until PLFS unit-level occupation-by-industry data is loaded.
- District ITI trade seats are **proxy** unless the user loads an NCVT MIS / DGT / Karnataka district-trade extract.
- Opening, fill, completion and sector-entry rates are uncertainty ranges in `clean/config.json`.

## Decision discipline

The mathematical interval still reports `GAP`, `SURPLUS` or `NEEDS DATA` based on the 80% interval.

However, the **policy-facing decision** is deliberately gated:

- Proxy-only run -> `NEEDS DATA` (we do not call a district gap from proxy supply).
- District-actual supply loaded -> the interval can become `PROVISIONAL GAP`, `PROVISIONAL SURPLUS` or `NEEDS DATA`.

This avoids the previous failure where every row was presented as an empirical gap.

## Shared uncertainty draws

Global parameters (openings, fill, completion, sector entry and seat-proxy uncertainty) use the **same random draw index across districts**, which makes district comparisons reproducible and comparable.

## User-input GUI

Run:

```text
python ksisu_gui.py
```

or double-click `run.bat`.

The GUI lets you:

1. Replace any source file without changing code.
2. Choose NCO groups 72/74/81.
3. Change low/mode/high assumptions.
4. Set the Monte Carlo draw count and seed.
5. Load a district-actual ITI supply CSV.
6. Rerun the identical model and compare proxy vs actual evidence.
7. Inspect results, district priority, sensitivity and validation.

## Judge demonstration

1. Run the bundled research inputs.
2. Show that proxy-only results are `NEEDS DATA` for policy even when the mathematical interval is below 1.
3. Show the VOI ranking - this is the onboarding recommendation.
4. Load a real district-trade ITI export for two districts.
5. Rerun and show those rows switch from proxy to district-actual and the interval narrows.
6. Show sensitivity and the corruption test.

## Files

- `run_gap.py` - reproducible analysis engine.
- `ksisu_gui.py` - live judge-demo interface.
- `raw/` - public research inputs and provenance.
- `clean/` - config, district aliases, crosswalks and mappings.
- `out/` - generated analytical results and audit logs.
- `input_templates/district_iti_supply_template.csv` - exact input shape for real district ITI data.

The proposed SCI and VOI indicators are **project indicators**, not an official Karnataka Skill Index formula.
