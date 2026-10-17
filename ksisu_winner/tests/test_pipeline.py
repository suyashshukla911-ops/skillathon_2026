import sys, tempfile
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from run_gap import compute_model, suppress_small

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
    mean_total=r['audit']['statewide_supply_draw_mean_sum']
    assert abs(mean_total/exp-1)<0.25

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
    rows.append({'district':'Tumakuru','iti_code':'TEST-OOS','trade':'Computer Operator','seats':500,'nco_group_2digit':'OUT_OF_SCOPE','reference_period':'2026','source_id':'TEST-FULL','coverage_status':'full_district_extract'})
    with tempfile.TemporaryDirectory() as td:
        f=Path(td)/'full.csv'; pd.DataFrame(rows).to_csv(f,index=False)
        r=compute_model(actual_supply_path=str(f),write_outputs=False)
        assert r['audit']['actual_supply_full_ready'] is True
        assert r['audit']['actual_required_district_group_pairs'] == 60
        assert r['audit']['actual_covered_district_group_pairs'] == 60
        assert r['audit']['actual_unmapped_share'] == 0.0
        assert r['audit']['actual_out_of_scope_share'] > 0.0
        assert r['ratio']['evidence_ready'].all()
        assert set(r['ratio']['supply_coverage'].unique())=={'full_actual'}

def test_dgt_provisional_uses_analytical_coverage_and_separates_out_of_scope():
    r=compute_model(actual_supply_path=str(ROOT/'clean/dgt_cts_2026_karnataka_supply_nco.csv'),write_outputs=False)
    assert r['audit']['actual_required_district_group_pairs'] == 60
    assert r['audit']['actual_covered_district_group_pairs'] == 58
    assert r['audit']['actual_unmapped_share'] == 0.0
    assert 0.11 < r['audit']['actual_out_of_scope_share'] < 0.13
    assert r['audit']['actual_supply_full_ready'] is False
    assert set(r['ratio'].decision_status.unique()) == {'NEEDS DATA'}
    assert set(r['ratio'].supply_coverage.unique()).issubset({'partial_floor','proxy'})


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


def test_demand_allocator_methods_change_rankings_and_share_sum():
    r=compute_model(write_outputs=False)
    a=r['audit']
    assert a['demand_allocation_method']=='udyam_employment'
    assert abs(float(a['demand_allocator_share_sum'])-1.0)<1e-9
    das=r['demand_allocator_rank_stability']
    assert set(['rank_udyam_employment','rank_udyam_units','rank_blend']).issubset(das.columns)
    assert abs(float(das['rank_udyam_employment'].min())-1.0)<1e-9
    emp_top=set(das.loc[das['rank_udyam_employment']<=5,'district'])
    units_top=set(das.loc[das['rank_udyam_units']<=5,'district'])
    assert emp_top != units_top
    assert (das['rank_range']>=0).all()


def test_demand_allocator_share_totals_for_each_method():
    methods=['udyam_employment','udyam_units','blend']
    for method in methods:
        r=compute_model(overrides={'demand_allocation_method':method},write_outputs=False)
        assert r['audit']['demand_allocation_method']==method
        assert abs(float(r['audit']['demand_allocator_share_sum'])-1.0)<1e-9
        assert (r['demand']['demand_allocation_share'].between(0,1)).all()

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


def test_dgt_share_mode_changes_allocation_and_preserves_gate():
    proxy=compute_model(write_outputs=False)
    dgt=compute_model(
        actual_supply_path=str(ROOT/'clean/dgt_cts_2026_karnataka_supply_nco.csv'),
        overrides={"proxy_allocation_method":"dgt_2026_seat_share"},
        write_outputs=False
    )
    assert dgt['audit']['proxy_allocation_method']=='dgt_2026_seat_share'
    assert dgt['audit']['actual_required_district_group_pairs']==60
    assert dgt['audit']['actual_covered_district_group_pairs']==58
    assert float(dgt['audit']['proxy_vs_dgt_spearman']) < 0.99
    assert float(dgt['audit']['statewide_supply_mean_conservation_ratio']) > 0.75
    assert float(dgt['audit']['statewide_supply_mean_conservation_ratio']) < 1.25
    assert set(dgt['ratio'].decision_status.unique())=={'NEEDS DATA'}
    merged=proxy['district'][['district','uncapped_ratio_median']].merge(
        dgt['district'][['district','uncapped_ratio_median']], on='district', suffixes=('_proxy','_dgt')
    )
    rho=float(merged['uncapped_ratio_median_proxy'].rank(method='average').corr(
        merged['uncapped_ratio_median_dgt'].rank(method='average')
    ))
    assert rho < 0.99

def test_dgt_share_crosswalk_review_columns():
    cw=pd.read_csv(ROOT/'clean/dgt_trade_nco_crosswalk.csv')
    assert {'reviewed_by','reviewed_on'}.issubset(cw.columns)
    assert cw['reviewed_by'].notna().all()
    assert cw['reviewed_on'].notna().all()



def test_dgt_share_missing_district_falls_back_and_is_not_an_artificial_zero():
    proxy=compute_model(write_outputs=False)
    dgt=compute_model(
        actual_supply_path=str(ROOT/'clean/dgt_cts_2026_karnataka_supply_nco.csv'),
        overrides={'proxy_allocation_method':'dgt_2026_seat_share'},
        write_outputs=False,
    )
    assert float(dgt['supply'].groupby('district')['supply_median'].sum()['Kodagu']) > 0.0
    proxy_supply=proxy['supply'].groupby('district')['supply_median'].sum()
    dgt_supply=dgt['supply'].groupby('district')['supply_median'].sum()
    coverage=dgt['district'].set_index('district')['matrix_iti_coverage']
    eligible=coverage[coverage>=0.20].index
    assert float((dgt_supply[eligible]/proxy_supply[eligible]).min()) >= 0.10


def test_dgt_share_uses_coverage_and_changes_signal_shape():
    proxy=compute_model(write_outputs=False)
    dgt=compute_model(
        actual_supply_path=str(ROOT/'clean/dgt_cts_2026_karnataka_supply_nco.csv'),
        overrides={'proxy_allocation_method':'dgt_2026_seat_share'},
        write_outputs=False,
    )
    assert {'dgt_itis_in_matrix','iti_2022_count','matrix_iti_coverage'}.issubset(dgt['district'].columns)
    assert int((dgt['ratio']['raw_signal']=='GAP').sum()) != int((proxy['ratio']['raw_signal']=='GAP').sum())
    low_cov=dgt['district'].query('matrix_iti_coverage < 0.20')
    assert not low_cov.empty
    assert not (low_cov['gap_cells']==2).all()
    p=dgt['district'].set_index('district')['uncapped_ratio_median'].rank()
    q=proxy['district'].set_index('district')['uncapped_ratio_median'].rank()
    assert float(p.corr(q)) < 0.99


def test_scenario_robustness_file_covers_all_six_runs():
    path=ROOT/'out/scenario_robustness.csv'
    assert path.exists()
    df=pd.read_csv(path)
    expected_cols={
        'district',
        'rank_proxy_udyam_employment',
        'rank_proxy_udyam_units',
        'rank_proxy_blend',
        'rank_dgt_share_udyam_employment',
        'rank_dgt_share_udyam_units',
        'rank_dgt_share_blend',
        'rank_min','rank_max','rank_range','top5_appearances','top5_all_six'
    }
    assert expected_cols.issubset(df.columns)
    assert len(df)==30
    assert int(df['top5_appearances'].max())==6
    assert int(df['top5_all_six'].sum())==1


def test_public_suppression_guardrail_blanks_small_seat_cells():
    df = pd.DataFrame([
        {"district": "Test", "trade": "Tiny Trade", "supply_seats": 4, "demand_openings": 12, "ratio_median": 0.2},
        {"district": "Test", "trade": "Enough Trade", "supply_seats": 5, "demand_openings": 12, "ratio_median": 0.8},
    ])
    out = suppress_small(df, "supply_seats")
    assert bool(out.loc[0, "suppressed"]) is True
    assert pd.isna(out.loc[0, "supply_seats"])
    assert pd.isna(out.loc[0, "demand_openings"])
    assert pd.isna(out.loc[0, "ratio_median"])
    assert bool(out.loc[1, "suppressed"]) is False
    assert float(out.loc[1, "supply_seats"]) == 5.0


def test_suppression_threshold_is_read_from_config():
    r = compute_model(write_outputs=False)
    assert int(r['audit']['min_count_suppression']) == 5


def test_public_export_harmonises_ballari_and_marks_absent_districts():
    from public_export import build_public_exports
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        build_public_exports(ROOT / 'out' / 'dgt_share_run', Path(td))
        public = pd.read_csv(Path(td) / 'district_indicators.csv')
        row = public.loc[public['district'] == 'Ballari-Vijayanagara'].iloc[0]
        assert float(row['supply_seats']) == 2268.0
        assert pd.notna(row['ratio_median'])
        assert bool(row['not_observed']) is False
        kodagu = public.loc[public['district'] == 'Kodagu'].iloc[0]
        assert bool(kodagu['not_observed']) is True
        assert 'no dgt rows' in str(kodagu['suppression_note']).lower()
        trade = pd.read_csv(Path(td) / 'district_trade_seats.csv')
        assert 'Ballari-Vijayanagara' in set(trade['district'])
        dgt_districts = pd.read_csv(ROOT / 'clean' / 'dgt_cts_2026_karnataka_supply_nco.csv')
        analytical = set(dgt_districts.loc[
            dgt_districts['nco_group_2digit'].astype(str).isin(['72','74']), 'district'
        ].map({'Ballari':'Ballari-Vijayanagara'}).fillna(dgt_districts.loc[
            dgt_districts['nco_group_2digit'].astype(str).isin(['72','74']), 'district'
        ]))
        analytical &= set(public['district'])
        check = public[public['district'].isin(analytical)]
        assert (pd.to_numeric(check['supply_seats'], errors='coerce') > 0).all()


def test_refresh_empty_review_file_has_headers(tmp_path):
    from refresh_pipeline import refresh
    registry = tmp_path / 'file_registry.csv'
    source = tmp_path / 'fixture.csv'
    source.write_text('state,seats_available_2022\nKarnataka,100\n')
    import hashlib, json
    h=hashlib.sha256(source.read_bytes()).hexdigest()
    registry.write_text(f'path,{"sha256"}\n{source.as_posix()},{h}\n')
    baseline = tmp_path / 'baseline.json'
    baseline.write_text(json.dumps({'files': {source.as_posix(): {'row_count':1,'columns':['state','seats_available_2022'],'statewide_seats':100}}}))
    review_path = tmp_path / 'review.csv'
    refresh(registry, baseline, tmp_path/'report.csv', review_path)
    assert review_path.read_text().splitlines()[0].startswith('path,hash_status')
