import sys, tempfile
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from run_gap import compute_model

def test_31_districts():
    df=pd.read_csv(ROOT/'raw/lgd_districts.csv')
    assert len(df)==31
    assert df.district_name.nunique()==31

def test_scope_not_normalized():
    mix=pd.read_csv(ROOT/'clean/occupation_mix_prior.csv')
    selected=mix[mix.nco_group_2digit.astype(str).isin(['72','74'])]
    assert abs(selected.share_within_manufacturing.sum()-0.40)<1e-9
    cw=pd.read_csv(ROOT/'clean/crosswalk.csv')
    assert set(cw.nco_group_2digit.astype(str)) <= {'72','74'}
    assert abs(cw.statewide_course_weight.sum()-0.82)<1e-9

def test_supply_conserves_state_total():
    r=compute_model(write_outputs=False)
    exp=r['audit']['statewide_supply_expected_mean']
    med=r['audit']['statewide_supply_median_sum']
    assert abs(med/exp-1)<0.25

def test_proxy_conservative_policy_gate():
    r=compute_model(write_outputs=False)
    assert len(r['ratio'])==60
    assert set(r['ratio'].decision_status.unique())=={'NEEDS DATA'}

def test_actual_sample_is_partial_and_does_not_overclaim():
    r=compute_model(actual_supply_path=str(ROOT/'raw/ncvtmis_file1171_real_partial.csv'),write_outputs=False)
    assert r['audit']['actual_supply_loaded'] is True
    assert r['audit']['actual_supply_full_ready'] is False
    sub=r['ratio'].query("supply_coverage=='partial_floor'")
    assert not sub.empty
    assert (sub.decision_status=='NEEDS DATA').all()

def test_full_extract_unlocks_gate():
    lgd=pd.read_csv(ROOT/'raw/lgd_districts.csv')
    rows=[]
    for district in lgd.district_name:
        for g in ['72','74']:
            rows.append({'district':district,'iti_code':f'TEST-{district[:3]}-{g}','trade':'Fitter' if g=='72' else 'Electrician','seats':100,'nco_group_2digit':g,'reference_period':'2026','source_id':'TEST-FULL','coverage_status':'full_district_extract'})
    with tempfile.TemporaryDirectory() as td:
        f=Path(td)/'full.csv'; pd.DataFrame(rows).to_csv(f,index=False)
        r=compute_model(actual_supply_path=str(f),write_outputs=False)
        assert r['audit']['actual_supply_full_ready'] is True
        assert r['ratio']['evidence_ready'].all()
        assert set(r['ratio']['supply_coverage'].unique())=={'full_actual'}

def test_corruption_rows_are_preserved_and_deduped():
    r=compute_model(write_outputs=False)
    c=r['corruption'].iloc[0]
    assert c['seeded_corruptions']==100
    assert c['seeded_typo_rows']==80
    assert c['seeded_typo_recovery_rate']>=0.90
    assert c['unseen_alias_rows']==20
    assert c['unseen_alias_matched']==0
    assert c['duplicate_rows_removed']==5
    assert bool(c['all_rows_preserved_for_review'])

def test_reproducible():
    a=compute_model(write_outputs=False)
    b=compute_model(write_outputs=False)
    cols=['district','nco_group_2digit','ratio_p10','ratio_median','ratio_p90','confidence_score']
    pd.testing.assert_frame_equal(a['ratio'][cols].reset_index(drop=True),b['ratio'][cols].reset_index(drop=True))


def test_district_iti_weights_used():
    r=compute_model(write_outputs=False)
    assert set(r['audit']['allocation_basis_counts']) == {'NCVT ITI-count weighted'}
    assert len(r['district']) == 30


def test_unmapped_full_extract_fails_gate():
    import tempfile
    lgd=pd.read_csv(ROOT/'raw/lgd_districts.csv')
    rows=[]
    for district in lgd.district_name:
        for g in ['72','74']:
            rows.append({'district':district,'iti_code':f'TEST-{district[:3]}-{g}','trade':'Fitter' if g=='72' else 'Electrician','seats':100,'nco_group_2digit':g,'reference_period':'2026','source_id':'TEST-FULL','coverage_status':'full_district_extract'})
    rows.append({'district':'Tumakuru','iti_code':'TEST-UNMAPPED','trade':'Unmapped Trade','seats':10000,'nco_group_2digit':'UNMAPPED','reference_period':'2026','source_id':'TEST-FULL','coverage_status':'full_district_extract'})
    with tempfile.TemporaryDirectory() as td:
        f=Path(td)/'bad.csv'; pd.DataFrame(rows).to_csv(f,index=False)
        r=compute_model(actual_supply_path=str(f),write_outputs=False)
        assert r['audit']['actual_supply_full_ready'] is False
        assert r['audit']['actual_unmapped_seat_share'] > 0.05
