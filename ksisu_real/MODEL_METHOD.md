# KSISU Real-Data Method Memo

Run: RUN-20261016-165144
Reference date: 2026-10-16

## What is real public data
- 31 Karnataka district names and public LGD district-code register (live LGD export should be re-downloaded for final verification).
- Karnataka Economic Survey 2022-23 Udyam units and employment up to Nov 2022 for all 31 districts.
- PLFS 2022-23 Karnataka manufacturing worker share = 10.4%.
- DGT/DITE tracer-study 2020-21 division-level ITI sanctioned, admitted and pass-out counts.
- Karnataka Economic Survey 2023-24 Udyam employment district shares used only for temporal consistency checking.
- June 2026 district Udyam enterprise totals are retained as contextual, secondary-reconciled data.

## What is an estimate / assumption
- District manufacturing employment is a proxy: Udyam employment x PLFS manufacturing share.
- District ITI seats are a proxy: real DGT/DITE division sanctioned seats allocated within division by district Udyam employment shares.
- Occupation mix inside manufacturing is an explicit prior (clean/occupation_mix_prior.csv).
- Course/trade to NCO is a versioned analyst crosswalk (clean/crosswalk.csv).
- Annual openings = stock proxy x 5-12%.
- Fill, completion, sector-entry are triangular uncertainty inputs.

## Decision rule
R = supply / annual openings.
- Gap: p90 < 1.
- Surplus: p10 > 1.
- Needs data: otherwise.
SCI(d) = sum_o [O(d,o) * min(R(d,o),1)] / sum_o O(d,o).
VOI(d) = weighted interval width x annual openings.

## Why this is not an official KSI formula
The KSISU prototype formula, SCI and VOI are proposed analytical methods for the competition. They are not represented as an official Karnataka Skill Index formula.
