# KSISU Skillathon 2026 — Final Project Position

## What this build is
A reproducible, source-driven manufacturing skill-alignment pilot for Karnataka. It is designed to answer: what can public data support today, what remains uncertain, and where KSISU should collect district evidence first.

## Scope
- Manufacturing only
- NCO groups 72, 74 and 81
- FY 2022-23 reference
- 5,000 shared Monte Carlo draws, fixed seed
- Policy gate: proxy/partial actual -> NEEDS DATA; complete district-actual -> provisional interval call

## What is demonstrated with real public evidence
- 31 district LGD-style matching
- ASI Karnataka manufacturing state base
- Karnataka Udyam district employment as a clearly labelled district allocator proxy
- NCVT MIS File 1171 indexed real rows for Tumakuru and Kalaburagi as a partial district-trade evidence upgrade
- Seats -> fill -> completion -> sector entry -> NCO crosswalk
- evidence update when partial/full district evidence replaces the proxy; partial rows are treated as floors and may legitimately widen the interval
- corruption/review queue
- provenance and audit log
- sensitivity and VOI priority

## What is intentionally not claimed
- No official Karnataka Skill Index formula
- No complete district ITI supply without a complete current NCVT/DGT/Karnataka extract
- No empirical occupation-by-industry prior until PLFS microdata is loaded
- No policy gap call from proxy or partial evidence

## Judge demo
Run `run.bat`, then click `Run 3-Min Judge Demo` or follow `JUDGE_DEMO.md`.
