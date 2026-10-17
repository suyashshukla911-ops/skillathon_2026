# V12 Change Log

## Main fix
The `dgt_2026_seat_share` allocation mode now uses coverage-weighted shrinkage instead of treating sparse DGT coverage as a complete district share:
- District weight = DGT ITIs in the 2026 matrix / historical 2022 ITI count, capped at 1.
- Blended share = coverage * DGT district/NCO share + (1 - coverage) * historical ITI-count proxy share.
- Missing districts such as Kodagu therefore retain non-zero proxy allocation instead of collapsing to zero.
- Shared Dirichlet concentration is 18 with 75% retention of the blended evidence mean because the DGT matrix is provisional/incomplete.

## Diagnostics added
- `dgt_itis_in_matrix`
- `iti_2022_count`
- `matrix_iti_coverage`
- `dgt_observed_seats_72_74`
- `modeled_supply_median_72_74`
- `dgt_observed_seats_to_modeled_supply_median`
- `proxy_vs_dgt_spearman`
- DGT matrix coverage summary in the audit log

## V12 verification
- `python self_test.py` -> PASS
- `python -m pytest -q` -> 15 passed
- proxy run -> exit 0
- DGT partial run -> exit 0
- DGT coverage-weighted share run -> exit 0
- final PDF -> 10 pages and rendered for visual inspection

## Interpretation
The district priority view remains a data-collection queue, not a validated district skill-gap ranking. Udyam employment remains an all-sector district demand proxy, and the DGT 2026 seat matrix is provisional.
