from pathlib import Path
import hashlib
import json
import pandas as pd

from refresh_pipeline import refresh


def _sha(path: Path) -> str:
    h=hashlib.sha256(); h.update(path.read_bytes()); return h.hexdigest()


def test_refresh_skips_matching_hash_and_flags_statewide_seat_anomaly(tmp_path):
    rel = Path("tests") / f"_refresh_fixture_{tmp_path.name}.csv"
    target = Path(__file__).resolve().parents[1] / rel
    try:
        pd.DataFrame([{"state":"Karnataka","seats_available_2022":100}]).to_csv(target, index=False)
        registry = tmp_path / "file_registry.csv"
        pd.DataFrame([{
            "path": rel.as_posix(),
            "sha256": _sha(target),
        }]).to_csv(registry, index=False)
        baseline = tmp_path / "baseline.json"
        baseline.write_text(json.dumps({"files": {rel.as_posix(): {
            "row_count": 1,
            "columns": ["state","seats_available_2022"],
            "statewide_seats": 100,
        }}}))
        report, review = refresh(registry, baseline, tmp_path/"report.csv", tmp_path/"review.csv")
        assert report.iloc[0]["hash_status"] == "UNCHANGED"
        assert review.empty

        pd.DataFrame([{"state":"Karnataka","seats_available_2022":125}]).to_csv(target, index=False)
        report, review = refresh(registry, baseline, tmp_path/"report2.csv", tmp_path/"review2.csv")
        row = report.iloc[0]
        assert row["hash_status"] == "CHANGED"
        assert row["schema_status"] == "PASS"
        assert row["row_count_status"] == "PASS"
        assert row["statewide_seats_status"] == "ANOMALY > THRESHOLD"
        assert bool(row["anomaly"]) is True
        assert len(review) == 1
    finally:
        target.unlink(missing_ok=True)
