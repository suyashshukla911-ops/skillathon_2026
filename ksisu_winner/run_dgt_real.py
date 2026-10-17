from pathlib import Path
import pandas as pd
from run_gap import CLEAN, compute_model

ROOT = Path(__file__).resolve().parent

def published_districts(res):
    summary = res.get('audit', {})
    # DGT raw extraction is preserved in the bundled source file; use its unique district count.
    raw = pd.read_csv(CLEAN / 'dgt_cts_2026_karnataka_supply_nco.csv')
    return int(raw['district'].nunique())

supply = CLEAN / 'dgt_cts_2026_karnataka_supply_nco.csv'
result = compute_model(actual_supply_path=str(supply), output_dir=ROOT / 'out' / 'dgt_run', write_outputs=True)
print('DGT 2026 REAL PROVISIONAL SUPPLY RUN')
print('====================================')
print(f"Rows loaded: {result['audit']['actual_supply_rows']:,}")
print(f"Published districts in DGT extraction: {published_districts(result)}")
print(f"Input provisional seats: {result['audit']['actual_total_input_seats']:,.0f}")
print(f"Mapped-seat share (pilot NCO 72/74): {100*(1-result['audit']['actual_unmapped_share']-result['audit'].get('actual_out_of_scope_share',0.0)):.1f}%")
print(f"OUT_OF_SCOPE seat share: {100*result['audit'].get('actual_out_of_scope_share',0.0):.1f}%")
print(f"UNMAPPED seat share: {100*result['audit']['actual_unmapped_share']:.1f}%")
print(f"Required district-group pairs: {result['audit']['actual_required_district_group_pairs']}")
print(f"Covered district-group pairs: {result['audit']['actual_covered_district_group_pairs']}")
print(f"DGT / NCVT state seat scale: {result['audit'].get('actual_to_state_seat_ratio',0.0):.3f}")
print(f"Scale warning (<0.5): {result['audit'].get('actual_scale_warning',False)}")
print(f"Full evidence gate: {result['audit']['actual_supply_full_ready']}")
print(f"Policy decisions: {result['ratio']['decision_status'].value_counts().to_dict()}")
print('Outputs written to out/.')
