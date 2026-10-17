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

iti=pd.read_csv(ROOT/'input_templates/district_iti_counts.csv')
assert len(iti)==30 and iti.district.nunique()==30 and iti.iti_count.sum()>0
assert set(proxy['audit']['allocation_basis_counts'].keys())=={'NCVT ITI-count weighted'}
assert (proxy['ratio']['interval_width']>=0).all()
expected=proxy['audit']['statewide_supply_expected_mean']
actual=proxy['audit']['statewide_supply_median_sum']
assert abs(actual/expected-1)<0.25

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
assert abs(float(dgt['audit']['actual_unmapped_share']) - 0.11960542540073983) < 1e-9
assert dgt['audit']['actual_supply_full_ready'] is False
assert int(dgt['audit']['actual_covered_district_group_pairs']) == 58
assert set(dgt['ratio']['decision_status']) == {'NEEDS DATA'}
assert (dgt['ratio']['supply_coverage'].isin(['partial_floor','proxy'])).all()
assert not actual['interval_demo'].empty
assert set(actual['interval_demo'].district).issuperset({'Tumakuru','Kalaburagi'})

# Full-extract gate test: construct 31x2 rows and mark coverage as full_district_extract.
lgd=pd.read_csv(ROOT/'raw/lgd_districts.csv')
rows=[]
for district in lgd.district_name:
    for g in ['72','74']:
        rows.append({'district':district,'iti_code':f'TEST-{district[:3]}-{g}','trade':'Fitter' if g=='72' else 'Electrician','seats':100,'nco_group_2digit':g,'reference_period':'2026','source_id':'TEST-FULL','coverage_status':'full_district_extract'})
with tempfile.TemporaryDirectory() as td:
    f=Path(td)/'full.csv'; pd.DataFrame(rows).to_csv(f,index=False)
    full=compute_model(actual_supply_path=str(f),write_outputs=False)
    assert full['audit']['actual_supply_full_ready'] is True
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
print('PASS: proxy-only policy gate -> NEEDS DATA')
print('PASS: partial NCVT sample treated as floor + uncertain remainder')
print('PASS: DGT CTS-2026 real provisional supply loaded: 1,734 rows / 45,416 seats / 29 published districts; full gate remains closed')
print('PASS: full-district extract unlocks evidence_ready gate')
print('PASS: 80 seeded typo cases + 20 unseen aliases + 5 real dedupe removals')
from verify_iti_counts import verify as verify_iti
_iti_problems=verify_iti(write=False)
assert not _iti_problems, _iti_problems
print('PASS: 30/30 ITI weights reproduce the bundled Annexure-IV transcription; independent PDF visual verification still required')
print('PASS: pipeline completed without exception')
