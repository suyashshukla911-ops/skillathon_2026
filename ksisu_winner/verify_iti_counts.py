"""Reproducible check of the historical ITI-count weights against Rajya Sabha Q131 Annexure-IV.

Source representation: raw/rajya_sabha_annexure_iv_official_text_extract.md, which is
a machine-extracted/transcribed representation of the referenced official PDF (https://sansad.in/getFile/annex/258/AU131.pdf?source=pqars,
PDF page 6), with labels exactly as printed.

What this script does
1. Parses the as-printed table and writes raw/rajya_sabha_annexure_iv_cts_as_printed.csv.
2. Checks the printed Govt + Private = Total on every row, and the printed column totals.
3. Checks every row of clean/district_iti_counts.csv (government, private, total) against
   the printed row it maps to, using the explicit label map below.
4. Checks clean/ and input_templates/ copies are identical.

It does NOT prove the extract matches the government PDF binary. Independent visual comparison of the official PDF page is still required.

Run:  python verify_iti_counts.py
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXTRACT = ROOT / "raw" / "rajya_sabha_annexure_iv_official_text_extract.md"
AS_PRINTED = ROOT / "raw" / "rajya_sabha_annexure_iv_cts_as_printed.csv"
CLEAN = ROOT / "clean" / "district_iti_counts.csv"
TEMPLATE = ROOT / "input_templates" / "district_iti_counts.csv"

# printed label -> analytical geography used by the model
SOURCE_TO_ANALYTICAL = {
    "Bagalkot": "Bagalkot",
    "Belgaum": "Belagavi",
    "Bellary": "Ballari-Vijayanagara",  # historical Bellary = merged Ballari + Vijayanagara
    "Bengaluru Rural": "Bengaluru Rural",
    "Bengaluru Urban": "Bengaluru Urban",
    "Bidar": "Bidar",
    "Bijapur": "Vijayapura",
    "Chamarajanagar": "Chamarajanagar",
    "Chikballapur": "Chikkaballapur",
    "Chikkamagaluru": "Chikkamagaluru",
    "Chitradurga": "Chitradurga",
    "Dakshin Kannad": "Dakshina Kannada",
    "Davangere": "Davanagere",
    "Dharwad": "Dharwad",
    "Gadag": "Gadag",
    "Gulbarga": "Kalaburagi",
    "Hassan": "Hassan",
    "Haveri": "Haveri",
    "Kodagu": "Kodagu",
    "Kolar": "Kolar",
    "Koppal": "Koppal",
    "Mandya": "Mandya",
    "Mysuru": "Mysuru",
    "Raichur": "Raichur",
    "Ramanagara": "Ramanagara",
    "Shivamogga": "Shivamogga",
    "Tumakuru": "Tumakuru",
    "Udupi": "Udupi",
    "Uttar Kannad": "Uttara Kannada",
    "Yadgir": "Yadgir",
    # Source artifacts: zero rows that are not separate analytical geographies.
    "Uttara Kannada": None,
    "Vijayapura": None,
}
PRINTED_TOTALS = (275, 1227, 1502)


def parse_extract(path: Path = EXTRACT) -> tuple[list[dict], tuple[int, int, int]]:
    rows, totals = [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 5:
            continue
        if re.fullmatch(r"\d+", cells[0]) and all(re.fullmatch(r"\d+", c) for c in cells[2:]):
            rows.append({
                "sl_no": int(cells[0]),
                "source_label": cells[1],
                "govt": int(cells[2]),
                "private": int(cells[3]),
                "total": int(cells[4]),
            })
        elif cells[0] == "" and cells[1].lower() == "total":
            totals = tuple(int(c) for c in cells[2:])
    if totals is None:
        raise ValueError("printed Total row not found in extract")
    return rows, totals


def write_as_printed(rows: list[dict], path: Path = AS_PRINTED) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["sl_no", "source_label", "govt_iti", "private_iti", "total", "analytical_geography"])
        for r in rows:
            w.writerow([r["sl_no"], r["source_label"], r["govt"], r["private"], r["total"],
                        SOURCE_TO_ANALYTICAL.get(r["source_label"]) or ""])


def verify(write: bool = True) -> list[str]:
    """Return a list of problems; empty list means every check passed."""
    problems: list[str] = []
    rows, totals = parse_extract()
    if write:
        write_as_printed(rows)

    if len(rows) != 32:
        problems.append(f"expected 32 printed rows, parsed {len(rows)}")
    for r in rows:
        if r["govt"] + r["private"] != r["total"]:
            problems.append(f"printed row {r['sl_no']} {r['source_label']}: Govt+Private != Total")
        if r["source_label"] not in SOURCE_TO_ANALYTICAL:
            problems.append(f"printed label '{r['source_label']}' has no mapping")
    sums = (sum(r["govt"] for r in rows), sum(r["private"] for r in rows), sum(r["total"] for r in rows))
    if sums != PRINTED_TOTALS or totals != PRINTED_TOTALS:
        problems.append(f"column sums {sums} / printed totals {totals} != expected {PRINTED_TOTALS}")

    by_geo = {SOURCE_TO_ANALYTICAL[r["source_label"]]: r for r in rows if SOURCE_TO_ANALYTICAL.get(r["source_label"])}
    with CLEAN.open(newline="", encoding="utf-8") as fh:
        clean = list(csv.DictReader(fh))
    if {c["district"] for c in clean} != set(by_geo):
        problems.append(f"district set differs: {sorted({c['district'] for c in clean} ^ set(by_geo))}")
    for c in clean:
        src = by_geo.get(c["district"])
        if src is None:
            continue
        got = (int(c["government_iti"]), int(c["private_iti"]), int(c["iti_count"]))
        want = (src["govt"], src["private"], src["total"])
        if got != want:
            problems.append(f"{c['district']}: CSV {got} != printed '{src['source_label']}' {want}")
    if sum(int(c["iti_count"]) for c in clean) != PRINTED_TOTALS[2]:
        problems.append("analytical total != printed state total 1502")
    if CLEAN.read_bytes() != TEMPLATE.read_bytes():
        problems.append("clean/ and input_templates/ district_iti_counts.csv differ")
    return problems


if __name__ == "__main__":
    issues = verify()
    if issues:
        print("ITI COUNT VERIFICATION FAILED")
        for i in issues:
            print(" -", i)
        sys.exit(1)
    print("PASS: 30/30 analytical ITI weights reproduce the bundled Annexure-IV transcription;")
    print("      printed totals 275 + 1,227 = 1,502 reproduced; clean/ and input_templates/ identical.")
