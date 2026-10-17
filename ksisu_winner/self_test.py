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
assert len(proxy['district'])==31
assert len(proxy['ratio'])==62
assert abs(proxy['audit']['occupation_share_sum_selected']-0.40)<1e-9
assert abs(proxy['audit']['selected_course_weight_sum']-0.82)<1e-9
assert proxy['ratio']['year'].nunique()==1
assert proxy['ratio']['year'].iloc[0]=='2022-23'
assert set(proxy['ratio']['decision_status'])=={'NEEDS DATA'}
assert proxy['audit']['monte_carlo_draws']==5000
assert (proxy['ratio']['interval_width']>=0).all()
expected=proxy['audit']['statewide_supply_expected_mode']
actual=proxy['audit']['statewide_supply_median_sum']
assert abs(actual/expected-1)<0.25

actual=compute_model(actual_supply_path=str(ROOT/'raw/ncvtmis_file1171_real_partial.csv'),write_outputs=False)
assert actual['audit']['actual_supply_loaded'] is True
assert int(actual['audit']['actual_supply_rows'])==9
assert (actual['ratio'].query("supply_coverage == 'partial_floor'")['decision_status']=='NEEDS DATA').all()
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

cor=proxy['corruption'].iloc[0]
assert int(cor['seeded_corruptions'])==100
assert int(cor['seeded_typo_rows'])==80
assert cor['seeded_typo_recovery_rate']>=0.90
assert int(cor['unseen_alias_rows'])==20
assert int(cor['unseen_alias_matched'])==0
assert int(cor['duplicate_rows_removed'])==5
assert bool(cor['all_rows_preserved_for_review']) is True
print('PASS: 31 districts')
print('PASS: 62 district x 2 NCO pilot rows')
print('PASS: occupation shares stay at 0.25 + 0.15 = 0.40; not normalized')
print('PASS: selected course weights stay at 0.82; group 81 excluded')
print('PASS: statewide supply conservation within 25% of mode expectation')
print('PASS: shared 5,000-draw Monte Carlo and year-aware grouping')
print('PASS: proxy-only policy gate -> NEEDS DATA')
print('PASS: partial NCVT sample treated as floor + uncertain remainder')
print('PASS: full-district extract unlocks evidence_ready gate')
print('PASS: 80 seeded typo cases + 20 unseen aliases + 5 real dedupe removals')
print('PASS: pipeline completed without exception')
