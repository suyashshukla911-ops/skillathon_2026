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
result = compute_model(actual_supply_path=str(supply), output_dir=ROOT / 'out', write_outputs=True)
print('DGT 2026 REAL PROVISIONAL SUPPLY RUN')
print('====================================')
print(f"Rows loaded: {result['audit']['actual_supply_rows']:,}")
print(f"Published districts in DGT extraction: {published_districts(result)}")
print(f"Input provisional seats: {result['audit']['actual_total_input_seats']:,.0f}")
print(f"Mapped-seat share (pilot NCO 72/74): {100*(1-result['audit']['actual_unmapped_share']):.1f}%")
print(f"Unmapped-seat share: {100*result['audit']['actual_unmapped_share']:.1f}%")
print(f"Full evidence gate: {result['audit']['actual_supply_full_ready']}")
print(f"Policy decisions: {result['ratio']['decision_status'].value_counts().to_dict()}")
print('Outputs written to out/.')
