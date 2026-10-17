# KSISU Real-Data Method Memo — Final Pilot

## 1. Research question

This pilot is intentionally narrow: **manufacturing only**, focused on ITI-linked NCO groups **72 and 74**.

The operational question is:

> Can public data support a defensible district-level comparison between estimated manufacturing openings and ITI trade supply, and when it cannot, which district should KSISU onboard first for better evidence?

The model distinguishes an **analytical signal** from a **policy decision**.

## 2. Demand model

Let d = district and o = selected NCO group.

1. `M_state` is Karnataka manufacturing persons engaged from ASI 2022-23.
2. `w_d` is the configured district demand-allocation share. The supported bases are Udyam employment share (default), Udyam enterprise-unit share, and their 50/50 blend. These are transparent allocators, **not manufacturing employment**.
3. `M_d = M_state * w_d`. The chosen allocator and its share sum are recorded in the audit log.
4. The selected NCO occupation shares remain fractions of **total manufacturing employment**. They are not renormalised.
   - NCO 72 = 0.25
   - NCO 74 = 0.15
   - 0.40 remains outside this pilot scope; NCO 81 is intentionally excluded from the pilot.
5. Annual openings:
   `O_d,o = M_d * m_o * r_open`
   where `r_open` is triangular(low, mode, high).

This avoids the previous basis error of multiplying all-sector Udyam employment by a manufacturing worker share.

## 3. Supply model

`S_d,o = Σ seats_d,c × fill × completion × sector_entry × x(c→o)`

- `seats` is capacity, not graduates.
- `fill` converts capacity to enrolment.
- `completion` converts enrolment to completion.
- `sector_entry` is the share entering the selected sector.
- `x(c→o)` is a versioned course/trade → NCO crosswalk.

### Demand allocator sensitivity

Three structurally different demand allocators are compared: `udyam_employment`, `udyam_units`, and `blend`. The output `demand_allocator_rank_stability.csv` records each district's rank under every allocator, its range across them, and whether it stays in the top five across all three. This is the main structural sensitivity for district ordering. The 0.35 lognormal term captures within-allocator allocation uncertainty only and has no empirical district calibration yet; it is an explicit assumption, not an observed Karnataka rate.

### Proxy supply

When district×trade seats are not available, the prototype uses the historical DGT/DITE division training structure and an **equal-within-division** district allocation. It deliberately does **not** reuse the Udyam district share used by demand, so demand and supply do not mechanically cancel to the same district pattern.

Proxy supply is a research assumption, not a finding.

### Actual supply

When a real NCVT MIS/DGT/Karnataka district×trade file is loaded, full district rows replace the proxy for the relevant district/trade cells. A file labelled partial is treated as observed floor + uncertain remainder. The DGT-share upgrade uses a coverage-weighted blend: DGT group share is blended with the historical 2022 ITI-count proxy using DGT-ITI / 2022-ITI coverage. This avoids treating sparse DGT districts as zero-supply districts. Missing trade cells stay proxy or missing; they are never silently treated as actual.

The bundled `raw/ncvtmis_file1171_real_partial.csv` contains a small official NCVT MIS indexed subset for Tumakuru and Kalaburagi. It is labelled **partial_floor** in the model: observed seats are a lower bound and the unobserved remainder stays uncertain. It cannot trigger a policy call by itself.

## 4. Monte Carlo uncertainty

5,000 draws use triangular distributions with a fixed seed.

The draw index for each global parameter is shared across districts so that districts are compared under the same system-level parameter realization.

Additional shared uncertainty is applied to the occupation prior and district allocation.

`R_d,o = S_d,o / O_d,o`

Report p10, median and p90.

- Mathematical shortfall signal: p90 < 1
- Mathematical SURPLUS: p10 > 1
- Otherwise: NEEDS DATA

### Policy gate

- Proxy-only: **NEEDS DATA**
- Partial actual: **NEEDS DATA**
- Complete district-actual cell: may become **PROVISIONAL GAP**, **PROVISIONAL SURPLUS**, or **NEEDS DATA**

## 5. Skill Coverage Index

`SCI(d) = Σ_o O_d,o × min(R_d,o,1) / Σ_o O_d,o`

SCI is a proposed project indicator, not an official Karnataka Skill Index formula.

## 6. Evidence score

The evidence score is not a probability and not a generic completeness percentage.

It combines configured weights for:

- demand evidence tier;
- supply evidence tier;
- district matching quality;
- interval width.

The weights are stored in `clean/config.json`.

## 7. Value of Information

`VOI(d) = interval_width × annual_openings`

The user-facing data-collection priority is:

`Priority(d) = VOI(d) × (1 - evidence_score(d))`

This reduces the chance that a large district wins priority merely because it is large.

## 8. Validation

### Linkage corruption test

The pipeline creates a seeded corruption sample with:

- unseen historical-style aliases;
- seeded typos selected to be fuzzy-matchable;
- about 5% duplicates.

The test reports:

- typo recovery rate;
- unseen aliases routed to review;
- duplicates that would be removed;
- confirmation that unmatched rows remain in the review queue.

### Independent benchmark

An external district employment total can be supplied through `input_templates/validation_totals_template.csv`. Until such a benchmark is loaded, the bundled Udyam 2022-vs-2023 comparison is reported only as a **temporal consistency check**, not as independent validation.

## 9. Sensitivity

The sensitivity output includes:

- opening rate;
- seat fill rate;
- completion rate;
- sector entry rate;
- occupation-prior uncertainty;
- allocation-share uncertainty;
- proxy-seat uncertainty.

## 10. Provenance and reproducibility

Every run records:

- source file ID;
- source URL;
- SHA-256 checksum;
- period and grain;
- configuration;
- Monte Carlo seed;
- number of draws;
- output file names.

The source registry is never overwritten with blank URLs or `unknown` grain.

## 11. What must be replaced before a high-stakes final empirical claim

1. Refresh the 31-row LGD export from the official LGD download interface.
2. Load the complete current district×trade ITI seat extract from NCVT MIS/DGT/Karnataka.
3. Replace the occupation prior with extracted PLFS occupation-by-industry evidence or a defensible microdata-derived share.
4. Add an independent district employment benchmark for the downscaling sanity check.

The prototype is therefore designed as a **reproducible evidence and data-onboarding system**, not a claim that the currently public proxy inputs are already the production KSISU dataset.

### Six-scenario robustness

`run_demand_scenarios.py` runs proxy and DGT-share supply modes under all three demand allocators and writes `out/scenario_robustness.csv`. A district is called robust only when it remains in the top five across all six scenarios. In the current evidence set, only a small number of districts are repeatedly high-priority across both supply routes and demand definitions; most ordering remains assumption-driven.
