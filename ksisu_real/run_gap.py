from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import math
import re
from difflib import SequenceMatcher
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
CLEAN = ROOT / "clean"
OUT = ROOT / "out"
OUT.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = CLEAN / "config.json"
DEFAULT_CONFIG = {
    "reference_fy": "2022-23",
    "sector": "Manufacturing",
    "selected_nco_groups": ["72", "74", "81"],
    "monte_carlo_draws": 5000,
    "random_seed": 20261016,
    "fuzzy_threshold": 0.90,
    "opening_rate": {"low": 0.05, "mode": 0.085, "high": 0.12},
    "seat_fill_rate": {"low": 0.50, "mode": 0.813, "high": 0.90},
    "completion_rate": {"low": 0.50, "mode": 0.593, "high": 0.70},
    "sector_entry_rate": {"low": 0.20, "mode": 0.30, "high": 0.40},
    "proxy_seat_uncertainty": {"low": 0.75, "mode": 1.0, "high": 1.25},
    "actual_seat_uncertainty": {"low": 0.98, "mode": 1.0, "high": 1.02},
    "min_count_suppression": 5,
    "use_state_mfg_base_source": "ASI 2022-23 Karnataka persons engaged in selected manufacturing sector",
}

if CONFIG_PATH.exists():
    try:
        CONFIG = {**DEFAULT_CONFIG, **json.loads(CONFIG_PATH.read_text(encoding="utf-8"))}
    except Exception:
        CONFIG = DEFAULT_CONFIG.copy()
else:
    CONFIG = DEFAULT_CONFIG.copy()

ALIAS_MAP = {
    "bangalore": "bengaluru urban",
    "bangalore urban": "bengaluru urban",
    "bangalore rural": "bengaluru rural",
    "bengaluru": "bengaluru urban",
    "bellary": "ballari",
    "bijapur": "vijayapura",
    "gulbarga": "kalaburagi",
    "shimoga": "shivamogga",
    "mysore": "mysuru",
    "tumkur": "tumakuru",
    "chikmagalur": "chikkamagaluru",
    "chikkamaglur": "chikkamagaluru",
    "dakshin kannada": "dakshina kannada",
    "uttara kanada": "uttara kannada",
}


def norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def triangular(rng: np.random.Generator, spec: dict, n: int) -> np.ndarray:
    return rng.triangular(float(spec["low"]), float(spec["mode"]), float(spec["high"]), n)


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def match_districts(values: pd.Series, master: pd.DataFrame, threshold: float = 0.90) -> pd.DataFrame:
    master = master.copy()
    master["_norm"] = master["district_name"].map(norm)
    exact = dict(zip(master["_norm"], master["district_name"]))
    code_by_name = dict(zip(master["district_name"], master["lgd_code"]))
    results = []
    for raw in values.astype(str):
        n = norm(raw)
        alias = ALIAS_MAP.get(n, n)
        method = "exact" if n in exact else None
        candidate = exact.get(n)
        if candidate is None and alias in exact:
            candidate = exact[alias]
            method = "alias"
        best_score = 0.0
        if candidate is None:
            for name_norm, name in exact.items():
                score = SequenceMatcher(None, alias, name_norm).ratio()
                if score > best_score:
                    best_score = score
                    candidate = name
            if best_score >= threshold:
                method = "fuzzy"
            else:
                candidate = None
                method = "review"
        else:
            best_score = 1.0
        results.append({
            "raw_district": raw,
            "matched_district": candidate or "",
            "lgd_code": code_by_name.get(candidate, "") if candidate else "",
            "match_method": method,
            "match_confidence": round(float(best_score), 4),
        })
    return pd.DataFrame(results)


def load_inputs(paths: dict[str, Path] | None = None):
    paths = paths or {}
    lgd = pd.read_csv(paths.get("lgd", RAW / "lgd_districts.csv"))
    emp = pd.read_csv(paths.get("employment", RAW / "karnataka_udyam_employment_nov2022.csv"))
    asi = pd.read_csv(paths.get("asi", RAW / "asi_karnataka_manufacturing_2022_23.csv"))
    ncvt = pd.read_csv(paths.get("ncvt", RAW / "ncvtmis_karnataka_state_2022.csv"))
    mix = pd.read_csv(paths.get("occupation_mix", CLEAN / "occupation_mix_prior.csv"))
    cw = pd.read_csv(paths.get("crosswalk", CLEAN / "crosswalk.csv"))
    dgt = pd.read_csv(paths.get("dgt", RAW / "iti_division_training_2020_21.csv"))
    dmap = pd.read_csv(paths.get("division_map", CLEAN / "district_dgt_division_map.csv"))
    return lgd, emp, asi, ncvt, mix, cw, dgt, dmap


def source_registry(paths: dict[str, Path] | None = None) -> pd.DataFrame:
    paths = paths or {}
    rows = []
    source_meta = pd.read_csv(RAW / "source_registry.csv") if (RAW / "source_registry.csv").exists() else pd.DataFrame()
    meta_by_file = {Path(r.path).name: r for r in source_meta.itertuples()} if not source_meta.empty and hasattr(source_meta, "path") else {}
    candidate_paths = [
        paths.get("lgd", RAW / "lgd_districts.csv"),
        paths.get("employment", RAW / "karnataka_udyam_employment_nov2022.csv"),
        paths.get("asi", RAW / "asi_karnataka_manufacturing_2022_23.csv"),
        paths.get("ncvt", RAW / "ncvtmis_karnataka_state_2022.csv"),
        paths.get("dgt", RAW / "iti_division_training_2020_21.csv"),
        paths.get("occupation_mix", CLEAN / "occupation_mix_prior.csv"),
        paths.get("crosswalk", CLEAN / "crosswalk.csv"),
        paths.get("actual_supply", OUT / "district_iti_supply.csv"),
    ]
    for p in candidate_paths:
        if not p.exists():
            continue
        rows.append({
            "file_id": "FILE-" + sha256(p)[:10].upper(),
            "path": str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),
            "sha256": sha256(p),
            "version": datetime.now().strftime("%Y%m%d"),
            "source_url": "",
            "accessed": datetime.now().date().isoformat(),
            "grain": "unknown",
            "status": "captured",
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df.to_csv(RAW / "file_registry.csv", index=False)
    return df


def prepare_model_data(lgd, emp, asi, ncvt, mix, cw, dgt, dmap, selected_groups):
    # District linkage cascade
    emp_match = match_districts(emp["district"], lgd, CONFIG["fuzzy_threshold"])
    emp = emp.copy()
    emp = pd.concat([emp.reset_index(drop=True), emp_match.drop(columns=["raw_district"])], axis=1)
    emp = emp[emp["matched_district"].ne("")].copy()
    emp = emp.drop_duplicates("lgd_code").reset_index(drop=True)

    # District Udyam shares are a proxy allocator only. They are NOT manufacturing employment.
    emp["district_proxy_share"] = emp["udyam_employment"].clip(lower=0) / emp["udyam_employment"].sum()

    state_mfg_workers = float(asi.loc[asi["state"].eq("Karnataka"), "persons_engaged"].iloc[0])
    emp["district_mfg_employment_proxy"] = state_mfg_workers * emp["district_proxy_share"]

    # Occupation prior; only the requested manufacturing trades groups are used.
    mix = mix.copy()
    mix["nco_group_2digit"] = mix["nco_group_2digit"].astype(str)
    mix = mix[mix.nco_group_2digit.isin([str(x) for x in selected_groups])].copy()
    mix["share_raw"] = mix["share_within_manufacturing"].astype(float)
    mix["share"] = mix["share_raw"] / mix["share_raw"].sum()

    # Division seat structure from older DGT data, scaled to the current NCVT state seat total.
    total_current_seats = float(ncvt.loc[ncvt["state"].str.upper().eq("KARNATAKA"), "seats_available_2022"].iloc[0])
    div_cols = [c for c in dgt.columns if c.endswith("_sanctioned")]
    dgt["division_sanctioned"] = dgt[div_cols].sum(axis=1)
    dgt["division_share"] = dgt["division_sanctioned"] / dgt["division_sanctioned"].sum()
    div_seats = dict(zip(dgt["division"], total_current_seats * dgt["division_share"]))

    dmap = dmap.copy()
    dmap = dmap.merge(emp[["district", "matched_district", "lgd_code", "district_proxy_share"]], on="district", how="left")
    dmap["division_pool_share"] = dmap.groupby("dgt_division")["district_proxy_share"].transform(lambda s: s / s.sum())
    dmap["proxy_seats"] = [div_seats.get(div, np.nan) * share for div, share in zip(dmap["dgt_division"], dmap["division_pool_share"])]

    cw = cw.copy()
    cw["nco_group_2digit"] = cw["nco_group_2digit"].astype(str)
    cw = cw[cw["nco_group_2digit"].isin([str(x) for x in selected_groups])].copy()
    group_weights = cw.groupby("nco_group_2digit")["statewide_course_weight"].sum()
    if group_weights.sum() <= 0:
        group_weights = pd.Series(1.0, index=mix.nco_group_2digit)
    group_weights = group_weights / group_weights.sum()

    return emp, mix, dmap, group_weights, state_mfg_workers, total_current_seats, emp_match


def load_actual_supply(path: Path | None, selected_groups) -> pd.DataFrame | None:
    if not path or not path.exists():
        return None
    df = pd.read_csv(path)
    required = {"district", "seats"}
    if not required.issubset(df.columns):
        raise ValueError("Actual supply file must contain district,seats. Optional column: nco_group_2digit or trade.")
    df = df.copy()
    if "nco_group_2digit" not in df.columns:
        if "trade" in df.columns:
            cw = pd.read_csv(CLEAN / "crosswalk.csv")
            df = df.merge(cw[["course_or_trade", "nco_group_2digit"]], left_on="trade", right_on="course_or_trade", how="left")
        else:
            df["nco_group_2digit"] = "ALL"
    df["nco_group_2digit"] = df["nco_group_2digit"].astype(str)
    return df


def compute_model(paths=None, overrides=None, actual_supply_path=None, output_dir=OUT):
    overrides = overrides or {}
    cfg = json.loads(json.dumps(CONFIG))
    cfg.update(overrides)
    seed = int(cfg.get("random_seed", 20261016))
    draws = int(cfg.get("monte_carlo_draws", 5000))
    selected_groups = [str(x) for x in cfg.get("selected_nco_groups", ["72", "74", "81"])]

    lgd, emp, asi, ncvt, mix, cw, dgt, dmap = load_inputs(paths)
    emp, mix, dmap, group_weights, state_mfg_workers, total_current_seats, emp_match = prepare_model_data(
        lgd, emp, asi, ncvt, mix, cw, dgt, dmap, selected_groups
    )

    actual_supply = load_actual_supply(Path(actual_supply_path) if actual_supply_path else None, selected_groups)
    actual_supply_loaded = actual_supply is not None
    mix_is_observed = False
    if "source_type" in mix.columns:
        mix_is_observed = not mix.source_type.astype(str).str.contains("analyst_prior", case=False, na=False).all()
    actual_map = None
    if actual_supply is not None:
        actual_match = match_districts(actual_supply["district"], lgd, cfg.get("fuzzy_threshold", 0.90))
        actual_supply = pd.concat([actual_supply.reset_index(drop=True), actual_match.drop(columns=["raw_district"])], axis=1)
        actual_supply = actual_supply[actual_supply["matched_district"].ne("")].copy()
        actual_supply["seats"] = pd.to_numeric(actual_supply["seats"], errors="coerce").fillna(0.0)
        actual_supply = actual_supply[actual_supply["nco_group_2digit"].isin(selected_groups + ["ALL"])].copy()
        actual_map = actual_supply.groupby(["matched_district", "nco_group_2digit"], as_index=False)["seats"].sum()

    # Global shared draws: the same parameter draw is used across districts/occupations.
    rng = np.random.default_rng(seed)
    rate_open = triangular(rng, cfg["opening_rate"], draws)
    rate_fill = triangular(rng, cfg["seat_fill_rate"], draws)
    rate_completion = triangular(rng, cfg["completion_rate"], draws)
    rate_entry = triangular(rng, cfg["sector_entry_rate"], draws)
    seat_proxy_mult = triangular(rng, cfg["proxy_seat_uncertainty"], draws)
    seat_actual_mult = triangular(rng, cfg["actual_seat_uncertainty"], draws)

    results = []
    demand_rows = []
    supply_rows = []

    year = "2022-23"
    for _, d in emp.iterrows():
        district = d["matched_district"]
        division = str(dmap.loc[dmap["matched_district"].eq(district), "dgt_division"].iloc[0]) if (dmap["matched_district"] == district).any() else ""
        proxy_seats_total = float(dmap.loc[dmap["matched_district"].eq(district), "proxy_seats"].iloc[0]) if (dmap["matched_district"] == district).any() else 0.0
        for _, o in mix.iterrows():
            group = str(o["nco_group_2digit"])
            occ_share = float(o["share"])
            demand_stock = float(d["district_mfg_employment_proxy"]) * occ_share
            openings = demand_stock * rate_open

            # Demand uses state manufacturing employment (ASI) allocated by the district Udyam employment share.
            # Occupation mix remains an analyst prior until PLFS microdata is loaded.
            demand_rows.append({
                "district": district,
                "lgd_code": d["lgd_code"],
                "year": year,
                "industry": "Manufacturing",
                "nco_group_2digit": group,
                "occupation_label": o["occupation_label"],
                "state_mfg_employment_base": state_mfg_workers,
                "district_proxy_share": d["district_proxy_share"],
                "manufacturing_employment_proxy": demand_stock,
                "openings_p10": float(np.quantile(openings, 0.10)),
                "openings_median": float(np.quantile(openings, 0.50)),
                "openings_p90": float(np.quantile(openings, 0.90)),
                "evidence_tier": "district-proxy + state-actual",
            })

            if actual_map is not None:
                exact = actual_map[(actual_map.matched_district == district) & (actual_map.nco_group_2digit == group)]
                all_rows = actual_map[actual_map.matched_district.eq(district) & actual_map.nco_group_2digit.eq("ALL")]
                if not exact.empty:
                    actual_seats = float(exact.seats.iloc[0])
                    supply_basis = "district-actual"
                elif not all_rows.empty:
                    actual_total = float(all_rows.seats.iloc[0])
                    actual_seats = actual_total * float(group_weights.get(group, 0))
                    supply_basis = "district-actual-total+crosswalk"
                else:
                    actual_seats = proxy_seats_total * float(group_weights.get(group, 0))
                    supply_basis = "district-proxy-fallback"
                seats_draw = actual_seats * seat_actual_mult
            else:
                actual_seats = np.nan
                supply_basis = "district-proxy"
                seats_draw = proxy_seats_total * float(group_weights.get(group, 0)) * seat_proxy_mult

            supply = seats_draw * rate_fill * rate_completion * rate_entry
            supply_rows.append({
                "district": district,
                "lgd_code": d["lgd_code"],
                "year": year,
                "nco_group_2digit": group,
                "occupation_label": o["occupation_label"],
                "proxy_seats": proxy_seats_total * float(group_weights.get(group, 0)),
                "actual_seats": actual_seats,
                "supply_basis": supply_basis,
                "supply_p10": float(np.quantile(supply, 0.10)),
                "supply_median": float(np.quantile(supply, 0.50)),
                "supply_p90": float(np.quantile(supply, 0.90)),
            })

            ratio = supply / np.maximum(openings, 1e-9)
            p10, p50, p90 = np.quantile(ratio, [0.10, 0.50, 0.90])
            if p90 < 1:
                signal = "GAP"
            elif p10 > 1:
                signal = "SURPLUS"
            else:
                signal = "NEEDS DATA"
            width = float(p90 - p10)
            demand_median = float(np.quantile(openings, 0.50))
            # Evidence tier: state source = strong, district proxy = moderate, occupation prior = weaker.
            demand_evidence = 0.78
            supply_evidence = 0.95 if supply_basis.startswith("district-actual") else 0.55
            mapping_rate = float((emp_match["match_method"] != "review").mean()) if not emp_match.empty else 0.0
            interval_penalty = 1.0 / (1.0 + width)
            confidence = max(0.0, min(1.0, (0.5 * demand_evidence + 0.35 * supply_evidence + 0.15 * mapping_rate) * interval_penalty))
            voi = width * demand_median
            decision_status = signal if actual_supply_loaded else "NEEDS DATA"
            if actual_supply_loaded and signal in {"GAP", "SURPLUS"}:
                decision_status = "PROVISIONAL " + signal
            elif actual_supply_loaded and signal == "NEEDS DATA":
                decision_status = "NEEDS DATA"
            results.append({
                "district": district,
                "lgd_code": d["lgd_code"],
                "year": year,
                "industry": "Manufacturing",
                "nco_group_2digit": group,
                "occupation_label": o["occupation_label"],
                "supply_basis": supply_basis,
                "ratio_p10": float(p10),
                "ratio_median": float(p50),
                "ratio_p90": float(p90),
                "interval_width": width,
                "signal": signal,
                "decision_status": decision_status,
                "evidence_ready": bool(actual_supply_loaded),
                "confidence_score": confidence,
                "annual_openings_median": demand_median,
                "voi_score": voi,
            })

    demand_df = pd.DataFrame(demand_rows)
    supply_df = pd.DataFrame(supply_rows)
    ratio_df = pd.DataFrame(results)

    district_summary = []
    for district, g in ratio_df.groupby("district"):
        # SCI uses median estimated openings as weights.
        w = g["annual_openings_median"].clip(lower=0)
        r = g["ratio_median"].clip(lower=0)
        sci = float((w * np.minimum(r, 1.0)).sum() / max(w.sum(), 1e-9))
        district_summary.append({
            "district": district,
            "SCI": sci,
            "mean_confidence": float(g.confidence_score.mean()),
            "max_interval_width": float(g.interval_width.max()),
            "total_annual_openings": float(g.annual_openings_median.sum()),
            "VOI": float(g.voi_score.sum()),
            "gap_cells": int((g.signal == "GAP").sum()),
            "needs_data_cells": int((g.signal == "NEEDS DATA").sum()),
            "supply_basis": ",".join(sorted(g.supply_basis.unique())),
            "decision_status": ",".join(sorted(g.decision_status.unique())),
        })
    district_df = pd.DataFrame(district_summary).sort_values(["VOI", "SCI"], ascending=[False, True])
    district_df["priority_rank"] = np.arange(1, len(district_df) + 1)

    # Focus contrast.
    focus_order = [d for d in ["Tumakuru", "Kalaburagi", "Bengaluru Rural", "Raichur"] if d in set(district_df.district)]
    focus_df = district_df[district_df.district.isin(focus_order)].copy()

    # Corruption test: corrupt clean employment names, duplicate 5%, recover district keys.
    corruption = run_corruption_test(lgd, emp)

    # Sanity: compare 2022 model allocation shares to 2023 Udyam employment shares (explicitly non-independent).
    sanity = run_sanity_check(emp)

    # Sensitivity and ranks.
    sensitivity = run_sensitivity(cfg, emp, mix, dmap, group_weights, state_mfg_workers, total_current_seats, selected_groups, actual_map)

    # Audit record.
    run_id = datetime.now().strftime("RUN-%Y%m%d-%H%M%S")
    audit = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "monte_carlo_draws": draws,
        "selected_nco_groups": selected_groups,
        "actual_supply_loaded": bool(actual_supply_loaded),
        "occupation_mix_observed": bool(mix_is_observed),
        "source_files": source_registry(paths).to_dict(orient="records"),
        "decision_rule": "GAP if p90 < 1; SURPLUS if p10 > 1; otherwise NEEDS DATA",
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    demand_df.to_csv(output_dir / "demand_estimates.csv", index=False)
    supply_df.to_csv(output_dir / "supply_estimates.csv", index=False)
    ratio_df.to_csv(output_dir / "ratio_intervals.csv", index=False)
    district_df.to_csv(output_dir / "district_priority.csv", index=False)
    focus_df.to_csv(output_dir / "focus_districts.csv", index=False)
    corruption[0].to_csv(output_dir / "corruption_match_results.csv", index=False)
    corruption[1].to_csv(output_dir / "corruption_test_summary.csv", index=False)
    sanity[0].to_csv(output_dir / "sanity_check.csv", index=False)
    sanity[1].to_csv(output_dir / "sanity_summary.csv", index=False)
    sensitivity.to_csv(output_dir / "sensitivity.csv", index=False)
    ratio_df["assumption_scope"] = "Worked illustration: state manufacturing base + district proxy + occupation prior"
    with (output_dir / "audit_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(audit, default=str) + "\n")
    (output_dir / "run_summary.json").write_text(json.dumps({
        "run_id": run_id,
        "districts": int(district_df.shape[0]),
        "rows": int(ratio_df.shape[0]),
        "gap_cells": int((ratio_df.signal == "GAP").sum()),
        "surplus_cells": int((ratio_df.signal == "SURPLUS").sum()),
        "needs_data_cells": int((ratio_df.signal == "NEEDS DATA").sum()),
        "actual_supply_loaded": bool(actual_supply_loaded),
    }, indent=2), encoding="utf-8")

    return {
        "demand": demand_df,
        "supply": supply_df,
        "ratio": ratio_df,
        "district": district_df,
        "focus": focus_df,
        "corruption": corruption[1],
        "sanity": sanity[1],
        "sensitivity": sensitivity,
        "audit": audit,
    }


def run_corruption_test(lgd, emp):
    clean = emp[["district"]].copy().drop_duplicates()
    corrupted = clean.copy()
    aliases = {"Bengaluru Urban": "Bangalore", "Kalaburagi": "Gulbarga", "Vijayapura": "Bijapur", "Ballari": "Bellary", "Shivamogga": "Shimoga", "Tumakuru": "Tumkur", "Mysuru": "Mysore"}
    corrupted["district"] = corrupted["district"].map(lambda x: aliases.get(x, x))
    # Add deterministic typos to some names.
    typo_map = {"Belagavi": "Belagvi", "Chikkaballapur": "Chikkaballpura", "Davanagere": "Davanagri"}
    corrupted["district"] = corrupted["district"].map(lambda x: typo_map.get(x, x))
    dup_n = max(1, int(math.ceil(len(corrupted) * 0.05)))
    corrupted = pd.concat([corrupted, corrupted.head(dup_n)], ignore_index=True)
    matched = match_districts(corrupted["district"], lgd, 0.90)
    matched = pd.concat([corrupted.reset_index(drop=True), matched], axis=1)
    before = len(matched)
    matched = matched[matched.matched_district.ne("")].copy()
    after_unique = matched.drop_duplicates("lgd_code")
    duplicates_removed = len(matched) - len(after_unique)
    recovered = after_unique.lgd_code.nunique()
    summary = pd.DataFrame([{
        "clean_districts": len(clean),
        "corrupted_rows": before,
        "matched_unique_districts": recovered,
        "matching_recovery_rate": recovered / len(clean),
        "duplicates_removed": duplicates_removed,
        "status": "PASS" if recovered == len(clean) else "REVIEW",
    }])
    return matched, summary


def run_sanity_check(emp: pd.DataFrame):
    current = emp[["matched_district", "district_proxy_share"]].copy()
    path = RAW / "karnataka_udyam_employment_share_2023.csv"
    if path.exists():
        other = pd.read_csv(path)
        m = other.merge(current, left_on="district", right_on="matched_district", how="inner")
        m["share_other"] = m["employment_share_percent"] / m["employment_share_percent"].sum()
        m["abs_share_diff"] = (m["district_proxy_share"] - m["share_other"]).abs()
        summary = pd.DataFrame([{
            "check": "2022 Udyam proxy share vs 2023 Udyam employment share",
            "median_abs_share_diff_pct_points": float(m.abs_share_diff.median() * 100),
            "note": "temporal consistency check, not an independent validation benchmark",
        }])
        return m, summary
    return pd.DataFrame(), pd.DataFrame([{"check": "not available", "median_abs_share_diff_pct_points": np.nan, "note": "no 2023 share file"}])


def run_sensitivity(cfg, emp, mix, dmap, group_weights, state_mfg_workers, total_current_seats, selected_groups, actual_map):
    base = cfg
    params = ["opening_rate", "seat_fill_rate", "completion_rate", "sector_entry_rate", "proxy_seat_uncertainty"]
    rows = []
    focus = [d for d in ["Tumakuru", "Kalaburagi"] if d in set(emp.matched_district)]
    if not focus:
        focus = emp.matched_district.head(2).tolist()
    occ_shares = dict(zip(mix.nco_group_2digit.astype(str), mix.share))
    # Deterministic central scenario ratios and low/high one-at-a-time effects.
    def ratio_for(district, changed_param=None, changed_side=None):
        d = emp[emp.matched_district.eq(district)].iloc[0]
        proxy_seats_total = float(dmap.loc[dmap.matched_district.eq(district), "proxy_seats"].iloc[0])
        demand_stock_total = float(d.district_mfg_employment_proxy)
        open_rate = base["opening_rate"]["mode"]
        fill = base["seat_fill_rate"]["mode"]
        comp = base["completion_rate"]["mode"]
        entry = base["sector_entry_rate"]["mode"]
        proxy_mult = base["proxy_seat_uncertainty"]["mode"]
        if changed_param:
            v = base[changed_param][changed_side]
            if changed_param == "opening_rate": open_rate = v
            elif changed_param == "seat_fill_rate": fill = v
            elif changed_param == "completion_rate": comp = v
            elif changed_param == "sector_entry_rate": entry = v
            elif changed_param == "proxy_seat_uncertainty": proxy_mult = v
        ratios=[]
        for g, share in occ_shares.items():
            demand = demand_stock_total * share * open_rate
            supply = proxy_seats_total * float(group_weights.get(g,0)) * proxy_mult * fill * comp * entry
            ratios.append(supply/max(demand,1e-9))
        return float(np.average(ratios, weights=list(occ_shares.values())))
    for p in params:
        for d in focus:
            b = ratio_for(d)
            lo = ratio_for(d, p, "low")
            hi = ratio_for(d, p, "high")
            rows.append({"district": d, "parameter": p, "base_ratio": b, "low_ratio": lo, "high_ratio": hi, "absolute_effect": max(abs(lo-b),abs(hi-b))})
    return pd.DataFrame(rows).sort_values("absolute_effect", ascending=False)


def main():
    res = compute_model()
    print(json.dumps({
        "districts": len(res["district"]),
        "ratio_rows": len(res["ratio"]),
        "signals": res["ratio"]["signal"].value_counts().to_dict(),
        "top_priority": res["district"].head(5)[["district", "SCI", "VOI", "priority_rank"]].to_dict(orient="records"),
    }, indent=2))


if __name__ == "__main__":
    main()
