# Web verification used for the final pilot

## Official LGD
Local Government Directory download interface:
https://lgdirectory.gov.in/demo/downloadDirectory.do

Use the live Karnataka district export before final submission. The prototype currently carries 31 district rows as its join-key working copy.

## Rajya Sabha Q131 Annexure-IV (historical ITI counts)
Official PDF: https://sansad.in/getFile/annex/258/AU131.pdf?source=pqars (Annexure-IV, page 6).
Checked 2026-10-17: the official PDF was run through a PDF text extractor and the CTS table was compared with `clean/district_iti_counts.csv` by `verify_iti_counts.py`. All 30 analytical rows match (Govt, Private, Total) and the printed totals 275 + 1,227 = 1,502 are reproduced. The PDF binary is not bundled; the check is against extracted text, so confirm visually on page 6 if needed.

## Karnataka Udyam district employment
Official OGD resource:
https://data.gov.in/resource/karnataka-udyam-registration-units-employment-details-district-wise-april-2023

The project uses this only as a district allocator, not as manufacturing employment.

## ASI
MoSPI ASI 2022-23 summary:
https://www.mospi.gov.in/sites/default/files/asi_results/ASI%20Summary%20Results%202022-23.pdf

Bundled state value: 1,166,555 persons engaged in selected manufacturing sector.

## PLFS
MoSPI PLFS annual report:
https://www.mospi.gov.in/sites/default/files/publication_reports/AR_PLFS_2022_23N.pdf

The pilot does not pretend to have a district occupation-by-industry estimate from PLFS. The occupation mix is explicitly marked as an analyst prior until microdata extraction is completed.

## NCVT MIS
ITI search:
https://www.ncvtmis.gov.in/Pages/ITI/Search.aspx

ITI count:
https://www.ncvtmis.gov.in/pages/iti/count.aspx

Indexed district/trade table used for the partial real-evidence demo:
https://ncvtmis.gov.in/Pages/FileDownload.aspx?fileId=1171

The official index exposes district, ITI, trade and seat fields. The bundled partial extract uses verified rows for Tumakuru and Kalaburagi only.

## DGT / Karnataka DITE
The DGT/DITE tracer material is included only for historical division-level training calibration. It is not presented as district supply.
