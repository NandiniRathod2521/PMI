"""Stage 2.3B: stream Cambridge schedule data into descriptive/label audits.

No imputation, working-calendar assumptions, model training, split or tuning.
Candidate elapsed labels describe reported timestamps, not independently verified
work durations. Estimated/unfinished at-completion records never become actuals.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import ijson

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/raw/cambridge/JPF_Anonymised_Project_Data.json"
OUT = ROOT / "data/processed/stage2/cambridge_audit"
INVENTORY = ROOT / "data/processed/external_inventory/cambridge_inventory.json"
MISSING = {"", "null", "none", "nan", "n/a", "na"}
ODE = "Original_Duration_Estimate(ODE)"
ACD = "At_Completion_Duration"
GROWTH = "Duration_Growth_Percentage(Y_values)"
PROGRESS = "Physical_Percent_Complete"
DATES = ("Actual_Start_Date", "Actual_Finish_Date", "Planned_Start_Date", "Planned_Finish_Date")
FEATURES = ("project_key", "activity_key", "project_type", "uk_region", "activity_description",
            "wbs_description", "original_duration_source_units", "planned_elapsed_calendar_days",
            "planned_start_month", "predecessor_count_as_exported")
TASKS = ("descriptive_analysis", "reported_completed_elapsed_duration", "recorded_at_completion_duration",
         "elapsed_planned_vs_actual_deviation", "stored_duration_growth", "project_schedule_risk")


class RejectDuplicateKeys(dict):
    def __setitem__(self, key, value):
        if key in self:
            raise ValueError(f"Duplicate JSON object key {key!r}; resolve source ambiguity before auditing")
        super().__setitem__(key, value)


def iter_projects(file):
    try:
        yield from ijson.kvitems(file, "Projects", use_float=True, map_type=RejectDuplicateKeys)
    except SystemError as error:
        # yajl2_c can wrap exceptions raised by a custom map builder.
        if isinstance(error.__cause__, ValueError):
            raise error.__cause__ from error
        raise


def text(value):
    return "" if value is None else str(value).strip()


def missing(value):
    return value is None or (isinstance(value, str) and value.strip().lower() in MISSING)


def numeric(value):
    if missing(value) or isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def source_mapping(value):
    if missing(value):
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object or missing sentinel, got {type(value).__name__}")
    return value


def date_value(value):
    if missing(value) or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
        # No silent localization or comparison of naive/aware timestamps.
        return parsed if parsed.tzinfo is None else None
    except ValueError:
        return None


def elapsed(start, finish):
    if start is None or finish is None or finish < start:
        return None
    return (finish - start).total_seconds() / 86400.0


def hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path):
    return path.resolve().relative_to(ROOT).as_posix()


def pointer(*keys):
    return "/" + "/".join(str(key).replace("~", "~0").replace("/", "~1") for key in keys)


def protect():
    paths = list((ROOT / "data/raw").rglob("*"))
    paths += [p for p in (ROOT / "data/processed/stage2").rglob("*") if not p.is_relative_to(OUT)]
    paths += list((ROOT / "models").rglob("*")) + list((ROOT / "scripts").glob("*.py"))
    paths += [ROOT / "app.py", ROOT / "run_pipeline.py", INVENTORY]
    paths += [ROOT / "training" / name for name in ("train_model.py", "validate_model.py", "prepare_ghent_delays.py", "verify_ghent_evidence.py")]
    return {rel(p): hash_file(p) for p in paths if p.is_file()}


def field_policy(level, name):
    """Availability means conceptual availability; this export has no issued-baseline lineage."""
    if level == "project":
        if name in ("Project_ID", "Activities", "Work_Breakdown_Structure"):
            return ("identifier_or_container", "metadata", "none", "Not a predictor; ID is not proof of independent projects")
        if name in ("Project_Type", "UK_Region"):
            return ("pre_execution_conceptually", "conditional_feature", "category", "Exported value; original issue time unverified")
        if name == "Status_Data_Date":
            return ("snapshot_metadata", "audit_only", "naive timestamp", "Use only to audit temporal coherence; never a baseline predictor")
        return ("snapshot_or_final_unknown", "exclude", "naive timestamp", "Earliest/latest project dates do not establish original contractual or actual completion")
    if level == "relationship":
        return ("pre_execution_conceptually_replanning_possible", "audit_or_conditional_topology", "identifier/category; Lag unit unverified",
                "Relationships may be revised; precomputed predecessor topic may have been fit on the whole corpus")
    if level == "wbs":
        return ("pre_execution_conceptually_replanning_possible", "metadata_or_conditional_text", "identifier/text", "WBS may reveal shared parent projects; identity needs review")
    if name in ("Task_ID", "WBS_ID", "Calendar_ID"):
        return ("identifier", "metadata", "identifier", "Calendar_ID is not a calendar definition and must not be globally equated across exports")
    if name == "Activity_Relationships":
        return ("pre_execution_conceptually_replanning_possible", "metadata_container", "nested object or missing sentinel",
                "Predecessor map, not a numeric feature; its counts are conditional as-exported topology")
    if name == "Task_Type:":
        return ("expected_static_but_suspect", "exclude", "unknown", "Audit equality to Task_ID; do not use to infer milestone or task-dependent status")
    if name in ("Activity_Description", "WBS_Description", ODE, "Planned_Start_Date", "Planned_Finish_Date"):
        unit = "unverified source duration units" if name == ODE else "naive timestamp" if "Date" in name else "text"
        return ("pre_execution_conceptually", "conditional_feature", unit, "Snapshot may contain revised baseline information; no verified original issue history")
    if name in (ACD, GROWTH, *DATES[:2], PROGRESS):
        unit = "0–100 percent" if name == PROGRESS else "fraction hypothesis; audit ratio, do not assume percent x100" if name == GROWTH else "unverified source duration units" if name == ACD else "naive timestamp"
        return ("post_start_or_post_execution", "target_audit_only_exclude_from_inputs", unit, "At-completion can be estimated for unfinished work; actual dates and completion are eligibility checks only")
    if name.startswith("Free_Float") or name.startswith("Total_Float"):
        return ("schedule_state_dependent", "exclude", "hours (header)" if "hrs" in name else "days (header)", "Float changes with progress/replanning; baseline provenance unverified")
    if name in ("Constraint_Type(if_any)", "Constraint_Date", "Concurrent_Activity_Count", "Task_Position_(percentage_through_project)"):
        return ("as_of_timing_unverified", "exclude", "source-specific", "Could depend on final dates, progress or replanning; recompute from an issued baseline if later authorized")
    if name == "GMM_Topic_Classification":
        return ("learned_on_unknown_corpus", "exclude", "category", "Precomputed clustering may leak evaluation corpus; future encoders must fit training groups only")
    if "Temperature" in name or name.startswith("Total_Monthly_"):
        return ("realized_or_climatological_timing_unknown", "exclude", "header-specific; mapping suspect", "Monthly weather may be realized after prediction; value alignment must be checked, not automatically repaired")
    if name.startswith("Market_Conditions"):
        return ("reference_date_and_release_timing_unknown", "exclude", "standard deviations per header", "Actual versus planned start and economic release vintage unverified")
    return ("unknown", "exclude", "unknown", "Unrecognized field; no model-input approval")


def field_description(level, name):
    meanings = {
        "Project_ID": "Exported project identifier; compare with the Projects object key",
        "Project_Type": "Source project-sector/type category", "UK_Region": "Source project region",
        "Earliest_Project_Start_Date": "Exported project start metadata; not certified original baseline",
        "Latest_Project_Finish_Date": "Exported project finish metadata; actual versus forecast is not established",
        "Status_Data_Date": "Exported schedule status/data-date snapshot reference",
        "Activities": "Project-local activity map", "Work_Breakdown_Structure": "Project-local WBS map",
        "Task_ID": "Exported task identifier; compare to project-local activity object key",
        "Task_Type:": "Field named task type; observed numeric identifiers are audited for corruption",
        "Activity_Description": "Anonymized task description", "WBS_Description": "Anonymized work-breakdown description",
        "WBS_ID": "Work-breakdown identifier", "WBS_Parent_ID": "Parent WBS identifier or missing root sentinel",
        ODE: "Original-duration estimate as exported; units and original-issue provenance unresolved",
        ACD: "At-completion duration as exported; can be an estimate/placeholder for unfinished work",
        GROWTH: "Exported duration-growth value; checked against ACD/ODE minus one, without rescaling",
        PROGRESS: "Reported physical completion percentage; not an independent completion certificate",
        "Actual_Start_Date": "Reported actual activity start timestamp",
        "Actual_Finish_Date": "Reported actual activity finish timestamp",
        "Planned_Start_Date": "Exported planned start, potentially revised rather than original",
        "Planned_Finish_Date": "Exported planned finish, potentially revised rather than original",
        "Calendar_ID": "Calendar reference only; no working hours, weekmask or holidays supplied",
        "Free_Float(hrs)": "Source free float with hour-labelled header",
        "Total_Float(d)": "Source total float with day-labelled header",
        "Constraint_Type(if_any)": "Exported scheduling-constraint category", "Constraint_Date": "Exported constraint timestamp",
        "Concurrent_Activity_Count": "Precomputed concurrency measure; scaling and computation window unverified",
        "Task_Position_(percentage_through_project)": "Precomputed project-position measure; timing and scale unverified",
        "GMM_Topic_Classification": "Precomputed learned task topic; fit population unknown",
        "Activity_Relationships": "Mapping of predecessor IDs to relationship records; may be the string null",
        "Predecessor_ID": "Linked predecessor task identifier; may refer outside the local project",
        "Relationship_Type": "Precedence relationship category, e.g. PR_FS or PR_FF",
        "Lag": "Source relationship lag; working/calendar units not supplied",
        "Predecessor_GMM_Classification": "Precomputed topic of a linked predecessor; not an observed duration outcome",
    }
    if name in meanings:
        return meanings[name]
    if "Temperature" in name or name.startswith("Total_Monthly_"):
        return "Monthly weather statistic named by the header; value/column alignment and observation vintage unresolved"
    if name.startswith("Market_Conditions"):
        return "Project-start market-condition index as named; planned/actual start reference and data vintage unresolved"
    return "Unrecognized source field; manual semantic review required"


class FieldAudit:
    def __init__(self):
        self.data = {}
        self.totals = Counter()

    def add(self, level, obj):
        self.totals[level] += 1
        for name, value in obj.items():
            item = self.data.setdefault((level, name), dict(present=0, missing=0, types=Counter(), examples=[],
                numeric_count=0, numeric_min=None, numeric_max=None, negative_count=0, zero_count=0,
                date_valid=0, date_invalid=0, values=set()))
            item["present"] += 1
            item["types"][type(value).__name__] += 1
            if missing(value):
                item["missing"] += 1
                continue
            if len(item["examples"]) < 3:
                item["examples"].append(text(value)[:100] if not isinstance(value, (dict, list)) else "nested container")
            # Cap distinct counting; do not retain every text or ID in memory.
            if len(item["values"]) < 1001:
                item["values"].add(text(value) if not isinstance(value, (dict, list)) else "container")
            num = numeric(value)
            if num is not None:
                item["numeric_count"] += 1
                item["negative_count"] += num < 0
                item["zero_count"] += num == 0
                item["numeric_min"] = num if item["numeric_min"] is None else min(item["numeric_min"], num)
                item["numeric_max"] = num if item["numeric_max"] is None else max(item["numeric_max"], num)
            if "Date" in name or name in DATES:
                item["date_valid" if date_value(value) is not None else "date_invalid"] += 1

    def rows(self):
        result = []
        for (level, name), stats in sorted(self.data.items()):
            availability, policy, unit, caveat = field_policy(level, name)
            absent = self.totals[level] - stats["present"]
            result.append(dict(level=level, field=name, description=field_description(level, name), total_records=self.totals[level], present=stats["present"],
                absent=absent, missing_or_absent=stats["missing"]+absent, nonmissing=stats["present"]-stats["missing"],
                source_types=json.dumps(dict(stats["types"])), examples=json.dumps(stats["examples"]),
                distinct_up_to_1000=len(stats["values"]) if len(stats["values"]) <= 1000 else ">1000",
                **{key: stats[key] for key in ("numeric_count", "numeric_min", "numeric_max", "negative_count", "zero_count", "date_valid", "date_invalid")},
                temporal_availability=availability, input_policy=policy, units=unit, caveat=caveat))
        return result


def audit_activity(project_key, project, key, activity):
    ode, acd, growth, progress = [numeric(activity.get(f)) for f in (ODE, ACD, GROWTH, PROGRESS)]
    parsed = {name: date_value(activity.get(name)) for name in DATES}
    actual = elapsed(parsed[DATES[0]], parsed[DATES[1]])
    planned = elapsed(parsed[DATES[2]], parsed[DATES[3]])
    status = date_value(project.get("Status_Data_Date"))
    complete = progress is not None and math.isclose(progress, 100, abs_tol=1e-8)
    has_pair = parsed[DATES[0]] is not None and parsed[DATES[1]] is not None
    finish_after_status = has_pair and status is not None and parsed[DATES[1]] > status
    key_ok = bool(text(key)) and text(activity.get("Task_ID")) == text(key) and text(project.get("Project_ID")) == text(project_key)
    # Candidate elapsed time is explicitly calendar elapsed time, not the stored duration field.
    elapsed_candidate = key_ok and complete and actual is not None and actual > 0 and status is not None and not finish_after_status
    planned_pair = planned is not None and planned > 0
    stored_ratio = acd / ode - 1 if ode is not None and ode > 0 and acd is not None and acd >= 0 else None
    ratio_check = "not_computable"
    if stored_ratio is not None and growth is not None:
        ratio_check = "matches_fraction" if math.isclose(stored_ratio, growth, rel_tol=1e-7, abs_tol=1e-6) else "mismatch"
    flags = []
    if not key_ok:
        flags.append("key_or_id_mismatch")
    for name in DATES:
        if not missing(activity.get(name)) and parsed[name] is None:
            flags.append("invalid_" + name)
    if has_pair and actual is None:
        flags.append("actual_finish_before_start")
    if actual == 0:
        flags.append("zero_actual_elapsed_span")
    if planned == 0:
        flags.append("zero_planned_elapsed_span")
    if parsed[DATES[2]] is not None and parsed[DATES[3]] is not None and planned is None:
        flags.append("planned_finish_before_start")
    if not complete:
        flags.append("not_reported_100_percent_complete")
    if progress is None or not 0 <= progress <= 100:
        flags.append("missing_or_invalid_progress")
    if complete and not has_pair:
        flags.append("complete_but_actual_pair_missing")
    if status is None:
        flags.append("status_date_missing_or_invalid")
    if finish_after_status:
        flags.append("actual_finish_after_status_date")
    if ode is None or ode <= 0:
        flags.append("nonpositive_or_invalid_ode")
    if acd is None or acd <= 0:
        flags.append("nonpositive_or_invalid_acd")
    if not has_pair and ode is not None and acd is not None and ode == acd:
        flags.append("at_completion_equals_plan_without_actual_pair")
    if ratio_check == "mismatch":
        flags.append("stored_growth_inconsistent")
    if text(activity.get("Task_Type:")) == text(activity.get("Task_ID")) and text(activity.get("Task_ID")):
        flags.append("task_type_duplicates_task_id")
    if missing(activity.get("Calendar_ID")):
        flags.append("calendar_id_missing")
    if not has_pair:
        provenance = "at_completion_estimate_or_placeholder_unknown_not_observed"
    elif not complete:
        provenance = "incomplete_or_conflicting_progress_unknown"
    elif actual is None or actual <= 0 or finish_after_status or status is None:
        provenance = "reported_actual_dates_temporally_unresolved"
    else:
        provenance = "reported_historical_timestamps_not_independently_verified"
    stored_candidate = elapsed_candidate and acd is not None and acd > 0
    growth_candidate = stored_candidate and ode is not None and ode > 0 and ratio_check == "matches_fraction"
    row = dict(project_key=text(project_key), activity_key=text(key), task_id_source=activity.get("Task_ID"),
        source_pointer=pointer("Projects", project_key, "Activities", key),
        original_duration_source=activity.get(ODE), at_completion_duration_source=activity.get(ACD),
        growth_source=activity.get(GROWTH), physical_percent_source=activity.get(PROGRESS),
        actual_start_source=activity.get(DATES[0]), actual_finish_source=activity.get(DATES[1]),
        planned_start_source=activity.get(DATES[2]), planned_finish_source=activity.get(DATES[3]),
        status_date_source=project.get("Status_Data_Date"), calendar_id_source=activity.get("Calendar_ID"),
        parsed_original_duration=ode, parsed_at_completion_duration=acd,
        planned_elapsed_calendar_days=planned, actual_elapsed_calendar_days=actual,
        audit_elapsed_deviation_calendar_days=(actual-planned) if actual is not None and planned is not None else None,
        audit_computed_growth_fraction=stored_ratio, growth_ratio_check=ratio_check,
        reported_complete=complete, actual_pair_parsed=has_pair, actual_finish_after_status=finish_after_status,
        candidate_elapsed_calendar_days=actual if elapsed_candidate else None,
        candidate_elapsed_duration=elapsed_candidate, candidate_stored_duration=stored_candidate,
        candidate_elapsed_deviation=elapsed_candidate and planned_pair, candidate_stored_growth=growth_candidate,
        label_provenance=provenance, verified_working_duration_label=False, verified_baseline_deviation_label=False,
        label_quality_flags=";".join(flags), source_duration_units="unverified_in_this_export",
        original_baseline_provenance="unverified", source_calendar_definition="not_in_export")
    features = dict(project_key=text(project_key), activity_key=text(key), project_type=project.get("Project_Type"),
        uk_region=project.get("UK_Region"), activity_description=activity.get("Activity_Description"),
        wbs_description=activity.get("WBS_Description"), original_duration_source_units=ode if ode is not None and ode >= 0 else None,
        planned_elapsed_calendar_days=planned, planned_start_month=parsed[DATES[2]].month if parsed[DATES[2]] else None,
        predecessor_count_as_exported=(None if missing(activity.get("Activity_Relationships"))
                                       else len(source_mapping(activity.get("Activity_Relationships")))))
    return row, features


def csv_writer(path, fields):
    file = path.open("w", newline="", encoding="utf-8")
    writer = csv.DictWriter(file, fieldnames=list(fields))
    writer.writeheader()
    return file, writer


def write_csv(path, rows, fields=None):
    fields = fields or list(rows[0] if rows else ["none"])
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def weather_flags(activity):
    maximum = numeric(activity.get("Maximum_Monthly_Temperature(C)"))
    minimum = numeric(activity.get("Minimum_Monthly_Temperature(C)"))
    mean = numeric(activity.get("Mean_Monthly_Temperature"))
    flags = []
    if maximum is not None and minimum is not None and minimum > maximum:
        flags.append("minimum_temperature_above_maximum")
    if mean is not None and minimum is not None and maximum is not None and not minimum <= mean <= maximum:
        flags.append("mean_temperature_outside_min_max")
    for field in ("Total_Monthly_Raindays(>=1mm)", "Total_Monthly_Days_of_Air_Frost"):
        value = numeric(activity.get(field))
        if value is not None and not 0 <= value <= 31:
            flags.append("monthly_day_count_outside_0_31:" + field)
    return flags


def audit(source=SOURCE, output=OUT, *, check_protected=True):
    source, output = source.resolve(), output.resolve()
    if not output.is_relative_to(OUT.resolve()):
        raise ValueError("Outputs must stay under data/processed/stage2/cambridge_audit")
    before = protect() if check_protected else {str(source): hash_file(source)}
    original_inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    archive_hash = hash_file(source.with_suffix(source.suffix + ".zip"))
    if archive_hash != original_inventory["archive_sha256"]:
        raise ValueError("Cambridge archive differs from the recorded Stage 1 source")
    output.mkdir(parents=True, exist_ok=True)
    stats, totals = FieldAudit(), Counter()
    projects, task_owners, wbs_owners = [], defaultdict(set), defaultdict(set)
    pair_overlap, project_keys, fingerprints = Counter(), set(), defaultdict(list)
    task_projects = {task: set() for task in TASKS}
    task_counts, quality, provenance, progress_counts, ratio_counts, weather = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
    anomalies = []
    label_file = feature_file = None
    with source.open("rb") as file:
        try:
            for project_key, project in iter_projects(file):
                if project_key in project_keys:
                    raise ValueError(f"Duplicate project key {project_key}")
                project_keys.add(project_key)
                if not isinstance(project, dict) or not isinstance(project.get("Activities"), dict):
                    raise ValueError(f"Project {project_key} has no Activities object")
                stats.add("project", project)
                activities = project["Activities"]
                activity_ids = {text(a.get("Task_ID")) for a in activities.values() if isinstance(a, dict) and text(a.get("Task_ID"))}
                local_task_ids = Counter(text(a.get("Task_ID")) for a in activities.values() if isinstance(a, dict))
                if any(count > 1 for count in local_task_ids.values()):
                    raise ValueError(f"Repeated Task_ID within project {project_key}; no ambiguous candidate rows emitted")
                previous_owners = Counter(owner for tid in activity_ids for owner in task_owners[tid])
                for owner, count in previous_owners.items():
                    pair_overlap[(owner, text(project_key))] += count
                for tid in activity_ids:
                    task_owners[tid].add(text(project_key))
                wbs = source_mapping(project.get("Work_Breakdown_Structure"))
                for key, item in wbs.items():
                    stats.add("wbs", item)
                    wbs_owners[text(key)].add(text(project_key))
                summary = dict(project_key=text(project_key), project_id_source=project.get("Project_ID"),
                    project_type=project.get("Project_Type"), region=project.get("UK_Region"),
                    status_date_source=project.get("Status_Data_Date"), activity_records=len(activities),
                    wbs_records=len(wbs), candidate_elapsed_duration=0, candidate_stored_duration=0,
                    candidate_elapsed_deviation=0, candidate_stored_growth=0, actual_date_pair_filled=0,
                    completed_progress_records=0, actual_finish_after_status=0, dangling_predecessor_links=0,
                    relationship_records=0, relationship_key_mismatches=0, missing_wbs_references=0,
                    task_type_equals_task_id=0, calendar_ids=set(), missing_predecessor_ids=set(),
                    task_position_values=set(), actual_dates_seen=[], planned_dates_seen=[])
                schedule_hash = hashlib.sha256()
                for key, activity in activities.items():
                    if not isinstance(activity, dict):
                        raise ValueError(f"Invalid activity {project_key}/{key}")
                    stats.add("activity", activity)
                    row, features = audit_activity(project_key, project, key, activity)
                    if label_file is None:
                        label_file, label_writer = csv_writer(output / "activity_label_audit.csv", row)
                        feature_file, feature_writer = csv_writer(output / "candidate_features.csv", FEATURES)
                    label_writer.writerow(row)
                    feature_writer.writerow(features)
                    totals["activities"] += 1
                    task_counts["descriptive_analysis"] += 1
                    task_projects["descriptive_analysis"].add(text(project_key))
                    for target, field in (("reported_completed_elapsed_duration", "candidate_elapsed_duration"),
                        ("recorded_at_completion_duration", "candidate_stored_duration"),
                        ("elapsed_planned_vs_actual_deviation", "candidate_elapsed_deviation"), ("stored_duration_growth", "candidate_stored_growth")):
                        if row[field]:
                            task_counts[target] += 1
                            task_projects[target].add(text(project_key))
                            summary[field] += 1
                    for flag in row["label_quality_flags"].split(";"):
                        if flag:
                            quality[flag] += 1
                    provenance[row["label_provenance"]] += 1
                    progress_counts[text(activity.get(PROGRESS)) or "missing"] += 1
                    ratio_counts[row["growth_ratio_check"]] += 1
                    filled = not missing(activity.get(DATES[0])) and not missing(activity.get(DATES[1]))
                    summary["actual_date_pair_filled"] += filled
                    summary["completed_progress_records"] += row["reported_complete"]
                    summary["actual_finish_after_status"] += row["actual_finish_after_status"]
                    summary["task_type_equals_task_id"] += "task_type_duplicates_task_id" in row["label_quality_flags"]
                    if not missing(activity.get("Calendar_ID")):
                        summary["calendar_ids"].add(text(activity["Calendar_ID"]))
                    if not missing(activity.get("Task_Position_(percentage_through_project)")):
                        summary["task_position_values"].add(text(activity["Task_Position_(percentage_through_project)"]))
                    if text(activity.get("WBS_ID")) not in wbs:
                        summary["missing_wbs_references"] += 1
                    for field, collection in ((DATES[1], "actual_dates_seen"), (DATES[3], "planned_dates_seen")):
                        value = date_value(activity.get(field))
                        if value:
                            summary[collection].append(value)
                    relations = source_mapping(activity.get("Activity_Relationships"))
                    for relation_key, relationship in relations.items():
                        stats.add("relationship", relationship)
                        summary["relationship_records"] += 1
                        predecessor = text(relationship.get("Predecessor_ID"))
                        if predecessor != text(relation_key):
                            summary["relationship_key_mismatches"] += 1
                        if predecessor not in activity_ids:
                            summary["dangling_predecessor_links"] += 1
                            summary["missing_predecessor_ids"].add(predecessor)
                    flags = weather_flags(activity)
                    for flag in flags:
                        weather[flag] += 1
                    if flags and len(anomalies) < 100:
                        anomalies.append(dict(project_key=project_key, activity_key=key, source_pointer=row["source_pointer"],
                            flags=";".join(flags), source_weather_values=json.dumps({k:v for k,v in activity.items() if "Monthly" in k or "Temperature" in k})))
                    schedule_hash.update(json.dumps([activity.get("Activity_Description"), activity.get("Planned_Start_Date"),
                                                    activity.get("Planned_Finish_Date"), activity.get(ODE)], sort_keys=True).encode())
                summary["calendar_ids"] = ";".join(sorted(summary["calendar_ids"]))
                summary["distinct_task_position_values"] = len(summary.pop("task_position_values"))
                summary["actual_latest_finish_observed"] = max(summary["actual_dates_seen"]).isoformat() if summary["actual_dates_seen"] else ""
                summary["planned_latest_finish_observed"] = max(summary["planned_dates_seen"]).isoformat() if summary["planned_dates_seen"] else ""
                summary["all_activities_reported_complete"] = summary["completed_progress_records"] == len(activities) and len(activities) > 0
                summary["original_project_baseline_verified"] = False
                summary["project_risk_label_verified"] = False
                summary["export_order_fingerprint"] = schedule_hash.hexdigest()
                fingerprints[schedule_hash.hexdigest()].append(text(project_key))
                del summary["actual_dates_seen"], summary["planned_dates_seen"]
                projects.append(summary)
                print(f"Audited project {len(projects)}: {project_key}, {len(activities)} activities", flush=True)
        finally:
            if label_file:
                label_file.close()
            if feature_file:
                feature_file.close()
    pair_rows = []
    lookup = {p["project_key"]: p for p in projects}
    for (left, right), shared in sorted(pair_overlap.items()):
        a, b = lookup[left], lookup[right]
        pair_rows.append(dict(project_key_a=left, project_key_b=right, shared_task_ids=shared,
            fraction_of_smaller_project=shared/min(a["activity_records"], b["activity_records"]),
            proposed_decision="Review snapshot/shared-parent identity; keep together if splitting later",
            relationship_verified=False))
    for project in projects:
        unknown = project.pop("missing_predecessor_ids")
        project["missing_predecessor_ids_found_in_other_projects"] = sum(bool(task_owners.get(tid)) for tid in unknown)
    dictionary = stats.rows()
    write_csv(output / "data_dictionary.csv", dictionary)
    write_csv(output / "project_audit.csv", projects)
    write_csv(output / "project_relationships.csv", pair_rows,
              ("project_key_a", "project_key_b", "shared_task_ids", "fraction_of_smaller_project", "proposed_decision", "relationship_verified"))
    write_csv(output / "weather_anomaly_examples.csv", anomalies,
              ("project_key", "activity_key", "source_pointer", "flags", "source_weather_values"))
    eligibility = []
    reasons = dict(descriptive_analysis="Available for source-level descriptive analysis, not verified outcomes",
        reported_completed_elapsed_duration="Reported complete, valid positive actual-date span, finish no later than status; calendar elapsed proxy only; baseline provenance/independence unresolved",
        recorded_at_completion_duration="Above temporal checks plus positive stored duration; missing working calendars/units prevent verified work-duration labels",
        elapsed_planned_vs_actual_deviation="Complete elapsed candidates plus positive planned span; original issued baseline unverified",
        stored_duration_growth="Complete positive stored pairs with growth fraction consistent; calendar/export contract and original baseline unverified",
        project_schedule_risk="No original contractual baseline, verified actual project completion or probability-of-risk target")
    for task in TASKS:
        eligibility.append(dict(task=task, structural_candidate_activities=task_counts[task],
            projects_with_structural_candidates=len(task_projects[task]), supervised_training_ready_activities=0,
            supervised_training_ready_projects=0, qualification=reasons[task]))
    write_csv(output / "task_eligibility.csv", eligibility)
    features_contract = dict(columns=list(FEATURES), identifier_columns=list(FEATURES[:2]),
        candidate_input_columns=list(FEATURES[2:]), availability="Conceptually baseline-available only; actual original issue timestamps not verified",
        excludes=[ACD, GROWTH, PROGRESS, *DATES[:2], "Status_Data_Date", "Latest_Project_Finish_Date", "Earliest_Project_Start_Date",
                  "all weather fields", "all costs if later added", "GMM_Topic_Classification", "Task_Type:", "float", "concurrency", "task position", "market conditions", "actual elapsed labels"],
        unit_notes="planned_elapsed_calendar_days uses timestamp difference/86400; ODE remains in unverified source units",
        no_fit_or_split=True)
    (output / "feature_contract.json").write_text(json.dumps(features_contract, indent=2) + "\n", encoding="utf-8")
    after = protect() if check_protected else {str(source): hash_file(source)}
    if before != after:
        raise RuntimeError("Protected raw, Stage 1, Ghent or application artifact changed")
    (output / "protected_hashes.json").write_text(json.dumps(before, indent=2) + "\n", encoding="utf-8")
    summary = dict(source=rel(source), source_sha256=hash_file(source), source_archive_sha256=archive_hash,
        inventory_match={"projects": len(projects)==original_inventory["project_records"], "activities": totals["activities"]==original_inventory["activity_records"],
                         "filled_actual_pairs": sum(p["actual_date_pair_filled"] for p in projects)==original_inventory["actual_date_pairs"]},
        project_records=len(projects), activities=totals["activities"], filled_actual_date_pairs=sum(p["actual_date_pair_filled"] for p in projects),
        quality_flag_counts=dict(quality), provenance_counts=dict(provenance), progress_values=dict(progress_counts),
        growth_ratio_checks=dict(ratio_counts), weather_anomaly_counts=dict(weather),
        reused_task_ids_across_projects=sum(len(owners)>1 for owners in task_owners.values()),
        reused_wbs_ids_across_projects=sum(len(owners)>1 for owners in wbs_owners.values()),
        project_pairs_with_shared_task_ids=len(pair_rows), matching_baseline_view_fingerprints=[v for v in fingerprints.values() if len(v)>1],
        independent_projects_verified=0,
        calendar_definitions_found=False, actual_cost_fields_found=[r["field"] for r in dictionary if "cost" in r["field"].lower()],
        all_activities_complete_projects=sum(p["all_activities_reported_complete"] for p in projects),
        task_eligibility=eligibility, verified_labels=0, released_labels=0, protected_files_unchanged=len(before),
        recommendation="Descriptive audit now. Conditional research target: reported completed-activity elapsed calendar duration; not working duration, verified delay or project risk. Original-baseline provenance and identity grouping must be verified before a supervised experiment.",
        label_origin="Institutional historical-schedule context; completed date spans are reported historical candidates, incomplete at-completion values are estimate/placeholder/unknown. No per-row independent verification or simulation flag is supplied.")
    (output / "audit_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_report(output, summary)
    write_provenance(output)
    return summary


def write_provenance(output):
    sources = [
        dict(source="https://doi.org/10.17863/CAM.53890", url="https://www.repository.cam.ac.uk/items/6cb214a6-f52d-4846-b2de-3a2e2a34d431",
             evidence="Institutional schedule dataset; CC BY 4.0; links the 2022 paper; archive SHA checked against local Stage 1 inventory"),
        dict(source="https://itcon.org/papers/2022_04-ITcon-Fitzsimmons.pdf", location="Section 3.1, printed p. 74; limitations pp. 88–89",
             evidence="Describes historical P6/XER data and a filtered 302-project/293263-task study, distinct from this raw export; records can be revised without preserved old schedules"),
        dict(source="https://github.com/fitzsimmonsjp/fitzsimmons_method_data/blob/master/Simulation%20Algorithm.py",
             location="Lines 172–219 and 234–245 in inspected author code",
             evidence="Related author code substitutes planned dates when actual pairs are absent, then counts business days and derives growth. Exact lineage to this JSON is NOT established. Never execute downloaded models/code or apply that fallback as actual data."),
    ]
    (output / "source_provenance.json").write_text(json.dumps(dict(checked_date="2026-11-11", sources=sources,
        unresolved=["Exact paper/code-to-JSON export version correspondence", "Original issued baseline and contractual completion", "Calendar definitions, holidays, hours/day and timezone", "Shared parent projects and snapshots", "Per-row actual-data verification and correction history"]), indent=2) + "\n", encoding="utf-8")


def write_report(output, summary):
    s = summary
    lines = ["# PMI Stage 2.3B — Cambridge activity-level audit", "",
        f"Audited {s['project_records']:,} project keys and {s['activities']:,} activities; {s['filled_actual_date_pairs']:,} rows have both actual-date fields filled. Stage 1 inventory checks: {s['inventory_match']}.",
        "Unique source identifiers are not certified independent projects. No model, split, tuning, imputation or label release was performed.", "",
        "## Which task is supported?", "",
        "Descriptive activity/schedule analysis is supported now. A conditional future target is **reported completed-activity elapsed calendar duration**, defined as (Actual_Finish_Date − Actual_Start_Date).total_seconds()/86400.",
        "It is a reported historical timestamp proxy, not active working time, not a verified contractor measurement, and not IFC-change-caused delay. It requires 100% reported completion, coherent positive dates, matching IDs and finish no later than the project status date.",
        "A future supervised experiment also needs original baseline feature provenance and project/snapshot grouping. No target is recommended for training immediately.", "",
        "| Task | Structural activity candidates | Projects represented | Verified training-ready activities/projects |", "|---|---:|---:|---|"]
    lines += [f"| {r['task']} | {r['structural_candidate_activities']:,} | {r['projects_with_structural_candidates']} | 0 / 0 |" for r in s["task_eligibility"]]
    lines += ["", "Structural counts are separate from verified eligibility. Project-risk zero does not mean no schedule risk; it means no defensible project-level supervised target is present.",
        "Elapsed planned-versus-actual differences are audit values only: an exported planned date is not proof of the original issued baseline.", "",
        "## Units, outcomes and source provenance", "",
        "The [Cambridge repository](https://doi.org/10.17863/CAM.53890) supplies the archive under CC BY 4.0. The [linked paper](https://itcon.org/papers/2022_04-ITcon-Fitzsimmons.pdf) describes a historical P6 sample; its filtered 302/293263 counts differ from this 299/444156 export. Correspondence to that filtered sample is unverified.",
        "Related [author extraction code](https://github.com/fitzsimmonsjp/fitzsimmons_method_data/blob/master/Simulation%20Algorithm.py) provides a warning about substituting planned dates for missing actuals. It does not prove this exact JSON's generation history, and was not executed.",
        "Stored ODE and At_Completion_Duration have no explicit, recoverable calendar contract here. Calendar_ID is a reference, not a definition. Do not infer weekdays, holidays, eight-hour days or unit equivalence from it. Float headers explicitly mix hours and days.",
        "Elapsed timestamp differences have explicit 24-hour calendar-day units; they must never replace working durations silently. Growth is audited as a fraction, despite its percentage name; zero ODE is never divided by or used as a duration-growth label.",
        f"Label provenance categories: {s['provenance_counts']}.",
        "Completed/date-coherent rows are historical as reported, not independently verified; unfinished/missing-actual at-completion values remain estimated/placeholder/unknown. No row is certified simulated or historical merely from the paper's empirical context.", "",
        "## Quality and relationships", "",
        f"Growth-ratio audit: {s['growth_ratio_checks']}.",
        f"Task IDs reused across projects: {s['reused_task_ids_across_projects']}; WBS IDs reused: {s['reused_wbs_ids_across_projects']}; project pairs sharing task IDs: {s['project_pairs_with_shared_task_ids']}.",
        "Use composite project/activity keys. Shared IDs can mean snapshots, shared work or identifier collisions, not necessarily independent observations. project_relationships.csv proposes conservative review, never a split or automatic merge.",
        f"Task_Type equals Task_ID in {s['quality_flag_counts'].get('task_type_duplicates_task_id',0):,} rows, so it cannot identify task-dependent work or milestones. Zero durations are not proven milestones. Completion conflicts and date/zero-span checks remain in the label audit.",
        f"Stored growth disagrees with ACD/ODE minus one in {s['growth_ratio_checks'].get('mismatch',0):,} rows. Matching ordered baseline views (not proven duplicate projects): {s['matching_baseline_view_fingerprints']}.",
        f"Weather sanity flags: {s['weather_anomaly_counts']}. No field realignment or value correction was attempted.",
        f"Explicit cost fields found: {s['actual_cost_fields_found']}. Actual cost would leak outcomes if later joined, but is not invented when absent.", "",
        "## Prediction-time separation", "",
        "candidate_features.csv uses a small allowlist of conceptual baseline descriptors, ODE and planned calendar span/month. All are as-exported, with original baseline timing still unverified; IDs are join metadata, never predictors.",
        "Exclude actual dates, elapsed labels, at-completion duration, growth, progress, status/final project dates, float, task position, concurrency and realized weather. Also exclude pretrained GMM topics (unknown training corpus), unresolved weather alignment and market vintages. Recompute any learned/text/topology transforms from verified baseline inputs within future training groups only.",
        "activity_label_audit.csv retains all raw source values, JSON pointers, completion/chronology eligibility and quality flags. It is not a ready-to-train dataset; no observed elapsed value is passed as an input feature.", "",
        "## Deliverables and preservation", "",
        "data_dictionary.csv covers every observed project, activity, WBS and relationship field with types, missingness, ranges, examples, timing and input policy. task_eligibility.csv and project_audit.csv provide activity/project counts; feature_contract.json documents the allowlist.",
        "source_provenance.json records source locations and unresolved assumptions. protected_hashes.json checks raw sources, Stage 1 models, Ghent verification, IFC/CPM scripts and application files unchanged.",
        "**0 verified/released labels. Descriptive analysis is defensible; conditional reported elapsed-duration research requires the listed provenance and grouping checks first.**"]
    (output / "audit_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    args = parser.parse_args()
    result = audit()
    print(json.dumps({k: result[k] for k in ("project_records", "activities", "task_eligibility", "verified_labels")}, indent=2))
