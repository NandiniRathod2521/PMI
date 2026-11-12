"""Prepare supervised training rows from IFC change reports and observed outcomes.

The schedule engine's rule-based impacts are assumptions, not training labels.
Labels must come from observed project records and are keyed by revision and
GlobalId in a separate CSV file.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Iterable

CHANNELS = ("attribute", "property", "material", "type", "geometry")
LABEL_FIELDS = ("revision_id", "global_id", "observed_extra_work_days")
DATASET_FIELDS = (
    "revision_id",
    "global_id",
    "ifc_type",
    "added",
    "deleted",
    "modified",
    "attribute_changed",
    "property_changed",
    "material_changed",
    "type_changed",
    "geometry_changed",
    "observed_extra_work_days",
)


def load_labels(path: Path) -> dict[tuple[str, str], float]:
    """Load measured additional work duration, keyed by revision and element."""
    labels: dict[tuple[str, str], float] = {}
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None or not set(LABEL_FIELDS).issubset(reader.fieldnames):
            raise ValueError(f"{path} must contain columns: {', '.join(LABEL_FIELDS)}")

        for line_number, row in enumerate(reader, start=2):
            revision_id = (row["revision_id"] or "").strip()
            global_id = (row["global_id"] or "").strip()
            if not revision_id or not global_id:
                raise ValueError(f"{path}:{line_number}: revision_id and global_id are required")
            key = (revision_id, global_id)
            if key in labels:
                raise ValueError(f"{path}:{line_number}: duplicate label for {revision_id}/{global_id}")
            try:
                days = float(row["observed_extra_work_days"])
            except (TypeError, ValueError) as error:
                raise ValueError(f"{path}:{line_number}: observed_extra_work_days must be numeric") from error
            if not math.isfinite(days) or days < 0:
                raise ValueError(f"{path}:{line_number}: observed_extra_work_days must be finite and non-negative")
            labels[key] = days
    return labels


def build_dataset(
    change_files: Iterable[Path], labels: dict[tuple[str, str], float]
) -> tuple[list[dict[str, object]], int]:
    """Join changed IFC elements to measured labels; return rows and unlabeled count.

    The revision ID is each change report's filename without its extension.
    """
    rows: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    unlabeled_count = 0

    for path in change_files:
        revision_id = path.stem
        report = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise ValueError(f"{path} must contain a JSON object")
        changes = report.get("changes")
        if not isinstance(changes, list):
            raise ValueError(f"{path} must contain a 'changes' list")

        for index, change in enumerate(changes, start=1):
            if not isinstance(change, dict):
                raise ValueError(f"{path}: change {index} must be an object")
            status = change.get("status")
            if status == "UNCHANGED":
                continue
            if status not in {"ADDED", "DELETED", "MODIFIED"}:
                raise ValueError(f"{path}: change {index} has unsupported status {status!r}")

            global_id = change.get("global_id")
            if not isinstance(global_id, str) or not global_id.strip():
                raise ValueError(f"{path}: change {index} is missing a valid global_id")
            key = (revision_id, global_id)
            if key in seen:
                raise ValueError(f"{path}: duplicate changed element {global_id!r}")
            seen.add(key)

            change_types = change.get("change_types", [])
            if not isinstance(change_types, list) or any(
                not isinstance(channel, str) or channel not in (*CHANNELS, "added", "deleted")
                for channel in change_types
            ):
                raise ValueError(f"{path}: change {index} has invalid change_types")
            geometry_changed = change.get("geometry_changed", "geometry" in change_types)
            if not isinstance(geometry_changed, bool):
                raise ValueError(f"{path}: change {index} geometry_changed must be a boolean")
            ifc_type = change.get("ifc_type")
            if not isinstance(ifc_type, str) or not ifc_type.strip():
                raise ValueError(f"{path}: change {index} is missing a valid ifc_type")

            if key not in labels:
                unlabeled_count += 1
                continue

            rows.append(
                {
                    "revision_id": revision_id,
                    "global_id": global_id,
                    "ifc_type": ifc_type,
                    "added": int(status == "ADDED"),
                    "deleted": int(status == "DELETED"),
                    "modified": int(status == "MODIFIED"),
                    "attribute_changed": int("attribute" in change_types),
                    "property_changed": int("property" in change_types),
                    "material_changed": int("material" in change_types),
                    "type_changed": int("type" in change_types),
                    "geometry_changed": int(geometry_changed),
                    "observed_extra_work_days": labels[key],
                }
            )

    unmatched_labels = set(labels) - seen
    if unmatched_labels:
        examples = ", ".join(f"{revision}/{gid}" for revision, gid in sorted(unmatched_labels)[:5])
        raise ValueError(f"Labels do not match a changed element in the reports: {examples}")
    return rows, unlabeled_count
    # Preserve the original project identifier
    df["original_project_name"] = df["ProjName"]

    # Create a unique internal identifier
    df["project_id"] = (
    df["ProjName"].astype(str)
    + "_"
    + df["Sl.no"].astype(str)
)   


def write_dataset(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=DATASET_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Join IFC change reports to measured additional-work labels."
    )
    parser.add_argument(
        "--changes-dir",
        type=Path,
        required=True,
        help="directory of changes JSON reports; each filename stem is its revision_id",
    )
    parser.add_argument(
        "--labels",
        type=Path,
        required=True,
        help="CSV with revision_id, global_id, observed_extra_work_days columns",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/training_dataset.csv"),
        help="output CSV path (default: data/training_dataset.csv)",
    )
    args = parser.parse_args()

    change_files = sorted(args.changes_dir.glob("*.json"))
    if not change_files:
        parser.error(f"no JSON change reports found in {args.changes_dir}")

    try:
        labels = load_labels(args.labels)
        rows, unlabeled_count = build_dataset(change_files, labels)
        if not rows:
            raise ValueError("no labeled changed elements found; dataset was not written")
        write_dataset(args.output, rows)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))

    print(f"Wrote {len(rows)} labeled examples to {args.output}")
    if unlabeled_count:
        print(f"Skipped {unlabeled_count} changed elements without observed labels.")


if __name__ == "__main__":
    main()
