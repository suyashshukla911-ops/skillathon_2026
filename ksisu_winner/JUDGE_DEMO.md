# 3-minute judge demonstration — final flow

## 0. Start

Run `RUN_ALL.bat` once to build and validate the full package. Then launch the GUI with `python ksisu_gui.py` for the interactive three-minute demonstration.

The GUI starts in **proxy baseline** mode and does not permit manual invention of supply numbers.

## 1. Baseline — show the discipline

Click **Run Proxy Baseline**.

Open **2. Gap Results**.

Say:

> “The model produces an analytical alignment interval, but policy status remains NEEDS DATA because district ITI supply is still a proxy.”

This immediately avoids the earlier failure where every district was presented as a proven gap.

## 2. Show where KSISU should collect data first

Open **3. District Priority**.

Point to:

- SCI
- VOI
- Data priority
- evidence score

Say:

> “We are not ranking districts by size alone. We rank the value of resolving their uncertainty, weighted by the stakes.”

## 3. Load real district evidence

Click **Load DGT 2026 Real Supply** for the bundled real public DGT evidence, or **Load Other Real Supply CSV** for a newer/current district x trade extract.

The bundled DGT file is an extraction from the official CTS-2026 provisional dynamic seat matrix. It contains real Karnataka ITI/trade seat-capacity rows, but the source is provisional and incomplete for the 30 analytical geographies.

## 4. Re-run

Click **Run With Loaded Supply**.

Open **2. Gap Results**.

Show that the affected cells now say `partial-observed-floor` rather than `district-proxy`.

They remain `NEEDS DATA` because coverage is incomplete. The interval change is not presented as a certainty gain: the observed seats are treated as a floor and the unobserved remainder stays uncertain.

## 5. Prove the uncertainty change

Open **5. Validation & Linkage**.

Show the partial-evidence update table: before width, after width, width change, and whether the interval widened or narrowed.

Say:

> “This experiment shows how the same model responds to better evidence. With a partial file the interval can widen; a complete district extract is the condition for a genuine uncertainty reduction.”

For the DGT 2026 evidence, describe the result as a **real but incomplete evidence update**. Mapped district×trade seats inform a coverage-weighted share allocation; the historical proxy remains in proportion to matrix coverage, so sparse or missing geographies do not become artificial zero-supply districts. The policy gate stays NEEDS DATA.

## 6. Sensitivity

Open **4. Sensitivity**.

Say:

> “We test rank stability across the shared Monte Carlo draws. This shows whether a data-collection priority is stable under common uncertainty, rather than simply repeating the chosen input ranges.”

## 7. Validation

Open **5. Validation & Linkage**.

Show:

- seeded typo recovery;
- unseen aliases sent to review;
- duplicates flagged;
- no unmatched rows dropped;
- provenance and source file registry.

## Demand-allocation robustness

Open `out/demand_allocator_rank_stability.csv`. Explain that this compares district rank under employment-share, enterprise-unit-share and blended demand allocators. Treat a district as structurally robust only when it remains highly ranked across these alternatives.

## Closing line

> “The product is not the dashboard. The product is a reproducible evidence pipeline that tells KSISU what it can infer today, what it cannot infer, and which district evidence to collect first.”

## Final competition upgrade

Before submission, replace/augment the bundled provisional DGT matrix with the **complete current district×trade seat extract** when available. Do not type or fabricate missing seats.

## V5 technical gates the demo now enforces

- District proxy allocation uses the populated historical 2022 district ITI-count weights; these are allocation weights only, not current district seat totals.
- District ranking is by the uncapped median ratio R. SCI is shown separately because it is capped at 1.
- Full district-actual evidence requires all 30 analytical geographies x both modeled NCO groups (72, 74) and no more than 5% of input seats unmapped.
- If the real file contains trades outside the 72/74 pilot, label them `OUT_OF_SCOPE` and report their seats separately. Only truly `UNMAPPED` seats count toward the 5% mapping gate.
- Full supply evidence does not upgrade demand evidence: district demand is still a proxy until district employment / DSDP / MIS evidence is loaded.
- Demand allocation has its own shared per-district lognormal uncertainty (sigma 0.35; documented as an analyst assumption) so demand uncertainty is not accidentally treated as zero.

### Six-scenario robustness (preferred judge statement)
Open `out/scenario_robustness.csv` (also copied to `public_export/scenario_robustness.csv`). `out/run_summary.json` records the robust district(s) and the number of districts whose rank range exceeds 5. This combines the six model scenarios: proxy supply × three demand allocators, and DGT-share supply × the same three allocators. Use the `top5_appearances`, `rank_range`, and `top5_all_six` columns. A district is structurally robust only when it remains highly ranked across all six scenarios. The current build has one district in the top five in all six scenarios; most ordering changes with assumptions.

The 50/50 demand blend is an arbitrary midpoint sensitivity case, not an empirically calibrated estimator. Udyam enterprise units and Udyam employment measure different underlying concepts. The within-allocator demand sigma of 0.35 is also an explicit analyst assumption with no district-level calibration yet.
