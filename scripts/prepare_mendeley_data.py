"""Clean the MENDLEY project-duration CSV and create a reproducible 80/20 split.

Uses only Python's standard library. Does not impute, scale or infer units.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = ("Sl.no", "ProjName", "AreaSite", "BuiltArea", "TowerNum", "TowerHgt",
           "TowerFlr", "BasementNum", "AreaBase", "UnitNum", "AreaUnit",
           "SellCost", "ConstCost", "ProjDura")
FEATURES = COLUMNS[2:-1]
MISSING = {"", "na", "n/a", "nan", "null", "none"}


def clean_rows(path: Path) -> tuple[list[dict], dict]:
    rows, issues, seen = [], [], set()
    duplicates = 0
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.reader(file)
        header = next(reader, [])
        # The source has eleven column names concatenated into its second cell.
        names = [name for cell in header for name in re.split(r"\s+", cell.strip()) if name]
        if tuple(names) != COLUMNS:
            raise ValueError(f"Unrecognized header: expected {', '.join(COLUMNS)}")
        for line, values in enumerate(reader, 2):
            if not values or not any(value.strip() for value in values):
                continue
            if len(values) != len(COLUMNS):
                raise ValueError(f"Line {line}: expected 14 cells, found {len(values)}")
            values = [value.strip() for value in values]
            row = dict(zip(COLUMNS, values))
            try:
                serial = float(row["Sl.no"])
                if not math.isfinite(serial) or serial <= 0 or not serial.is_integer():
                    raise ValueError()
                row["Sl.no"] = int(serial)
            except ValueError as error:
                raise ValueError(f"Line {line}: invalid Sl.no") from error
            if not row["ProjName"]:
                raise ValueError(f"Line {line}: missing project identifier")
            for column in COLUMNS[2:]:
                value = row[column]
                if value.lower() in MISSING:
                    row[column] = ""
                    continue
                try:
                    number = float(value)
                except ValueError as error:
                    raise ValueError(f"Line {line}: {column} is not numeric: {value!r}") from error
                if not math.isfinite(number):
                    raise ValueError(f"Line {line}: {column} must be finite")
                row[column] = number
            if row["ProjDura"] == "" or row["ProjDura"] <= 0:
                raise ValueError(f"Line {line}: ProjDura must be present and positive")
            key = tuple(row[column] for column in COLUMNS)
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            for column in FEATURES:
                if row[column] != "" and row[column] < 0:
                    issues.append({"line": line, "project": row["ProjName"], "column": column,
                                   "value": row[column], "issue": "negative_feature"})
                    # Preserve the project, but do not expose invalid values as model inputs.
                    row[column] = ""
            rows.append(row)
    for column in ("Sl.no",):
        identifiers = [row[column] for row in rows]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError(f"Conflicting duplicate {column}; resolve project identity before splitting")
    if len(rows) < 2:
        raise ValueError("At least two distinct projects are required")
    repeated = sorted({row["ProjName"] for row in rows
                       if sum(other["ProjName"] == row["ProjName"] for other in rows) > 1})
    return rows, {"exact_duplicates_removed": duplicates, "issues": issues,
                  "repeated_project_identifiers": repeated,
                  "missing_features": {column: sum(row[column] == "" for row in rows) for column in FEATURES}}


def prepare(input_path: Path, output_dir: Path, seed: int = 42) -> dict:
    rows, report = clean_rows(input_path)
    groups = {}
    for index, row in enumerate(rows):
        groups.setdefault(row["ProjName"], []).append(index)
    identifiers = list(groups)
    random.Random(seed).shuffle(identifiers)
    test_count = math.ceil(len(rows) * 0.2)
    # Choose whole identifier groups, reaching the requested test size if possible.
    choices = {0: set()}
    for identifier in identifiers:
        group = set(groups[identifier])
        for size, selected in list(choices.items()):
            if size + len(group) <= test_count:
                choices.setdefault(size + len(group), selected | group)
    if test_count not in choices:
        raise ValueError("Cannot achieve an 80/20 row split without separating a project group")
    test_indices = choices[test_count]
    train = [row for index, row in enumerate(rows) if index not in test_indices]
    test = [row for index, row in enumerate(rows) if index in test_indices]
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, subset in (("clean", rows), ("train", train), ("test", test)):
        with (output_dir / f"mendeley_{name}.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(subset)
    report.update(source=str(input_path.resolve()), source_sha256=hashlib.sha256(input_path.read_bytes()).hexdigest(),
                  rows_clean=len(rows), rows_train=len(train), rows_test=len(test), seed=seed,
                  target="ProjDura", duration_unit="unverified", task="total_project_duration",
                  identifier_columns=list(COLUMNS[:2]), feature_columns=list(FEATURES),
                  preprocessing="No imputation or scaling; fit later on training data only",
                  cost_features="SellCost and ConstCost availability at prediction time must be verified")
    (output_dir / "mendeley_quality_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/raw/Data set_MENDLEY.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/processed")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        report = prepare(args.input, args.output_dir, args.seed)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Clean: {report['rows_clean']} projects; train: {report['rows_train']}; test: {report['rows_test']}")
    print(f"Duplicates removed: {report['exact_duplicates_removed']}; negative features flagged: {len(report['issues'])}")
    print(f"Repeated project identifiers (kept together in split): {report['repeated_project_identifiers']}")
    print(f"Outputs: {args.output_dir}")
    print("Target: total project duration (ProjDura), units unverified; not design-change delay.")


if __name__ == "__main__":
    main()
