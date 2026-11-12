"""Prepare auditable Ghent building-duration candidates, without training or splitting.

Numeric duration pairs are candidates, not automatically verified day-delay labels.
All source workbooks are read-only. Missing observations are never imputed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/raw/ghent/construction_excel/DSLIB_Analysis_Sheet.xlsx"
OUT = ROOT / "data/processed/stage2"
SECTORS = {"construction (residential building)", "construction (commercial building)",
           "construction (institutional building)"}
ID_PATTERN = re.compile(r"C\d{4}-\d{2}\Z")
MISSING = {"", "n/a", "na", "n.a.", "-", "none", "null", "nan"}
SOURCE_FIELDS = {
    "project_id": "Code", "project_name": "Project name", "sector": "Sector",
    "submitted_by": "Submitted by", "project_authenticity": "Project",
    "tracking_authenticity": "Tracking", "planned_duration_source": "PD (days)",
    "real_duration_source": "Duration", "early_late_source": "Early/late",
    "activity_count": "# activities", "baseline_cost_eur": "BAC",
    "renewable_resources": "Renewable", "consumable_resources": "Consumable",
    "network_sp": "SP", "network_ad": "AD", "network_la": "LA",
    "network_tf": "TF", "network_ri": "RI",
}
# Only baseline-available quantities are exported as potential model inputs.
NUMERIC_FEATURES = ("activity_count", "baseline_cost_eur", "renewable_resources",
                    "consumable_resources", "network_sp", "network_ad", "network_la", "network_tf", "network_ri")
FEATURE_COLUMNS = ("project_id", "planned_duration_days", *NUMERIC_FEATURES)
VERIFICATION_FIELDS = (
    "project_id", "planned_unit", "real_unit", "planned_day_basis", "real_day_basis",
    "planned_calendar", "real_calendar", "calendar_comparable", "original_baseline_verified",
    "unit_evidence", "calendar_evidence", "baseline_evidence", "verified_by",
    "source_issue_reviewed", "source_issue_evidence",
    "independence_verified", "independence_evidence",
)


def text(value) -> str:
    return "" if value is None else str(value).strip()


def number(value, *, positive=False) -> tuple[float | None, str]:
    if value is None or text(value).casefold() in MISSING:
        return None, "missing"
    if isinstance(value, bool):
        return None, "not_numeric"
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None, "not_numeric"
    if not math.isfinite(parsed):
        return None, "non_finite"
    if positive and parsed <= 0:
        return None, "not_positive"
    return parsed, "valid"


def normalized_name(value) -> str:
    name = unicodedata.normalize("NFKD", text(value)).encode("ascii", "ignore").decode().lower()
    name = re.sub(r"\s*\(\d+\)\s*$", "", name)
    name = re.sub(r"[^a-z0-9]+", " ", name).strip()
    # Conservative flags for similarly named phases; these are review groups, not proven entities.
    for prefix in ("residential house", "apartment building"):
        if name.startswith(prefix):
            return prefix
    return name


def yes(value) -> bool:
    raw = text(value).lower()
    if raw in ("true", "1", "yes"):
        return True
    if raw in ("", "false", "0", "no", "unverified"):
        return False
    raise ValueError(f"Invalid verification boolean {value!r}")


def overview_definitions(cells: list[dict]) -> dict:
    # Verify the definitions actually present in this workbook, not just expected column names.
    by_row = defaultdict(dict)
    for cell in cells:
        by_row[cell["row"]][cell["column"]] = text(cell["value"])
    entries = {}
    for row in by_row.values():
        label, definition = row.get(2, ""), row.get(3, "")
        if label:
            entries[label.casefold()] = definition
    planned = entries.get("pd (days)", "")
    actual = entries.get("real duration", "")
    return dict(planned_definition=planned, real_definition=actual,
                planned_real_interpretation_verified=("planned duration" in planned.lower()
                    and "real total project duration" in actual.lower()
                    and "finish" in actual.lower()),
                authenticity_project_definition=entries.get("project", ""),
                authenticity_tracking_definition=next((v for k, v in entries.items() if k.startswith("tracking")), ""),
                authenticity_code_legend="Overview refers to colour coding and the 2015 paper; it does not define G/O/Y individually",
                planned_unit="days (explicit source header)",
                real_unit="not explicitly specified in Overview Real duration entry",
                calendars="working/calendar day basis, hours/day and calendar equivalence are not established by Overview")


def sheet_cells(sheet) -> list[dict]:
    return [dict(cell=cell.coordinate, row=cell.row, column=cell.column, value=cell.value)
            for row in sheet.iter_rows() for cell in row if cell.value is not None]


def read_source(path: Path) -> tuple[list[dict], dict]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    raw_book = load_workbook(path, read_only=True, data_only=False)
    try:
        for name in ("DSLIB", "Overview", "Known Problems"):
            if name not in workbook.sheetnames:
                raise ValueError(f"Missing worksheet {name}")
        sheet = workbook["DSLIB"]
        headers = list(sheet.iter_rows(min_row=3, max_row=3, values_only=True))[0]
        indexes = {}
        for field, header in SOURCE_FIELDS.items():
            matches = [index for index, value in enumerate(headers) if value == header]
            if len(matches) != 1:
                raise ValueError(f"Expected one {header!r} column in header row index 2")
            indexes[field] = matches[0]
        real_index = indexes["real_duration_source"]
        parent_headers = next(sheet.iter_rows(min_row=2, max_row=2, values_only=True))
        if parent_headers[real_index] != "Real":
            raise ValueError("Duration column is not under the Real parent heading")
        records = []
        raw_rows = raw_book["DSLIB"].iter_rows(min_row=4, values_only=True)
        for row_number, (row, raw) in enumerate(zip(sheet.iter_rows(min_row=4, values_only=True), raw_rows), 4):
            if not any(value is not None for value in raw):
                continue
            record = {field: row[index] for field, index in indexes.items()}
            record.update(source_excel_row=row_number,
                          planned_duration_original=raw[indexes["planned_duration_source"]],
                          real_duration_original=raw[real_index])
            records.append(record)
        docs = {name: sheet_cells(workbook[name]) for name in ("Overview", "Known Problems")}
        if "Updates" in workbook.sheetnames:
            docs["Updates"] = sheet_cells(workbook["Updates"])
        docs["definitions"] = overview_definitions(docs["Overview"])
        docs["headers"] = {field: dict(index=index, name=headers[index]) for field, index in indexes.items()}
        return records, docs
    finally:
        workbook.close()
        raw_book.close()


def project_notes(cells: list[dict]) -> dict[str, list[str]]:
    rows = defaultdict(list)
    for cell in cells:
        rows[cell["row"]].append(text(cell["value"]))
    result = defaultdict(list)
    for values in rows.values():
        match = re.fullmatch(r"C?(\d{4})-(\d{1,2})", values[0])
        if match:
            code = f"C{match[1]}-{int(match[2]):02d}"
            result[code].append(" | ".join(values[1:]))
    return dict(result)


def load_verification(path: Path | None) -> dict:
    if path is None:
        return {}
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if not set(VERIFICATION_FIELDS).issubset(reader.fieldnames or []):
            raise ValueError("Verification CSV is missing required columns; use the generated template")
        rows = {}
        for row in reader:
            code = text(row["project_id"])
            if not ID_PATTERN.fullmatch(code) or code in rows:
                raise ValueError(f"Invalid or duplicate verification project ID {code!r}")
            for key in ("calendar_comparable", "original_baseline_verified", "independence_verified", "source_issue_reviewed"):
                yes(row[key])
            rows[code] = row
    return rows


def target_blockers(row: dict, verification: dict, definitions: dict) -> list[str]:
    blockers = []
    if not definitions.get("planned_real_interpretation_verified"):
        blockers.append("planned_real_definitions_unverified")
    for field in ("planned_duration", "real_duration"):
        if row[field + "_status"] != "valid":
            blockers.append(field + "_" + row[field + "_status"])
    if row["duplicate_id"]:
        blockers.append("duplicate_project_id")
    resolved_issue = yes(verification.get("source_issue_reviewed")) and text(verification.get("source_issue_evidence"))
    if row["known_problem_notes"] and not resolved_issue:
        blockers.append("known_problem_requires_review")
    if row["early_late_check"] == "mismatch" and not resolved_issue:
        blockers.append("duration_ratio_inconsistent_with_source")
    if not (verification.get("planned_unit") == verification.get("real_unit") == "days"
            and text(verification.get("unit_evidence"))):
        blockers.append("duration_units_unverified")
    if not (verification.get("planned_day_basis") == verification.get("real_day_basis")
            and verification.get("planned_day_basis") in ("working", "calendar")
            and text(verification.get("planned_calendar")) and text(verification.get("real_calendar"))
            and yes(verification.get("calendar_comparable")) and text(verification.get("calendar_evidence"))):
        blockers.append("calendar_comparability_unverified")
    if not (yes(verification.get("original_baseline_verified")) and text(verification.get("baseline_evidence"))):
        blockers.append("original_baseline_unverified")
    if not text(verification.get("verified_by")):
        blockers.append("verification_reviewer_missing")
    return blockers


def process_records(records: list[dict], docs: dict, verification: dict | None = None) -> tuple[list[dict], list[dict], list[dict]]:
    verification = verification or {}
    buildings, excluded = [], []
    known = project_notes(docs.get("Known Problems", []))
    updates = project_notes(docs.get("Updates", []))
    id_counts = Counter(text(record.get("project_id")) for record in records
                        if ID_PATTERN.fullmatch(text(record.get("project_id"))))
    for record in records:
        row = dict(record)
        row["project_id"] = text(row.get("project_id"))
        if not ID_PATTERN.fullmatch(row["project_id"]):
            row["exclusion_reason"] = "missing_or_invalid_project_id_summary_or_nonproject"
            excluded.append(row)
            continue
        if text(row.get("sector")).casefold() not in SECTORS:
            row["exclusion_reason"] = "nonbuilding_sector"
            excluded.append(row)
            continue
        for field in ("project_authenticity", "tracking_authenticity"):
            row[field + "_raw"] = row.get(field)
            value = text(row.get(field)).upper()
            row[field] = "" if value.casefold() in MISSING else value
        for prefix in ("planned_duration", "real_duration"):
            value, status = number(row.get(prefix + "_source"), positive=True)
            row[prefix + "_days"] = value  # source-scale candidates; day equivalence not asserted
            row[prefix + "_status"] = status
        for feature in NUMERIC_FEATURES:
            value, status = number(row.get(feature))
            if value is not None and value < 0:
                value, status = None, "negative"
            row[feature] = value
            row[feature + "_status"] = status
        row["duplicate_id"] = id_counts[row["project_id"]] > 1
        row["known_problem_notes"] = "; ".join(known.get(row["project_id"], []))
        row["update_notes"] = "; ".join(updates.get(row["project_id"], []))
        row["early_late_check"] = "unavailable"
        row["audit_computed_duration_ratio"] = None
        ratio, _ = number(row.get("early_late_source"))
        if row["planned_duration_status"] == row["real_duration_status"] == "valid":
            computed_ratio = row["real_duration_days"] / row["planned_duration_days"] - 1
            # This is an audit ratio, never a baseline prediction input or a released day target.
            row["audit_computed_duration_ratio"] = computed_ratio
            if ratio is not None:
                row["early_late_check"] = "consistent_within_rounding" if abs(computed_ratio - ratio) <= .0051 else "mismatch"
        buildings.append(row)
    building_ids = {row["project_id"] for row in buildings}
    if set(verification) - building_ids:
        raise ValueError(f"Verification contains nonbuilding or absent projects: {sorted(set(verification) - building_ids)}")
    families = defaultdict(list)
    for row in buildings:
        family = normalized_name(row.get("project_name"))
        # An absent name supplies no relationship evidence.
        families[family or row["project_id"]].append(row)
    related = []
    for family, members in families.items():
        ids = sorted({row["project_id"] for row in members})
        potential = len(ids) > 1
        for row in members:
            row["potential_related_projects"] = potential
            row["review_group_id"] = "name:" + family if potential else row["project_id"]
        if potential:
            related.append(dict(review_group_id="name:" + family, project_ids=";".join(ids),
                                project_names=";".join(text(row.get("project_name")) for row in members),
                                evidence="Name/phase similarity only; not confirmed shared parent or independence"))
    for row in buildings:
        attestation = verification.get(row["project_id"], {})
        blockers = target_blockers(row, attestation, docs.get("definitions", {}))
        row["target_blockers"] = ";".join(blockers)
        row["label_status"] = "verified_duration_deviation" if not blockers else "unverified"
        row["duration_deviation_days"] = None if blockers else row["real_duration_days"] - row["planned_duration_days"]
        row["verified_day_basis"] = attestation.get("planned_day_basis", "") if not blockers else ""
        row["authenticity_gg"] = row["project_authenticity"] == row["tracking_authenticity"] == "G"
        independence = (yes(attestation.get("independence_verified")) and text(attestation.get("independence_evidence"))
                        and text(attestation.get("verified_by")))
        row["independently_usable"] = not blockers and row["authenticity_gg"] and bool(independence)
    return buildings, excluded, related


def write_csv(path: Path, rows: list[dict], fields=None) -> None:
    fields = list(fields or dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def combos(rows: list[dict]) -> dict:
    return dict(sorted(Counter(f"{r['project_authenticity'] or 'missing'}/{r['tracking_authenticity'] or 'missing'}"
                               for r in rows).items()))


def prepare(source: Path, output: Path, verification_path: Path | None = None) -> dict:
    source = source.resolve()
    output = output.resolve()
    if source.is_relative_to(output) or output.is_relative_to(source.parent):
        raise ValueError("Output must be separate from the raw source directory")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    records, docs = read_source(source)
    verification = load_verification(verification_path)
    buildings, excluded, related = process_records(records, docs, verification)
    candidates = [r for r in buildings if r["planned_duration_status"] == r["real_duration_status"] == "valid"
                  and not r["duplicate_id"]]
    labels = [r for r in candidates if r["label_status"] == "verified_duration_deviation"]
    definitions = docs["definitions"]
    report = dict(source=str(source), source_sha256=before, worksheet="DSLIB", header_row_index=2,
                  valid_project_records=sum(bool(ID_PATTERN.fullmatch(text(r["project_id"]))) for r in records),
                  valid_building_records=len(buildings), positive_numeric_duration_pairs=len(candidates),
                  building_summary_rows_excluded=sum(text(r.get("sector")).casefold() in SECTORS
                                                    and not ID_PATTERN.fullmatch(text(r.get("project_id"))) for r in excluded),
                  nonbuilding_project_records=sum(r["exclusion_reason"] == "nonbuilding_sector" for r in excluded),
                  excluded_reason_counts=dict(Counter(r["exclusion_reason"] for r in excluded)),
                  duplicate_ids=sorted({r["project_id"] for r in buildings if r["duplicate_id"]}),
                  authenticity_combinations_buildings=combos(buildings),
                  authenticity_combinations_candidates=combos(candidates),
                  project_authenticity_candidates=dict(Counter(r["project_authenticity"] or "missing" for r in candidates)),
                  tracking_authenticity_candidates=dict(Counter(r["tracking_authenticity"] or "missing" for r in candidates)),
                  authenticity_gg_candidates=sum(r["authenticity_gg"] for r in candidates),
                  duration_validation={field: dict(Counter(r[field + "_status"] for r in buildings))
                                       for field in ("planned_duration", "real_duration")},
                  missing_or_invalid_baseline_features={f: dict(Counter(r[f + "_status"] for r in candidates)) for f in NUMERIC_FEATURES},
                  early_late_checks=dict(Counter(r["early_late_check"] for r in candidates)),
                  early_late_mismatch_ids=[r["project_id"] for r in candidates if r["early_late_check"] == "mismatch"],
                  early_late_audit_tolerance=.0051,
                  known_problem_project_ids=list(project_notes(docs["Known Problems"])),
                  related_review_groups=related,
                  provisional_candidate_groups=len({r["review_group_id"] for r in candidates}),
                  verified_target_records=len(labels),
                  independently_usable_projects_confirmed=sum(r["independently_usable"] for r in candidates),
                  verification_source=str(verification_path.resolve()) if verification_path else None,
                  verification_sha256=hashlib.sha256(verification_path.read_bytes()).hexdigest() if verification_path else None,
                  target_blocker_counts=dict(Counter(reason for row in buildings for reason in row["target_blockers"].split(";") if reason)),
                  definitions=definitions,
                  target_definition="Signed total project duration deviation; real minus planned. Negative means early; not IFC-caused extra work or start-date slippage.",
                  baseline_feature_columns=list(FEATURE_COLUMNS),
                  metadata_not_model_features=["project_id", "authenticity", "review_group_id", "submitted_by"],
                  excluded_predictors=["Real Duration", "Real Cost", "Early/late", "Under/over budget", "CV", "SV", "SV(t)",
                                       "CPI", "SPI", "SPI(t)", "p-factor", "all progress averages/stddev/final metrics", "actual duration", "target", "authenticity"],
                  unresolved_assumptions=[
                      "Day-equivalence and project calendar comparability require project-level evidence; no hours/day conversion inferred.",
                      "G/O/Y are preserved source codes; Overview provides no explicit code-to-authenticity legend. G/G is only a conservative screen.",
                      "Updates include revised schedules/precedences: the baseline must be verified as the original prediction-time plan.",
                      "Early/late disagreement is a review blocker; resolution requires source_issue_reviewed and evidence, never editing original durations.",
                      "Name-based related groups can overgroup generic names and miss other shared projects; they do not prove independence.",
                      "Absence from Known Problems does not certify a record. The sheet contains an out-of-scope project issue.",
                      "Summary rows are never observations; missing outcomes and features stay missing. No split, imputation or model training.",
                  ])
    if hashlib.sha256(source.read_bytes()).hexdigest() != before:
        raise RuntimeError("Raw source changed during processing")
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "ghent_buildings_audit.csv", buildings)
    write_csv(output / "ghent_delay_candidates.csv", candidates, buildings[0].keys() if buildings else ["project_id"])
    write_csv(output / "ghent_excluded_rows.csv", excluded)
    write_csv(output / "ghent_related_projects_review.csv", related,
              ("review_group_id", "project_ids", "project_names", "evidence"))
    write_csv(output / "ghent_baseline_features.csv", [{k: row[k] for k in FEATURE_COLUMNS} for row in candidates], FEATURE_COLUMNS)
    label_fields = ("project_id", "duration_deviation_days", "verified_day_basis", "label_status", "independently_usable")
    write_csv(output / "ghent_verified_labels.csv", [{k: row[k] for k in label_fields} for row in labels], label_fields)
    template = output / "duration_verification_template.csv"
    if not template.exists():  # Never overwrite evidence the user has already entered.
        write_csv(template, [dict.fromkeys(VERIFICATION_FIELDS, "") | {"project_id": row["project_id"], "planned_unit": "days"}
                             for row in candidates], VERIFICATION_FIELDS)
    (output / "source_documentation.json").write_text(json.dumps(docs, indent=2, default=str) + "\n", encoding="utf-8")
    (output / "verification_used.json").write_text(json.dumps(verification, indent=2) + "\n", encoding="utf-8")
    (output / "cleaning_report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_report(output / "cleaning_report.md", report)
    return report


def write_report(path: Path, report: dict) -> None:
    lines = ["# PMI Stage 2.2 — Ghent building-duration preparation", "",
             f"Source: `{report['source']}`, worksheet DSLIB, header row index 2.",
             f"Source SHA256: `{report['source_sha256']}`. Excel files are never saved or modified.", "",
             "## Counts and inclusion", "",
             f"- Overall valid project records: {report['valid_project_records']}.",
             f"- Valid building records: {report['valid_building_records']}.",
             f"- Building-category summary rows excluded: {report['building_summary_rows_excluded']}.",
             f"- Positive planned/real duration pairs: {report['positive_numeric_duration_pairs']}.",
             f"- G/G source-code candidates: {report['authenticity_gg_candidates']} (not independently validated).",
             f"- Verified deviation targets: {report['verified_target_records']}.",
             f"- Independently usable projects confirmed: {report['independently_usable_projects_confirmed']}.",
             f"- Duplicate building IDs: {report['duplicate_ids']}.",
             f"- Provisional candidate groups after name/phase flags: {report['provisional_candidate_groups']} (NOT a verified independent count).", "",
             "87 building-sector records include partial works and facilities, not necessarily 87 complete buildings.",
             "All exclusions and source row numbers are in ghent_excluded_rows.csv; missing/invalid duration rows remain in the building audit.", "",
             "## Source definitions and units", "",
             "Overview B33:C33 defines PD (days) as planned project-schedule duration.",
             "Overview B89:C89 defines Real duration as total duration known after project finish.",
             "These definitions verify planned/real interpretation, but not a common working/calendar-day convention.",
             "No calendar-day difference is substituted for working days, and no default eight-hour day is assumed.",
             "Source raw values (including formulas if present) and cached values are retained separately.",
             "Fields ending _days hold source-scale candidates; only nonempty duration_deviation_days is a verified day-based target.", "",
             "## Authenticity and known issues", "",
             "Overview rows 25–29 distinguish static-project and progress-tracking authenticity using a referenced colour-coded framework.",
             "It does not explicitly decode G/O/Y. Missing codes, N/A and unexpected codes are not promoted to G.",
             f"Candidate project codes: {report['project_authenticity_candidates']}.",
             f"Candidate tracking codes: {report['tracking_authenticity_candidates']}.",
             f"Candidate combinations: {report['authenticity_combinations_candidates']}.",
             f"Known Problems project IDs: {report['known_problem_project_ids']}; none should be silently treated as a quality certificate for other records.",
             "The known issue is that C2011-06 cannot be rescheduled; that project is outside the building filter.",
             "Updates is also captured and linked by project ID so revised baselines/precedences can be reviewed.",
             f"Early/late checks: {report['early_late_checks']}; tolerance {report['early_late_audit_tolerance']} in fractional deviation.",
             f"Mismatched project IDs: {report['early_late_mismatch_ids']}.",
             "This post-execution ratio is used only for auditing; it never enters baseline features.", "",
             "## Target and independence gate", "",
             report["target_definition"],
             "A target requires positive numeric durations, verified source definitions, units, day basis/calendar comparability, original baseline and reviewer evidence.",
             "Duplicate IDs block release. Known problems or contradictory Early/late require explicit source-issue review evidence. No raw values are corrected automatically.",
             "Use duration_verification_template.csv for documented per-project evidence, then pass it with --verification-file.",
             "An independently usable count additionally requires G/G and an evidenced independence attestation. Do not mark this from unique IDs alone.",
             "The numeric-pair candidates are not an independently usable training set. Related names/phases are review hints, never a split or proof of shared identity.", "",
             "## Missing values and feature contract", "",
             f"Duration statuses: {report['duration_validation']}.",
             "Feature-level missing/invalid counts and every target blocker are in cleaning_report.json. Nothing is imputed.",
             "ghent_baseline_features.csv is an explicit numeric baseline-only allowlist plus project_id for joins.",
             "No actual outcome, EVM performance metric, tracking statistic, authenticity code, project name or reviewer metadata is a prediction input.",
             "ghent_verified_labels.csv contains released labels only; its header-only default means no labels passed the verification gate.", "",
             "## Unresolved assumptions", ""]
    lines.extend("- " + value for value in report["unresolved_assumptions"])
    lines += ["", "No model was trained; no 80/20 split or change to Stage 1 models, IFC, CPM or Streamlit was made."]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    parser.add_argument("--verification-file", type=Path)
    args = parser.parse_args()
    try:
        report = prepare(args.source, args.output_dir, args.verification_file)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Overall projects: {report['valid_project_records']}; buildings: {report['valid_building_records']}")
    print(f"Positive duration-pair candidates: {report['positive_numeric_duration_pairs']}; verified targets: {report['verified_target_records']}")
    print(f"Independently usable projects confirmed: {report['independently_usable_projects_confirmed']}")
    print(f"Report: {args.output_dir / 'cleaning_report.md'}")


if __name__ == "__main__":
    main()
