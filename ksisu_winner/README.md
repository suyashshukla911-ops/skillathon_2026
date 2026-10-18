# KSISU Real-Data Evidence Workbench — Final Pilot

This project is the competition-facing prototype for **KSISU Skillathon 2026**.

It is deliberately **not** a synthetic district dashboard. The core design is an evidence pipeline:

`Ingest → Registry → Harmonise → Demand model → Supply model → Shared Monte Carlo → Alignment → Evidence score → VOI → Human review`

## Judge-ready operating flow

Run `RUN_ALL.bat` to perform refresh QA, rebuild the baseline/DGT outputs, run all six robustness scenarios, and create machine-readable public exports. The refresh step compares registered file hashes, validates changed CSV schema/row counts, flags statewide seat changes above 20%, and stops when human review is required.
When an official source file is intentionally updated, replace the file, then run `python refresh_pipeline.py --make-baseline` to reset the registered baseline before the next scheduled refresh.

Public downloads are in `public_export/`: `district_indicators.csv`, `district_indicators.json`, `scenario_robustness.csv`, and `data_dictionary.csv`. The public export also includes `iti_trade_rows.csv`, `district_trade_seats.csv`, and `suppression_check.csv`.

The public suppression threshold is `min_count_suppression = 5`. No personal data is ingested; suppression is a safeguard for future finer-grained data. Genuine observed cells below the threshold are flagged and their public supply/demand/ratio values are blanked. An absent source observation is reported separately with `not_observed`.

The six-scenario summary is `out/run_summary.json`; it records the district(s) that are top-five in all six scenarios and the count of districts whose rank range exceeds 5.

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
Demand uses a configurable district allocator: Udyam employment share, Udyam enterprise-unit share, or a 50/50 blend. The default is employment share. Structural allocator sensitivity is reported in `demand_allocator_rank_stability.csv`; a district priority is considered robust only when it remains high across these allocator choices. Proxy supply uses the historical DGT division pool with a district ITI-count weight. The allocation draw is a multiplier with mean 1.0, so it cannot divide the district base twice.

### Shared uncertainty
The same Monte Carlo draw index is used across districts for global rates and allocation draws. District rank stability is reported from those shared draws.

### Unmatched rows are never dropped
The matcher reports exact, alias, fuzzy and review states. Unmatched rows remain in the review outputs.

### Provenance is preserved
The registry keeps source URL, grain, year, SHA-256 and source ID. The raw source files are not overwritten.

## Run it

Create a clean virtual environment and run the two documented model passes:

```text
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python self_test.py
python run_gap.py --demand-allocation-method udyam_employment --out out/proxy_baseline
python run_gap.py --actual-supply clean/dgt_cts_2026_karnataka_supply_nco.csv --proxy-allocation-method dgt_2026_seat_share --demand-allocation-method udyam_employment --out out/dgt_share_run
python run_demand_scenarios.py
python -m pytest -q
python make_submission_pdf.py
python ksisu_gui.py
```

> [!NOTE]
> `python -m pytest -q` executes 35 end-to-end integration tests across multiple full Monte Carlo simulations (5,000 draws each) and takes approximately 3 minutes to complete. It has not hung.

The first run is the proxy baseline. The second is the DGT-share evidence-upgrade run. The PDF reads both run directories so its numbers cannot silently drift from the model.

## GUI judge demonstration

You can run the complete 3-minute sequence automatically or step-by-step:

### Automated 3-Minute Judge Flow
1. Click **Run 3-Min Judge Demo** on the top toolbar.
2. The flow runs all six scenarios, regenerates public exports, and applies the V17 policy layer.
3. Automatically opens **3. District Priority**:
   - Inspect **Evidence Level**: 27 districts in `A – Exploratory`, 3 districts in `B – Watchlist` (Gadag, Tumakuru, Vijayapura).
   - Inspect **Robust 6-Scen**: Highlights Vijayapura with the `★ robust` badge as the sole district top-5 in all 6 scenarios.
4. Switch to **4. Policy Actions**:
   - Notice the prominent evidence banner: *"Gate status: NEEDS DATA for all cells; levels A/B are data-collection and verification actions, not seat decisions."*
   - Inspect operationalised DSDP clauses, decision-makers, and evidence limitations.
   - Note on **Vijayapura**: While Vijayapura is the headline structurally robust priority, no official district skill development plan (DSDP) is bundled in the source register; it explicitly relies on the generic evidence safeguard (`ALL_DISTRICTS`) rather than an invented or substituted plan.

### Manual Step-by-Step Flow
1. Click **Run Proxy Baseline**. Say: "This is what KSISU can infer before complete district ITI supply is available. Mathematical ratios are shown, but policy status remains NEEDS DATA."
2. Show **District Priority** and explain the VOI/data-collection ranking.
3. Click **Load DGT 2026 Real Supply** (or **Load Official NCVT Sample**).
4. Click **Run With Loaded Supply**.
5. Click **Run DGT Share Upgrade**.
6. Inspect **District Priority**, **Policy Actions**, **Sensitivity**, and **Validation & Linkage**.

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
- Full actual gate requires all 30 analytical geographies x both modeled NCO groups and <=5% truly UNMAPPED seat share; OUT_OF_SCOPE trades are reported separately.
- District allocation uses populated historical 2022 district ITI-count weights from an official Rajya Sabha CTS table, scaled to the NCVT statewide seat magnitude.
- Demand includes independent per-district lognormal allocation uncertainty (sigma 0.35, configuration assumption).
- District ranking is by uncapped median R; SCI is reported separately.
- Conservation is compared with the triangular-mean expectation, not the mode.
- GUI and PDF use the same model outputs and configuration.


### Annexure-IV evidence (what is and is not verified)
The package reproduces 30 historical analytical-geography ITI weights from the bundled machine-extracted Annexure-IV source representation. This reproduces the printed totals 275 Government + 1,227 Private = 1,502, but the package does not claim independent visual verification of the government PDF binary.

- The comparison uses `raw/rajya_sabha_annexure_iv_official_text_extract.md`, which is machine-extracted **text** of the official PDF with labels as printed (Belgaum, Bellary, Bijapur...). It is not a scan, and the PDF binary itself is not stored here because it could not be downloaded into the build environment.
- Re-run the check any time: `python verify_iti_counts.py` (also run by `SELF_TEST.bat`).
- `raw/rajya_sabha_annexure_iv_page6_PROJECT_TRANSCRIPTION_not_official.*` is a project-made summary table. It is **not** the official document and is not evidence.
- To confirm visually, open the official URL and compare page 6.
- The counts are historical 2022 allocation weights, not current district seat totals.


## Bundled real DGT supply evidence

The package now includes the uploaded official DGT CTS-2026 Provisional Dynamic Seat Matrix PDF and an extracted Karnataka dataset:

- `raw/dgt_cts_2026_provisional_seat_matrix.pdf`
- `raw/dgt_cts_2026_karnataka_provisional.csv`
- `clean/dgt_cts_2026_karnataka_supply_nco.csv`

The DGT letter says the provisional matrix was generated from approved instructor mappings as of 08.07.2026 and could change until the 20.07.2026 cut-off. Therefore these rows are labelled provisional public evidence, not a final frozen seat matrix. The Karnataka extraction in this build contains 1,734 ITI/trade rows, 588 ITIs and 45,416 provisional seats. A pilot human-reviewed trade-to-NCO mapping places 39,984 seats (88.0%) into NCO 72/74; 5,432 seats (12.0%) are explicitly OUT_OF_SCOPE for the pilot. True UNMAPPED seats are tracked separately. The full policy gate remains closed because 58 of 60 analytical district-group pairs are covered and the source is provisional.


## V12 Coverage-Weighted DGT Share Evidence Upgrade

V11 adds a third supply allocation mode:

`dgt_2026_seat_share`

It uses the real DGT CTS-2026 district/group seat distribution as an evidence signal, but first shrinks each district/group share toward the historical 2022 ITI-count proxy using approximate matrix coverage = DGT ITIs in the matrix / 2022 ITI count. A district absent from DGT therefore keeps its proxy share instead of receiving zero supply. The blended distribution is perturbed with shared Dirichlet uncertainty (concentration 18, 75% mean retention) because the DGT matrix is provisional and incomplete. The mode remains policy-gated and reports the DGT/ITI proxy Spearman diagnostic, matrix-coverage fields, and DGT observed-seats-to-modeled-supply ratio.

Run:
```text
python run_gap.py --out out/proxy_baseline
python run_gap.py --actual-supply clean/dgt_cts_2026_karnataka_supply_nco.csv --out out/dgt_run
python run_gap.py --actual-supply clean/dgt_cts_2026_karnataka_supply_nco.csv --proxy-allocation-method dgt_2026_seat_share --out out/dgt_share_run
```

The primary conservation benchmark is the mean across Monte Carlo draws; the prior median-of-cell-medians figure is retained separately for diagnostics.

## Demand allocator structural sensitivity

The model can allocate district manufacturing demand using:
- `udyam_employment`: district Udyam employment shares (default);
- `udyam_units`: district Udyam enterprise-unit shares from the June 2026 district totals file;
- `blend`: the 50/50 average of the two normalized shares.

Use `--demand-allocation-method` to choose a method. The default run writes `demand_allocator_rank_stability.csv`. It contains district ranks under all three allocators, the rank range, and a `top5_all_methods` flag. A robust district priority should remain high across the allocator alternatives. The 0.35 lognormal term remains a within-allocator uncertainty prior; it is an explicit assumption with no empirical district calibration. The 50/50 blend is an arbitrary midpoint sensitivity case because enterprise units and employment measure different concepts.

### Six-scenario judge check
Run `RUN_DEMAND_SCENARIOS.bat` to execute proxy and DGT-share supply routes under all three demand allocators. The combined `out/scenario_robustness.csv` is the judge-facing robustness table. A district is structurally robust only if it remains top-five across all six scenarios; otherwise describe the ordering as assumption-driven.




## V18 Policy-to-Evidence Refinements

The policy layer remains a separate add-on around the frozen model outputs. `policy_layer.py <root>` derives every output path from the supplied root, reads district aliases from `clean/district_aliases.csv`, and writes policy state to `out/policy_summary.json` rather than mutating the model `out/run_summary.json`.

`out/policy_actions.csv` now presents `evidence_level_name` and `model_gate_status` separately (for example, `Provisional watchlist | gate: NEEDS DATA`) and includes `action_basis` to distinguish a KSISU rule from the cited district-plan channel. The `main_evidence_limitation` field is deliberately a limitation statement, not a measured sensitivity driver.

The policy register has 23/30 analytical districts with district-specific clauses. The other seven use an explicit `ALL_DISTRICTS` generic safeguard and no longer cite another district's plan. Vijayapura therefore no longer displays Ballari p.24 as its policy source; the bundled policy-source manifest is the audit surface for all source-backed clauses.

Benchmark comparison is reported as district-level benchmark-to-model-P50 ratios and P10-P90 inclusion. The current rank correlation is retained only with its sample size and exact permutation p-value; it is explicitly labelled directional triangulation, not validation.

The package now bundles the supplied policy PDFs under `docs/policy_sources/`, together with `docs/policy_source_manifest.csv`, so a judge can independently inspect every source-backed page citation. If a future official Vijayapura DSDP is added, add it to the supplied policy bundle and then promote the generic Vijayapura fallback to a district-specific register row; do not substitute another district's plan.
