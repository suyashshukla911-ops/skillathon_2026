# KSISU Real-Data Method Memo

## 1. Problem definition

The pilot is intentionally narrow: **manufacturing only**, with ITI-linked occupation groups NCO **72, 74 and 81**. The question is whether public data can support district-level alignment between estimated annual openings and ITI trade supply, and, where it cannot, which districts have the highest value of better data.

## 2. Demand

Let d = district and o = NCO group.

1. State manufacturing employment base `M_state` is taken from ASI 2022-23 for Karnataka selected manufacturing.
2. District proxy share `w_d` is district Udyam employment / statewide Udyam employment.
3. District manufacturing employment proxy:

`M_d = M_state * w_d`

4. Occupation share `m_o` is restricted to NCO 72/74/81 and normalised from the versioned occupation-prior file until PLFS microdata is loaded.
5. Annual openings:

`O_d,o = M_d * m_o * r_open`

where `r_open` is triangular(low, mode, high).

The explicit assumption is that the occupation mix within manufacturing does not vary by district until district or microdata evidence replaces the prior.

## 3. Supply

`S_d,o = Seats_d,o * Fill * Completion * SectorEntry`

- `Seats_d,o` comes from district/trade input when the user loads actual NCVT MIS/DGT/Karnataka data.
- Without district data, the state NCVT MIS 2022 seat total is allocated using the historical DGT/DITE division structure and district Udyam shares within each division. This is marked as `district-proxy`.
- Trade to NCO mapping is versioned in `clean/crosswalk.csv`.

Seats, fill, completion and sector entry remain separate quantities. A seat is never treated as a graduate.

## 4. Uncertainty

5,000 Monte Carlo draws use triangular distributions. The draw arrays for each global parameter are **shared across all districts**, so the district comparison is reproducible and not contaminated by independent random noise in every row.

`R_d,o = S_d,o / O_d,o`

Report p10, median and p90.

- Mathematical GAP: p90 < 1
- Mathematical SURPLUS: p10 > 1
- Otherwise NEEDS DATA

Policy decision is conservative:

- Proxy-only run: policy status = NEEDS DATA
- District-actual supply loaded: policy status = PROVISIONAL GAP / PROVISIONAL SURPLUS / NEEDS DATA

## 5. Skill Coverage Index

`SCI(d) = sum_o O_d,o * min(R_d,o,1) / sum_o O_d,o`

This is a project indicator for the share of annual openings that local training could cover under the model.

## 6. Confidence

Confidence combines:

- evidence tier for state / district-proxy / district-actual inputs,
- district match rate,
- interval width penalty.

Confidence is not a completeness score.

## 7. Value of Information

`VOI(d) = interval_width * annual_openings`

The higher the VOI, the stronger the case for KSISU to request better district data there first.

## 8. Validation

- District corruption test: old names, aliases, typos and 5% duplicated rows.
- Temporal sanity check: 2022 Udyam district allocation share versus 2023 Udyam employment share. This is explicitly a consistency check, not an independent benchmark.
- Sensitivity: one-at-a-time low/high movement for opening, fill, completion, sector entry and proxy-seat uncertainty.

## 9. Replacement rule

The prototype is built so that the proxy can be replaced, not hidden. When district-actual ITI trade seats are loaded, the same code reruns the calculation and the policy status can move from NEEDS DATA to a provisional interval-based result. The source file IDs and run audit record preserve reproducibility.
