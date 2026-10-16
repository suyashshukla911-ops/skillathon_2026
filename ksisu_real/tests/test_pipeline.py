import pandas as pd
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_31_districts():
    df=pd.read_csv(ROOT/"raw/lgd_districts.csv")
    assert len(df)==31
    assert df.district_name.nunique()==31

def test_sources_present():
    for f in ["karnataka_udyam_employment_nov2022.csv","iti_division_training_2020_21.csv","plfs_karnataka_industry_share_2022_23.csv"]:
        assert (ROOT/"raw"/f).exists()

def test_gap_outputs():
    df=pd.read_csv(ROOT/"out/ratio_intervals.csv")
    assert len(df)==31*6
    assert set(df.signal.unique()) <= {"GAP","SURPLUS","NEEDS DATA"}
