from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from run_gap import CLEAN, CONFIG, ROOT, OUT, apply_analytical_merge, suppress_small


def _policy_status_by_district(ratio: pd.DataFrame) -> pd.Series:
    def status(s: pd.Series) -> str:
        vals = set(s.astype(str))
        if vals == {"NEEDS DATA"}:
            return "NEEDS DATA"
        if len(vals) == 1:
            return next(iter(vals))
        return "MIXED / REVIEW"
    return ratio.groupby("district")["decision_status"].agg(status)


def _harmonise_districts(df: pd.DataFrame, col: str = "district") -> pd.DataFrame:
    out = df.copy()
    if col not in out.columns:
        raise KeyError(f"Missing district column: {col}")
    out[col] = out[col].astype(str).map(apply_analytical_merge)
    return out


def build_public_exports(run_dir: Path, export_dir: Path) -> dict[str, Path]:
    export_dir.mkdir(parents=True, exist_ok=True)
    district = pd.read_csv(run_dir / "district_priority.csv")
    ratio = pd.read_csv(run_dir / "ratio_intervals.csv")
    dgt = pd.read_csv(CLEAN / "dgt_cts_2026_karnataka_supply_nco.csv")
    scenarios = pd.read_csv(OUT / "scenario_robustness.csv")

    indicator_cols = [
        "district", "SCI", "uncapped_ratio_median", "mean_confidence", "total_annual_openings",
        "VOI", "data_collection_priority", "needs_data_cells", "actual_cells", "dgt_itis_in_matrix",
        "iti_2022_count", "matrix_iti_coverage", "ratio_rank", "rank_range", "top5_appearances", "robust_priority"
    ]
    present = [c for c in indicator_cols if c in district.columns]
    public = district[present].copy()
    public = public.rename(columns={
        "SCI": "ratio_sci",
        "uncapped_ratio_median": "ratio_median",
        "total_annual_openings": "demand_annual_openings",
        "VOI": "demand_voi",
        "data_collection_priority": "demand_data_collection_priority",
    })

    policy = _policy_status_by_district(ratio).rename("policy_status")
    public = public.merge(policy, left_on="district", right_index=True, how="left")
    scenario_public = scenarios[["district", "rank_range", "top5_appearances", "robust_priority"]].copy()
    public = public.merge(scenario_public, on="district", how="left")

    selected = dgt[dgt["nco_group_2digit"].astype(str).isin([str(x) for x in CONFIG.get("selected_nco_groups", ["72", "74"])])].copy()
    selected["seats"] = pd.to_numeric(selected["seats"], errors="coerce")
    selected = _harmonise_districts(selected)

    district_seats = (selected.groupby("district", as_index=False)["seats"].sum()
                      .rename(columns={"seats": "supply_seats"}))
    public = public.merge(district_seats, on="district", how="left")

    # Distinguish an absent source observation from a genuinely small observed count.
    # Absence is not itself a suppression event and keeps modeled values visible.
    public["not_observed"] = public["supply_seats"].isna()
    public["supply_seats"] = pd.to_numeric(public["supply_seats"], errors="coerce")
    public = suppress_small(public, "supply_seats")
    public["suppression_note"] = ""
    public.loc[public["not_observed"], "suppression_note"] = (
        "No DGT rows; value is modelled from the historical ITI weight."
    )
    public.loc[~public["not_observed"] & public["suppressed"], "suppression_note"] = (
        "Suppressed because observed institutional seat total is below the configured threshold."
    )
    public.loc[~public["not_observed"] & ~public["suppressed"], "suppression_note"] = (
        "Observed institutional aggregate exceeds the configured threshold."
    )
    public = public.sort_values("district").reset_index(drop=True)

    public_iti = selected[[
        "district", "iti_mis_code", "iti_name", "trade", "trade_duration",
        "nco_group_2digit", "seats", "source_period", "source_id", "coverage_status"
    ]].copy()
    public_iti = public_iti.rename(columns={"seats": "supply_seats"})
    public_iti = suppress_small(public_iti, "supply_seats")
    public_iti["suppression_note"] = public_iti["suppressed"].map({
        True: "Seat count suppressed under the public small-cell threshold.",
        False: "Institutional seat row published; no personal data is present.",
    })
    public_iti = public_iti.sort_values(["district", "iti_name", "trade"]).reset_index(drop=True)

    district_trade = (selected.groupby(["district", "nco_group_2digit"], as_index=False)["seats"].sum()
                      .rename(columns={"seats": "supply_seats"}))
    district_trade = suppress_small(district_trade, "supply_seats")

    public.to_csv(export_dir / "district_indicators.csv", index=False)
    public.to_json(export_dir / "district_indicators.json", orient="records", indent=2)
    scenarios.to_csv(export_dir / "scenario_robustness.csv", index=False)
    public_iti.to_csv(export_dir / "iti_trade_rows.csv", index=False)
    district_trade.to_csv(export_dir / "district_trade_seats.csv", index=False)

    update_freq = {
        "ratio_sci": "On each model refresh",
        "ratio_median": "On each model refresh",
        "demand_annual_openings": "On each model refresh; demand source refresh as available",
        "demand_voi": "On each model refresh",
        "demand_data_collection_priority": "On each model refresh",
        "policy_status": "On each model refresh; policy gate remains NEEDS DATA until evidence is complete",
        "supply_seats": "On DGT/NCVT source refresh",
        "matrix_iti_coverage": "On DGT source refresh",
        "rank_range": "On six-scenario run",
        "top5_appearances": "On six-scenario run",
        "robust_priority": "On six-scenario run",
    }
    definitions = {
        "district": ("Analytical KSISU geography", "Source geography after configured Ballari/Vijayanagara merge", "district", "When LGD geography refreshes"),
        "ratio_sci": ("SCI: weighted share of openings covered", "sum(min(S_i/D_i,1)*D_i)/sum(D_i)", "district", update_freq["ratio_sci"]),
        "ratio_median": ("Median uncapped supply-to-demand ratio across Monte Carlo draws", "median(S/D)", "district", update_freq["ratio_median"]),
        "mean_confidence": ("Mean evidence confidence across modeled district cells", "mean(cell confidence score)", "district", "On each model refresh"),
        "demand_annual_openings": ("Median modeled annual openings for the selected NCO groups", "median(opening rate × state demand × district allocation)", "district", update_freq["demand_annual_openings"]),
        "demand_voi": ("Value of information score", "interval width × annual openings", "district", update_freq["demand_voi"]),
        "demand_data_collection_priority": ("Composite evidence-collection priority", "VOI weighted by data/evidence quality signals", "district", update_freq["demand_data_collection_priority"]),
        "needs_data_cells": ("Number of NCO cells blocked by the policy gate", "count(decision_status = NEEDS DATA)", "district", "On each model refresh"),
        "actual_cells": ("Number of modeled NCO cells with full actual evidence", "count(supply_coverage = full_actual)", "district", "On each model refresh"),
        "dgt_itis_in_matrix": ("Distinct DGT ITIs represented in the provisional matrix", "count distinct ITI codes from DGT matrix", "district", "On DGT source refresh"),
        "iti_2022_count": ("Historical 2022 ITI count used only as an allocation weight", "source total", "district", "Historical snapshot; replace when current district totals arrive"),
        "matrix_iti_coverage": ("DGT matrix ITI coverage relative to the historical 2022 count", "DGT ITIs in matrix / 2022 ITI count", "district", "On DGT source refresh"),
        "ratio_rank": ("District rank by uncapped median ratio", "rank descending on ratio_median", "district", "On each model refresh"),
        "rank_range": ("Maximum minus minimum district rank across the six scenarios", "max(rank) − min(rank)", "district", update_freq["rank_range"]),
        "top5_appearances": ("Number of the six scenarios in which a district is top five", "count(rank <= 5)", "district", update_freq["top5_appearances"]),
        "robust_priority": ("Structural robustness flag", "top5_appearances = 6", "district", update_freq["robust_priority"]),
        "policy_status": ("Public policy gate status across the district's modeled NCO cells", "NEEDS DATA unless all cells share an actionable status", "district", update_freq["policy_status"]),
        "supply_seats": ("Observed institutional seat capacity used for public small-cell suppression", "sum(source seat rows)", "district or ITI-trade", update_freq["supply_seats"]),
        "not_observed": ("No selected DGT rows were observed for the analytical district", "supply_seats is missing before suppression", "district", "On each public export"),
        "suppressed": ("Small-cell suppression flag", f"supply_seats > 0 and supply_seats < {int(CONFIG.get('min_count_suppression',5))}", "public row", "On each public export"),
        "suppression_note": ("Human-readable publication status", "derived from not_observed and suppressed flags", "public row", "On each public export"),
    }
    dictionary_rows = []
    all_public_columns = list(public.columns) + [c for c in scenarios.columns if c not in public.columns]
    for col in all_public_columns:
        if col not in definitions:
            definitions[col] = (col.replace("_", " ").title(), "Derived from the six-scenario robustness output", "scenario/district", "On each six-scenario run")
        definition, formula, level, freq = definitions[col]
        if col in public.columns and col in scenarios.columns:
            src_file = "district_indicators.csv, scenario_robustness.csv"
        elif col in public.columns:
            src_file = "district_indicators.csv"
        else:
            src_file = "scenario_robustness.csv"
        dictionary_rows.append({
            "indicator": col,
            "source_file": src_file,
            "definition": definition,
            "formula": formula,
            "reporting_level": level,
            "update_frequency": freq,
        })
    pd.DataFrame(dictionary_rows).drop_duplicates("indicator").to_csv(export_dir / "data_dictionary.csv", index=False)

    demo = suppress_small(pd.DataFrame([{
        "supply_seats": 4, "demand_openings": 8, "ratio_median": 0.5
    }]), "supply_seats")
    suppression_check = pd.DataFrame([{
        "check": "Configured min-count suppression",
        "threshold": int(CONFIG.get("min_count_suppression", 5)),
        "district_rows_suppressed": int(public["suppressed"].sum()),
        "iti_trade_rows_suppressed": int(public_iti["suppressed"].sum()),
        "demo_input_seats": 4,
        "demo_suppressed": bool(demo.loc[0, "suppressed"]),
        "demo_public_supply_value_is_blank": bool(pd.isna(demo.loc[0, "supply_seats"])),
        "statement": "Institutional aggregate seat data only; no personal data. Suppression is a safeguard for future finer-grained data. Rows below the threshold are flagged and their public supply/demand/ratio values are blanked.",
    }])
    suppression_check.to_csv(export_dir / "suppression_check.csv", index=False)

    return {
        "district_indicators": export_dir / "district_indicators.csv",
        "district_indicators_json": export_dir / "district_indicators.json",
        "scenario_robustness": export_dir / "scenario_robustness.csv",
        "data_dictionary": export_dir / "data_dictionary.csv",
        "iti_trade_rows": export_dir / "iti_trade_rows.csv",
        "district_trade_seats": export_dir / "district_trade_seats.csv",
        "suppression_check": export_dir / "suppression_check.csv",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate machine-readable public exports with small-cell suppression.")
    ap.add_argument("--run-dir", default=str(OUT / "dgt_share_run"), help="Primary district run directory")
    ap.add_argument("--export-dir", default=str(ROOT / "public_export"), help="Public export directory")
    args = ap.parse_args()
    outputs = build_public_exports(Path(args.run_dir), Path(args.export_dir))
    print("PUBLIC EXPORT COMPLETE")
    for name, path in outputs.items():
        print(f"{name}: {path.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
