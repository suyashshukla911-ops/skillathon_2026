Rajya Sabha Q131 Annexure-IV - evidence and how it was checked
==============================================================

Official source (authoritative):
  https://sansad.in/getFile/annex/258/AU131.pdf?source=pqars
  Government of India, Ministry of Skill Development and Entrepreneurship,
  Rajya Sabha Unstarred Question No. 131, answered 07.12.2022.
  Annexure-IV (CTS ITIs), PDF page 6 of 6.

What is in this folder, and what each file is
---------------------------------------------
1. rajya_sabha_annexure_iv_official_text_extract.md
   Machine-extracted text of the OFFICIAL PDF, retrieved 2026-10-17, labels exactly
   as printed (Belgaum, Bellary, Bijapur, Gulbarga, ...). Not re-typed.

2. rajya_sabha_annexure_iv_cts_as_printed.csv
   The table above in CSV form, parsed by verify_iti_counts.py, with a column that
   maps each printed label to the model's analytical geography.

3. rajya_sabha_annexure_iv_page6_PROJECT_TRANSCRIPTION_not_official.pdf / .png
   A project-made table in analytical-geography names (Ballari-Vijayanagara, Belagavi...).
   It is NOT a scan or screenshot of the official page and is kept only as a
   readable summary. Do not treat it as source evidence.

4. rajya_sabha_annexure_iv_official_url.txt - the official URL.

What was checked
----------------
Run `python verify_iti_counts.py` (also part of SELF_TEST). It checks that
  - every printed row has Govt + Private = Total, and the printed column totals
    are reproduced: 275 Government + 1,227 Private = 1,502;
  - all 30 analytical geographies in clean/district_iti_counts.csv (Govt, Private,
    Total) equal the printed row they map to;
  - clean/ and input_templates/ copies of the file are identical.

Limits (stated plainly)
-----------------------
  - The check is against machine-extracted TEXT of the official PDF. The original PDF
    binary could not be downloaded into the build environment, so it is not stored here.
    To confirm visually, open the URL above and compare page 6 with item 1.
  - Historical Bellary (89) is used as the merged Ballari-Vijayanagara geography.
  - The printed table has two zero rows (Uttara Kannada, Vijayapura) that are source
    artifacts: the non-zero counts are printed under "Uttar Kannad" (24) and
    "Bijapur" (98). They are not separate analytical geographies.
  - The counts are historical 2022 allocation weights, not current district seat totals.
