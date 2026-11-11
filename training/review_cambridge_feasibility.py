"""Stage 2.3C: provenance, project-history grouping and exploratory eligibility.

This is a review, not model training or a label-release operation. All grouping
rules are conservative review heuristics, fixed before any model evaluation.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from itertools import combinations, zip_longest
from pathlib import Path

from audit_cambridge import (ACD, ODE, ROOT, SOURCE, OUT as AUDIT, date_value, hash_file,
                            iter_projects, missing, numeric, pointer, protect, source_mapping, text)

OUT = ROOT / "data/processed/stage2/cambridge_feasibility"
MINIMAL_FEATURES = ("project_type", "uk_region", "activity_description")
OUTCOME_TEXT = re.compile(r"\b(?:actual duration|completed on|finished on|as[ -]built|delay of)\b", re.I)


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def write_csv(path, rows, fields=None):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields or list(rows[0] if rows else ["none"]))
        writer.writeheader()
        writer.writerows(rows)


def normalize(value):
    return " ".join(text(value).casefold().split())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


class Groups:
    def __init__(self, keys):
        self.parent = {key: key for key in keys}

    def find(self, key):
        while self.parent[key] != key:
            self.parent[key] = self.parent[self.parent[key]]
            key = self.parent[key]
        return key

    def join(self, left, right):
        a, b = self.find(left), self.find(right)
        self.parent[max(a, b)] = min(a, b)

    def assignments(self, prefix):
        members = defaultdict(list)
        for key in sorted(self.parent):
            members[self.find(key)].append(key)
        result = {}
        for values in members.values():
            identifier = prefix + digest(values)[:12]
            for key in values:
                result[key] = identifier
        return result


def snapshot_signature(project, activity):
    description = normalize(activity.get("Activity_Description"))
    context = (normalize(project.get("Project_Type")), normalize(project.get("UK_Region")))
    baseline = (text(activity.get("Planned_Start_Date")), text(activity.get("Planned_Finish_Date")), text(activity.get(ODE)))
    actual = (text(activity.get("Actual_Start_Date")), text(activity.get("Actual_Finish_Date")))
    return dict(description=description, context=context, baseline=baseline, actual=actual,
                distinctive=len(description.split()) >= 3 and len(description) >= 20,
                baseline_present=all(not missing(v) for v in baseline),
                actual_present=all(not missing(v) for v in actual))


def compare_shared(left, right):
    shared = sorted(set(left) & set(right))
    counts = Counter()
    affected = []
    examples = []
    for task_id in shared:
        a, b = left[task_id], right[task_id]
        same_text = bool(a["description"]) and a["description"] == b["description"]
        same_context = a["context"] == b["context"]
        same_plan = a["baseline_present"] and b["baseline_present"] and a["baseline"] == b["baseline"]
        same_actual = a["actual_present"] and b["actual_present"] and a["actual"] == b["actual"]
        counts["same_description"] += same_text
        counts["same_context"] += same_context
        counts["same_baseline_tuple"] += bool(same_plan)
        counts["same_actual_pair"] += bool(same_actual)
        strong = same_text and a["distinctive"] and same_context and same_plan
        counts["corroborated_baseline_rows"] += bool(strong)
        counts["possible_baseline_revision_or_copy"] += bool(same_text and a["distinctive"] and a["baseline"] != b["baseline"])
        conflict = strong and a["actual_present"] and b["actual_present"] and not same_actual
        counts["same_baseline_conflicting_actuals"] += bool(conflict)
        if conflict:
            affected.append(task_id)
        if len(examples) < 3:
            examples.append(dict(task_id=task_id, left=a, right=b))
    return {key: counts[key] for key in ("same_description", "same_context", "same_baseline_tuple", "same_actual_pair",
            "corroborated_baseline_rows", "possible_baseline_revision_or_copy", "same_baseline_conflicting_actuals")} | dict(
            shared_ids=len(shared), affected_ids=affected, examples=examples)


def protected_hashes():
    prefix = OUT.relative_to(ROOT).as_posix() + "/"
    saved = {name: value for name, value in protect().items() if not name.startswith(prefix)}
    # Stage 2.3B's protector excludes its own output; this review must preserve it too.
    saved.update({p.relative_to(ROOT).as_posix(): hash_file(p) for p in AUDIT.rglob("*") if p.is_file()})
    return saved


def collect_shared_details(shared_ids):
    details = defaultdict(dict)
    wbs_owners = defaultdict(dict)
    with SOURCE.open("rb") as file:
        for index, (project_key, project) in enumerate(iter_projects(file), 1):
            for key, activity in project["Activities"].items():
                if text(activity.get("Task_ID")) in shared_ids:
                    details[text(project_key)][text(activity["Task_ID"])] = snapshot_signature(project, activity)
            for wbs_id, wbs in source_mapping(project.get("Work_Breakdown_Structure")).items():
                wbs_owners[text(wbs_id)][text(project_key)] = normalize(wbs.get("WBS_Description"))
            if index % 50 == 0:
                print(f"Reviewed raw histories: {index} projects", flush=True)
    return details, {key: owners for key, owners in wbs_owners.items() if len(owners) > 1}


def build_group_proposals(projects, pairs, details, shared_wbs, fingerprint_groups):
    keys = [p["project_key"] for p in projects]
    conservative, content_supported, task_only = Groups(keys), Groups(keys), Groups(keys)
    comparison_rows, affected = [], set()
    examples = []
    project_lookup = {p["project_key"]: p for p in projects}
    for pair in pairs:
        a, b = pair["project_key_a"], pair["project_key_b"]
        result = compare_shared(details.get(a, {}), details.get(b, {}))
        if result["shared_ids"] != int(pair["shared_task_ids"]):
            raise ValueError(f"Raw shared-ID count disagrees with Stage 2.3B for {a}/{b}")
        conservative.join(a, b)
        task_only.join(a, b)
        # Evidence heuristic only, never an identity certificate or model hyperparameter.
        strong = (result["corroborated_baseline_rows"] >= 3 and
                  result["corroborated_baseline_rows"] / result["shared_ids"] >= .8 and
                  float(pair["fraction_of_smaller_project"]) >= .5)
        if strong:
            content_supported.join(a, b)
        classification = ("possible_snapshot_or_copied_baseline" if strong else
                          "identifier_collision_plausible" if result["same_description"] == 0 else
                          "mixed_shared_ID_evidence_manual_review")
        for task_id in result["affected_ids"]:
            affected.update(((a, task_id), (b, task_id)))
        examples.append(dict(project_a=a, project_b=b, source=SOURCE.relative_to(ROOT).as_posix(),
            examples=[dict(**example, source_pointer_a=pointer("Projects", a, "Activities", example["task_id"]),
                           source_pointer_b=pointer("Projects", b, "Activities", example["task_id"])) for example in result["examples"]]))
        comparison_rows.append(dict(project_a=a, project_b=b,
            **{k:v for k,v in result.items() if k not in ("affected_ids", "examples")},
            fraction_of_smaller_project=pair["fraction_of_smaller_project"], classification=classification,
            project_type_a=project_lookup[a]["project_type"], project_type_b=project_lookup[b]["project_type"],
            status_date_a=project_lookup[a]["status_date_source"], status_date_b=project_lookup[b]["status_date_source"],
            identity_verified=False, conservative_group_together=True, content_supported_group_proposal=strong))
    wbs_pairs = defaultdict(lambda: Counter(shared_ids=0, same_description=0))
    wbs_examples = defaultdict(list)
    for wbs_id, owners in shared_wbs.items():
        for a, b in combinations(sorted(owners), 2):
            conservative.join(a, b)
            wbs_pairs[(a,b)]["shared_ids"] += 1
            wbs_pairs[(a,b)]["same_description"] += bool(owners[a]) and owners[a] == owners[b]
            if len(wbs_examples[(a,b)]) < 3:
                wbs_examples[(a,b)].append(dict(wbs_id=wbs_id, description_a=owners[a], description_b=owners[b],
                    source_pointer_a=pointer("Projects", a, "Work_Breakdown_Structure", wbs_id),
                    source_pointer_b=pointer("Projects", b, "Work_Breakdown_Structure", wbs_id)))
    wbs_rows = [dict(project_a=a, project_b=b, **counts, evidence_examples=json.dumps(wbs_examples[(a,b)]), identity_verified=False,
                     decision="Keep in same conservative evaluation block; WBS IDs can collide and do not prove a common parent")
                for (a,b), counts in sorted(wbs_pairs.items())]
    for members in fingerprint_groups:
        for other in members[1:]:
            conservative.join(members[0], other)
            content_supported.join(members[0], other)
    maps = dict(conservative=conservative.assignments("C-"), content_supported=content_supported.assignments("E-"),
                task_ID_only=task_only.assignments("T-"))
    rows = []
    for key in sorted(keys):
        rows.append(dict(project_key=key, conservative_group=maps["conservative"][key],
                        content_supported_group=maps["content_supported"][key], task_ID_only_group=maps["task_ID_only"][key],
                        identity_status="unresolved_no_parent_project_registry", independence_verified=False,
                        note="Evaluation containment proposal, not physical-project identity or verified independence"))
    return rows, comparison_rows, wbs_rows, affected, examples


def feature_policy():
    policies = {
        "project_type": ("minimal_context", "Conceptually known before execution; exported classification has no original issue certificate"),
        "uk_region": ("minimal_context", "Geographical context plausibly static; export vintage and parent identity unverified"),
        "activity_description": ("minimal_context", "As-exported text may reflect later scope edits; exclude explicit outcome phrases and frame experiment retrospectively"),
        "wbs_description": ("sensitivity_only_not_default", "May encode parent identity, phase or revised scope; original hierarchy unverified"),
        "original_duration_source_units": ("exclude_until_baseline_and_units_review", "ODE naming does not certify original issuance, units or immutable baseline"),
        "planned_elapsed_calendar_days": ("exclude_until_baseline_review", "Derived from exported planned dates, not an issued baseline; schedule revisions can leak execution knowledge"),
        "planned_start_month": ("exclude_until_baseline_review", "Can change with replanning; not an original-plan calendar feature without version provenance"),
        "predecessor_count_as_exported": ("exclude_until_baseline_review", "Exported topology may include execution corrections; missing maps remain unknown"),
    }
    return [dict(feature=feature, conceptual_prediction_time_availability=reason,
                 verified_baseline_feature=False, provenance_status="as_exported_unverified",
                 exploratory_policy=policy, allowed_in_minimal_retrospective_experiment=feature in MINIMAL_FEATURES,
                 forward_prediction_claim_supported=False) for feature, (policy,reason) in policies.items()]


def eligibility_record(label, features, group, conflict, seen):
    if (label["project_key"], label["activity_key"]) != (features["project_key"], features["activity_key"]):
        raise ValueError("Feature/label key alignment failure")
    structural = label["candidate_elapsed_duration"] == "True"
    if not structural:
        return None
    start, finish, status = [date_value(label.get(field)) for field in
                             ("actual_start_source", "actual_finish_source", "status_date_source")]
    target = numeric(label.get("candidate_elapsed_calendar_days"))
    if (numeric(label.get("physical_percent_source")) != 100 or start is None or finish is None or status is None
            or finish <= start or finish > status or target is None
            or not math.isclose((finish-start).total_seconds()/86400, target, rel_tol=1e-10, abs_tol=1e-8)):
        raise ValueError("Structural-candidate flag contradicts raw progress/dates/elapsed value; re-audit the source")
    description = normalize(features["activity_description"])
    context_complete = bool(description) and not missing(features["project_type"]) and not missing(features["uk_region"])
    outcome_text = bool(OUTCOME_TEXT.search(description))
    key = (label["project_key"], label["activity_key"])
    # Exact review fingerprint within a task-ID namespace, not generic text deduplication.
    signature = digest([label["task_id_source"], features["project_type"], features["uk_region"], description,
        label["original_duration_source"], label["planned_start_source"], label["planned_finish_source"],
        label["actual_start_source"], label["actual_finish_source"]])
    prior = seen.setdefault(signature, "/".join(key))
    duplicate = prior != "/".join(key)
    reasons = []
    if not context_complete:
        reasons.append("minimal_context_missing")
    if outcome_text:
        reasons.append("explicit_outcome_phrase_in_description")
    if key in conflict:
        reasons.append("same_baseline_conflicting_actual_timestamps")
    if duplicate:
        reasons.append("exact_repeated_candidate_keep_first_source_occurrence_only")
    flags = label["label_quality_flags"].split(";")
    return dict(project_key=key[0], activity_key=key[1], conservative_group=group,
        source_pointer=label["source_pointer"], reported_elapsed_calendar_days=label["candidate_elapsed_calendar_days"],
        actual_start_source=label["actual_start_source"], actual_finish_source=label["actual_finish_source"],
        status_date_source=label["status_date_source"], structural_candidate=True,
        traceable_to_export=True, original_baseline_verified=False, per_record_historical_provenance_verified=False,
        independent_project_identity_verified=False, exact_repeated_candidate=duplicate,
        repeated_record_representative=prior, possible_actual_history_conflict=key in conflict,
        possible_revised_baseline=True, baseline_revision_status="possible_not_proven_no_original_issue_history",
        stored_growth_inconsistent="stored_growth_inconsistent" in flags,
        explicit_outcome_text_flag=outcome_text, exploratory_retrospective_eligible=not reasons,
        exploratory_exclusion_reasons=";".join(reasons),
        unresolved_requirements="original_feature_timing;row_level_outcome_provenance;parent_project_identity;timezone_and_calendar_context",
        research_label_class="reported_elapsed_calendar_time_unverified", verified_ground_truth_released=False)


def generate_eligibility(groups, conflict, output):
    group_map = {r["project_key"]:r["conservative_group"] for r in groups}
    totals, exclusion, project_counts, block_counts = Counter(), Counter(), Counter(), Counter()
    all_blocks, structural_projects = set(), set()
    seen = {}
    writer = None
    with (AUDIT / "activity_label_audit.csv").open(newline="", encoding="utf-8") as labels, \
         (AUDIT / "candidate_features.csv").open(newline="", encoding="utf-8") as features, \
         (output / "exploratory_eligibility.csv").open("w", newline="", encoding="utf-8") as destination, \
         (output / "excluded_activity_index.csv").open("w", newline="", encoding="utf-8") as excluded_file:
        excluded_writer = csv.DictWriter(excluded_file, fieldnames=("project_key", "activity_key", "source_pointer", "label_quality_flags"))
        excluded_writer.writeheader()
        for label, feature in zip_longest(csv.DictReader(labels), csv.DictReader(features)):
            if label is None or feature is None:
                raise ValueError("Feature/label row counts differ")
            totals["audited_records"] += 1
            record = eligibility_record(label, feature, group_map[label["project_key"]], conflict, seen)
            if record is None:
                totals["nonstructural_records"] += 1
                excluded_writer.writerow({field:label[field] for field in excluded_writer.fieldnames})
                continue
            if writer is None:
                writer = csv.DictWriter(destination, fieldnames=list(record))
                writer.writeheader()
            writer.writerow(record)
            totals["structural_candidates"] += 1
            structural_projects.add(record["project_key"])
            all_blocks.add(record["conservative_group"])
            for field in ("exact_repeated_candidate", "possible_actual_history_conflict", "explicit_outcome_text_flag", "stored_growth_inconsistent"):
                totals[field] += record[field]
            if record["exploratory_retrospective_eligible"]:
                totals["exploratory_retrospective_eligible"] += 1
                project_counts[record["project_key"]] += 1
                block_counts[record["conservative_group"]] += 1
            for reason in record["exploratory_exclusion_reasons"].split(";"):
                if reason:
                    exclusion[reason] += 1
    totals["structural_project_IDs"] = len(structural_projects)
    totals["structural_conservative_blocks"] = len(all_blocks)
    totals["exploratory_project_IDs"] = len(project_counts)
    totals["exploratory_conservative_blocks"] = len(block_counts)
    return dict(totals), dict(exclusion), project_counts, block_counts


def provenance_review(output):
    # Short evidence notes from the primary publication; no external code/model execution.
    review = dict(checked_date="2026-11-11", sources=[
        dict(url="https://itcon.org/papers/2022_04-ITcon-Fitzsimmons.pdf", location="Section 3.1, p.74; Eq.4 and adjacent text, p.77; limitations pp.88–89",
             evidence="ODE names the original estimate; AOD may adjust finish to successor start for CPM. The study uses historical exports and acknowledges missing old schedule versions. The published filtered sample differs from this raw export."),
        dict(url="https://www.repository.cam.ac.uk/items/6cb214a6-f52d-4846-b2de-3a2e2a34d431", location="Dataset DOI 10.17863/CAM.53890",
             evidence="Institutional archive provides dataset-level source context, not activity-level original-issue certificates."),
        dict(url="https://raw.githubusercontent.com/fitzsimmonsjp/fitzsimmons_method_data/master/Simulation%20Algorithm.py",
             location="Lines 172–219 and 234–245 of inspected related author code",
             evidence="Reads target start/end fields and can substitute planned dates if actuals are missing. Exact generation lineage to this JSON is unverified; code was not executed."),
    ], distinction="Raw timestamp elapsed time is not the paper's adjusted AOD, stored At_Completion_Duration, working time, or IFC-caused delay.",
        findings=dict(verified_original_baseline_features=0, fully_provenance_supported_candidates=0,
                      per_record_provenance_reason="No original-issued version registry, row-level measurement certificate or independent parent-project registry provided"))
    (output / "provenance_review.json").write_text(json.dumps(review, indent=2)+"\n", encoding="utf-8")


def run(output=OUT):
    output = output.resolve()
    if not output.is_relative_to(OUT.resolve()):
        raise ValueError("Outputs must stay under data/processed/stage2/cambridge_feasibility")
    before = protected_hashes()
    audit_summary = json.loads((AUDIT / "audit_summary.json").read_text())
    dictionary = read_csv(AUDIT / "data_dictionary.csv")
    previous_provenance = json.loads((AUDIT / "source_provenance.json").read_text())
    feature_contract = json.loads((AUDIT / "feature_contract.json").read_text())
    projects, pairs = read_csv(AUDIT / "project_audit.csv"), read_csv(AUDIT / "project_relationships.csv")
    if {r["feature"] for r in feature_policy()} != set(feature_contract["candidate_input_columns"]):
        raise ValueError("Feature-policy review does not cover every Stage 2.3B candidate feature")
    counts = Counter()
    with (AUDIT / "activity_label_audit.csv").open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            counts[row["task_id_source"]] += 1
    shared_ids = {key for key, count in counts.items() if count > 1}
    if len(shared_ids) != audit_summary["reused_task_ids_across_projects"]:
        raise ValueError("Reused task ID count differs from Stage 2.3B")
    details, wbs = collect_shared_details(shared_ids)
    grouping, pair_review, wbs_pairs, conflicts, examples = build_group_proposals(projects, pairs, details, wbs,
        audit_summary.get("matching_baseline_view_fingerprints", []))
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "grouping_proposal.csv", grouping)
    write_csv(output / "activity_identity_pair_review.csv", pair_review)
    write_csv(output / "wbs_identity_pair_review.csv", wbs_pairs,
              ("project_a", "project_b", "shared_ids", "same_description", "evidence_examples", "identity_verified", "decision"))
    write_csv(output / "feature_provenance_policy.csv", feature_policy())
    (output / "shared_history_evidence.json").write_text(json.dumps(examples, indent=2)+"\n", encoding="utf-8")
    totals, exclusions, per_project, per_block = generate_eligibility(grouping, conflicts, output)
    if totals["audited_records"] != audit_summary["activities"] or totals["structural_candidates"] != 180335:
        raise ValueError("Eligibility counts differ from audited source")
    scenario_counts = {field:len({row[field] for row in grouping}) for field in
                       ("task_ID_only_group", "content_supported_group", "conservative_group")}
    group_rows = []
    for identifier in sorted({r["conservative_group"] for r in grouping}):
        members = [r["project_key"] for r in grouping if r["conservative_group"] == identifier]
        group_rows.append(dict(conservative_group=identifier, project_ID_count=len(members), project_IDs=";".join(members),
            exploratory_candidates=per_block[identifier], independence_verified=False,
            caution="Containment block, not a confirmed independent physical project"))
    write_csv(output / "evaluation_blocks.csv", group_rows)
    provenance_review(output)
    (output / "input_review_manifest.json").write_text(json.dumps(dict(dictionary_field_count=len(dictionary),
        inspected_provenance=previous_provenance, source_files=before, grouping_rule="Any shared task ID or WBS ID or identical ordered baseline view connects a conservative block; no split",
        content_group_rule="At least 3 distinctive matching baseline rows, >=80% of shared IDs, >=50% smaller-project coverage; review heuristic only",
        minimal_features=list(MINIMAL_FEATURES), field_level_original_baseline_verification=False), indent=2)+"\n", encoding="utf-8")
    after = protected_hashes()
    if before != after:
        raise RuntimeError("Protected raw, audit, model or application inputs changed")
    summary = dict(**totals, exclusion_reasons=exclusions, project_identifier_count=len(projects),
        grouping_scenarios=scenario_counts, independently_verified_project_groups=0,
        largest_conservative_block_project_IDs=max(len(r["project_IDs"].split(";")) for r in group_rows),
        largest_exploratory_block_activities=max(per_block.values(), default=0),
        largest_exploratory_block_share=max(per_block.values(), default=0)/max(totals["exploratory_retrospective_eligible"],1),
        task_pair_review_classifications=dict(Counter(r["classification"] for r in pair_review)),
        shared_task_IDs=len(shared_ids), shared_wbs_IDs=len(wbs), wbs_project_pairs=len(wbs_pairs),
        possible_revised_baseline_pair_count=sum(r["possible_baseline_revision_or_copy"] > 0 for r in pair_review),
        fully_provenance_supported_candidates=0, unresolved_for_verified_ground_truth=totals["structural_candidates"],
        verified_original_baseline_feature_count=0, verified_labels_released=0, split_performed=False,
        model_trained=False, hyperparameters_tuned=False, protected_files_unchanged=len(before),
        retrospective_exploratory_experiment_justified=totals["exploratory_retrospective_eligible"] > 0 and totals["exploratory_conservative_blocks"] >= 5,
        prospective_pre_execution_prediction_justified=False,
        target="Reported completed-activity elapsed calendar days = naive Actual_Finish_Date minus Actual_Start_Date divided by 86400 seconds",
        label_class="Exploratory reported timestamps; not verified historical ground truth, adjusted AOD, working duration or IFC delay",
        future_experiment_policy="Minimal as-exported text/context features only, conservative grouped evaluation, exact repeats excluded, conflict/outcome-text quarantine; no original-baseline or deployment claim")
    (output / "feasibility_summary.json").write_text(json.dumps(summary, indent=2)+"\n", encoding="utf-8")
    write_report(output, summary)
    print(json.dumps(summary, indent=2))
    return summary


def write_report(output, s):
    decision = ("A narrowly scoped **retrospective exploratory supervised experiment is justified in principle**, subject to the grouping and feature policy below."
                if s["retrospective_exploratory_experiment_justified"] else
                "An exploratory supervised experiment is not justified under the current eligibility/grouping policy.")
    lines = ["# PMI Stage 2.3C — Cambridge supervised-learning feasibility", "",
        "## Decision", "",
        decision + " It would ask whether exported task descriptions and coarse context relate to reported elapsed calendar time. This is not a pre-execution schedule forecast or a validation against independently verified historical ground truth.",
        "No experiment was performed here: no split, fitting, tuning or verified-label release.", "",
        "## Candidate and provenance counts", "", "| Category | Count |", "|---|---:|",
        f"| Source activities audited | {s['audited_records']:,} |",
        f"| Structural completed-timestamp candidates | {s['structural_candidates']:,} |",
        f"| Source project IDs represented by structural candidates | {s['structural_project_IDs']} |",
        f"| Exploratory eligible after the explicit review filters | {s['exploratory_retrospective_eligible']:,} |",
        f"| Project IDs / conservative blocks with exploratory candidates | {s['exploratory_project_IDs']} / {s['exploratory_conservative_blocks']} |",
        "| Fully provenance-supported prospective-training candidates | 0 |",
        f"| Structural candidates unresolved as verified ground truth | {s['unresolved_for_verified_ground_truth']:,} |",
        "| Verified baseline features / independently verified project groups | 0 / 0 |",
        "| Verified labels released | 0 |", "",
        "These categories overlap: exploratory eligibility is a research scope, not a provenance approval. Traceability to a raw JSON pointer supports what was reported, not that the report was measured correctly or available before execution.",
        f"Exploratory exclusions (may overlap): {s['exclusion_reasons']}.", "",
        "## Project/history grouping proposal", "",
        f"There are {s['shared_task_IDs']:,} reused task IDs, {s['shared_wbs_IDs']:,} reused WBS IDs and {s['wbs_project_pairs']} project pairs sharing WBS IDs.",
        f"Shared task-ID pair evidence: {s['task_pair_review_classifications']}.",
        f"{s['possible_revised_baseline_pair_count']} pairs have matching distinctive text but changed planned fields: possible revision or copied scope, not proven revision history.",
        "Comparisons check task text, project type/region, planned dates/ODE and actual dates. Shared numeric identifiers with unrelated text suggest namespace collisions; corroborated content suggests snapshots or copied work. Neither proves physical-project identity.",
        f"Scenario block counts across 299 source IDs: {s['grouping_scenarios']}.",
        f"The largest conservative block contains {s['largest_conservative_block_project_IDs']} source project IDs. The largest exploratory block holds {s['largest_exploratory_block_activities']:,} activities ({s['largest_exploratory_block_share']:.1%} of eligible rows). Future evaluation must report both row-weighted and group-level performance; block counts are not effective sample sizes.",
        "Default future evaluation containment: connect all shared task IDs, shared WBS IDs and matching ordered baseline views, including uncertain edges. This deliberately overgroups possible collisions to reduce known cross-evaluation contamination. The content-supported scenario is a sensitivity proposal, not an approved independent grouping.",
        "These are scenario-based evaluation-block counts, not a confidence interval, effective sample size or verified count of independent projects. Hidden shared histories can remain. No IDs were merged in the raw data and no split was created.", "",
        "## Feature timing and recommended target", "",
        "The reviewed primary publication and author-code references are recorded with locations in provenance_review.json. The paper's adjusted AOD is not our raw elapsed-time target. A field named original estimate, or a planned date, is not an original-issued version certificate.",
        "All eight Stage 2.3B candidate features are reviewed in feature_provenance_policy.csv. **None is verified as an original baseline field.**",
        "For retrospective exploration only, permit project_type, uk_region and activity_description as exported; their precise prediction-time provenance remains uncertain. Exclude explicit outcome phrases. WBS description is sensitivity-only because it may encode parent identity or revised scope.",
        "Keyword exclusions are precautions: an as-built drawing can be planned work, so a matching phrase is not proof of leakage. Review these exclusions before a later experiment; do not reinterpret them as confirmed post-execution edits.",
        "Exclude ODE, planned span/month and exported predecessor counts until baseline provenance is resolved. Exclude outcomes, actual/final dates, progress, stored growth/at-completion duration, learned GMM topics, float, concurrency, weather, market vintages and IDs from inputs. Any future text encoder must fit only within future training groups.",
        "Target: `(Actual_Finish_Date - Actual_Start_Date).total_seconds()/86400` for reported 100%-complete activities with positive coherent timestamps and finish no later than the status date. It measures naive elapsed calendar time, not working time, adjusted CPM duration, causation or delay attributable to IFC changes.",
        "The eligibility CSV carries this exploratory research value and unresolved provenance flags; it is not an approved historical-ground-truth dataset. Calendar/timezone interpretation and data-collection authenticity still require source review.", "",
        "## Ambiguity and next step", "",
        f"Exact repeated candidate records flagged: {s.get('exact_repeated_candidate',0):,}; possible same-baseline/conflicting-actual records: {s.get('possible_actual_history_conflict',0):,}. These are quarantined or reduced to a documented first-source representative for exploratory counting only.",
        "Raw/candidate feature and label rows are joined by composite keys with no imputation. excluded_activity_index.csv identifies nonstructural records and their Stage 2.3B quality flags, including incomplete/conflicting progress and incoherent dates. Growth inconsistencies are flagged even when unused by the minimal experiment.",
        "Next, review the highest-content-overlap histories and conflicts in activity_identity_pair_review.csv/shared_history_evidence.json. Seek original-issued schedules and parent registries for a prospective claim. If separately authorized, predeclare a retrospective-only experiment with the minimal feature policy and conservative grouped evaluation; preserve a grouped holdout and compare simple baselines before a neural network. Do not integrate predictions into CPM or claim working-day delay accuracy on this evidence.",
        f"Protected input checks passed for {s['protected_files_unchanged']} files, including Stage 1, Ghent, Stage 2.3B, raw IFC/schedule sources and application files."]
    (output / "feasibility_report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


if __name__ == "__main__":
    run()
