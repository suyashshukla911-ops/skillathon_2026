import pandas as pd
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_31_districts():
    df=pd.read_csv(ROOT/"raw/lgd_districts.csv")
    assert len(df)==31
    assert df.district_name.nunique()==31

def test_required_sources_present():
    for f in [
        "karnataka_udyam_employment_nov2022.csv",
        "asi_karnataka_manufacturing_2022_23.csv",
        "ncvtmis_karnataka_state_2022.csv",
        "iti_division_training_2020_21.csv",
    ]:
        assert (ROOT/"raw"/f).exists()

def test_model_is_narrow_and_conservative():
    df=pd.read_csv(ROOT/"out/ratio_intervals.csv")
    assert len(df)==31*3
    assert set(df.nco_group_2digit.astype(str)) == {"72","74","81"}
    assert set(df.decision_status.unique()) == {"NEEDS DATA"}

def test_shared_reproducible_run_outputs():
    df=pd.read_csv(ROOT/"out/ratio_intervals.csv")
    assert df.year.nunique()==1
    assert df.year.iloc[0] == "2022-23"
    assert (df.interval_width >= 0).all()
