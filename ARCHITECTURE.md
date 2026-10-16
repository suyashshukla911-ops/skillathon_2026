# KSISU Prototype Architecture

```text
                           DATA SOURCES
              departments / central govt / industry
                 Excel / CSV / APIs / reports
                              |
                              v
                    INGESTION CONNECTORS
                              |
                              v
                         RAW STORE
                  immutable source artifacts
                              |
                              v
                    SOURCE REGISTRY / CATALOG
        file_id | checksum | version | schema | period | owner
                              |
                              v
                       DATA QUALITY
             completeness | validity | uniqueness
                              |
                              v
                     SCHEMA MAPPER
         district | occupation | industry | demand | year
                              |
                              v
                     HARMONISATION
                  LGD      NCO      NIC
                              |
                              v
                    CURATED DATA MODEL
       training | demand | economy | labour | lineage
                              |
                              v
                      INTELLIGENCE
               supply vs demand | trends | gaps
                              |
                              v
                    EVIDENCE FOR KSI
                              |
             +----------------+----------------+
             |                                 |
             v                                 v
      Government analytics             Public outputs
```

The 31 district Excel files bundled in the demo represent source artifacts only.
