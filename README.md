# KSISU Data Intelligence Workbench

This package implements the source-driven architecture discussed for the KSISU prototype.

## Core idea

Do not treat 31 district Excel files as the final KSISU architecture.

Treat them as **simulated source artifacts** that enter a common pipeline:

**Data Sources → Ingestion → Raw Data Store → Data Catalog / Metadata → Data Quality → Schema Detection → LGD/NCO/NIC Harmonisation → Curated Data Model → Analytics / Skill Gap**

## What is implemented

### Source discovery
Recursive discovery of CSV/XLSX/JSON/HTML artifacts under `data/incoming/`.

### File registry
Each ingested artifact gets:
- `file_id`
- source/dataset name
- district hint
- period
- format
- row count
- schema
- SHA-256 checksum
- version
- privacy/status
- raw stored copy

The registry is stored in `runtime/ksisu.db`.

### Raw layer
Original source artifacts are copied to:

`runtime/raw_store/`

They are not overwritten by cleaning.

### Schema mapper
Common aliases are mapped to canonical fields, e.g.:
- `DISTRICT_NAME` → `district`
- `JOB_ROLE` / `TRADE` → `occupation`
- `VACANCIES` → `demand`
- `FIN_YEAR` → `year`

Unknown columns are retained as `raw_*`.

### Quality engine
Checks:
- missing district/occupation/industry
- missing demand/supply
- exact duplicates
- near-duplicate groups
- prototype file quality score

### Harmonisation
Supports:
- district → LGD
- occupation → NCO
- industry → NIC

Import official master tables using the templates in `data_templates/`.

### Curated layer
Creates:
- `training_supply.csv`
- `skill_demand.csv`
- `economic_activity.csv`
- `labour_supply.csv`
- `curated_fact.csv`

and corresponding SQLite tables.

### Intelligence
Computes:
- district × industry × occupation groups
- demand
- usable supply
- supply method
- gap
- gap %
- mapping confidence
- signal
- human-review recommendation
- source file IDs

### Lineage
Each analytical record retains source file IDs, and the raw artifact is retained on disk.

## Demo data note

The 31 district Excel files contain synthetic metrics. Some company/entity names were included for realism, but their associated numbers are not official statistics.

## Production next step

Replace the demo source artifacts with publicly available, non-personal datasets and authoritative LGD/NCO/NIC masters.

The official KSI formula is intentionally not fabricated in this prototype. The prototype produces the harmonised evidence layer that can feed an eventual index.

### Demo mapping for local testing
The `examples/demo_masters/` files contain synthetic DEMO-LGD/DEMO-NIC/DEMO-NCO labels only. They exist so you can demonstrate the mapping stage locally. They are not official classification codes.
