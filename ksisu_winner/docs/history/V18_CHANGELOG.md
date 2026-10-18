# V18 Change Log — Policy-to-Evidence Refinement

## Scope
This release keeps the analytical/model layer frozen and hardens the separate policy evidence layer.

## Changes
- Removed the misleading Ballari DSDP page citation from `ALL_DISTRICTS` fallback rows.
- Added explicit generic safeguard wording for districts without a supplied district-specific plan; no unrelated district is cited as a substitute.
- Added a dynamic `23/30` district-specific-clause mapping-quality check.
- Split `evidence_level_name` from `model_gate_status` in policy outputs.
- Renamed `main_uncertainty_driver` to `main_evidence_limitation`; wording no longer implies a measured sensitivity decomposition.
- Added `action_basis` to distinguish the KSISU rule from the cited DSDP policy channel.
- `policy_layer.py <root>` now derives every read/write path from the supplied root.
- District aliases are loaded from `clean/district_aliases.csv`; Ballari/Vijayanagara/Bellary aliases resolve to the merged analytical geography.
- Policy state is written to `out/policy_summary.json`; `out/run_summary.json` remains model/robustness-only.
- Mapping validation now checks source file presence, manifest membership, page <= manifest page count, bundled SHA-256, and district-specific vs generic coverage.
- DSDP triangulation now reports benchmark-to-model-P50 ratios per district and Spearman n + p-value; it is explicitly labelled directional triangulation, not validation.
- Bundled the supplied policy PDFs under `docs/policy_sources/` so judges can independently inspect page-cited clauses.
- Added `docs/policy_source_duplicates.csv` for exact duplicate-source bookkeeping.
- `RUN_ALL.bat` retains ITI verification as the first command and the policy layer as the final command.

## Current policy-state regression
- 27 districts: A_EXPLORATORY
- 3 districts: B_PROVISIONAL_WATCHLIST (Gadag, Tumakuru, Vijayapura)
- 0 districts: C_POLICY_READY

## Validation
- `python self_test.py`: 18/18 PASS
- `python -m pytest -q tests/test_policy_layer.py`: 12/12 PASS
- Public/export/refresh regression subsets passed.
- Full unfiltered pytest remains compute-heavy in the container; one pre-existing pipeline test can exceed the execution window. No model change was made to address it.
