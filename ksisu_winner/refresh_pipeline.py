from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
DEFAULT_REGISTRY = RAW / "file_registry.csv"
DEFAULT_BASELINE = RAW / "file_quality_baseline.json"
DEFAULT_REPORT = ROOT / "out" / "data_quality_report.csv"
DEFAULT_REVIEW = ROOT / "out" / "review_queue.csv"
STATEWIDE_SEATS_FILE = "raw/ncvtmis_karnataka_state_2022.csv"
STATEWIDE_SEAT_THRESHOLD = 0.20


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def make_baseline(registry_path: Path = DEFAULT_REGISTRY, baseline_path: Path = DEFAULT_BASELINE) -> None:
    reg = pd.read_csv(registry_path)
    rows = {}
    for _, r in reg.iterrows():
        rel = str(r["path"])
        if rel == "raw/file_registry.csv":
            continue
        p = ROOT / rel
        if not p.exists():
            continue
        entry = {"row_count": None, "columns": [], "statewide_seats": None}
        if p.suffix.lower() == ".csv":
            df = pd.read_csv(p)
            entry["row_count"] = int(len(df))
            entry["columns"] = [str(c) for c in df.columns]
            if rel == STATEWIDE_SEATS_FILE and "seats_available_2022" in df.columns:
                entry["statewide_seats"] = float(pd.to_numeric(df["seats_available_2022"], errors="coerce").dropna().iloc[0])
        rows[rel] = entry
    baseline_path.write_text(json.dumps({"created_utc": datetime.now(timezone.utc).isoformat(), "files": rows}, indent=2), encoding="utf-8")


def refresh(registry_path: Path = DEFAULT_REGISTRY, baseline_path: Path = DEFAULT_BASELINE,
            report_path: Path = DEFAULT_REPORT, review_path: Path = DEFAULT_REVIEW,
            threshold: float = STATEWIDE_SEAT_THRESHOLD) -> tuple[pd.DataFrame, pd.DataFrame]:
    reg = pd.read_csv(registry_path)
    baseline = json.loads(baseline_path.read_text(encoding="utf-8")) if baseline_path.exists() else {"files": {}}
    rows = []
    review = []
    for _, r in reg.iterrows():
        rel = str(r["path"])
        if rel == "raw/file_registry.csv":
            continue
        p = ROOT / rel
        expected_hash = str(r["sha256"]).strip().lower()
        base = baseline.get("files", {}).get(rel, {})
        if not p.exists():
            rec = {"path": rel, "hash_status": "MISSING", "schema_status": "NOT CHECKED", "row_count_status": "NOT CHECKED", "statewide_seats_status": "NOT APPLICABLE", "anomaly": True, "action": "REVIEW", "message": "Registered file is missing."}
            rows.append(rec); review.append(rec); continue

        current_hash = sha256(p)
        if current_hash == expected_hash:
            rec = {"path": rel, "hash_status": "UNCHANGED", "schema_status": "SKIPPED", "row_count_status": "SKIPPED", "statewide_seats_status": "UNCHANGED" if rel == STATEWIDE_SEATS_FILE else "NOT APPLICABLE", "anomaly": False, "action": "SKIP", "message": "Hash matches file_registry.csv; no refresh validation needed."}
            rows.append(rec)
            continue

        schema_status = "NOT APPLICABLE"
        row_status = "NOT APPLICABLE"
        message = "Hash changed; file requires validation and human review."
        anomaly = False
        current_rows = None
        try:
            if p.suffix.lower() == ".csv":
                df = pd.read_csv(p)
                current_rows = int(len(df))
                expected_rows = base.get("row_count")
                expected_cols = list(base.get("columns", []))
                actual_cols = [str(c) for c in df.columns]
                schema_status = "PASS" if actual_cols == expected_cols else "FAIL"
                row_status = "PASS" if expected_rows is None or current_rows == int(expected_rows) else "FAIL"
                if schema_status == "FAIL" or row_status == "FAIL":
                    anomaly = True
                    message += " Schema or row-count mismatch."
            else:
                schema_status = "NOT APPLICABLE"
                row_status = "NOT APPLICABLE"
        except Exception as exc:
            schema_status = "ERROR"
            row_status = "ERROR"
            anomaly = True
            message += f" Could not validate file: {exc}"

        statewide_status = "NOT APPLICABLE"
        statewide_current = None
        statewide_baseline = None
        if base.get("statewide_seats") is not None and p.suffix.lower() == ".csv":
            try:
                df = pd.read_csv(p)
                if "seats_available_2022" not in df.columns:
                    statewide_status = "FAIL"
                    anomaly = True
                    message += " Missing statewide seat column."
                else:
                    statewide_current = float(pd.to_numeric(df["seats_available_2022"], errors="coerce").dropna().iloc[0])
                    statewide_baseline = float(base.get("statewide_seats")) if base.get("statewide_seats") is not None else None
                    if statewide_baseline and statewide_baseline > 0:
                        move = abs(statewide_current - statewide_baseline) / statewide_baseline
                        if move > threshold:
                            statewide_status = "ANOMALY > THRESHOLD"
                            anomaly = True
                            message += f" Statewide seats moved {move:.1%}, above {threshold:.0%} threshold."
                        else:
                            statewide_status = "PASS < THRESHOLD"
                    else:
                        statewide_status = "NO BASELINE"
                        anomaly = True
                        message += " No statewide seat baseline available."
            except Exception as exc:
                statewide_status = "ERROR"
                anomaly = True
                message += f" Could not compute statewide seat anomaly: {exc}"

        rec = {
            "path": rel,
            "hash_status": "CHANGED",
            "schema_status": schema_status,
            "row_count_status": row_status,
            "current_row_count": current_rows,
            "statewide_seats_current": statewide_current,
            "statewide_seats_baseline": statewide_baseline,
            "statewide_seats_status": statewide_status,
            "anomaly": bool(anomaly),
            "action": "REVIEW",
            "message": message,
        }
        rows.append(rec); review.append(rec)

    report = pd.DataFrame(rows)
    review_columns = [
        "path", "hash_status", "schema_status", "row_count_status",
        "statewide_seats_status", "anomaly", "action", "message",
    ]
    review_df = pd.DataFrame(review, columns=review_columns)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(report_path, index=False)
    review_df.to_csv(review_path, index=False)
    return report, review_df


def main() -> None:
    ap = argparse.ArgumentParser(description="Check registered source files for scheduled refresh readiness.")
    ap.add_argument("--make-baseline", action="store_true", help="Create/reset the file-quality baseline before checking")
    ap.add_argument("--seat-threshold", type=float, default=STATEWIDE_SEAT_THRESHOLD, help="Statewide seat anomaly threshold")
    args = ap.parse_args()
    if args.make_baseline:
        make_baseline()
        print(f"Baseline created: {DEFAULT_BASELINE.relative_to(ROOT).as_posix()}")
        return
    if not DEFAULT_BASELINE.exists():
        print("REFRESH STOPPED: missing raw/file_quality_baseline.json; run python refresh_pipeline.py --make-baseline once after an approved data snapshot.")
        raise SystemExit(2)
    report, review = refresh(threshold=args.seat_threshold)
    unchanged = int((report["hash_status"] == "UNCHANGED").sum()) if not report.empty else 0
    changed = int((report["hash_status"] == "CHANGED").sum()) if not report.empty else 0
    print(f"DATA QUALITY REPORT: {len(report)} registered files checked; {unchanged} unchanged/skipped; {changed} changed/review.")
    print(f"Report: {DEFAULT_REPORT.relative_to(ROOT).as_posix()}")
    print(f"Review queue: {DEFAULT_REVIEW.relative_to(ROOT).as_posix()}")
    if not review.empty:
        print("REFRESH STOPPED: one or more inputs need human review before publication.")
        raise SystemExit(2)
    print("REFRESH PASS: no inputs require human review.")


if __name__ == "__main__":
    main()
