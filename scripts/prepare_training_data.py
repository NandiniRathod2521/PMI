"""Export change events; optionally attach synthetic rule labels for demonstrations.

No training or schedule recalculation is performed. Actual outcomes remain blank.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from build_training_dataset import DATASET_FIELDS, build_dataset

ROOT = Path(__file__).resolve().parents[1]
FEATURE_FIELDS = tuple(field for field in DATASET_FIELDS if field != "observed_extra_work_days")
FIELDS = (*FEATURE_FIELDS, "change_category", "activity_id", "baseline_activity_duration_days",
          "mapping_status", "actual_extra_days", "target_extra_days", "label_source")


def prepare_rows(changes: Path, mapping_path: Path, baseline_path: Path,
                 assumptions_path: Path, synthetic: bool = False) -> list[dict]:
    # Reuse the schedule engine's exact mapping and impact rules without running CPM.
    from schedule_engine import base_type, load_assumptions, load_mapping, map_changes_to_activities

    report = json.loads(changes.read_text(encoding="utf-8"))
    if not isinstance(report, dict) or not isinstance(report.get("changes"), list):
        raise ValueError("change report must contain a 'changes' list")
    events = report["changes"]
    # Placeholder values are used only to reuse feature validation, then discarded.
    keys = {(changes.stem, event.get("global_id")): 0.0 for event in events
            if isinstance(event, dict) and isinstance(event.get("global_id"), str)
            and event.get("status") != "UNCHANGED"}
    features, _ = build_dataset([changes], keys)
    mapping = load_mapping(mapping_path)
    baseline = {}
    with baseline_path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if not {"id", "duration_days"}.issubset(reader.fieldnames or []):
            raise ValueError("baseline CSV requires id and duration_days")
        for row in reader:
            duration = float(row["duration_days"])
            if not math.isfinite(duration) or duration < 0 or row["id"] in baseline:
                raise ValueError("baseline durations must be finite, non-negative, with unique activity IDs")
            baseline[row["id"]] = duration
    changed = [event for event in events if event["status"] != "UNCHANGED"]
    impacts = {}
    if synthetic and changed:
        impacts = {row["global_id"]: row["extra_days"] for row in
                   map_changes_to_activities(changed, mapping, load_assumptions(assumptions_path)).to_dict("records")}
    rows = []
    for feature, event in zip(features, changed):
        row = {field: feature[field] for field in FEATURE_FIELDS}
        activity = (mapping.get(event["ifc_type"]) or mapping.get(base_type(event["ifc_type"])) or (None,))[0]
        ready = activity is not None and activity in baseline
        row.update(change_category=";".join(event.get("change_types", [])),
                   activity_id=activity or "", baseline_activity_duration_days=baseline.get(activity, ""),
                   mapping_status="mapped" if ready else "manual_review",
                   actual_extra_days="", target_extra_days=impacts[event["global_id"]] if synthetic and ready else "",
                   label_source="synthetic_rule" if synthetic and ready else "unlabeled")
        rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--changes", type=Path, default=ROOT / "data/changes.json")
    parser.add_argument("--mapping", type=Path, default=ROOT / "data/activity_mapping.csv")
    parser.add_argument("--baseline", type=Path, default=ROOT / "data/baseline_schedule.csv")
    parser.add_argument("--assumptions", type=Path, default=ROOT / "data/assumptions.json")
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or ROOT / "data/training" / (
        "synthetic_rule_labels.csv" if args.synthetic else "change_events_unlabeled.csv")
    try:
        rows = prepare_rows(args.changes, args.mapping, args.baseline, args.assumptions, args.synthetic)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    print(f"Wrote {len(rows)} change events to {output}")
    if args.synthetic:
        print("Synthetic rule labels are for pipeline demonstrations, not real-world accuracy evaluation.")


if __name__ == "__main__":
    main()
