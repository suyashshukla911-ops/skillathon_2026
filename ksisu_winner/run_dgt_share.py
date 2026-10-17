from pathlib import Path
from run_gap import CLEAN, compute_model

ROOT = Path(__file__).resolve().parent
supply = CLEAN / "dgt_cts_2026_karnataka_supply_nco.csv"
result = compute_model(
    actual_supply_path=str(supply),
    overrides={"proxy_allocation_method": "dgt_2026_seat_share"},
    output_dir=ROOT / "out" / "dgt_share_run",
    write_outputs=True,
)
print("DGT 2026 SEAT-SHARE EVIDENCE-UPGRADE RUN")
print("========================================")
print(f"Rows loaded: {result['audit']['actual_supply_rows']:,}")
print(f"Published DGT seats: {result['audit']['actual_total_input_seats']:,.0f}")
print(f"Required analytical pairs: {result['audit']['actual_required_district_group_pairs']}")
print(f"Covered analytical pairs: {result['audit']['actual_covered_district_group_pairs']}")
print(f"Proxy-vs-DGT Spearman: {result['audit'].get('proxy_vs_dgt_spearman', float('nan')):.3f}")
print(f"DGT-share Dirichlet concentration: {result['audit'].get('dgt_share_allocation_concentration')}")
print(f"Statewide mean-supply conservation ratio: {result['audit'].get('statewide_supply_mean_conservation_ratio', float('nan')):.3f}")
print(f"Median-supply conservation ratio: {result['audit'].get('statewide_supply_conservation_ratio', float('nan')):.3f} (median rows; not the conservation benchmark)")
print(f"Policy decisions: {result['ratio']['decision_status'].value_counts().to_dict()}")
print("Outputs written to out/dgt_share_run.")
