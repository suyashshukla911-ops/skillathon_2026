from pathlib import Path
import json
import shutil
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from policy_layer import run, evidence_level


def test_policy_layer_register_is_cited_and_has_required_chain():
    r = pd.read_csv(ROOT / 'clean/policy_register.csv')
    required = {'policy_id','source_doc','page','clause','instrument','decision_maker','indicator','trigger_rule','action','district_scope','analytical_district_scope','source_priority','action_basis'}
    assert required.issubset(r.columns)
    assert len(r) >= 50
    source_backed = r[r['source_file'].notna() & r['page'].notna()]
    assert source_backed['page'].astype(str).str.len().gt(0).all()
    assert r['source_doc'].notna().all()
    assert r['decision_maker'].notna().all()
    assert set(r['trigger_rule']).issubset({'A_EXPLORATORY','B_PROVISIONAL_WATCHLIST','C_POLICY_READY'})


def test_policy_layer_current_levels_are_27_3_0():
    # Regression fixture for the frozen V18 snapshot.
    run(ROOT)
    d = pd.read_csv(ROOT / 'out/district_evidence_levels.csv')
    counts = (d['evidence_level'].eq('A_EXPLORATORY').sum(), d['evidence_level'].eq('B_PROVISIONAL_WATCHLIST').sum(), d['evidence_level'].eq('C_POLICY_READY').sum())
    assert len(d) == 30
    assert counts == (27,3,0)
    assert set(d.loc[d.evidence_level=='B_PROVISIONAL_WATCHLIST','district']) == {'Gadag','Tumakuru','Vijayapura'}


def test_policy_actions_are_structurally_complete_and_visible_status_is_split():
    run(ROOT)
    a = pd.read_csv(ROOT / 'out/policy_actions.csv')
    assert len(a) == pd.read_csv(ROOT/'public_export/district_indicators.csv').district.nunique()
    assert a['district'].nunique() == len(a)
    assert a['evidence_level_name'].notna().all()
    assert a['model_gate_status'].notna().all()
    assert a['action_basis'].notna().all()
    assert a['why_this_district'].str.len().gt(20).all()
    assert a['main_evidence_limitation'].str.len().gt(20).all()


def test_policy_benchmark_reports_ratios_and_uncertainty_not_just_rho():
    run(ROOT)
    c = pd.read_csv(ROOT / 'out/dsdp_benchmark_comparison.csv')
    assert len(c) >= 5
    sample = c[c['included_in_rank_correlation']]
    assert sample['benchmark_to_model_p50_ratio'].notna().all()
    s = pd.read_csv(ROOT / 'out/dsdp_benchmark_summary.csv').iloc[0]
    assert int(s['comparable_sample_n']) == len(sample)
    assert 0 <= float(s['spearman_p_value_asymptotic']) <= 1
    assert 'not validation' in str(s['interpretation']).lower()


def test_level_b_rule_is_stability_only():
    row = pd.Series({'policy_status':'NEEDS DATA','needs_data_cells':60,'top5_appearances':5,'rank_range':5})
    assert evidence_level(row) == 'B_PROVISIONAL_WATCHLIST'
    row2 = row.copy(); row2['top5_appearances'] = 4
    assert evidence_level(row2) == 'A_EXPLORATORY'


def test_policy_ready_preserves_existing_gate():
    row = pd.Series({'policy_status':'READY','needs_data_cells':0,'top5_appearances':0,'rank_range':30})
    assert evidence_level(row) == 'C_POLICY_READY'


def test_merged_ballari_vijayanagara_mapping_is_explicit_and_deterministic():
    r = pd.read_csv(ROOT / 'clean/policy_register.csv')
    merged = r[r['analytical_district_scope'].eq('Ballari-Vijayanagara')]
    assert set(merged['district_scope']) >= {'Ballari','Vijayanagara'}
    assert merged.loc[merged['district_scope'].eq('Vijayanagara'),'source_priority'].min() < merged.loc[merged['district_scope'].eq('Ballari'),'source_priority'].min()
    run(ROOT)
    a = pd.read_csv(ROOT / 'out/policy_actions.csv')
    row = a[a['district'].eq('Ballari-Vijayanagara')].iloc[0]
    assert row['source_district_scope'] == 'Vijayanagara'
    assert int(row['page']) in {28,29,30}


def test_source_manifest_pages_and_hashes_are_verified():
    run(ROOT)
    q = pd.read_csv(ROOT / 'out/policy_mapping_quality.csv')
    row = q[q['check'].eq('Policy source manifest/page/hash integrity')].iloc[0]
    assert row['status'] == 'PASS'


def test_district_specific_mapping_is_dynamic_not_hardcoded():
    run(ROOT)
    d = pd.read_csv(ROOT/'out/district_evidence_levels.csv')
    a = pd.read_csv(ROOT/'out/policy_actions.csv')
    # Every district has either a district-specific source clause or the explicit generic safeguard.
    for district in d['district']:
        x = a[a['district'].eq(district)].iloc[0]
        if x['source_file'] != x['source_file']:  # NaN generic fallback
            assert 'generic' in str(x['source_doc']).lower()


def test_model_summary_is_not_mutated_by_policy_layer():
    run(ROOT)
    s = json.loads((ROOT/'out/run_summary.json').read_text(encoding='utf-8'))
    assert 'policy_evidence_levels' not in s
    assert 'provisional_watchlist' not in s
    assert (ROOT/'out/policy_summary.json').exists()


def test_run_respects_policy_root(tmp_path):
    # Copy only the inputs the policy layer needs into an isolated root.
    t = tmp_path/'pkg'
    (t/'public_export').mkdir(parents=True)
    (t/'clean').mkdir()
    (t/'docs').mkdir()
    (t/'out'/'dgt_share_run').mkdir(parents=True)
    shutil.copy(ROOT/'public_export/district_indicators.csv', t/'public_export/district_indicators.csv')
    for fn in ['policy_register.csv','dsdp_benchmark.csv','district_aliases.csv']:
        shutil.copy(ROOT/'clean'/fn, t/'clean'/fn)
    shutil.copy(ROOT/'docs/policy_source_manifest.csv', t/'docs/policy_source_manifest.csv')
    # Bundle source PDFs is checked separately in the real package; isolated structural test uses empty stubs.
    (t/'docs'/'policy_sources').mkdir()
    manifest = pd.read_csv(ROOT/'docs/policy_source_manifest.csv')
    for fn in manifest['source_file'].drop_duplicates():
        shutil.copy(ROOT/'docs/policy_sources'/fn, t/'docs'/'policy_sources'/fn)
    shutil.copy(ROOT/'out/dgt_share_run/demand_estimates.csv', t/'out/dgt_share_run/demand_estimates.csv')
    out = run(t)
    assert out['policy_summary'] == t/'out/policy_summary.json'
    assert (t/'out/policy_actions.csv').exists()
    # The real package outputs are separate from this isolated root.
    assert not (t/'policy_actions.csv').exists()


def test_generic_fallback_does_not_reference_another_district():
    run(ROOT)
    a = pd.read_csv(ROOT/'out/policy_actions.csv')
    generic = a[a['source_doc'].eq('No district plan in supplied bundle — generic KSISU safeguard')]
    assert not generic.empty
    assert generic['page'].isna().all()
    assert not generic['source_district_scope'].fillna('').str.contains('Ballari', case=False).any()
