from __future__ import annotations
from pathlib import Path
import pandas as pd
import tempfile
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from run_gap import compute_model

print('KSISU SELF TEST')
print('='*60)
proxy=compute_model(write_outputs=False)
assert len(proxy['district'])==30
assert len(proxy['ratio'])==60
assert abs(proxy['audit']['occupation_share_sum_selected']-0.40)<1e-9
assert abs(proxy['audit']['selected_course_weight_sum']-0.82)<1e-9
assert proxy['ratio']['year'].nunique()==1
assert proxy['ratio']['year'].iloc[0]=='2022-23'
assert set(proxy['ratio']['decision_status'])=={'NEEDS DATA'}
assert proxy['audit']['monte_carlo_draws']==5000

small = pd.DataFrame([{"supply_seats": 4, "demand_openings": 8, "ratio_median": 0.5}])
from run_gap import suppress_small
small_checked = suppress_small(small, "supply_seats")
assert bool(small_checked.loc[0, "suppressed"]) is True
assert pd.isna(small_checked.loc[0, "supply_seats"])
assert pd.isna(small_checked.loc[0, "demand_openings"])
assert pd.isna(small_checked.loc[0, "ratio_median"])
print('PASS: public small-cell suppression blanks supply/demand/ratio values below configured threshold')

# Structural demand-allocation sensitivity: employment, enterprise units, and 50/50 blend.
assert abs(float(proxy['audit']['demand_allocator_share_sum']) - 1.0) < 1e-9
das = proxy['demand_allocator_rank_stability']
assert set(["udyam_employment","udyam_units","blend"]).issubset(
    {c.removeprefix("rank_") for c in das.columns if c.startswith("rank_")}
)
top5_emp = set(das.loc[das["rank_udyam_employment"] <= 5, "district"])
top5_units = set(das.loc[das["rank_udyam_units"] <= 5, "district"])
assert top5_emp != top5_units
assert (das["rank_range"] >= 0).all()
assert proxy['audit']['monte_carlo_draws']==5000

iti=pd.read_csv(ROOT/'input_templates/district_iti_counts.csv')
assert len(iti)==30 and iti.district.nunique()==30 and iti.iti_count.sum()>0
assert set(proxy['audit']['allocation_basis_counts'].keys())=={'NCVT ITI-count weighted'}
assert (proxy['ratio']['interval_width']>=0).all()
expected=proxy['audit']['statewide_supply_expected_mean']
actual_mean=proxy['audit']['statewide_supply_draw_mean_sum']
assert abs(actual_mean/expected-1)<0.25

actual=compute_model(actual_supply_path=str(ROOT/'raw/ncvtmis_file1171_real_partial.csv'),write_outputs=False)
assert actual['audit']['actual_supply_loaded'] is True
assert int(actual['audit']['actual_supply_rows'])==9
assert (actual['ratio'].query("supply_coverage == 'partial_floor'")['decision_status']=='NEEDS DATA').all()

# DGT CTS-2026 real public supply evidence. This is provisional and incomplete, so it must not unlock policy calls.
dgt_path=ROOT/'clean/dgt_cts_2026_karnataka_supply_nco.csv'
dgt=compute_model(actual_supply_path=str(dgt_path),write_outputs=False)
assert dgt['audit']['actual_supply_loaded'] is True
assert int(dgt['audit']['actual_supply_rows']) == 1734
assert int(dgt['audit']['actual_total_input_seats']) == 45416
assert float(dgt['audit']['actual_unmapped_share']) == 0.0
assert abs(float(dgt['audit']['actual_out_of_scope_share']) - 0.11960542540073983) < 1e-9
assert abs(float(dgt['audit']['actual_to_state_seat_ratio']) - (45416/216788)) < 1e-9
assert bool(dgt['audit']['actual_scale_warning']) is True
assert dgt['audit']['actual_supply_full_ready'] is False
assert int(dgt['audit']['actual_required_district_group_pairs']) == 60
assert int(dgt['audit']['actual_covered_district_group_pairs']) == 58
assert set(dgt['ratio']['decision_status']) == {'NEEDS DATA'}
assert (dgt['ratio']['supply_coverage'].isin(['partial_floor','proxy'])).all()
assert not actual['interval_demo'].empty
assert set(actual['interval_demo'].district).issuperset({'Tumakuru','Kalaburagi'})

# DGT 2026 seat-share allocation mode: real DGT district shares must change the allocation without opening policy calls.
dgt_share = compute_model(
    actual_supply_path=str(ROOT/'clean/dgt_cts_2026_karnataka_supply_nco.csv'),
    overrides={"proxy_allocation_method": "dgt_2026_seat_share"},
    write_outputs=False
)
assert dgt_share['audit']['proxy_allocation_method'] == 'dgt_2026_seat_share'
assert float(dgt_share['audit']['proxy_vs_dgt_spearman']) < 0.99
assert dgt_share['audit']['actual_supply_full_ready'] is False
assert set(dgt_share['ratio']['decision_status'].unique()) == {'NEEDS DATA'}
assert set(dgt_share['ratio']['supply_basis'].unique()).issubset({'dgt-seat-share-calibrated','district-proxy'})
assert float(dgt_share['audit']['statewide_supply_mean_conservation_ratio']) > 0.75
assert float(dgt_share['audit']['statewide_supply_mean_conservation_ratio']) < 1.25
merged = proxy['district'][['district','uncapped_ratio_median']].merge(
    dgt_share['district'][['district','uncapped_ratio_median']],
    on='district', suffixes=('_proxy','_dgt')
)
assert not merged.empty
assert float(merged['uncapped_ratio_median_proxy'].rank(method='average').corr(merged['uncapped_ratio_median_dgt'].rank(method='average'))) < 0.99
cw_real=pd.read_csv(ROOT/'clean/dgt_trade_nco_crosswalk.csv')
assert {'reviewed_by','reviewed_on'}.issubset(cw_real.columns)

# DGT-share coverage correction: missing districts must fall back to proxy rather than zero.
dgt_share_supply = dgt_share['supply'].groupby('district')['supply_median'].sum()
proxy_supply = proxy['supply'].groupby('district')['supply_median'].sum()
coverage = dgt_share['district'].set_index('district')['matrix_iti_coverage']
share_vs_proxy = (dgt_share_supply / proxy_supply).replace([float('inf'), -float('inf')], float('nan')).dropna()
assert float(dgt_share_supply['Kodagu']) > 0.0
assert float(share_vs_proxy[coverage.loc[coverage >= 0.20].index].min()) >= 0.10
assert int((dgt_share['ratio']['raw_signal'] == 'GAP').sum()) != int((proxy['ratio']['raw_signal'] == 'GAP').sum())
low_cov = coverage[coverage < 0.20].index
assert not low_cov.empty
assert not dgt_share['district'].set_index('district').loc[low_cov, 'gap_cells'].eq(2).all()
assert {'dgt_itis_in_matrix','iti_2022_count','matrix_iti_coverage'}.issubset(dgt_share['district'].columns)
print('PASS: DGT share mode uses coverage-weighted shrinkage; Kodagu retains nonzero proxy fallback')
print('PASS: DGT-share vs proxy allocation materially differs without opening policy calls')

# Full-extract gate test: construct 31x2 rows and mark coverage as full_district_extract.
lgd=pd.read_csv(ROOT/'raw/lgd_districts.csv')
rows=[]
for district in lgd.district_name:
    for g in ['72','74']:
        rows.append({'district':district,'iti_code':f'TEST-{district[:3]}-{g}','trade':'Fitter' if g=='72' else 'Electrician','seats':100,'nco_group_2digit':g,'reference_period':'2026','source_id':'TEST-FULL','coverage_status':'full_district_extract'})
rows.append({'district':'Tumakuru','iti_code':'TEST-OOS','trade':'Computer Operator','seats':500,'nco_group_2digit':'OUT_OF_SCOPE','reference_period':'2026','source_id':'TEST-FULL','coverage_status':'full_district_extract'})
with tempfile.TemporaryDirectory() as td:
    f=Path(td)/'full.csv'; pd.DataFrame(rows).to_csv(f,index=False)
    full=compute_model(actual_supply_path=str(f),write_outputs=False)
    assert full['audit']['actual_supply_full_ready'] is True
    assert full['audit']['actual_required_district_group_pairs'] == 60
    assert full['audit']['actual_covered_district_group_pairs'] == 60
    assert full['audit']['actual_unmapped_share'] == 0.0
    assert full['audit']['actual_out_of_scope_share'] > 0.0
    assert full['ratio']['evidence_ready'].all()

    bad = pd.DataFrame(rows[:-1] + [{'district':'Tumakuru','iti_code':'TEST-X','trade':'Unmapped Trade','seats':10000,'nco_group_2digit':'UNMAPPED','reference_period':'2026','source_id':'TEST-FULL','coverage_status':'full_district_extract'}])
    with tempfile.TemporaryDirectory() as td:
        bf=Path(td)/'bad_full.csv'; bad.to_csv(bf,index=False)
        bad_full=compute_model(actual_supply_path=str(bf),write_outputs=False)
        assert bad_full['audit']['actual_supply_full_ready'] is False
        assert bad_full['audit']['actual_unmapped_seat_share'] > 0.05

cor=proxy['corruption'].iloc[0]
assert int(cor['seeded_corruptions'])==100
assert int(cor['seeded_typo_rows'])==80
assert cor['seeded_typo_recovery_rate']>=0.90
assert int(cor['unseen_alias_rows'])==20
assert int(cor['unseen_alias_matched'])==0
assert int(cor['duplicate_rows_removed'])==5
assert bool(cor['all_rows_preserved_for_review']) is True
print('PASS: 31 raw LGD districts / 30 analytical geographies')
print('PASS: 60 analytical geography x 2 NCO pilot rows')
print('PASS: occupation shares stay at 0.25 + 0.15 = 0.40; not normalized')
print('PASS: selected course weights stay at 0.82; group 81 excluded')
print('PASS: statewide supply conservation is measured against the triangular-mean expectation')
print('PASS: shared 5,000-draw Monte Carlo and year-aware grouping')
print('PASS: demand allocator shares sum to 1.0 and employment vs units top-5 sets differ')
print('PASS: proxy-only policy gate -> NEEDS DATA')
print('PASS: partial NCVT sample treated as floor + uncertain remainder')
print('PASS: DGT CTS-2026 real provisional supply loaded: 1,734 rows / 45,416 seats / 29 published districts; 58/60 analytical pairs; 0.0% UNMAPPED; 12.0% OUT_OF_SCOPE; full gate remains closed')
print('PASS: DGT seat-share mode changes district allocation, reports proxy-vs-DGT Spearman, preserves conservation, and keeps policy gate NEEDS DATA')
print('PASS: full-district extract with OUT_OF_SCOPE rows unlocks evidence_ready gate; UNMAPPED still blocks it')
print('PASS: 80 seeded typo cases + 20 unseen aliases + 5 real dedupe removals')
from verify_iti_counts import verify as verify_iti
_iti_problems=verify_iti(write=False)
assert not _iti_problems, _iti_problems
print('PASS: 30/30 ITI weights reproduce the bundled Annexure-IV transcription; independent PDF visual verification still required')
print('PASS: pipeline completed without exception')
