from __future__ import annotations
from pathlib import Path
import json
import pandas as pd
from run_gap import compute_model, ROOT, CLEAN, OUT

DEMAND_METHODS = ["udyam_employment", "udyam_units", "blend"]
SUPPLY_SCENARIOS = [
    ("proxy", None, None),
    ("dgt_share", str(CLEAN / "dgt_cts_2026_karnataka_supply_nco.csv"), "dgt_2026_seat_share"),
]


def _rank_table(run_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(run_dir / "district_priority.csv", usecols=["district", "ratio_rank"])
    return df.rename(columns={"ratio_rank": "rank"})


def build_scenario_robustness(scenario_dirs: list[tuple[str, Path]]) -> pd.DataFrame:
    frames = []
    for label, run_dir in scenario_dirs:
        df = _rank_table(run_dir).rename(columns={"rank": f"rank_{label}"})
        frames.append(df)
    merged = frames[0]
    for df in frames[1:]:
        merged = merged.merge(df, on="district", how="outer")
    rank_cols = [c for c in merged.columns if c.startswith("rank_")]
    merged["rank_min"] = merged[rank_cols].min(axis=1)
    merged["rank_max"] = merged[rank_cols].max(axis=1)
    merged["rank_range"] = merged["rank_max"] - merged["rank_min"]
    merged["top5_appearances"] = (merged[rank_cols] <= 5).sum(axis=1)
    merged["top5_all_six"] = merged["top5_appearances"].eq(len(rank_cols))
    merged["robust_priority"] = merged["top5_all_six"]
    return merged.sort_values(
        ["top5_appearances", "rank_range", "district"],
        ascending=[False, True, True],
    ).reset_index(drop=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    scenario_dirs: list[tuple[str, Path]] = []
    scenario_rows = []

    for demand_method in DEMAND_METHODS:
        proxy_out = OUT / "scenarios" / f"proxy_{demand_method}"
        dgt_out = OUT / "scenarios" / f"dgt_share_{demand_method}"
        proxy = compute_model(
            overrides={"demand_allocation_method": demand_method},
            output_dir=proxy_out,
        )
        dgt = compute_model(
            actual_supply_path=str(CLEAN / "dgt_cts_2026_karnataka_supply_nco.csv"),
            overrides={
                "demand_allocation_method": demand_method,
                "proxy_allocation_method": "dgt_2026_seat_share",
            },
            output_dir=dgt_out,
        )
        scenario_dirs.extend([
            (f"proxy_{demand_method}", proxy_out),
            (f"dgt_share_{demand_method}", dgt_out),
        ])
        scenario_rows.append({
            "demand_allocation_method": demand_method,
            "proxy_output": str(proxy_out.relative_to(ROOT)).replace("\\", "/"),
            "dgt_share_output": str(dgt_out.relative_to(ROOT)).replace("\\", "/"),
            "proxy_policy": json.dumps(proxy["ratio"]["decision_status"].value_counts().to_dict(), sort_keys=True),
            "dgt_share_policy": json.dumps(dgt["ratio"]["decision_status"].value_counts().to_dict(), sort_keys=True),
            "proxy_top5": ", ".join(proxy["district"].sort_values("ratio_rank").head(5)["district"].tolist()),
            "dgt_share_top5": ", ".join(dgt["district"].sort_values("ratio_rank").head(5)["district"].tolist()),
        })

    combined = build_scenario_robustness(scenario_dirs)
    robustness_path = OUT / "scenario_robustness.csv"
    combined.to_csv(robustness_path, index=False)
    pd.DataFrame(scenario_rows).to_csv(OUT / "scenario_run_summary.csv", index=False)

    robust_priority_districts = combined.loc[combined["robust_priority"], "district"].astype(str).tolist()
    run_summary = {
        "scenario_count": int(len(scenario_dirs)),
        "robust_priority": robust_priority_districts,
        "robust_priority_count": int(len(robust_priority_districts)),
        "districts_rank_range_above_5": int((pd.to_numeric(combined["rank_range"], errors="coerce") > 5).sum()),
        "scenario_robustness_file": str(robustness_path.relative_to(ROOT)).replace("\\", "/"),
        "top5_threshold": 5,
        "rank_range_threshold": 5,
    }
    (OUT / "run_summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")

    print("KSISU DEMAND ALLOCATOR SCENARIO RUN")
    print("=" * 60)
    for s in scenario_rows:
        print(f"\n{s['demand_allocation_method']}")
        print("  proxy:", s["proxy_policy"])
        print("  dgt_share:", s["dgt_share_policy"])
        print("  proxy top5:", s["proxy_top5"])
        print("  dgt-share top5:", s["dgt_share_top5"])
    print("\nSix-scenario robustness written to out/scenario_robustness.csv")
    print("Robust top-5 across all six scenarios:", ", ".join(combined.loc[combined["top5_all_six"], "district"].tolist()) or "None")
    print("Mean six-scenario rank range:", f"{combined['rank_range'].mean():.2f}")


if __name__ == "__main__":
    main()
