# KSISU Real-Data Evidence Workbench — Final Pilot

This project is the competition-facing prototype for **KSISU Skillathon 2026**.

It is deliberately **not** a synthetic district dashboard. The core design is an evidence pipeline:

`Ingest → Registry → Harmonise → Demand model → Supply model → Shared Monte Carlo → Alignment → Evidence score → VOI → Human review`

## What is real in this package

- 31 Karnataka district rows from a bundled LGD-style district register.
- Karnataka district Udyam employment data used as a clearly labelled **district allocation proxy**.
- Karnataka ASI 2022-23 selected-manufacturing persons engaged = 1,166,555 as the state manufacturing base.
- NCVT MIS Karnataka state supply magnitude: 1,467 ITIs and 216,788 seats available in the 2022 row.
- A small official NCVT MIS File 1171 indexed subset with real Tumakuru and Kalaburagi ITI trade/seat rows.
- Historical DGT/DITE division-level training totals for calibration only.

## What is not claimed as real

- District manufacturing employment is not directly observed.
- The NCO 72/74 occupation shares are an **analyst prior** until PLFS occupation-by-industry data is loaded; NCO 81 is intentionally outside the pilot scope.
- The bundled NCVT File 1171 extract is **partial**, so it must not be used as a complete district supply figure.
- The project SCI, VOI and evidence score are proposed methodology, not the official KSI formula.

## Corrected failure modes

### No occupation-share renormalisation
The pilot keeps:

- NCO 72 = 0.25
- NCO 74 = 0.15

Selected share = 0.40. The remaining 0.60 of manufacturing employment stays outside the two-group pilot scope.

### No seat/completion conflation
Seats, fill, completion and sector entry are separate terms in the supply model.

### No district share cancellation
Demand uses Udyam share to downscale the ASI manufacturing state total. Proxy supply uses the historical DGT division pool with a district ITI-count weight when a complete NCVT district count file is supplied; otherwise the explicit equal-within-division fallback is used. The allocation draw is a multiplier with mean 1.0, so it cannot divide the district base twice.

### Shared uncertainty
The same Monte Carlo draw index is used across districts for global rates and allocation draws. District rank stability is reported from those shared draws.

### Unmatched rows are never dropped
The matcher reports exact, alias, fuzzy and review states. Unmatched rows remain in the review outputs.

### Provenance is preserved
The registry keeps source URL, grain, year, SHA-256 and source ID. The raw source files are not overwritten.

## Run it

```text
python -m pip install -r requirements.txt
SELF_TEST.bat
run.bat
```

## GUI judge demonstration

1. Click **Run Proxy Baseline**.
2. Show **District Priority** and explain the VOI/data-collection ranking.
3. Click **Load Official NCVT Sample**.
4. Click **Run With Loaded Supply**.
5. Show Tumakuru and Kalaburagi switching from proxy to partial floor and the partial-evidence update table.
6. Show Sensitivity.
7. Show Validation & Linkage.
8. For the final empirical demo, replace the bundled partial sample with the full current district×trade NCVT MIS / DGT / Karnataka extract.

## Final competition requirement

Before making a strong district policy claim, refresh the 31-row LGD export, load the **complete current district×trade ITI seat file**, and replace the occupation prior with extracted PLFS occupation-by-industry evidence or a defensible microdata-derived share.

Do not type fabricated numbers into the GUI.


## Partial real evidence is treated as a floor
The bundled NCVT File 1171 rows are not treated as complete district supply. For a partial district file, observed seats are a lower bound and the unobserved remainder is carried as a separate uncertainty term. Only a file explicitly marked `coverage_status=full_district_extract` can unlock a provisional district policy call with the narrow actual-seat uncertainty.

## Relative district index
The proxy-only SCI is shown relative to the statewide median SCI (`relative_SCI_vs_state_median`). It is a prioritisation signal for data collection, not a finding about absolute skill shortages.

## Validation scale
The corruption test now runs 100 seeded corruptions plus a 5% duplicate batch. It reports typo recovery, unseen-alias review, duplicate detection, and preserved review rows.


V5 critical fixes
- Partial evidence retains allocation and proxy-seat uncertainty; observed partial rows are floors, not exact district totals.
- Full actual gate requires all 31 raw LGD districts / 30 analytical geographies x both modeled NCO groups and <=5% unmapped seat share.
- District allocation uses populated historical 2022 district ITI-count weights from an official Rajya Sabha CTS table, scaled to the NCVT statewide seat magnitude.
- Demand includes independent per-district lognormal allocation uncertainty (sigma 0.35, configuration assumption).
- District ranking is by uncapped median R; SCI is reported separately.
- Conservation is compared with the triangular-mean expectation, not the mode.
- GUI and PDF use the same model outputs and configuration.


### Annexure-IV evidence (how the ITI weights were checked)
All 30 positive historical analytical-geography ITI counts (Government, Private, Total) were compared row by row with the official Rajya Sabha Q131 Annexure-IV table (PDF p.6, https://sansad.in/getFile/annex/258/AU131.pdf?source=pqars) on 2026-10-17. All 30 match, and the printed totals 275 Government + 1,227 Private = 1,502 are reproduced.

- The comparison uses `raw/rajya_sabha_annexure_iv_official_text_extract.md`, which is machine-extracted **text** of the official PDF with labels as printed (Belgaum, Bellary, Bijapur...). It is not a scan, and the PDF binary itself is not stored here because it could not be downloaded into the build environment.
- Re-run the check any time: `python verify_iti_counts.py` (also run by `SELF_TEST.bat`).
- `raw/rajya_sabha_annexure_iv_page6_PROJECT_TRANSCRIPTION_not_official.*` is a project-made summary table. It is **not** the official document and is not evidence.
- To confirm visually, open the official URL and compare page 6.
- The counts are historical 2022 allocation weights, not current district seat totals.
