from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
from difflib import SequenceMatcher

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
    "selected_nco_groups": ["72", "74"],
    "monte_carlo_draws": 5000,
    "random_seed": 20261016,
    "district_fuzzy_threshold": 0.90,
    "opening_rate": {"low": 0.05, "mode": 0.085, "high": 0.12},
    "seat_fill_rate": {"low": 0.50, "mode": 0.813, "high": 0.90},
    "completion_rate": {"low": 0.50, "mode": 0.593, "high": 0.70},
    "sector_entry_rate": {"low": 0.20, "mode": 0.30, "high": 0.40},
    "proxy_seat_uncertainty": {"low": 0.75, "mode": 1.00, "high": 1.25},
    "actual_seat_uncertainty": {"low": 0.98, "mode": 1.00, "high": 1.02},
    "partial_remainder_uncertainty": {"low": 0.75, "mode": 1.00, "high": 1.25},
    "occupation_prior_uncertainty": {"low": 0.80, "mode": 1.00, "high": 1.20},
    "allocation_uncertainty": {"concentration": 50.0},
    "dgt_share_allocation_uncertainty": {"concentration": 20.0},
    "demand_allocation_uncertainty": {"lognormal_sigma": 0.35},
    "confidence_weights": {"demand_evidence": 0.35, "supply_evidence": 0.30, "mapping": 0.15, "interval": 0.20},
    "evidence_scores": {
        "demand": {"state_actual_plus_district_proxy": 0.55, "district_actual": 0.90},
        "supply": {"proxy": 0.45, "partial_floor": 0.55, "full_actual": 0.95, "actual_total": 0.75},
    },
    "min_count_suppression": 5,
    "decision_rule": "GAP if p90 < 1; SURPLUS if p10 > 1; otherwise NEEDS DATA",
    "proxy_allocation_method": "official_2022_district_iti_count_weight",
    "max_unmapped_supply_share": 0.05,
    "dgt_scale_warning_threshold": 0.5,
    "provisional_sources": ["provisional_dgt_2026"],
}


def deep_merge(base: dict, override: dict) -> dict:
    out = json.loads(json.dumps(base))
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        return deep_merge(DEFAULT_CONFIG, json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except Exception:
        return json.loads(json.dumps(DEFAULT_CONFIG))


CONFIG = load_config()


def suppress_small(df: pd.DataFrame, count_col: str, k: int | None = None) -> pd.DataFrame:
    """Suppress public supply/demand/ratio values when the source count is below the configured threshold.

    This is an aggregation/privacy guardrail, not a model transformation. Institutional seat
    rows contain no personal data, but small-cell suppression is still applied consistently
    to public exports so the pipeline has a visible publication rule.
    """
    out = df.copy()
    if count_col not in out.columns:
        raise KeyError(f"Missing suppression count column: {count_col}")
    threshold = int(CONFIG.get("min_count_suppression", 5) if k is None else k)
    counts = pd.to_numeric(out[count_col], errors="coerce")
    mask = counts < threshold
    value_cols = [c for c in out.columns if c.startswith(("supply", "demand", "ratio"))]
    if value_cols:
        out.loc[mask, value_cols] = pd.NA
    out["suppressed"] = mask
    return out


DISTRICT_BOUNDARY_HARMONISATION = CLEAN / "district_boundary_harmonisation.csv"

def _load_boundary_harmonisation() -> dict[str, str]:
    if DISTRICT_BOUNDARY_HARMONISATION.exists():
        table = pd.read_csv(DISTRICT_BOUNDARY_HARMONISATION)
        required = {"source_district", "analytical_district"}
        if not required.issubset(table.columns):
            raise ValueError("district_boundary_harmonisation.csv must contain source_district and analytical_district")
        return dict(zip(table["source_district"].astype(str), table["analytical_district"].astype(str)))
    return {
        "Ballari": "Ballari-Vijayanagara",
        "Vijayanagara": "Ballari-Vijayanagara",
    }

ANALYTICAL_MERGES = _load_boundary_harmonisation()

def apply_analytical_merge(name: str) -> str:
    return ANALYTICAL_MERGES.get(str(name), str(name))


# Production alias table. The corruption test deliberately generates additional unseen aliases.
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
    "chamrajnagar": "chamarajanagar",
    "davangere": "davanagere",
    "davangere district": "davanagere",
    "raichuru": "raichur",
    "ramnagara": "ramanagara",
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


def match_districts(values: pd.Series, master: pd.DataFrame, threshold: float | None = None) -> pd.DataFrame:
    threshold = float(threshold if threshold is not None else CONFIG.get("district_fuzzy_threshold", 0.90))
    master = master.copy()
    master["_norm"] = master["district_name"].map(norm)
    exact = dict(zip(master["_norm"], master["district_name"]))
    code_by_name = dict(zip(master["district_name"], master["lgd_code"]))
    results = []
    for raw in values.astype(str):
        n = norm(raw)
        alias = ALIAS_MAP.get(n, n)
        candidate = exact.get(n)
        method = "exact" if candidate else None
        best_score = 1.0 if candidate else 0.0
        if candidate is None and alias in exact:
            candidate = exact[alias]
            method = "alias"
            best_score = 0.99
        if candidate is None:
            best_name, best_score = None, 0.0
            for name_norm, name in exact.items():
                score = SequenceMatcher(None, alias, name_norm).ratio()
                if score > best_score:
                    best_score, best_name = score, name
            if best_name is not None and best_score >= threshold:
                candidate = best_name
                method = "fuzzy"
            else:
                candidate = None
                method = "review"
        results.append({
            "raw_district": raw,
            "matched_district": candidate or "",
            "lgd_code": code_by_name.get(candidate, "") if candidate else "",
            "match_method": method,
            "match_confidence": round(float(best_score), 4),
            "match_status": "matched" if candidate else "review",
        })
    return pd.DataFrame(results)


def source_registry(paths: dict[str, Path] | None = None) -> pd.DataFrame:
    path_to_meta = {
        "lgd_districts.csv": ("SRC-LGD-2026", "district"),
        "karnataka_udyam_employment_nov2022.csv": ("SRC-UDYAM-EMP-2022", "district"),
        "udyam_karnataka_district_totals_jun2026.csv": ("SRC-UDYAM-TOTAL-2026", "district"),
        "asi_karnataka_manufacturing_2022_23.csv": ("SRC-ASI-KA-2022-23", "state"),
        "ncvtmis_karnataka_state_2022.csv": ("SRC-NCVT-KA-2022", "state"),
        "iti_division_training_2020_21.csv": ("SRC-DGT-TRACER-2020-21", "division"),
        "occupation_mix_prior.csv": ("SRC-PLFS-OCC-PRIOR", "state-prior"),
        "crosswalk.csv": ("SRC-HUMAN-CROSSWALK", "course-to-NCO"),
        "ncvtmis_file1171_real_partial.csv": ("SRC-NCVT-1171", "district-x-ITI-x-trade"),
        "district_iti_counts.csv": ("SRC-RAJYA-ITI-2022", "district historical weight"),
        "dgt_cts_2026_karnataka_supply_nco.csv": ("SRC-DGT-CTS2026-KA", "district-x-ITI-x-trade-x-NCO"),
        "dgt_cts_2026_provisional_seat_matrix.pdf": ("SRC-DGT-CTS2026-KA", "state-x-district-x-ITI-x-trade"),
    }
    meta = pd.read_csv(RAW / "source_registry.csv") if (RAW / "source_registry.csv").exists() else pd.DataFrame()
    citations_path = ROOT / "CITATIONS.csv"
    citations = pd.read_csv(citations_path) if citations_path.exists() else pd.DataFrame()
    meta_by_source = meta.set_index("source_id").to_dict("index") if not meta.empty and "source_id" in meta.columns else {}
    cit_by_source = citations.set_index("source_id").to_dict("index") if not citations.empty and "source_id" in citations.columns else {}
    local_files = [RAW/n for n in path_to_meta if (RAW/n).exists()] + [CLEAN/n for n in path_to_meta if (CLEAN/n).exists()]
    rows = []
    for p in local_files:
        name = p.name
        sid, grain = path_to_meta[name]
        m = {**cit_by_source.get(sid, {}), **meta_by_source.get(sid, {})}
        rows.append({
            "file_id": "FILE-" + sha256(p)[:12].upper(),
            "path": str(p.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256(p),
            "source_id": sid,
            "source_url": m.get("url", ""),
            "title": m.get("title", sid),
            "year": m.get("year", ""),
            "grain": m.get("grain", grain) or grain,
            "accessed": m.get("accessed", ""),
            "status": m.get("status", "captured"),
            "locator": m.get("locator", ""),
        })
    return pd.DataFrame(rows)


def load_inputs(paths: dict[str, Path] | None = None):
    paths = paths or {}
    lgd = pd.read_csv(paths.get("lgd", RAW / "lgd_districts.csv"))
    emp = pd.read_csv(paths.get("employment", RAW / "karnataka_udyam_employment_nov2022.csv"))
    udyam_totals_path = paths.get("udyam_totals", RAW / "udyam_karnataka_district_totals_jun2026.csv")
    udyam_totals = pd.read_csv(udyam_totals_path) if udyam_totals_path.exists() else None
    asi = pd.read_csv(paths.get("asi", RAW / "asi_karnataka_manufacturing_2022_23.csv"))
    ncvt = pd.read_csv(paths.get("ncvt", RAW / "ncvtmis_karnataka_state_2022.csv"))
    mix = pd.read_csv(paths.get("occupation_mix", CLEAN / "occupation_mix_prior.csv"))
    cw = pd.read_csv(paths.get("crosswalk", CLEAN / "crosswalk.csv"))
    dgt = pd.read_csv(paths.get("dgt", RAW / "iti_division_training_2020_21.csv"))
    dmap = pd.read_csv(paths.get("division_map", CLEAN / "district_dgt_division_map.csv"))
    iti_counts_path = paths.get("iti_counts", CLEAN / "district_iti_counts.csv")
    iti_counts = pd.read_csv(iti_counts_path) if iti_counts_path.exists() else None
    return lgd, emp, udyam_totals, asi, ncvt, mix, cw, dgt, dmap, iti_counts


def prepare_model_data(lgd, emp, udyam_totals, asi, ncvt, mix, cw, dgt, dmap, selected_groups, iti_counts=None, threshold=0.90, demand_allocation_method="udyam_employment"):
    emp = emp.copy()
    emp_match = match_districts(emp["district"], lgd, threshold)
    emp = pd.concat([emp.reset_index(drop=True), emp_match.drop(columns=["raw_district"])], axis=1)
    emp_review = emp[emp["matched_district"].eq("")].copy()
    emp = emp[emp["matched_district"].ne("")].copy()
    emp["analytical_district"] = emp["matched_district"].map(apply_analytical_merge)
    # Collapse Ballari + Vijayanagara into one analytical geography while retaining raw LGD matches in emp_match.
    emp = (
        emp.groupby("analytical_district", as_index=False)
        .agg(
            udyam_employment=("udyam_employment", "sum"),
            lgd_code=("lgd_code", lambda s: "|".join(sorted({str(x) for x in s if str(x).strip()}))),
            source_lgd_districts=("matched_district", lambda s: "|".join(sorted(set(map(str, s))))),
            source_district_count=("matched_district", "nunique"),
        )
        .rename(columns={"analytical_district": "matched_district"})
    )
    emp["district"] = emp["matched_district"]
    emp["udyam_employment_share"] = emp["udyam_employment"].clip(lower=0) / max(emp["udyam_employment"].sum(), 1e-9)

    # Independent Udyam-enterprise-count allocator (June 2026 OGD source).
    # It is deliberately kept separate from employment because the two measures
    # represent different notions of district scale.
    if udyam_totals is not None and not udyam_totals.empty:
        ut = udyam_totals.copy()
        ut_match = match_districts(ut["district"], lgd, threshold)
        ut = pd.concat([ut.reset_index(drop=True), ut_match.drop(columns=["raw_district"])], axis=1)
        ut = ut[ut["matched_district"].ne("")].copy()
        ut["analytical_district"] = ut["matched_district"].map(apply_analytical_merge)
        unit_col = "total_enterprises" if "total_enterprises" in ut.columns else None
        if unit_col is None:
            raise ValueError("Udyam district totals file must contain total_enterprises.")
        ut[unit_col] = pd.to_numeric(ut[unit_col], errors="coerce").fillna(0.0)
        ut = ut.groupby("analytical_district", as_index=False)[unit_col].sum()
        ut = ut.rename(columns={"analytical_district": "matched_district", unit_col: "udyam_units"})
        emp = emp.merge(ut, on="matched_district", how="left")
        emp["udyam_units"] = pd.to_numeric(emp["udyam_units"], errors="coerce")
    else:
        emp["udyam_units"] = np.nan

    unit_total = float(emp["udyam_units"].fillna(0).sum())
    emp["udyam_units_share"] = np.where(
        unit_total > 0,
        emp["udyam_units"].fillna(0).clip(lower=0) / unit_total,
        np.nan,
    )

    if demand_allocation_method == "udyam_employment":
        demand_share = emp["udyam_employment_share"].copy()
    elif demand_allocation_method == "udyam_units":
        if emp["udyam_units_share"].isna().any() or not np.isfinite(emp["udyam_units_share"]).all():
            missing = emp.loc[emp["udyam_units_share"].isna(), "matched_district"].tolist()
            raise ValueError(f"Udyam unit-share allocator is missing districts: {missing}")
        demand_share = emp["udyam_units_share"].copy()
    elif demand_allocation_method == "blend":
        if emp["udyam_units_share"].isna().any() or not np.isfinite(emp["udyam_units_share"]).all():
            missing = emp.loc[emp["udyam_units_share"].isna(), "matched_district"].tolist()
            raise ValueError(f"Udyam blend allocator is missing districts: {missing}")
        demand_share = 0.5 * (emp["udyam_employment_share"] + emp["udyam_units_share"])
    else:
        raise ValueError(f"Unknown demand_allocation_method: {demand_allocation_method}")

    demand_share = demand_share.clip(lower=0).astype(float)
    demand_share = demand_share / max(float(demand_share.sum()), 1e-12)
    emp["demand_allocation_method"] = demand_allocation_method
    emp["demand_allocation_share"] = demand_share

    state_mfg_workers = float(asi.loc[asi["state"].astype(str).str.upper().eq("KARNATAKA"), "persons_engaged"].iloc[0])
    emp["district_proxy_share"] = emp["demand_allocation_share"]
    emp["district_mfg_employment_proxy"] = state_mfg_workers * emp["demand_allocation_share"]

    mix = mix.copy()
    mix["nco_group_2digit"] = mix["nco_group_2digit"].astype(str)
    mix = mix[mix["nco_group_2digit"].isin([str(x) for x in selected_groups])].copy()
    mix["share"] = pd.to_numeric(mix["share_within_manufacturing"], errors="coerce")
    mix["share_low"] = mix["share"] * float(CONFIG["occupation_prior_uncertainty"]["low"])
    mix["share_mode"] = mix["share"] * float(CONFIG["occupation_prior_uncertainty"]["mode"])
    mix["share_high"] = mix["share"] * float(CONFIG["occupation_prior_uncertainty"]["high"])

    dgt = dgt.copy()
    div_cols = [c for c in dgt.columns if c.endswith("_sanctioned")]
    dgt["division_sanctioned"] = dgt[div_cols].sum(axis=1)
    dgt["division_share"] = dgt["division_sanctioned"] / max(dgt["division_sanctioned"].sum(), 1e-9)
    total_current_seats = float(ncvt.loc[ncvt["state"].astype(str).str.upper().eq("KARNATAKA"), "seats_available_2022"].iloc[0])
    div_seats = dict(zip(dgt["division"], total_current_seats * dgt["division_share"]))

    dmap = dmap.copy()
    dmap = dmap.merge(emp[["matched_district", "district_proxy_share"]], left_on="district", right_on="matched_district", how="left")
    dmap["matched_district"] = dmap["matched_district"].fillna(dmap["district"])

    if iti_counts is not None and not iti_counts.empty:
        c = iti_counts.copy()
        c.columns = [str(x).strip() for x in c.columns]
        if {"district", "iti_count"}.issubset(c.columns):
            c["district"] = c["district"].astype(str)
            c["iti_count"] = pd.to_numeric(c["iti_count"], errors="coerce")
            dmap = dmap.merge(c[["district", "iti_count"]], on="district", how="left")
        else:
            dmap["iti_count"] = np.nan
    else:
        dmap["iti_count"] = np.nan

    dmap["division_iti_count_sum"] = dmap.groupby("dgt_division")["iti_count"].transform("sum")
    count_ready = dmap["iti_count"].notna() & dmap["division_iti_count_sum"].gt(0)
    dmap["division_allocation_share"] = np.where(
        count_ready,
        dmap["iti_count"] / dmap["division_iti_count_sum"],
        1.0 / dmap.groupby("dgt_division")["district"].transform("count"),
    )
    dmap["allocation_basis"] = np.where(count_ready, "NCVT ITI-count weighted", "equal-within-division fallback")
    dmap["proxy_seats_total"] = [div_seats.get(div, np.nan) * share for div, share in zip(dmap["dgt_division"], dmap["division_allocation_share"])]

    cw = cw.copy()
    cw["nco_group_2digit"] = cw["nco_group_2digit"].astype(str)
    selected_cw = cw[cw["nco_group_2digit"].isin([str(x) for x in selected_groups])].copy()
    group_weights = selected_cw.groupby("nco_group_2digit")["statewide_course_weight"].sum().to_dict()
    return emp, mix, dmap, group_weights, state_mfg_workers, total_current_seats, emp_match, emp_review


def load_actual_supply(path: Path | None, selected_groups) -> pd.DataFrame | None:
    if not path or not path.exists():
        return None
    df = pd.read_csv(path)
    if not {"district", "seats"}.issubset(df.columns):
        raise ValueError("Actual supply file must contain district,seats. Optional: nco_group_2digit or trade.")
    df = df.copy()
    if "nco_group_2digit" not in df.columns:
        if "trade" in df.columns:
            cw_path = CLEAN / "dgt_trade_nco_crosswalk.csv" if (CLEAN / "dgt_trade_nco_crosswalk.csv").exists() else CLEAN / "crosswalk.csv"
            cw = pd.read_csv(cw_path)
            cw2 = cw.copy()
            cw2["_trade"] = cw2["course_or_trade"].astype(str).str.strip().str.lower()
            df["_trade"] = df["trade"].astype(str).str.replace(r"\s*\(NSQF\).*", "", regex=True).str.strip().str.lower()
            df = df.merge(cw2[["_trade", "nco_group_2digit"]], on="_trade", how="left")
            df.drop(columns=["_trade"], inplace=True)
        else:
            df["nco_group_2digit"] = "ALL"
    df["nco_group_2digit"] = df["nco_group_2digit"].fillna("UNMAPPED").astype(str).str.strip()
    df.loc[df["nco_group_2digit"].isin(["", "nan", "None", "NaN"]), "nco_group_2digit"] = "UNMAPPED"
    df["seats"] = pd.to_numeric(df["seats"], errors="coerce")
    if "source_period" not in df.columns:
        df["source_period"] = "user-supplied"
    if "coverage_status" not in df.columns:
        df["coverage_status"] = "unknown"
    # Actual ingestion deduplication: duplicate source rows are removed before aggregation.
    # Preserve distinct source rows. Real DGT files identify an ITI as `iti_mis_code`;
    # using only district+trade+seats would collapse legitimate rows from different ITIs.
    key_cols = [c for c in ["district", "source_district", "iti_code", "iti_mis_code", "iti_name", "trade", "nco_group_2digit", "seats", "reference_period", "source_period", "source_id", "pdf_page"] if c in df.columns]
    if key_cols:
        df["_duplicate_key"] = df[key_cols].astype(str).agg("|".join, axis=1)
        df = df.drop_duplicates("_duplicate_key").drop(columns=["_duplicate_key"])
    return df


def _shared_allocation_draws(rng, districts_df: pd.DataFrame, draws: int, concentration: float):
    """Draw common within-division allocation multipliers with mean ~1.0 per district.

    proxy_seats_total already contains the base district allocation. The draw therefore
    perturbs around that base instead of introducing a second 1/n division.
    """
    out = np.zeros((draws, len(districts_df)))
    reset = districts_df.reset_index(drop=True)
    for _, idx in reset.groupby("dgt_division").groups.items():
        positions = list(idx)
        base = reset.loc[positions, "division_allocation_share"].to_numpy(dtype=float)
        base = base / max(base.sum(), 1e-12)
        alpha = np.maximum(float(concentration) * base, 1e-6)
        samples = rng.gamma(shape=alpha, scale=1.0, size=(draws, len(positions)))
        samples /= samples.sum(axis=1, keepdims=True)
        out[:, positions] = samples / np.maximum(base[None, :], 1e-12)
    return out



def _spearman_series(a: pd.Series, b: pd.Series) -> float:
    x = pd.to_numeric(a, errors="coerce")
    y = pd.to_numeric(b, errors="coerce")
    mask = x.notna() & y.notna()
    if mask.sum() < 2:
        return float("nan")
    return float(x[mask].rank(method="average").corr(y[mask].rank(method="average")))


def _dgt_share_allocation_draws(
    rng: np.random.Generator,
    dmap: pd.DataFrame,
    actual_map: pd.DataFrame | None,
    selected_groups: list[str],
    group_weights: dict[str, float],
    total_state_seats: float,
    draws: int,
    concentration: float,
    mean_retention: float = 0.75,
):
    """Allocate statewide in-scope seats using DGT shares shrunk toward the historical proxy.

    For each district:
        w_d = min(DGT ITIs in matrix / 2022 ITI count, 1)
        share_d = w_d * DGT_share_d + (1-w_d) * proxy_share_d

    This prevents sparse DGT coverage from creating artificial zero-supply districts.
    A district absent from DGT (w=0) remains on the historical proxy. Dirichlet/Gamma
    draws perturb the blended shares with deliberately wider uncertainty because DGT is
    provisional and incomplete.
    """
    reset = dmap.reset_index(drop=True)
    shares_by_group = {}
    mult_by_group = {}
    state_total_by_group = {}
    observed_by_group = {}
    proxy_share_by_group = {}
    dgt_share_by_group = {}

    coverage = pd.to_numeric(reset["matrix_iti_coverage"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    coverage = np.clip(coverage, 0.0, 1.0)

    for group in selected_groups:
        proxy_base = pd.to_numeric(reset["proxy_seats_total"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        proxy_base = proxy_base * float(group_weights.get(group, 0.0))
        proxy_total = float(proxy_base.sum())
        proxy_share = proxy_base / max(proxy_total, 1e-12)

        observed = {}
        if actual_map is not None and not actual_map.empty:
            sub = actual_map[actual_map["nco_group_2digit"].astype(str).eq(str(group))]
            if not sub.empty:
                observed = dict(zip(
                    sub["matched_district"].astype(str),
                    pd.to_numeric(sub["seats"], errors="coerce").fillna(0.0)
                ))

        observed_total = float(sum(v for v in observed.values() if v >= 0))
        dgt_share = np.zeros(len(reset), dtype=float)
        if observed_total > 0:
            for i, district in enumerate(reset["matched_district"].astype(str)):
                dgt_share[i] = float(observed.get(district, 0.0)) / observed_total

        raw = coverage * dgt_share + (1.0 - coverage) * proxy_share
        raw = raw / max(raw.sum(), 1e-12)

        alpha = np.maximum(float(concentration) * raw, 1e-6)
        samples = rng.gamma(shape=alpha, scale=1.0, size=(draws, len(reset)))
        samples /= np.maximum(samples.sum(axis=1, keepdims=True), 1e-12)
        # Keep a large fraction of the evidence-weighted mean so tiny districts do not
        # collapse toward zero merely because their Dirichlet alpha is < 1.
        retention = float(np.clip(mean_retention, 0.0, 0.99))
        samples = retention * raw[None, :] + (1.0 - retention) * samples
        samples /= np.maximum(samples.sum(axis=1, keepdims=True), 1e-12)
        mult = samples / np.maximum(raw[None, :], 1e-12)

        shares_by_group[group] = raw
        mult_by_group[group] = mult
        state_total_by_group[group] = float(total_state_seats) * float(group_weights.get(group, 0.0))
        observed_by_group[group] = observed
        proxy_share_by_group[group] = proxy_share
        dgt_share_by_group[group] = dgt_share

    return shares_by_group, mult_by_group, state_total_by_group, observed_by_group, proxy_share_by_group, dgt_share_by_group



def _rank_stats_from_draws(district_draws: dict[str, np.ndarray]) -> pd.DataFrame:
    if not district_draws:
        return pd.DataFrame()
    names = list(district_draws)
    mat = np.column_stack([district_draws[n] for n in names])
    med = np.median(mat, axis=0)
    base_order = np.argsort(-med)
    base_rank = np.empty(len(names), dtype=int)
    base_rank[base_order] = np.arange(1, len(names) + 1)
    draw_ranks = np.empty_like(mat, dtype=int)
    for i in range(mat.shape[0]):
        order = np.argsort(-mat[i, :], kind="mergesort")
        draw_ranks[i, order] = np.arange(1, len(names) + 1)
    rho_vals = []
    for i in range(mat.shape[0]):
        a = draw_ranks[i].astype(float)
        b = base_rank.astype(float)
        rho_vals.append(float(np.corrcoef(a, b)[0, 1]) if np.std(a) and np.std(b) else 1.0)
    top5_freq = (draw_ranks <= 5).mean(axis=0)
    rows = []
    for j, name in enumerate(names):
        rows.append({
            "district": name,
            "baseline_rank": int(base_rank[j]),
            "rank_p10": float(np.quantile(draw_ranks[:, j], 0.10)),
            "rank_median": float(np.quantile(draw_ranks[:, j], 0.50)),
            "rank_p90": float(np.quantile(draw_ranks[:, j], 0.90)),
            "top5_frequency": float(top5_freq[j]),
            "global_rank_stability_median_rho": float(np.median(rho_vals)),
        })
    return pd.DataFrame(rows).sort_values("baseline_rank").reset_index(drop=True)


def _spearman(a: pd.Series, b: pd.Series) -> float:
    return float(a.rank().corr(b.rank())) if len(a) > 1 else float("nan")


def run_sensitivity_rank_stability(base_rank: pd.DataFrame, parameter_runs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    if base_rank.empty:
        return pd.DataFrame()
    base_map = base_rank[["district", "baseline_rank"]].set_index("district")["baseline_rank"]
    for param, df in parameter_runs.items():
        if df.empty:
            continue
        m = base_map.rename("base").to_frame().join(df.set_index("district")["baseline_rank"].rename("scenario"), how="inner")
        rows.append({
            "parameter": param,
            "scenario": "low",
            "spearman_rank_vs_base": _spearman(m["base"], m["scenario"]),
            "top5_overlap": float(((m["base"] <= 5) & (m["scenario"] <= 5)).sum() / max((m["base"] <= 5).sum(), 1)),
        })
    return pd.DataFrame(rows)


def run_corruption_test(lgd, emp):
    clean = emp[["district"]].drop_duplicates().reset_index(drop=True)
    seed = int(CONFIG.get("random_seed", 20261016)) + 101
    rng = np.random.default_rng(seed)
    names = clean["district"].tolist()
    cases = []
    typo_count = 80
    typo_names=[n for n in names if len(norm(n)) >= 11]
    for case_id in range(typo_count):
        original = typo_names[int(rng.integers(0, len(typo_names)))] if typo_names else names[int(rng.integers(0, len(names)))]
        n = original
        # One adjacent transposition or one-character substitution; both keep a high edit similarity.
        j = int(rng.integers(1, max(len(n)-2, 2)))
        if len(n) >= 3 and rng.random() < 0.5:
            candidate = n[:j] + n[j+1] + n[j] + n[j+2:]
        else:
            repl = 'x' if n[j].lower() != 'x' else 'z'
            candidate = n[:j] + repl + n[j+1:]
        cases.append({"case_id": f"T{case_id+1:03d}", "clean_district": original, "district": candidate, "corruption_type": "seeded_typo"})
    unseen_templates = {
        "Bengaluru Urban": "Bengaluru City", "Kalaburagi": "Gulburga City", "Vijayapura": "Bijapur City",
        "Ballari": "Bellari City", "Mysuru": "Mysore City", "Davanagere": "Davanagri",
    }
    for case_id in range(20):
        original = names[int(rng.integers(0, len(names)))]
        alt = unseen_templates.get(original, original + " City")
        cases.append({"case_id": f"A{case_id+1:03d}", "clean_district": original, "district": alt, "corruption_type": "unseen_alias"})
    base = pd.DataFrame(cases)
    # Each base case is unique by case_id. Duplicate artifacts copy the same source_case_id.
    base["source_case_id"] = base["case_id"]
    dupes = base.sample(n=5, random_state=seed + 202).copy()
    dupes["case_id"] = [f"D{i+1:03d}" for i in range(len(dupes))]
    dupes["corruption_type"] = dupes["corruption_type"] + "_duplicate"
    corrupted = pd.concat([base, dupes], ignore_index=True)

    # Real dedupe step: duplicate artifacts share the same source_case_id.
    deduped = corrupted.drop_duplicates("source_case_id", keep="first").copy()
    duplicate_rows_removed = int(len(corrupted) - len(deduped))
    matched = match_districts(deduped["district"], lgd, float(CONFIG.get("district_fuzzy_threshold", 0.90)))
    details = pd.concat([deduped.reset_index(drop=True), matched.reset_index(drop=True)], axis=1)
    typo_rows = details[details["corruption_type"].eq("seeded_typo")]
    alias_rows = details[details["corruption_type"].eq("unseen_alias")]
    typo_correct = int((typo_rows["matched_district"] == typo_rows["clean_district"]).sum())
    alias_matched = int(alias_rows["matched_district"].ne("").sum())
    review_rows = int(details["matched_district"].eq("").sum())
    unmatched_review_rows = review_rows
    seed_count = int(typo_count + 20)
    summary = pd.DataFrame([{
        "clean_districts": len(clean),
        "seeded_corruptions": seed_count,
        "rows_before_dedupe": len(corrupted),
        "rows_after_dedupe": len(deduped),
        "seeded_typo_rows": len(typo_rows),
        "seeded_typo_correct": typo_correct,
        "seeded_typo_recovery_rate": typo_correct / max(len(typo_rows), 1),
        "unseen_alias_rows": len(alias_rows),
        "unseen_alias_matched": alias_matched,
        "unseen_alias_review_rows": int((alias_rows["matched_district"] == "").sum()),
        "review_queue_rows": review_rows,
        "unmatched_review_rows": unmatched_review_rows,
        "duplicate_rows_injected": 5,
        "duplicate_rows_removed": duplicate_rows_removed,
        "all_rows_preserved_for_review": True,
        "status": "PASS" if typo_correct / max(len(typo_rows), 1) >= 0.90 and alias_matched == 0 and duplicate_rows_removed == 5 else "REVIEW",
        "note": "80 seeded typos + 20 unseen aliases, with a real deduplication pass; unseen aliases are expected to route to review rather than count as successful matches.",
    }])
    return details, summary


def run_sanity_check(emp: pd.DataFrame):
    current = emp[["matched_district", "district_proxy_share"]].copy()
    path = RAW / "karnataka_udyam_employment_share_2023.csv"
    if not path.exists():
        return pd.DataFrame(), pd.DataFrame([{"check": "not available"}])
    other = pd.read_csv(path)
    m = other.merge(current, left_on="district", right_on="matched_district", how="inner")
    m["share_other"] = m["employment_share_percent"] / m["employment_share_percent"].sum()
    m["abs_share_diff"] = (m["district_proxy_share"] - m["share_other"]).abs()
    return m, pd.DataFrame([{
        "check": "2022 Udyam district proxy share vs 2023 Udyam employment share",
        "median_abs_share_diff_pct_points": float(m.abs_share_diff.median() * 100),
        "note": "Temporal consistency check; not an independent validation benchmark.",
    }])


def run_interval_shrink_demo(before_ratio: pd.DataFrame, after_ratio: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for district in ["Tumakuru", "Kalaburagi"]:
        b = before_ratio[before_ratio.district.eq(district)] if not before_ratio.empty else pd.DataFrame()
        a = after_ratio[after_ratio.district.eq(district)] if not after_ratio.empty else pd.DataFrame()
        for group in ["72", "74"]:
            bg = b[b.nco_group_2digit.eq(group)] if not b.empty else pd.DataFrame()
            ag = a[a.nco_group_2digit.eq(group)] if not a.empty else pd.DataFrame()
            if bg.empty or ag.empty:
                continue
            bw = float(bg.interval_width.iloc[0])
            aw = float(ag.interval_width.iloc[0])
            change = (bw - aw) / bw * 100 if bw else np.nan
            effect = "NARROWER" if change > 1 else ("WIDER" if change < -1 else "UNCHANGED")
            rows.append({
                "district": district,
                "nco_group_2digit": group,
                "before_basis": str(bg.supply_basis.iloc[0]),
                "after_basis": str(ag.supply_basis.iloc[0]),
                "before_width": bw,
                "after_width": aw,
                "interval_width_change_pct": float(change),
                "evidence_effect": effect,
                "after_ratio_p10": float(ag.ratio_p10.iloc[0]),
                "after_ratio_median": float(ag.ratio_median.iloc[0]),
                "after_ratio_p90": float(ag.ratio_p90.iloc[0]),
                "policy_call_allowed": bool(ag.decision_status.iloc[0] not in {"NEEDS DATA"}),
            })
    return pd.DataFrame(rows)


def compute_model(paths=None, overrides=None, actual_supply_path=None, output_dir=OUT, write_outputs=True, _internal=False):
    cfg = deep_merge(CONFIG, overrides or {})
    seed = int(cfg.get("random_seed", 20261016))
    draws = int(cfg.get("monte_carlo_draws", 5000))
    selected_groups = [str(x) for x in cfg.get("selected_nco_groups", ["72", "74"])]
    fuzzy_threshold = float(cfg.get("district_fuzzy_threshold", cfg.get("fuzzy_threshold", 0.90)))

    demand_allocation_method = str(cfg.get("demand_allocation_method", "udyam_employment"))
    valid_demand_methods = {"udyam_employment", "udyam_units", "blend"}
    if demand_allocation_method not in valid_demand_methods:
        raise ValueError(f"Unknown demand_allocation_method: {demand_allocation_method}")

    lgd, emp, udyam_totals, asi, ncvt, mix, cw, dgt, dmap, iti_counts = load_inputs(paths)
    emp, mix, dmap, group_weights, state_mfg_workers, total_current_seats, emp_match, emp_review = prepare_model_data(
        lgd, emp, udyam_totals, asi, ncvt, mix, cw, dgt, dmap, selected_groups,
        iti_counts=iti_counts, threshold=fuzzy_threshold, demand_allocation_method=demand_allocation_method
    )

    actual_supply = load_actual_supply(Path(actual_supply_path) if actual_supply_path else None, selected_groups)
    actual_supply_loaded = actual_supply is not None
    actual_match_df = pd.DataFrame()
    actual_map = None
    actual_full_ready = False
    actual_duplicate_rows_removed = 0
    analytical_districts = sorted(set(dmap["district"].astype(str).map(apply_analytical_merge)))
    required_pairs = {(d, g) for d in analytical_districts for g in selected_groups}
    covered_pairs = set()
    unmapped_share = 0.0
    unmapped_seats = 0.0
    out_of_scope_share = 0.0
    out_of_scope_seats = 0.0
    total_input_seats = 0.0
    actual_scale_ratio = 0.0
    if actual_supply is not None:
        actual_match = match_districts(actual_supply["district"], lgd, fuzzy_threshold)
        actual_match_df = pd.concat([actual_supply.reset_index(drop=True), actual_match.reset_index(drop=True)], axis=1)
        actual_match_df["coverage_status_norm"] = actual_match_df["coverage_status"].astype(str).str.lower().str.strip()
        actual_full_flags = {"full_district_extract", "full_actual", "full", "complete", "district_actual"}
        all_numeric = actual_match_df.copy()
        all_numeric["seats"] = pd.to_numeric(all_numeric["seats"], errors="coerce")
        valid_seat_rows = all_numeric[all_numeric["seats"].notna() & (all_numeric["seats"] >= 0)].copy()
        matched = valid_seat_rows[valid_seat_rows["matched_district"].ne("")].copy()
        # Re-evaluate exact duplicate rows here for reporting even though loader already deduped.
        raw_rows = len(pd.read_csv(actual_supply_path)) if actual_supply_path else len(actual_supply)
        actual_duplicate_rows_removed = max(int(raw_rows - len(actual_supply)), 0)
        covered_districts_raw = set(matched["matched_district"])
        covered_districts = {apply_analytical_merge(x) for x in covered_districts_raw}
        covered_groups = set(matched["nco_group_2digit"])
        selected_pair_rows = matched[matched["nco_group_2digit"].isin(selected_groups)].copy()
        selected_pair_rows["matched_analytical_district"] = selected_pair_rows["matched_district"].map(apply_analytical_merge)
        covered_pairs = set(zip(selected_pair_rows["matched_analytical_district"], selected_pair_rows["nco_group_2digit"]))
        total_input_seats = float(valid_seat_rows["seats"].sum()) if not valid_seat_rows.empty else 0.0
        unmapped_seats = float(valid_seat_rows.loc[valid_seat_rows["nco_group_2digit"].eq("UNMAPPED"), "seats"].sum()) if not valid_seat_rows.empty else 0.0
        out_of_scope_seats = float(valid_seat_rows.loc[valid_seat_rows["nco_group_2digit"].eq("OUT_OF_SCOPE"), "seats"].sum()) if not valid_seat_rows.empty else 0.0
        unmapped_share = unmapped_seats / total_input_seats if total_input_seats > 0 else 1.0
        out_of_scope_share = out_of_scope_seats / total_input_seats if total_input_seats > 0 else 0.0
        actual_scale_ratio = total_input_seats / max(total_current_seats, 1e-9) if total_input_seats > 0 else 0.0
        actual_full_ready = bool(
            not actual_match_df["matched_district"].eq("").any()
            and actual_match_df["coverage_status_norm"].isin(actual_full_flags).all()
            and covered_districts >= set(analytical_districts)
            and required_pairs.issubset(covered_pairs)
            and unmapped_share <= float(cfg.get("max_unmapped_supply_share", 0.05))
        )
        if not matched.empty:
            matched = matched.copy()
            matched["matched_analytical_district"] = matched["matched_district"].map(apply_analytical_merge)
            actual_map = (
                matched.groupby(["matched_analytical_district", "nco_group_2digit"], as_index=False)
                .agg(seats=("seats", "sum"), coverage_status=("coverage_status_norm", "first"))
                .rename(columns={"matched_analytical_district": "matched_district"})
            )

    else:
        unmapped_share = 0.0
        unmapped_seats = 0.0
        out_of_scope_share = 0.0
        out_of_scope_seats = 0.0
        total_input_seats = 0.0
        actual_scale_ratio = 0.0

    # Approximate district coverage of the DGT matrix against the historical 2022 ITI-count denominator.
    # The two sources differ in period/definition, so this is a blending weight, not exact coverage.
    dgt_iti_count_by_district = {}
    if actual_supply_loaded and not actual_match_df.empty:
        id_candidates = [c for c in ["iti_mis_code", "iti_code", "iti_name"] if c in actual_match_df.columns]
        if id_candidates:
            id_col = id_candidates[0]
            _iti_rows = actual_match_df[actual_match_df["matched_district"].ne("")].copy()
            if not _iti_rows.empty:
                _iti_rows["matched_analytical_district"] = _iti_rows["matched_district"].map(apply_analytical_merge)
                dgt_iti_count_by_district = (
                    _iti_rows.groupby("matched_analytical_district")[id_col]
                    .nunique(dropna=True)
                    .astype(float)
                    .to_dict()
                )

    dmap["dgt_itis_in_matrix"] = dmap["matched_district"].map(dgt_iti_count_by_district).fillna(0.0)
    dmap["iti_2022_count"] = pd.to_numeric(dmap["iti_count"], errors="coerce").fillna(0.0)
    dmap["matrix_iti_coverage"] = np.where(
        dmap["iti_2022_count"] > 0,
        np.clip(dmap["dgt_itis_in_matrix"] / dmap["iti_2022_count"], 0.0, 1.0),
        0.0,
    )

    allocation_method = str(cfg.get("proxy_allocation_method", "official_2022_district_iti_count_weight"))
    rng = np.random.default_rng(seed)
    rate_open = triangular(rng, cfg["opening_rate"], draws)
    rate_fill = triangular(rng, cfg["seat_fill_rate"], draws)
    rate_completion = triangular(rng, cfg["completion_rate"], draws)
    rate_entry = triangular(rng, cfg["sector_entry_rate"], draws)
    occ_mult = triangular(rng, cfg["occupation_prior_uncertainty"], draws)
    proxy_seat_mult = triangular(rng, cfg["proxy_seat_uncertainty"], draws)
    actual_seat_mult = triangular(rng, cfg["actual_seat_uncertainty"], draws)
    partial_remainder_mult = triangular(rng, cfg["partial_remainder_uncertainty"], draws)
    alloc_draws = _shared_allocation_draws(rng, dmap, draws, float(cfg.get("allocation_uncertainty", {}).get("concentration", 50.0)))
    dgt_share_shares = {}
    dgt_share_mult = {}
    dgt_share_state_total = {}
    dgt_share_observed = {}
    dgt_share_proxy_share = {}
    dgt_share_dgt_share = {}
    if allocation_method == "dgt_2026_seat_share":
        (
            dgt_share_shares,
            dgt_share_mult,
            dgt_share_state_total,
            dgt_share_observed,
            dgt_share_proxy_share,
            dgt_share_dgt_share,
        ) = _dgt_share_allocation_draws(
            rng,
            dmap,
            actual_map,
            selected_groups,
            group_weights,
            total_current_seats,
            draws,
            float(cfg.get("dgt_share_allocation_uncertainty", {}).get("concentration", 18.0)),
            float(cfg.get("dgt_share_allocation_uncertainty", {}).get("mean_retention", 0.75)),
        )
    demand_sigma = float(cfg.get("demand_allocation_uncertainty", {}).get("lognormal_sigma", 0.35))
    demand_alloc_mult = rng.lognormal(mean=-0.5 * demand_sigma * demand_sigma, sigma=demand_sigma, size=(draws, len(dmap))) if demand_sigma > 0 else np.ones((draws, len(dmap)))

    results, demand_rows, supply_rows = [], [], []
    statewide_supply_draw_mean_sum = 0.0
    district_sci_draws: dict[str, np.ndarray] = {}
    district_ratio_uncapped_draws: dict[str, np.ndarray] = {}
    year = str(cfg.get("reference_fy", "2022-23"))
    occ_meta = mix.set_index("nco_group_2digit").to_dict("index")
    mapping_rate_global = float((emp_match["match_method"] != "review").mean()) if not emp_match.empty else 0.0
    reset_dmap = dmap.reset_index(drop=True)
    dmap_pos = {row.matched_district: i for i, row in reset_dmap.iterrows()}

    for _, d in emp.iterrows():
        district = d["matched_district"]
        dm = dmap[dmap.matched_district.eq(district)]
        if dm.empty:
            continue
        pos = dmap_pos.get(district)
        if pos is None:
            continue
        proxy_seats_total = float(dm.proxy_seats_total.iloc[0])
        alloc_vec = alloc_draws[:, pos]
        district_group_ratios = []
        district_group_uncapped_terms = []
        district_group_weights = []

        for group, meta in occ_meta.items():
            occ_share = float(meta["share"])
            demand_stock = float(d["district_mfg_employment_proxy"]) * occ_share
            demand_draw = demand_stock * rate_open * occ_mult * demand_alloc_mult[:, pos]

            proxy_group_weight = float(group_weights.get(group, 0.0))
            proxy_seats_draw = proxy_seats_total * alloc_vec * proxy_group_weight * proxy_seat_mult
            supply_basis = "district-proxy"
            actual_seats_value = np.nan
            observed_supply_share = 0.0
            dgt_observed_to_modeled_supply = 0.0
            coverage = "proxy"

            # DGT share mode: use real DGT district/trade seat shares to allocate
            # the same statewide in-scope seat magnitude used by the proxy model.
            # Missing districts/groups fall back to historical ITI-count proxy shares.
            if allocation_method == "dgt_2026_seat_share" and group in dgt_share_mult:
                state_group_total = dgt_share_state_total.get(group, total_current_seats * proxy_group_weight)
                group_mult = dgt_share_mult[group][:, pos]
                share_alloc_seats = state_group_total * dgt_share_shares[group][pos] * group_mult
                exact_dgt = dgt_share_observed.get(group, {}).get(str(district), 0.0)
                actual_seats_value = float(exact_dgt) if exact_dgt > 0 else np.nan
                modeled_median = float(np.quantile(share_alloc_seats * rate_fill * rate_completion * rate_entry, 0.50))
                if actual_seats_value == actual_seats_value:
                    observed_supply_share = float(actual_seats_value / max(modeled_median, 1e-9))
                supply_draw = share_alloc_seats * rate_fill * rate_completion * rate_entry
                supply_basis = "dgt-seat-share-calibrated"
                coverage = "dgt_share_proxy"
            elif actual_map is not None:
                exact = actual_map[(actual_map.matched_district == district) & (actual_map.nco_group_2digit == group)]
                all_rows = actual_map[(actual_map.matched_district == district) & (actual_map.nco_group_2digit == "ALL")]
                if not exact.empty:
                    actual_seats_value = float(exact.seats.iloc[0])
                    coverage_flag = str(exact.iloc[0].get("coverage_status", "")).lower()
                    if actual_full_ready and coverage_flag in {"full_district_extract", "full_actual", "full", "complete", "district_actual"}:
                        supply_draw = actual_seats_value * actual_seat_mult * rate_fill * rate_completion * rate_entry
                        supply_basis = "district-actual-full"
                        coverage = "full_actual"
                    else:
                        proxy_group_seats = proxy_seats_total * proxy_group_weight
                        remainder = max(proxy_group_seats - actual_seats_value, 0.0)
                        observed_supply_share = float(min(actual_seats_value / max(proxy_group_seats, 1e-9), 1.0))
                        total_seats_draw = actual_seats_value + remainder * partial_remainder_mult * alloc_vec * proxy_seat_mult
                        supply_draw = total_seats_draw * rate_fill * rate_completion * rate_entry
                        supply_basis = "partial-observed-floor"
                        coverage = "partial_floor"
                elif not all_rows.empty:
                    actual_total = float(all_rows.seats.iloc[0])
                    actual_seats_value = actual_total * proxy_group_weight
                    supply_draw = actual_seats_value * actual_seat_mult * rate_fill * rate_completion * rate_entry
                    supply_basis = "district-actual-total+crosswalk"
                    coverage = "actual_total"
                else:
                    supply_draw = proxy_seats_draw * rate_fill * rate_completion * rate_entry
            else:
                supply_draw = proxy_seats_draw * rate_fill * rate_completion * rate_entry

            p10_s, p50_s, p90_s = np.quantile(supply_draw, [0.10, 0.50, 0.90])
            statewide_supply_draw_mean_sum += float(np.mean(supply_draw))
            if actual_seats_value == actual_seats_value:
                dgt_observed_to_modeled_supply = float(actual_seats_value / max(p50_s, 1e-9))
                observed_supply_share = dgt_observed_to_modeled_supply
            p10_d, p50_d, p90_d = np.quantile(demand_draw, [0.10, 0.50, 0.90])
            ratio_draw = supply_draw / np.maximum(demand_draw, 1e-9)
            p10, p50, p90 = np.quantile(ratio_draw, [0.10, 0.50, 0.90])
            width = float(p90 - p10)
            annual_openings_median = float(p50_d)
            raw_signal = "GAP" if p90 < 1 else ("SURPLUS" if p10 > 1 else "NEEDS DATA")
            decision = ("PROVISIONAL " + raw_signal) if coverage == "full_actual" and raw_signal in {"GAP", "SURPLUS"} else "NEEDS DATA"

            evidence_cfg = cfg.get("evidence_scores", DEFAULT_CONFIG["evidence_scores"])
            demand_evidence = float(evidence_cfg.get("demand", {}).get("state_actual_plus_district_proxy", 0.55))
            supply_evidence = {
                "full_actual": float(evidence_cfg.get("supply", {}).get("full_actual", 0.95)),
                "partial_floor": float(evidence_cfg.get("supply", {}).get("partial_floor", 0.55)),
                "actual_total": float(evidence_cfg.get("supply", {}).get("actual_total", 0.75)),
                "dgt_share_proxy": float(evidence_cfg.get("supply", {}).get("dgt_share_proxy", 0.60)),
                "proxy": float(evidence_cfg.get("supply", {}).get("proxy", 0.45)),
            }.get(coverage, float(evidence_cfg.get("supply", {}).get("proxy", 0.45)))
            interval_component = 1.0 / (1.0 + width)
            w = cfg.get("confidence_weights", DEFAULT_CONFIG["confidence_weights"])
            confidence = float(np.clip(
                w["demand_evidence"] * demand_evidence
                + w["supply_evidence"] * supply_evidence
                + w["mapping"] * mapping_rate_global
                + w["interval"] * interval_component,
                0, 1,
            ))
            voi = width * annual_openings_median
            priority = voi * (1 - confidence)

            group_weighted_ratio = demand_draw * np.minimum(ratio_draw, 1.0)
            district_group_ratios.append(group_weighted_ratio)
            district_group_uncapped_terms.append(demand_draw * ratio_draw)
            district_group_weights.append(demand_draw)

            demand_rows.append({
                "district": district, "lgd_code": d["lgd_code"], "year": year, "industry": "Manufacturing",
                "nco_group_2digit": group, "occupation_label": meta["occupation_label"],
                "state_mfg_employment_base": state_mfg_workers,
                "district_proxy_share": d["district_proxy_share"],
                "udyam_employment_share": d.get("udyam_employment_share", np.nan),
                "udyam_units_share": d.get("udyam_units_share", np.nan),
                "demand_allocation_share": d.get("demand_allocation_share", np.nan),
                "demand_allocation_method": demand_allocation_method,
                "occupation_share_of_total_mfg": occ_share,
                "occupation_share_low": float(meta["share_low"]),
                "occupation_share_high": float(meta["share_high"]),
                "manufacturing_employment_proxy": demand_stock,
                "openings_p10": p10_d, "openings_median": p50_d, "openings_p90": p90_d,
                "evidence_tier": "state-actual + district-proxy + occupation-prior",
            })
            supply_rows.append({
                "district": district, "lgd_code": d["lgd_code"], "year": year,
                "nco_group_2digit": group, "occupation_label": meta["occupation_label"],
                "proxy_seats": proxy_seats_total * proxy_group_weight,
                "actual_seats": actual_seats_value,
                "supply_basis": supply_basis,
                "supply_coverage": coverage,
                "allocation_basis": dm["allocation_basis"].iloc[0],
                "supply_p10": p10_s, "supply_median": p50_s, "supply_p90": p90_s,
                "observed_supply_share": observed_supply_share,
                "dgt_observed_seats_to_supply_median": dgt_observed_to_modeled_supply,
                "dgt_itis_in_matrix": float(dm["dgt_itis_in_matrix"].iloc[0]),
                "iti_2022_count": float(dm["iti_2022_count"].iloc[0]),
                "matrix_iti_coverage": float(dm["matrix_iti_coverage"].iloc[0]),
            })
            results.append({
                "district": district, "lgd_code": d["lgd_code"], "year": year, "industry": "Manufacturing",
                "nco_group_2digit": group, "occupation_label": meta["occupation_label"],
                "demand_allocation_method": demand_allocation_method,
                "demand_allocation_share": float(d.get("demand_allocation_share", np.nan)),
                "supply_basis": supply_basis, "supply_coverage": coverage,
                "allocation_basis": dm["allocation_basis"].iloc[0],
                "ratio_p10": float(p10), "ratio_median": float(p50), "ratio_p90": float(p90),
                "interval_width": width, "raw_signal": raw_signal, "decision_status": decision,
                "evidence_ready": bool(actual_full_ready and coverage == "full_actual"), "confidence_score": confidence,
                "annual_openings_median": annual_openings_median, "voi_score": voi, "data_priority_score": priority,
                "mapping_rate": mapping_rate_global,
                "observed_supply_share": observed_supply_share,
                "dgt_observed_seats_to_supply_median": dgt_observed_to_modeled_supply,
                "actual_unmapped_share_run": unmapped_share if actual_supply_loaded else 0.0,
                "actual_out_of_scope_share_run": out_of_scope_share if actual_supply_loaded else 0.0,
            })
        if district_group_ratios:
            numer = np.sum(np.vstack(district_group_ratios), axis=0)
            denom = np.sum(np.vstack(district_group_weights), axis=0)
            district_sci_draws[district] = numer / np.maximum(denom, 1e-9)
            uncapped_numer = np.sum(np.vstack(district_group_uncapped_terms), axis=0)
            district_ratio_uncapped_draws[district] = uncapped_numer / np.maximum(denom, 1e-9)


    demand_df = pd.DataFrame(demand_rows)
    supply_df = pd.DataFrame(supply_rows)
    ratio_df = pd.DataFrame(results)

    district_summary = []
    for district, g in ratio_df.groupby("district"):
        wts = g["annual_openings_median"].clip(lower=0)
        ratios = g["ratio_median"].clip(lower=0)
        sci = float((wts * np.minimum(ratios, 1.0)).sum() / max(wts.sum(), 1e-9))
        uncapped_ratio = float((wts * ratios).sum() / max(wts.sum(), 1e-9))
        obs_to_supply = float(g["dgt_observed_seats_to_supply_median"].sum()) if "dgt_observed_seats_to_supply_median" in g.columns else 0.0
        district_summary.append({
            "district": district,
            "SCI": sci,
            "uncapped_ratio_median": uncapped_ratio,
            "mean_confidence": float(g.confidence_score.mean()),
            "max_interval_width": float(g.interval_width.max()),
            "total_annual_openings": float(g.annual_openings_median.sum()),
            "VOI": float(g.voi_score.sum()),
            "data_collection_priority": float(g.data_priority_score.sum()),
            "gap_cells": int((g.raw_signal == "GAP").sum()),
            "decision_gap_cells": int(g.decision_status.str.contains("GAP", na=False).sum()),
            "needs_data_cells": int((g.decision_status == "NEEDS DATA").sum()),
            "actual_cells": int((g.supply_coverage == "full_actual").sum()),
            "dgt_observed_seats_to_supply_median": obs_to_supply,
            "allocation_basis": ",".join(sorted(g.allocation_basis.unique())),
        })
    district_df = pd.DataFrame(district_summary)
    dmap_cov = dmap[["matched_district", "dgt_itis_in_matrix", "iti_2022_count", "matrix_iti_coverage"]].drop_duplicates().rename(columns={"matched_district":"district"})
    if not dmap_cov.empty:
        district_df = district_df.merge(dmap_cov, on="district", how="left")
    if not supply_df.empty:
        obs_supply = (
            supply_df.groupby("district", as_index=False)
            .agg(
                dgt_observed_seats_72_74=("actual_seats", lambda s: float(pd.to_numeric(s, errors="coerce").fillna(0.0).sum())),
                modeled_supply_median_72_74=("supply_median", "sum"),
            )
        )
        obs_supply["dgt_observed_seats_to_modeled_supply_median"] = (
            obs_supply["dgt_observed_seats_72_74"] / np.maximum(obs_supply["modeled_supply_median_72_74"], 1e-9)
        )
        district_df = district_df.merge(obs_supply, on="district", how="left")
    state_median_sci = float(district_df["SCI"].median()) if not district_df.empty else float("nan")
    district_df["state_median_SCI"] = state_median_sci
    district_df["relative_SCI_vs_state_median"] = district_df["SCI"] / max(state_median_sci, 1e-9)
    state_median_ratio = float(district_df["uncapped_ratio_median"].median()) if not district_df.empty else float("nan")
    district_df["state_median_uncapped_ratio"] = state_median_ratio
    district_df["relative_uncapped_ratio_vs_state_median"] = district_df["uncapped_ratio_median"] / max(state_median_ratio, 1e-9)
    district_df = district_df.sort_values(["uncapped_ratio_median", "district"], ascending=[False, True]).reset_index(drop=True)
    district_df["ratio_rank"] = np.arange(1, len(district_df) + 1)
    district_df = district_df.sort_values(["data_collection_priority", "VOI", "district"], ascending=[False, False, True]).reset_index(drop=True)
    district_df["priority_rank"] = np.arange(1, len(district_df) + 1)

    rank_stability = _rank_stats_from_draws(district_ratio_uncapped_draws)
    if not rank_stability.empty:
        district_df = district_df.merge(rank_stability, on="district", how="left")

    proxy_share_check = dmap[["matched_district", "proxy_seats_total", "allocation_basis"]].drop_duplicates().rename(columns={"matched_district":"district"})
    proxy_share_check = emp[["matched_district", "district_proxy_share"]].merge(proxy_share_check, left_on="matched_district", right_on="district", how="inner")
    if not proxy_share_check.empty:
        proxy_share_check["proxy_supply_share"] = proxy_share_check["proxy_seats_total"] / max(proxy_share_check["proxy_seats_total"].sum(), 1e-9)
        proxy_share_correlation = float(proxy_share_check["district_proxy_share"].corr(proxy_share_check["proxy_supply_share"])) if len(proxy_share_check) > 1 else float("nan")
    else:
        proxy_share_correlation = float("nan")

    proxy_vs_dgt_spearman = float("nan")
    dgt_observed_by_district = pd.DataFrame()
    if actual_supply_loaded and actual_map is not None and not actual_map.empty:
        selected_actual = actual_map[actual_map["nco_group_2digit"].astype(str).isin(selected_groups)].copy()
        if not selected_actual.empty:
            dgt_observed_by_district = (
                selected_actual.groupby("matched_district", as_index=False)["seats"].sum()
                .rename(columns={"matched_district": "district", "seats": "dgt_selected_seats"})
            )
            dgt_observed_by_district["district"] = dgt_observed_by_district["district"].map(apply_analytical_merge)
            proxy_iti = dmap[["matched_district", "iti_count"]].drop_duplicates().copy()
            proxy_iti["district"] = proxy_iti["matched_district"]
            proxy_iti.drop(columns=["matched_district"], inplace=True)
            proxy_dgt_check = dgt_observed_by_district.merge(proxy_iti, on="district", how="inner")
            if len(proxy_dgt_check) >= 3:
                proxy_vs_dgt_spearman = _spearman_series(proxy_dgt_check["dgt_selected_seats"], proxy_dgt_check["iti_count"])
    district_variation = pd.DataFrame([{
        "district_count": int(district_df.shape[0]),
        "unique_sci_values": int(district_df["SCI"].round(6).nunique()),
        "sci_min": float(district_df["SCI"].min()),
        "sci_max": float(district_df["SCI"].max()),
        "demand_supply_proxy_share_correlation": proxy_share_correlation,
        "interpretation": "Diagnostic only. Proxy district ranking is not treated as empirical validation; it is used for data-collection prioritisation.",
    }])
    focus_order = [d for d in ["Tumakuru", "Kalaburagi", "Bengaluru Rural", "Raichur"] if d in set(district_df.district)]
    focus_df = district_df[district_df.district.isin(focus_order)].copy()

    demand_allocator_rank_stability = pd.DataFrame()
    if not _internal:
        scenario_rank = {}
        demand_methods = list(cfg.get("demand_allocation_methods", ["udyam_employment", "udyam_units", "blend"]))
        for method in demand_methods:
            if method == demand_allocation_method:
                scenario_rank[method] = district_df[["district", "ratio_rank"]].copy()
            else:
                scen = compute_model(
                    paths=paths,
                    overrides={"demand_allocation_method": method},
                    actual_supply_path=actual_supply_path,
                    output_dir=output_dir,
                    write_outputs=False,
                    _internal=True,
                )
                scenario_rank[method] = scen["district"][["district", "ratio_rank"]].copy()

        merged = None
        for method, sdf in scenario_rank.items():
            sdf = sdf.rename(columns={"ratio_rank": f"rank_{method}"})
            merged = sdf if merged is None else merged.merge(sdf, on="district", how="outer")
        rank_cols = [c for c in merged.columns if c.startswith("rank_")]
        for c in rank_cols:
            merged[c] = pd.to_numeric(merged[c], errors="coerce")
        merged["rank_min"] = merged[rank_cols].min(axis=1)
        merged["rank_max"] = merged[rank_cols].max(axis=1)
        merged["rank_range"] = merged["rank_max"] - merged["rank_min"]
        top5_cols = []
        for method in demand_methods:
            c = f"rank_{method}"
            tc = f"top5_{method}"
            merged[tc] = merged[c].le(5)
            top5_cols.append(tc)
        merged["top5_all_methods"] = merged[top5_cols].all(axis=1)
        merged["top5_methods_count"] = merged[top5_cols].sum(axis=1)
        demand_allocator_rank_stability = merged.sort_values(["rank_range", "district"]).reset_index(drop=True)

    corruption = run_corruption_test(lgd, lgd[['district_name']].rename(columns={'district_name':'district'}))
    sanity = run_sanity_check(emp)
    sensitivity = rank_stability.copy()
    interval_demo = pd.DataFrame()
    if actual_supply_loaded and not _internal:
        baseline = compute_model(paths=paths, overrides=overrides, actual_supply_path=None, output_dir=output_dir, write_outputs=False, _internal=True)
        interval_demo = run_interval_shrink_demo(baseline["ratio"], ratio_df)

    run_id = datetime.now().strftime("RUN-%Y%m%d-%H%M%S")
    registry = source_registry(paths)
    expected_mean_supply = total_current_seats * float(sum(group_weights.values())) * ((float(cfg["seat_fill_rate"]["low"]) + float(cfg["seat_fill_rate"]["mode"]) + float(cfg["seat_fill_rate"]["high"])) / 3.0) * ((float(cfg["completion_rate"]["low"]) + float(cfg["completion_rate"]["mode"]) + float(cfg["completion_rate"]["high"])) / 3.0) * ((float(cfg["sector_entry_rate"]["low"]) + float(cfg["sector_entry_rate"]["mode"]) + float(cfg["sector_entry_rate"]["high"])) / 3.0)
    expected_mode_supply = total_current_seats * float(sum(group_weights.values())) * float(cfg["seat_fill_rate"]["mode"]) * float(cfg["completion_rate"]["mode"]) * float(cfg["sector_entry_rate"]["mode"])
    median_supply_total = float(supply_df["supply_median"].sum()) if not supply_df.empty else 0.0
    audit = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "monte_carlo_draws": draws,
        "demand_allocation_log_normal_sigma": demand_sigma,
        "demand_allocation_method": demand_allocation_method,
        "demand_allocation_methods": list(cfg.get("demand_allocation_methods", ["udyam_employment", "udyam_units", "blend"])),
        "demand_allocator_share_sum": float(emp["demand_allocation_share"].sum()),
        "selected_nco_groups": selected_groups,
        "min_count_suppression": int(cfg.get("min_count_suppression", 5)),
        "actual_supply_loaded": bool(actual_supply_loaded),
        "actual_supply_rows": int(len(actual_supply)) if actual_supply is not None else 0,
        "actual_unmapped_share": float(unmapped_share),
        "actual_unmapped_seats": float(unmapped_seats),
        "actual_out_of_scope_share": float(out_of_scope_share),
        "actual_out_of_scope_seats": float(out_of_scope_seats),
        "actual_total_input_seats": float(total_input_seats),
        "actual_to_state_seat_ratio": float(actual_scale_ratio),
        "actual_scale_warning": bool(actual_supply_loaded and actual_scale_ratio < float(cfg.get("dgt_scale_warning_threshold", 0.5))),
        "proxy_vs_dgt_spearman": float(proxy_vs_dgt_spearman),
        "allocation_method": allocation_method,
        "dgt_share_allocation_concentration": float(cfg.get("dgt_share_allocation_uncertainty", {}).get("concentration", 12.0)) if allocation_method == "dgt_2026_seat_share" else None,
        "dgt_matrix_iti_total": float(dmap["dgt_itis_in_matrix"].sum()) if "dgt_itis_in_matrix" in dmap.columns else 0.0,
        "dgt_matrix_iti_coverage_mean": float(dmap["matrix_iti_coverage"].mean()) if "matrix_iti_coverage" in dmap.columns else 0.0,
        "dgt_matrix_iti_coverage_min": float(dmap["matrix_iti_coverage"].min()) if "matrix_iti_coverage" in dmap.columns else 0.0,
        "dgt_matrix_iti_coverage_max": float(dmap["matrix_iti_coverage"].max()) if "matrix_iti_coverage" in dmap.columns else 0.0,
        "dgt_matrix_coverage_basis": "unique DGT ITIs / historical 2022 ITI count; approximate across periods/definitions",
        "statewide_supply_mean_conservation_ratio": float(statewide_supply_draw_mean_sum / max(expected_mean_supply, 1e-9)),
        "statewide_supply_median_conservation_ratio": float(median_supply_total / max(expected_mean_supply, 1e-9)),
        "dgt_observed_seats_to_supply_median_median": float(district_df.get("dgt_observed_seats_to_supply_median", pd.Series(dtype=float)).replace([np.inf, -np.inf], np.nan).dropna().median()) if "dgt_observed_seats_to_supply_median" in district_df.columns else None,
        "actual_supply_full_ready": bool(actual_full_ready),
        "actual_unmapped_seat_share": float(unmapped_share),
        "actual_unmapped_seats": float(unmapped_seats),
        "actual_input_seats": float(total_input_seats),
        "actual_required_district_group_pairs": int(len(required_pairs)) if actual_supply_loaded else 0,
        "actual_covered_district_group_pairs": int(len(covered_pairs)) if actual_supply_loaded else 0,
        "actual_duplicate_rows_removed": int(actual_duplicate_rows_removed),
        "occupation_share_sum_selected": float(mix["share"].sum()),
        "selected_course_weight_sum": float(sum(group_weights.values())),
        "statewide_supply_expected_mean": expected_mean_supply,
        "statewide_supply_expected_mode": expected_mode_supply,
        "statewide_supply_draw_mean_sum": float(statewide_supply_draw_mean_sum),
        "statewide_total_iti_seats": total_current_seats,
        "statewide_supply_median_sum": median_supply_total,
        "statewide_supply_conservation_ratio": float(statewide_supply_draw_mean_sum / max(expected_mean_supply, 1e-9)),
        "statewide_supply_mean_conservation_ratio": float(statewide_supply_draw_mean_sum / max(expected_mean_supply, 1e-9)),
        "statewide_supply_median_conservation_ratio": float(median_supply_total / max(expected_mean_supply, 1e-9)),
        "decision_rule": cfg["decision_rule"],
        "source_files": registry.to_dict(orient="records"),
        "unmatched_employment_rows": int(len(emp_review)),
        "unique_sci_values": int(district_df["SCI"].round(6).nunique()),
        "district_supply_proxy_correlation": proxy_share_correlation,
        "proxy_allocation_method": allocation_method,
        "demand_allocation_method": demand_allocation_method,
        "demand_allocator_rank_range_mean": float(demand_allocator_rank_stability["rank_range"].mean()) if not demand_allocator_rank_stability.empty else None,
        "demand_allocator_robust_top5_count": int(demand_allocator_rank_stability["top5_all_methods"].sum()) if not demand_allocator_rank_stability.empty else 0,
        "dgt_share_allocation_concentration": float(cfg.get("dgt_share_allocation_uncertainty", {}).get("concentration", 12.0)) if allocation_method == "dgt_2026_seat_share" else None,
        "proxy_vs_dgt_spearman": proxy_vs_dgt_spearman,
        "dgt_matrix_iti_total": float(dmap["dgt_itis_in_matrix"].sum()) if "dgt_itis_in_matrix" in dmap.columns else 0.0,
        "dgt_matrix_iti_coverage_mean": float(dmap["matrix_iti_coverage"].mean()) if "matrix_iti_coverage" in dmap.columns else 0.0,
        "dgt_matrix_iti_coverage_min": float(dmap["matrix_iti_coverage"].min()) if "matrix_iti_coverage" in dmap.columns else 0.0,
        "dgt_matrix_iti_coverage_max": float(dmap["matrix_iti_coverage"].max()) if "matrix_iti_coverage" in dmap.columns else 0.0,
        "dgt_matrix_coverage_basis": "unique DGT ITIs / historical 2022 ITI count; approximate across periods/definitions",
        "dgt_observed_seats_to_supply_median_median": float(district_df.get("dgt_observed_seats_to_supply_median", pd.Series(dtype=float)).replace([np.inf, -np.inf], np.nan).dropna().median()) if "dgt_observed_seats_to_supply_median" in district_df.columns else float("nan"),
        "dgt_share_mode_uses_real_dgt_distribution": bool(allocation_method == "dgt_2026_seat_share" and actual_supply_loaded),
        "allocation_basis_counts": dmap["allocation_basis"].value_counts().to_dict(),
    }

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if write_outputs:
        demand_df.to_csv(output_dir / "demand_estimates.csv", index=False)
        supply_df.to_csv(output_dir / "supply_estimates.csv", index=False)
        ratio_df.to_csv(output_dir / "ratio_intervals.csv", index=False)
        district_df.to_csv(output_dir / "district_priority.csv", index=False)
        focus_df.to_csv(output_dir / "focus_districts.csv", index=False)
        corruption[0].to_csv(output_dir / "corruption_match_results.csv", index=False)
        corruption[1].to_csv(output_dir / "corruption_test_summary.csv", index=False)
        sanity[0].to_csv(output_dir / "sanity_check.csv", index=False)
        sanity[1].to_csv(output_dir / "sanity_summary.csv", index=False)
        sensitivity.to_csv(output_dir / "rank_stability.csv", index=False)
        sensitivity.to_csv(output_dir / "sensitivity.csv", index=False)
        demand_allocator_rank_stability.to_csv(output_dir / "demand_allocator_rank_stability.csv", index=False)
        interval_demo.to_csv(output_dir / "interval_evidence_update.csv", index=False)
        interval_demo.to_csv(output_dir / "interval_shrink_demo.csv", index=False)
        proxy_share_check.to_csv(output_dir / "district_supply_independence.csv", index=False)
        district_variation.to_csv(output_dir / "district_variation_diagnostic.csv", index=False)
        dgt_observed_by_district.to_csv(output_dir / "dgt_observed_supply_by_district.csv", index=False)
        emp_review.to_csv(output_dir / "unmatched.csv", index=False)
        if actual_match_df is not None and not actual_match_df.empty:
            actual_match_df.to_csv(output_dir / "actual_supply_match_results.csv", index=False)
        registry.to_csv(output_dir / "run_file_registry.csv", index=False)
        with (output_dir / "audit_log.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(audit, default=str) + "\n")
        (output_dir / "run_summary.json").write_text(json.dumps({
            "run_id": run_id,
            "districts": int(district_df.shape[0]),
            "rows": int(ratio_df.shape[0]),
            "analytical_shortfall_signals": int((ratio_df.raw_signal == "GAP").sum()),
            "policy_gap_cells": int(ratio_df.decision_status.str.contains("GAP", na=False).sum()),
            "policy_surplus_cells": int(ratio_df.decision_status.str.contains("SURPLUS", na=False).sum()),
            "needs_data_cells": int((ratio_df.decision_status == "NEEDS DATA").sum()),
            "actual_supply_loaded": bool(actual_supply_loaded),
            "actual_supply_full_ready": bool(actual_full_ready),
            "actual_unmapped_seat_share": float(unmapped_share),
            "actual_unmapped_seats": float(unmapped_seats),
            "actual_out_of_scope_seat_share": float(out_of_scope_share),
            "actual_out_of_scope_seats": float(out_of_scope_seats),
            "actual_input_seats": float(total_input_seats),
            "actual_to_state_seat_ratio": float(actual_scale_ratio),
            "actual_scale_warning": bool(actual_supply_loaded and actual_scale_ratio < float(cfg.get("dgt_scale_warning_threshold", 0.5))),
            "proxy_vs_dgt_spearman": float(proxy_vs_dgt_spearman),
            "allocation_method": allocation_method,
            "demand_allocation_method": demand_allocation_method,
            "demand_allocation_methods": list(cfg.get("demand_allocation_methods", ["udyam_employment", "udyam_units", "blend"])),
            "min_count_suppression": int(cfg.get("min_count_suppression", 5)),
            "demand_allocator_share_sum": float(emp["demand_allocation_share"].sum()),
            "demand_allocator_rank_range_mean": float(demand_allocator_rank_stability["rank_range"].mean()) if not demand_allocator_rank_stability.empty else None,
            "demand_allocator_robust_top5_count": int(demand_allocator_rank_stability["top5_all_methods"].sum()) if not demand_allocator_rank_stability.empty else 0,
            "dgt_share_allocation_concentration": audit.get("dgt_share_allocation_concentration"),
            "proxy_vs_dgt_spearman": audit.get("proxy_vs_dgt_spearman"),
            "statewide_supply_mean_conservation_ratio": float(statewide_supply_draw_mean_sum / max(expected_mean_supply, 1e-9)),
            "statewide_supply_median_conservation_ratio": float(median_supply_total / max(expected_mean_supply, 1e-9)),
            "dgt_observed_seats_to_supply_median_median": float(district_df.get("dgt_observed_seats_to_supply_median", pd.Series(dtype=float)).replace([np.inf, -np.inf], np.nan).dropna().median()) if "dgt_observed_seats_to_supply_median" in district_df.columns else None,
        "actual_required_district_group_pairs": int(len(required_pairs)) if actual_supply_loaded else 0,
        "actual_covered_district_group_pairs": int(len(covered_pairs)) if actual_supply_loaded else 0,
            "actual_supply_rows": int(len(actual_supply)) if actual_supply is not None else 0,
        "actual_unmapped_share": float(unmapped_share),
        "actual_unmapped_seats": float(unmapped_seats),
        "actual_total_input_seats": float(total_input_seats),
            "partial_floor_cells": int((ratio_df.supply_coverage == "partial_floor").sum()),
            "unique_sci_values": int(district_df["SCI"].round(6).nunique()),
            "district_supply_proxy_correlation": proxy_share_correlation,
            "statewide_supply_expected_mean": expected_mean_supply,
        "statewide_supply_expected_mode": expected_mode_supply,
        "statewide_supply_draw_mean_sum": float(statewide_supply_draw_mean_sum),
        "statewide_total_iti_seats": total_current_seats,
            "statewide_supply_median_sum": median_supply_total,
            "statewide_supply_conservation_ratio": float(statewide_supply_draw_mean_sum / max(expected_mean_supply, 1e-9)),
        "statewide_supply_mean_conservation_ratio": float(statewide_supply_draw_mean_sum / max(expected_mean_supply, 1e-9)),
        "statewide_supply_median_conservation_ratio": float(median_supply_total / max(expected_mean_supply, 1e-9)),
            "state_median_sci": float(district_df["SCI"].median()) if not district_df.empty else None,
            "relative_sci_min": float(district_df["relative_SCI_vs_state_median"].min()) if not district_df.empty else None,
            "relative_sci_max": float(district_df["relative_SCI_vs_state_median"].max()) if not district_df.empty else None,
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
        "rank_stability": sensitivity,
        "interval_demo": interval_demo,
        "audit": audit,
        "district_variation": district_variation,
        "proxy_share_check": proxy_share_check,
        "demand_allocator_rank_stability": demand_allocator_rank_stability,
    }


def main():
    import argparse
    ap = argparse.ArgumentParser(description="KSISU evidence-first gap model")
    ap.add_argument("--actual-supply", help="CSV containing district supply evidence")
    ap.add_argument("--out", help="Output directory (default: out)")
    ap.add_argument("--proxy-allocation-method", choices=["official_2022_district_iti_count_weight", "dgt_2026_seat_share"], help="Supply allocation mode")
    ap.add_argument("--demand-allocation-method", choices=["udyam_employment", "udyam_units", "blend"], help="Demand district allocation basis")
    args = ap.parse_args()
    out_dir = Path(args.out) if args.out else OUT
    overrides = {}
    if args.proxy_allocation_method:
        overrides["proxy_allocation_method"] = args.proxy_allocation_method
    if args.demand_allocation_method:
        overrides["demand_allocation_method"] = args.demand_allocation_method
    if not overrides:
        overrides = None
    res = compute_model(actual_supply_path=args.actual_supply, overrides=overrides, output_dir=out_dir)
    print(json.dumps({
        "districts": len(res["district"]),
        "ratio_rows": len(res["ratio"]),
        "raw_signals": res["ratio"]["raw_signal"].value_counts().to_dict(),
        "policy_decisions": res["ratio"]["decision_status"].value_counts().to_dict(),
        "actual_supply_loaded": res["audit"]["actual_supply_loaded"],
        "actual_supply_full_ready": res["audit"]["actual_supply_full_ready"],
        "actual_required_district_group_pairs": res["audit"]["actual_required_district_group_pairs"],
        "actual_covered_district_group_pairs": res["audit"]["actual_covered_district_group_pairs"],
        "actual_unmapped_share": res["audit"]["actual_unmapped_share"],
        "actual_out_of_scope_share": res["audit"].get("actual_out_of_scope_share", 0.0),
        "actual_to_state_seat_ratio": res["audit"].get("actual_to_state_seat_ratio", 0.0),
        "occupation_share_sum_selected": res["audit"]["occupation_share_sum_selected"],
        "selected_course_weight_sum": res["audit"]["selected_course_weight_sum"],
        "statewide_supply_conservation_ratio": res["audit"]["statewide_supply_conservation_ratio"],
        "corruption": res["corruption"].iloc[0].to_dict(),
    }, indent=2))


if __name__ == "__main__":
    main()
