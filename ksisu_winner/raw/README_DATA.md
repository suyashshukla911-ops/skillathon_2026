# Raw-data provenance

This folder contains public research inputs or explicitly labelled analyst priors.

- `lgd_districts.csv`: 31 Karnataka districts used as the join key. Refresh from the LGD Download Directory before final submission.
- `karnataka_udyam_employment_nov2022.csv`: Karnataka district Udyam employment proxy from Economic Survey 2022-23. This is **not** a manufacturing-employment observation.
- `asi_karnataka_manufacturing_2022_23.csv`: state manufacturing persons engaged used as the state demand base.
- `ncvtmis_karnataka_state_2022.csv`: state ITI/seat magnitude from NCVT MIS; not district supply.
- `iti_division_training_2020_21.csv`: historical DGT division-level training totals for calibration only.
- `ncvtmis_file1171_real_partial.csv`: small official NCVT MIS indexed extract for Tumakuru and Kalaburagi. It is real, but incomplete and historical. It is included only to demonstrate how a real district supply observation changes the uncertainty interval.

No synthetic company metrics are included in the worked analysis.
