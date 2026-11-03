"""
PMI - STEP 4: CONTROLLED VALIDATION (Plan step 7)
=================================================

Runs the three controlled scenarios (A wall, B door, C window), the combined case,
and one synthetic float test, then compares the ENGINE result with a MANUAL
hand calculation written out below.  Nothing is hard-coded as "passed":
the Validation column is computed by comparing the two numbers.

Hand calculation (single finish-to-start network, working days)
----------------------------------------------------------------
Baseline critical path: A1 10 + A2 20 + A3 12 + A4 8 + A6 15 + A7 5 = 70
(A5 MEP 10 days runs parallel to A3+A4 = 20 days -> 10 days of float)

A  wall   +4 on A3 (critical)          -> 70 + 4       = 74
B  door   +2 on A4 (critical)          -> 70 + 2       = 72
C  window +3 on A4 (critical)          -> 70 + 3       = 73
ALL       +4 on A3, +5 on A4           -> 70 + 9       = 79
D  float  +5 on A5 (float 10, synthetic test) -> 70    (absorbed by float)

Output: data/validation_results.csv  (schedule) + data/detection_validation.csv (detection)
Run:    python scripts/validate.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import schedule_engine as se  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "validation_results.csv"
OUT_DET = ROOT / "data" / "detection_validation.csv"
TRUTH = ROOT / "data" / "revision_log.csv"

WALL = "2O2Fr$t4X7Zf8NOew3FKau"
DOOR = "1hOSvn6df7F8_7GcBWlRGQ"
WINDOW = "1hOSvn6df7F8_7GcBWlR72"

MANUAL = {"A": 74, "B": 72, "C": 73, "ALL": 79, "D": 70}


def main():
    changes = se.load_changes()
    if not changes:
        sys.exit("data/changes.json not found or empty - run scripts/detect_changes.py first")
    detected = {c["global_id"]: c for c in changes}

    baseline = se.load_baseline()
    base_days = se.project_duration(se.cpm(se.build_network(baseline)))
    mapping, A = se.load_mapping(), se.load_assumptions()

    rows = []
    cases = [("A", "Wall modification", [WALL]),
             ("B", "Door modification", [DOOR]),
             ("C", "Window modification", [WINDOW]),
             ("ALL", "All three modifications", [WALL, DOOR, WINDOW])]
    for key, label, ids in cases:
        found = [detected[i] for i in ids if i in detected]
        imp = se.map_changes_to_activities(found, mapping, A)
        days = se.project_duration(se.cpm(se.build_network(baseline, imp)))
        rows.append({
            "Scenario": key,
            "IFC Change": label + ("" if len(found) == len(ids) else "  (NOT DETECTED)"),
            "Detected channels": "; ".join(sorted({t for c in found for t in c["change_types"]})) or "-",
            "Affected Task": ", ".join(sorted(imp["activity_id"].dropna().unique())) if not imp.empty else "-",
            "Assumed extra days": int(imp["extra_days"].sum()) if not imp.empty else 0,
            "Baseline Duration": base_days,
            "Revised Duration": days,
            "Project Delay": days - base_days,
            "Manual calculation": MANUAL[key],
            "Validation": "PASS" if days == MANUAL[key] and len(found) == len(ids) else "FAIL",
        })

    # D - synthetic test of float handling (no IFC element - checks the CPM logic only)
    net = se.build_network(baseline)
    net.added_days["A5"] = 5
    d = se.project_duration(se.cpm(net))
    rows.append({
        "Scenario": "D", "IFC Change": "Synthetic: +5 days on MEP rough-in (non-critical)",
        "Detected channels": "n/a", "Affected Task": "A5", "Assumed extra days": 5,
        "Baseline Duration": base_days, "Revised Duration": d, "Project Delay": d - base_days,
        "Manual calculation": MANUAL["D"], "Validation": "PASS" if d == MANUAL["D"] else "FAIL",
    })

    df = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    pd.set_option("display.width", 220)
    print("\nPMI - SCHEDULE VALIDATION (engine vs hand calculation)")
    print(df.to_string(index=False))
    print(f"\nSaved {OUT}")

    # ---- Detection validation: detected channels vs the ground truth written by create_v2.py
    if TRUTH.is_file():
        truth = pd.read_csv(TRUTH)
        det_rows = []
        for t in truth.itertuples():
            c = detected.get(t.global_id)
            expected = set(str(t.expected_channels).split(";"))
            found = set(c["change_types"]) if c else set()
            det_rows.append({
                "Element": t.new_name, "IFC type": t.ifc_type, "Expected channels": ", ".join(sorted(expected)),
                "Detected channels": ", ".join(sorted(found)) or "NOT DETECTED",
                "Validation": "PASS" if found == expected else "FAIL",
            })
        unexpected = [c for g, c in detected.items() if g not in set(truth.global_id)]
        det_rows.append({"Element": "All other elements", "IFC type": "-", "Expected channels": "unchanged",
                         "Detected channels": f"{len(unexpected)} unexpected changes",
                         "Validation": "PASS" if not unexpected else "FAIL"})
        det = pd.DataFrame(det_rows)
        det.to_csv(OUT_DET, index=False)
        print("\nPMI - DETECTION VALIDATION (detected vs ground truth in data/revision_log.csv)")
        print(det.to_string(index=False))
        print(f"\nSaved {OUT_DET}")


if __name__ == "__main__":
    main()
