from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from run_gap import compute_model

print("KSISU SELF TEST")
print("=" * 50)

result = compute_model()
ratio = result["ratio"]
district = result["district"]

assert len(district) == 31, f"Expected 31 districts, got {len(district)}"
assert len(ratio) == 93, f"Expected 93 district×occupation rows, got {len(ratio)}"
assert {"year", "supply_basis", "decision_status", "confidence_score", "ratio_p10", "ratio_p90"}.issubset(ratio.columns)

print(f"PASS: {len(district)} districts")
print(f"PASS: {len(ratio)} district×occupation rows")
print(f"PASS: year-aware results present")
print(f"PASS: shared-draw Monte Carlo intervals present")
print(f"PASS: policy decision gate present")
print("PASS: pipeline completed without exception")
