# V17 Policy-to-Evidence Layer Changelog

## Purpose
V17 adds a policy-to-evidence layer around the frozen KSISU model. The model, demand allocators, DGT-share logic, and evidence gate are unchanged.

## Added
- `clean/policy_register.csv`: 75 page-cited operational clauses sourced only from the attached district skill-development / annual-work-plan PDFs.
- `clean/dsdp_benchmark.csv`: seven numeric external benchmark rows from attached DSDPs, with explicit comparability labels.
- `policy_layer.py`: joins existing public district indicators to the cited policy register and writes evidence levels, district actions, and benchmark comparisons.
- `out/district_evidence_levels.csv`
- `out/policy_actions.csv`
- `out/dsdp_benchmark_comparison.csv`
- `out/dsdp_benchmark_summary.csv`
- `out/policy_mapping_quality.csv`
- `docs/policy_source_manifest.csv`: source-file SHA-256/page-count inventory for the supplied policy bundle.

## Evidence levels
- `A_EXPLORATORY`: data-collection priority.
- `B_PROVISIONAL_WATCHLIST`: top-five in at least 5 of 6 scenarios and rank range <=5; action is verification before any seat decision.
- `C_POLICY_READY`: existing full evidence gate only; unchanged.

Current frozen state: 27 A, 3 B (Gadag, Tumakuru, Vijayapura), 0 C.

## Geography mapping
The register stores both source geography and explicit analytical geography. Ballari and Vijayanagara source plans map to the analytical `Ballari-Vijayanagara` unit. The Vijayanagara plan is the primary clause source (priority 1) and the Ballari plan is retained as secondary traceable evidence (priority 2). No source geography is silently treated as the analytical geography.

## External triangulation
The DSDP comparison is deliberately directional triangulation, not validation. Five one-to-one demand/capacity benchmark rows are used for rank correlation; two of those five fall inside the model P10-P90 interval. The current Spearman rank correlation is 0.30. Broader-scope, training-target and merged-geography rows remain visible but are excluded from the one-to-one correlation sample.

## Operating rule
`RUN_ALL.bat` runs `verify_iti_counts.py` first and `policy_layer.py` after public export. A legitimate source update uses:

```text
python refresh_pipeline.py --make-baseline
```

before the next scheduled refresh.
