from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from functools import lru_cache
from pathlib import Path

import pandas as pd

REQUIRED_INDICATORS = {
    "demand_annual_openings", "demand_voi", "demand_data_collection_priority",
    "matrix_iti_coverage", "rank_range", "top5_appearances", "policy_status"
}

LEVEL_NAMES = {
    "A_EXPLORATORY": "Exploratory",
    "B_PROVISIONAL_WATCHLIST": "Provisional watchlist",
    "C_POLICY_READY": "Policy-ready",
}


def _load_aliases(clean_dir: Path) -> dict[str, str]:
    path = clean_dir / "district_aliases.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    aliases = pd.read_csv(path)
    required = {"alias", "canonical"}
    if not required.issubset(aliases.columns):
        raise ValueError(f"district_aliases.csv missing columns: {sorted(required - set(aliases.columns))}")
    return dict(zip(aliases["alias"].astype(str).str.strip(), aliases["canonical"].astype(str).str.strip()))


def _norm_district(v: str, aliases: dict[str, str]) -> str:
    s = str(v).strip()
    return aliases.get(s, s)


def evidence_level(row: pd.Series) -> str:
    # C preserves the existing full-extract policy gate.
    if str(row.get("policy_status", "NEEDS DATA")) != "NEEDS DATA" and int(float(row.get("needs_data_cells", 1))) == 0:
        return "C_POLICY_READY"
    # B is intentionally stability-only: no tuning to a named district.
    top5 = int(float(row.get("top5_appearances", 0)))
    rr = float(row.get("rank_range", 999))
    if top5 >= 5 and rr <= 5:
        return "B_PROVISIONAL_WATCHLIST"
    return "A_EXPLORATORY"


def _fmt_num(v) -> str:
    try:
        return f"{float(v):,.1f}"
    except Exception:
        return "NA"


def why_this_district(row: pd.Series, level: str) -> str:
    top5 = int(float(row.get("top5_appearances", 0)))
    rr = float(row.get("rank_range", 999))
    pri = float(row.get("demand_data_collection_priority", 0))
    cov = float(row.get("matrix_iti_coverage", 0))
    if level == "B_PROVISIONAL_WATCHLIST":
        return (f"Top-five in {top5}/6 scenarios with rank range {int(rr)}; "
                "the signal is stable enough for verification-first watchlisting, not a seat decision.")
    if level == "C_POLICY_READY":
        return "The existing full-evidence gate is open; the model can support a policy-facing action under its documented scope."
    return (f"Priority is driven by the existing evidence-collection score ({_fmt_num(pri)}) with "
            f"top-five appearance in {top5}/6 scenarios and DGT ITI coverage of {cov:.0%}; the output remains exploratory.")


def main_evidence_limitation(row: pd.Series) -> str:
    cov = float(row.get("matrix_iti_coverage", 0))
    rr = float(row.get("rank_range", 999))
    if bool(row.get("not_observed", False)) or cov <= 0:
        return "DGT source not observed for this district; modeled supply retains the historical ITI-weighted proxy rather than treating absence as zero."
    if cov < 0.50:
        return f"Incomplete DGT matrix coverage ({cov:.0%}); observed supply remains a partial evidence signal."
    if rr > 5:
        return f"Ranking sensitivity across scenarios (rank range {int(rr)}); the priority is assumption-sensitive."
    return "Provisional DGT coverage and the demand-allocation assumptions remain the main evidence limitations."


def next_data_action(row: pd.Series, level: str) -> str:
    cov = float(row.get("matrix_iti_coverage", 0))
    if bool(row.get("not_observed", False)) or cov <= 0:
        return "Complete the DGT district × ITI × trade extract for this geography and re-run the six-scenario evidence test."
    if cov < 0.50:
        return "Complete DGT matrix coverage and verify the local employer-demand signal before any seat decision."
    if float(row.get("rank_range", 999)) > 5:
        return "Add district occupation/employer evidence and re-run robustness; the ranking is assumption-sensitive."
    if level == "B_PROVISIONAL_WATCHLIST":
        return "Verify seats and occupation mix before any seat decision; use the district employer/placement channel as corroboration."
    return "Refresh district demand and training-outcome evidence, then re-run the evidence gate."


def _choose_rule_level(register: pd.DataFrame, district: str, level: str) -> pd.DataFrame:
    exact = register[(register["analytical_district_scope"] == district) & (register["trigger_rule"] == level)].copy()
    if not exact.empty:
        exact["source_priority"] = pd.to_numeric(exact["source_priority"], errors="coerce").fillna(99)
        return exact.sort_values(["source_priority", "policy_id"]).head(1)
    generic = register[(register["analytical_district_scope"] == "ALL_DISTRICTS") & (register["trigger_rule"] == level)].copy()
    return generic.sort_values(["source_priority", "policy_id"]).head(1)


def _action_for_level(source_action: str, level: str) -> str:
    if level == "A_EXPLORATORY":
        return f"DATA COLLECTION PRIORITY: {source_action}"
    if level == "B_PROVISIONAL_WATCHLIST":
        return f"VERIFY BEFORE ANY SEAT DECISION: {source_action}"
    return f"POLICY-READY ACTION (gate open): {source_action}"


def _source_manifest(root: Path) -> pd.DataFrame:
    path = root / "docs" / "policy_source_manifest.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    m = pd.read_csv(path)
    required = {"source_file", "sha256", "pages"}
    if not required.issubset(m.columns):
        raise ValueError(f"policy_source_manifest.csv missing columns: {sorted(required - set(m.columns))}")
    return m




@lru_cache(maxsize=128)
def _sha256_file(path_str: str, mtime_ns: int, size: int) -> str:
    h = hashlib.sha256()
    with open(path_str, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _validate_source_backed_register(reg: pd.DataFrame, manifest: pd.DataFrame, root: Path) -> dict:
    source_rows = reg[reg["source_file"].notna() & reg["page"].notna()].copy()
    if source_rows.empty:
        return {"rows": 0, "pages_in_range": True, "manifest_files_resolve": True, "hashes_match": True}
    m = manifest.drop_duplicates("source_file").set_index("source_file")
    pages_ok = []
    file_ok = []
    hash_ok = []
    missing_bundle = []
    for _, r in source_rows.iterrows():
        fn = str(r["source_file"])
        page = int(float(r["page"]))
        if fn not in m.index:
            file_ok.append(False); pages_ok.append(False); hash_ok.append(False); missing_bundle.append(fn); continue
        pages = int(m.loc[fn, "pages"])
        pages_ok.append(1 <= page <= pages)
        bundled = root / "docs" / "policy_sources" / fn
        file_ok.append(bundled.exists())
        if bundled.exists():
            st = bundled.stat()
            h = _sha256_file(str(bundled), int(st.st_mtime_ns), int(st.st_size))
            hash_ok.append(h == str(m.loc[fn, "sha256"]).lower())
        else:
            hash_ok.append(False)
    return {
        "rows": len(source_rows),
        "pages_in_range": all(pages_ok),
        "manifest_files_resolve": all(fn in m.index for fn in source_rows["source_file"].astype(str)),
        "bundled_source_files_present": all(file_ok),
        "bundled_hashes_match": all(hash_ok),
        "missing_bundle_files": sorted(set(missing_bundle)),
    }


def _spearman_stats(sample: pd.DataFrame) -> tuple[float | None, float | None]:
    """Return rho and the conventional scipy Spearman asymptotic p-value.

    The p-value is reported only as a small-sample diagnostic and is never used
    as a model gate or ranking criterion.  Keeping it out of the frozen model
    prevents the benchmark layer from changing any analytical result.
    """
    n = len(sample)
    if n < 3:
        return None, None
    try:
        from scipy.stats import spearmanr
        result = spearmanr(sample["model_p50"], sample["annual_equivalent"], nan_policy="omit")
        return (None if pd.isna(result.statistic) else float(result.statistic),
                None if pd.isna(result.pvalue) else float(result.pvalue))
    except Exception:
        # Keep the policy layer usable if scipy is unavailable; rho can still be
        # reported, but do not fabricate a p-value.
        rho = sample["model_p50"].rank(ascending=False).corr(sample["annual_equivalent"].rank(ascending=False))
        return (None if pd.isna(rho) else float(rho), None)


def _write_policy_summary(out: Path, lev: pd.DataFrame, quality: dict, benchmark_summary: dict | None):
    counts = lev["evidence_level"].value_counts().to_dict()
    summary = {
        "evidence_levels": {
            "A_EXPLORATORY": int(counts.get("A_EXPLORATORY", 0)),
            "B_PROVISIONAL_WATCHLIST": int(counts.get("B_PROVISIONAL_WATCHLIST", 0)),
            "C_POLICY_READY": int(counts.get("C_POLICY_READY", 0)),
        },
        "provisional_watchlist": sorted(lev.loc[lev.evidence_level.eq("B_PROVISIONAL_WATCHLIST"), "district"].tolist()),
        "policy_ready_districts": sorted(lev.loc[lev.evidence_level.eq("C_POLICY_READY"), "district"].tolist()),
        "district_specific_clause_count": quality["district_specific_clause_count"],
        "district_count": quality["district_count"],
        "generic_fallback_districts": quality["generic_fallback_districts"],
        "source_validation": quality["source_validation"],
    }
    if benchmark_summary:
        summary["dsdp_triangulation"] = benchmark_summary
    (out / "policy_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")


def run(policy_root: Path) -> dict[str, Path]:
    root = Path(policy_root).resolve()
    public = root / "public_export"
    clean = root / "clean"
    out = root / "out"
    public_path = public / "district_indicators.csv"
    register_path = clean / "policy_register.csv"
    benchmark_path = clean / "dsdp_benchmark.csv"
    alias_map = _load_aliases(clean)
    manifest = _source_manifest(root)
    if not public_path.exists(): raise FileNotFoundError(public_path)
    if not register_path.exists(): raise FileNotFoundError(register_path)
    df = pd.read_csv(public_path)
    reg = pd.read_csv(register_path)
    missing = REQUIRED_INDICATORS - set(df.columns)
    if missing: raise ValueError(f"district_indicators.csv missing columns: {sorted(missing)}")
    df["district"] = df["district"].map(lambda x: _norm_district(x, alias_map))
    reg["district_scope"] = reg["district_scope"].fillna("").astype(str)
    reg["analytical_district_scope"] = reg["analytical_district_scope"].map(lambda x: _norm_district(x, alias_map))
    reg["source_priority"] = pd.to_numeric(reg["source_priority"], errors="coerce").fillna(99).astype(int)
    reg["page"] = reg["page"].astype("string")

    levels=[]
    for _, r in df.iterrows():
        level = evidence_level(r)
        levels.append({
            "district": r["district"],
            "evidence_level": level,
            "evidence_level_name": LEVEL_NAMES[level],
            "ratio_median": r.get("ratio_median"),
            "ratio_sci": r.get("ratio_sci"),
            "demand_annual_openings": r.get("demand_annual_openings"),
            "demand_voi": r.get("demand_voi"),
            "demand_data_collection_priority": r.get("demand_data_collection_priority"),
            "matrix_iti_coverage": r.get("matrix_iti_coverage"),
            "rank_range": r.get("rank_range"),
            "top5_appearances": r.get("top5_appearances"),
            "robust_priority": r.get("robust_priority"),
            "model_gate_status": r.get("policy_status"),
            "not_observed": bool(r.get("not_observed", False)),
            "why_this_district": why_this_district(r, level),
            "main_evidence_limitation": main_evidence_limitation(r),
            "next_data_action": next_data_action(r, level),
        })
    lev = pd.DataFrame(levels)
    out.mkdir(exist_ok=True)
    lev.to_csv(out / "district_evidence_levels.csv", index=False)

    actions=[]
    for _, r in lev.iterrows():
        choice = _choose_rule_level(reg, r["district"], r["evidence_level"])
        if choice.empty:
            actions.append({
                "district": r["district"],
                "evidence_level_name": LEVEL_NAMES[r["evidence_level"]],
                "model_gate_status": r["model_gate_status"],
                "evidence_level": r["evidence_level"],
                "indicator": "demand_data_collection_priority",
                "indicator_value": r["demand_data_collection_priority"],
                "rule_fired": r["evidence_level"],
                "action": r["next_data_action"],
                "action_basis": "Generic KSISU fallback — no registered source clause.",
                "decision_maker": "District Skill Committee (DSC) / district skill governance body",
                "evidence_status": r["model_gate_status"],
                "source_doc": "No district plan in supplied bundle — generic KSISU safeguard",
                "source_district_scope": pd.NA,
                "analytical_district_scope": r["district"],
                "source_priority": 99,
                "source_file": pd.NA,
                "page": pd.NA,
                "clause": "No district-specific DSDP is present in the supplied policy bundle; apply the generic evidence gate.",
                "instrument": "Generic KSISU evidence safeguard",
                "why_this_district": r["why_this_district"],
                "main_evidence_limitation": r["main_evidence_limitation"],
                "next_data_action": r["next_data_action"],
                "mapping_note": "Explicit generic fallback; not a citation to another district.",
            })
            continue
        c = choice.iloc[0]
        actions.append({
            "district": r["district"],
            "evidence_level_name": LEVEL_NAMES[r["evidence_level"]],
            "model_gate_status": r["model_gate_status"],
            "evidence_level": r["evidence_level"],
            "indicator": c["indicator"],
            "indicator_value": r.get(c["indicator"], pd.NA),
            "rule_fired": c["trigger_rule"],
            "action": _action_for_level(c["action"], r["evidence_level"]),
            "action_basis": c.get("action_basis", "KSISU evidence-level rule routed through the cited DSDP instrument."),
            "decision_maker": c["decision_maker"],
            "evidence_status": r["model_gate_status"],
            "source_doc": c["source_doc"],
            "source_district_scope": c["district_scope"],
            "analytical_district_scope": c["analytical_district_scope"],
            "source_priority": c["source_priority"],
            "source_file": c["source_file"],
            "page": c["page"],
            "clause": c["clause"],
            "instrument": c["instrument"],
            "why_this_district": r["why_this_district"],
            "main_evidence_limitation": r["main_evidence_limitation"],
            "next_data_action": r["next_data_action"],
            "mapping_note": c["mapping_note"],
        })
    act = pd.DataFrame(actions)
    act.to_csv(out / "policy_actions.csv", index=False)

    # Benchmark triangulation. Do not headline rho; report n, p-value and per-row ratios.
    benchmark_summary = None
    if benchmark_path.exists():
        bench = pd.read_csv(benchmark_path)
        demand_path = out / "dgt_share_run" / "demand_estimates.csv"
        demand = pd.read_csv(demand_path) if demand_path.exists() else pd.DataFrame()
        if not bench.empty and not demand.empty:
            demand_agg=(demand.groupby("district", as_index=False)
                        .agg(model_p10=("openings_p10","sum"), model_p50=("openings_median","sum"), model_p90=("openings_p90","sum")))
            cmp=bench.merge(demand_agg,on="district",how="left")
            cmp["inside_model_p10_p90"] = cmp["annual_equivalent"].between(cmp["model_p10"],cmp["model_p90"])
            cmp["benchmark_to_model_p50_ratio"] = cmp["annual_equivalent"] / cmp["model_p50"]
            corr_mask = cmp["comparability"].eq("DIRECTIONAL_ONLY") & cmp["benchmark_type"].isin(["incremental_capacity","demand_higher_than_capacity_sample","estimated_aggregated_demand"]) & cmp["model_p50"].notna()
            sample = cmp[corr_mask].copy()
            sample["model_rank"] = sample["model_p50"].rank(ascending=False, method="average")
            sample["benchmark_rank"] = sample["annual_equivalent"].rank(ascending=False, method="average")
            rho, p_value = _spearman_stats(sample) if len(sample) >= 3 else (None, None)
            cmp["included_in_rank_correlation"] = corr_mask
            cmp["rank_correlation_sample_size"] = int(corr_mask.sum())
            cmp["spearman_rank_correlation"] = rho
            cmp["spearman_p_value_asymptotic"] = p_value
            cmp["triangulation_note"] = "Directional triangulation only; DSDP figures can cover broader sectors/periods than the NCO 72/74 model. Ratios are benchmark annual-equivalent divided by model P50 openings."
            cmp.to_csv(out / "dsdp_benchmark_comparison.csv", index=False)
            inside_n = int(cmp.loc[corr_mask,"inside_model_p10_p90"].sum())
            sample_n = int(corr_mask.sum())
            benchmark_summary = {
                "benchmark_rows": int(len(cmp)),
                "comparable_sample_n": sample_n,
                "inside_model_p10_p90": f"{inside_n}/{sample_n}",
                "spearman_rank_correlation": None if pd.isna(rho) else float(rho),
                "spearman_p_value_asymptotic": p_value,
                "interpretation": "Directional triangulation, not validation; benchmark scopes differ from the NCO 72/74 pilot.",
                "reporting_note": "Do not headline rho without n and p; publish per-district benchmark/model-P50 ratios instead. P-value is the conventional Spearman asymptotic diagnostic and is not a policy gate."
            }
            pd.DataFrame([benchmark_summary]).to_csv(out / "dsdp_benchmark_summary.csv", index=False)

    known_districts = set(df["district"])
    generic_fallback = sorted(set(df.loc[~df["district"].isin(set(reg.loc[reg["analytical_district_scope"] != "ALL_DISTRICTS", "analytical_district_scope"])), "district"]))
    exact_clause_districts = sorted(known_districts - set(generic_fallback))
    source_validation = _validate_source_backed_register(reg, manifest, root)
    quality = {
        "district_count": len(known_districts),
        "district_specific_clause_count": len(exact_clause_districts),
        "generic_fallback_districts": generic_fallback,
        "source_validation": source_validation,
    }
    # Source manifest + page range + bundled hash checks are publication integrity checks.
    status = "PASS" if source_validation.get("pages_in_range") and source_validation.get("manifest_files_resolve") and source_validation.get("bundled_source_files_present") and source_validation.get("bundled_hashes_match") else "FAIL"
    quality_df = pd.DataFrame([
        {"check":"Policy register row count","value":len(reg),"status":"PASS" if len(reg)>=50 else "REVIEW","detail":"Operationalised policy rows, including explicit generic fallback rows."},
        {"check":"Districts with district-specific clauses","value":f"{len(exact_clause_districts)}/{len(known_districts)}","status":"PASS","detail":"All remaining districts use an explicit generic fallback; no unrelated district citation is shown."},
        {"check":"Generic fallback districts","value":", ".join(generic_fallback),"status":"PASS","detail":"Fallback rows are labelled generic and carry no misleading source page."},
        {"check":"Policy source manifest/page/hash integrity","value":f"{source_validation.get('rows',0)} source-backed rows","status":status,"detail":json.dumps(source_validation, sort_keys=True)},
        {"check":"Current evidence levels","value":lev["evidence_level"].value_counts().to_dict(),"status":"PASS","detail":"Evidence levels are derived from the frozen model outputs; Level B is stability-only."},
    ])
    quality_df.to_csv(out / "policy_mapping_quality.csv", index=False)
    _write_policy_summary(out, lev, quality, benchmark_summary)

    # Restore the model summary as model-only. Policy state lives in policy_summary.json.
    model_summary = out / "run_summary.json"
    if model_summary.exists():
        try:
            obj = json.loads(model_summary.read_text(encoding="utf-8"))
            for k in ["policy_evidence_levels","provisional_watchlist","policy_ready_districts","dsdp_triangulation"]:
                obj.pop(k, None)
            model_summary.write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=True), encoding="utf-8")
        except Exception:
            pass
    return {
        "evidence_levels": out / "district_evidence_levels.csv",
        "policy_actions": out / "policy_actions.csv",
        "benchmark": out / "dsdp_benchmark_comparison.csv",
        "benchmark_summary": out / "dsdp_benchmark_summary.csv",
        "policy_summary": out / "policy_summary.json",
        "mapping_quality": out / "policy_mapping_quality.csv",
    }


def main():
    ap=argparse.ArgumentParser(description="Operational policy layer for KSISU evidence levels and attached DSDP actions.")
    ap.add_argument("root", nargs="?", default=".")
    args=ap.parse_args()
    out=run(Path(args.root))
    print("POLICY LAYER COMPLETE")
    for k,v in out.items():
        print(f"{k}: {v}")

if __name__=="__main__":
    main()
