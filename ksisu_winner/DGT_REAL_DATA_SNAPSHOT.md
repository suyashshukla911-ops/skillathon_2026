# DGT CTS-2026 real supply snapshot

This build contains real public DGT seat-capacity evidence extracted from the uploaded official PDF:

- Source: Directorate General of Training, "Provisional Dynamic Seat Matrix" for CTS academic session 2026.
- Official page: https://www.dgt.gov.in/en/node/4675
- Source date: 09.07.2026; rows are based on instructor mappings as of 08.07.2026.
- Karnataka extraction: PDF pages 376-440.
- 1,734 Karnataka district x ITI x trade rows.
- 588 distinct ITI MIS codes.
- 29 published districts in the extracted matrix.
- 45,416 provisional seat-capacity records.
- 39,984 seats (88.0%) map into the pilot NCO 72/74 scope through the versioned project crosswalk.
- 5,432 seats (12.0%) are explicitly OUT_OF_SCOPE for the NCO 72/74 pilot; true UNMAPPED seats are tracked separately.
- Kodagu is absent from the analytical geography; Ballari covers the merged Ballari-Vijayanagara geography in the model.

## Interpretation

These are real public DGT rows, not synthetic numbers. They are **provisional seat-capacity evidence**, not a final frozen matrix and not student completions, placements, or employment. The evidence is therefore used to replace district supply proxies where rows are mapped, while the policy gate remains closed until complete analytical district x trade coverage, acceptable UNMAPPED share, and non-provisional evidence are achieved.
