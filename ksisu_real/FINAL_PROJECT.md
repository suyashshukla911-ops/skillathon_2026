# FINAL PROJECT - KSISU Real-Data Skillathon 2026

This package is the real-data prototype, not the earlier synthetic Tkinter demo. The raw layer contains only public research inputs and explicitly labelled transcriptions/reconciliations. No company names are paired with fabricated metrics.

## Core pipeline
Ingest -> Registry -> Harmonise (LGD/NIC/NCO) -> Demand model -> Supply model -> Alignment ratio with 80% interval -> Confidence -> VOI priority -> Human review -> Output

## Worked sector / districts
Manufacturing. The draft contrasts Tumakuru (industrial/manufacturing-linked pilot) and Kalaburagi (lagging/lower-base pilot).

## Real public inputs
- 31 Karnataka district names and LGD district-code register, with a live-download verification flag.
- Karnataka Economic Survey 2022-23 Udyam units and employment up to Nov 2022 for all 31 districts.
- PLFS 2022-23 Karnataka manufacturing worker share = 10.4%.
- DGT/DITE tracer-study 2020-21 division-level ITI sanctioned/admitted/pass-out counts.
- Karnataka Economic Survey 2023-24 Udyam employment shares for a temporal sanity check.
- June 2026 Udyam district enterprise totals as contextual AMBER data.

## Explicit estimates / priors
- District manufacturing workforce proxy = Udyam employment x PLFS manufacturing share.
- District ITI seat proxy = real DGT/DITE division sanctioned seats allocated within division by district Udyam-employment share.
- Manufacturing occupation mix prior in `clean/occupation_mix_prior.csv`.
- Course/trade -> NCO crosswalk in `clean/crosswalk.csv`.
- 5-12% annual openings range.
- Triangular fill, completion and sector-entry rates.

## Reproducibility
Run `python run_gap.py` from this folder. The script rebuilds the source registry, demand/supply estimates, Monte Carlo intervals, SCI, VOI priority, corruption test, sanity check and draft PDF. Random seed = 20261016; Monte Carlo draws = 5000 per district/occupation.

## Important truthfulness limits
The district-level PLFS occupation-by-industry microdata was not directly accessible without restricted microdata registration/download, so the occupation mix in this worked illustration is an analyst prior. Direct district ITI seat data was also not verified, so a division-calibrated proxy is used. These gaps are intentional and visible in the output. They must be replaced with district-actual sources before presenting the estimates as empirical findings.

The proposed Skill Coverage Index and VOI are project indicators, not an official Karnataka Skill Index formula.
