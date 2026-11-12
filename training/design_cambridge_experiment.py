"""Stage 2.3D: freeze retrospective grouped holdouts without fitting a model.

Allocations use eligible row counts and block IDs only. Outcome and category
diagnostics run after the protocol and manifests have been written. Existing
frozen designs are checked, never silently regenerated.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from audit_cambridge import ROOT, date_value, hash_file, missing

FEASIBILITY = ROOT / "data/processed/stage2/cambridge_feasibility"
AUDIT = ROOT / "data/processed/stage2/cambridge_audit"
OUT = ROOT / "data/processed/stage2/cambridge_experiment_design"
FEATURES = ("activity_description", "project_type", "uk_region")
SCENARIOS = {
    "conservative": "conservative_group",
    "content_supported": "content_supported_group",
    "task_id_only": "task_ID_only_group",
}
SEED = "PMI-Stage2.3D-v1"
VERSION = "PMI-Cambridge-retrospective-v1"
TARGET = "reported_completed_activity_elapsed_calendar_days"
KEYS = ("project_key", "activity_key")


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def composite_key(row):
    values = tuple(row[field] for field in KEYS)
    if any(not value or value != value.strip() for value in values):
        raise ValueError("Missing or noncanonical composite activity key")
    return values


def unique_rows(path, fields=KEYS):
    """Reject duplicates before joining, including noneligible source rows."""
    seen = set()
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        headers = reader.fieldnames or []
        if len(set(headers)) != len(headers) or not set(fields) <= set(headers):
            raise ValueError(f"Invalid or duplicate CSV headers: {path.name}")
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Malformed CSV row in {path.name}")
            key = composite_key(row) if tuple(fields) == KEYS else tuple(row[f] for f in fields)
            if any(not k or k != k.strip() for k in key):
                raise ValueError(f"Missing or noncanonical key in {path.name}")
            if key in seen:
                raise ValueError(f"Duplicate key {key!r} in {path.name}; join refused")
            seen.add(key)
            yield row


def write_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")


def load_records(eligibility, features, grouping, policy):
    policies = list(unique_rows(policy, ("feature",)))
    allowed = {r["feature"] for r in policies if r["allowed_in_minimal_retrospective_experiment"] == "True"}
    if allowed != set(FEATURES):
        raise ValueError("Stage 2.3C feature allowlist changed; explicit protocol revision required")
    groups = {r["project_key"]: r for r in unique_rows(grouping, ("project_key",))}
    labels = {}
    structural_count = 0
    for row in unique_rows(eligibility):
        structural_count += 1
        key = composite_key(row)
        group = groups.get(key[0])
        if group is None or row["conservative_group"] != group["conservative_group"]:
            raise ValueError(f"Missing or conflicting grouping for {key}")
        if row["exploratory_retrospective_eligible"] != "True":
            continue
        if any(row[f] != "False" for f in ("verified_ground_truth_released", "original_baseline_verified",
                                           "per_record_historical_provenance_verified")):
            raise ValueError("Unexpected verification status; do not relabel provenance in this design")
        if row["structural_candidate"] != "True" or row["traceable_to_export"] != "True":
            raise ValueError("Eligible row is not a traceable structural candidate")
        if row["exploratory_exclusion_reasons"] or any(row[f] == "True" for f in
                ("exact_repeated_candidate", "possible_actual_history_conflict", "explicit_outcome_text_flag")):
            raise ValueError("Eligibility contradicts exclusion flags")
        start, finish, status = (date_value(row[f]) for f in
                                ("actual_start_source", "actual_finish_source", "status_date_source"))
        target = float(row["reported_elapsed_calendar_days"])
        if (not math.isfinite(target) or target <= 0 or start is None or finish is None or status is None
                or finish <= start or finish > status
                or not math.isclose((finish - start).total_seconds() / 86400, target, rel_tol=1e-10, abs_tol=1e-8)):
            raise ValueError("Incoherent elapsed calendar target")
        labels[key] = dict(project_key=key[0], activity_key=key[1], composite_activity_key=canonical(key),
                           source_pointer=row["source_pointer"], target=target,
                           **{column: group[column] for column in SCENARIOS.values()})
    joined = set()
    source_feature_rows = 0
    for feature in unique_rows(features):
        source_feature_rows += 1
        key = composite_key(feature)
        if key not in labels:
            continue
        if any(missing(feature[f]) for f in FEATURES):
            raise ValueError(f"Missing allowed feature in an eligible row: {key}")
        labels[key].update({f: feature[f] for f in FEATURES})
        joined.add(key)
    if joined != set(labels):
        raise ValueError("Eligible label keys lack exactly one feature row")
    if not labels:
        raise ValueError("No exploratory eligible records")
    return [labels[key] for key in sorted(labels)], groups, dict(
        structural_rows=structural_count, feature_rows=source_feature_rows,
        eligible_rows=len(labels), duplicate_keys=0, unmatched_eligible_keys=0)


def allocate_blocks(counts, namespace=SEED, test_fraction=0.2):
    """Exact nearest achievable row proportion; no labels or category inputs.

    Subset-sum bitsets retain reachability for deterministic reconstruction.
    Fixed SHA-256 order breaks equal-size choices. Equidistant row totals choose
    the smaller test side. Neither side may be empty.
    """
    if len(counts) < 2 or any(not isinstance(n, int) or isinstance(n, bool) or n <= 0 for n in counts.values()):
        raise ValueError("At least two nonempty evaluation blocks are required")
    if not 0 < test_fraction < 1:
        raise ValueError("Test fraction must lie between zero and one")
    order = sorted(counts, key=lambda key: (fingerprint([namespace, key]), key))
    total = sum(counts.values())
    desired = math.floor(total * test_fraction + 0.5)
    states = [1]
    for key in order:
        states.append(states[-1] | (states[-1] << counts[key]))
    nonempty = states[-1] & ~1 & ~(1 << total)
    if not nonempty:
        raise ValueError("No nonempty grouped allocation")
    lower_bits = nonempty & ((1 << (desired + 1)) - 1)
    lower = lower_bits.bit_length() - 1 if lower_bits else None
    upper_bits = nonempty >> desired
    upper = desired + ((upper_bits & -upper_bits).bit_length() - 1) if upper_bits else None
    chosen = min((v for v in (lower, upper) if v is not None), key=lambda n: (abs(n - desired), n))
    residual = chosen
    test = set()
    for i in range(len(order) - 1, -1, -1):
        if not (states[i] >> residual) & 1:
            test.add(order[i])
            residual -= counts[order[i]]
    if residual != 0 or sum(counts[k] for k in test) != chosen:
        raise AssertionError("Subset reconstruction failed")
    return {key: "test" if key in test else "train" for key in sorted(counts)}


def development_folds(counts, assignment, n_folds=5):
    """Training-only grouped validation plan; no fitting or outcomes used."""
    train = [g for g in counts if assignment[g] == "train"]
    if len(train) < n_folds:
        raise ValueError("Too few development blocks for the fixed validation plan")
    loads = [0] * n_folds
    result = {}
    for group in sorted(train, key=lambda g: (-counts[g], fingerprint([SEED, "inner", g]), g)):
        fold = min(range(n_folds), key=lambda i: (loads[i], i))
        result[group] = fold
        loads[fold] += counts[group]
    return result, loads


def split_records(records):
    scenarios = {}
    for name, column in SCENARIOS.items():
        counts = Counter(r[column] for r in records)
        assignment = allocate_blocks(counts, SEED + ":" + name)
        folds, fold_sizes = development_folds(counts, assignment)
        scenarios[name] = dict(column=column, counts=counts, assignment=assignment,
                               development_folds=folds, development_fold_rows=fold_sizes)
    return scenarios


def assert_disjoint(records, column, assignment):
    sides = {"train": set(), "test": set()}
    projects = {"train": set(), "test": set()}
    seen = set()
    for row in records:
        key = composite_key(row)
        if key in seen:
            raise ValueError("Duplicate activity reached split manifest")
        seen.add(key)
        side = assignment[row[column]]
        sides[side].add(row[column])
        projects[side].add(row["project_key"])
    if not all(sides.values()) or sides["train"] & sides["test"] or projects["train"] & projects["test"]:
        raise ValueError("Group or project overlap across train/test")


def quantile(values, fraction):
    index = (len(values) - 1) * fraction
    low, high = math.floor(index), math.ceil(index)
    return values[low] + (values[high] - values[low]) * (index - low)


def target_summary(rows):
    values = sorted(r["target"] for r in rows)
    return dict(min=min(values), p05=quantile(values, .05), q25=quantile(values, .25),
                median=quantile(values, .5), q75=quantile(values, .75), p95=quantile(values, .95),
                max=max(values), mean=statistics.fmean(values), population_std=statistics.pstdev(values))


def category_diagnostics(train, test, column, dimension):
    categories = sorted({r[dimension] for r in train + test})
    results = []
    frequencies = []
    for side, rows in (("train", train), ("test", test)):
        counts = Counter(r[dimension] for r in rows)
        frequencies.append({c: counts[c] / len(rows) for c in categories})
        for category in categories:
            subset = [r for r in rows if r[dimension] == category]
            results.append(dict(split=side, dimension=dimension, category=category,
                                rows=counts[category], row_share=counts[category] / len(rows),
                                source_project_ids=len({r["project_key"] for r in subset}),
                                blocks=len({r[column] for r in subset})))
    details = dict(total_variation_distance=.5 * sum(abs(frequencies[0][c] - frequencies[1][c]) for c in categories),
                   train_only_categories=[c for c in categories if frequencies[1][c] == 0],
                   test_only_categories=[c for c in categories if frequencies[0][c] == 0])
    return results, details


def identity_crossings(group_rows, assignment, column, pairs):
    project_side = {r["project_key"]: assignment[r[column]] for r in group_rows if r[column] in assignment}
    exposed = [p for p in pairs if p["project_a"] in project_side and p["project_b"] in project_side
               and project_side[p["project_a"]] != project_side[p["project_b"]]]
    return len(exposed)


def diagnose(records, groups, scenarios, task_pairs, wbs_pairs, output):
    summary, categories, targets, bins = {}, [], [], []
    for name, scenario in scenarios.items():
        column, assignment = scenario["column"], scenario["assignment"]
        train, test = ([r for r in records if assignment[r[column]] == side] for side in ("train", "test"))
        details = {}
        for side, rows in (("train", train), ("test", test)):
            counts = Counter(r[column] for r in rows)
            details[side] = dict(rows=len(rows), row_share=len(rows) / len(records), blocks=len(counts),
                                 source_project_ids=len({r["project_key"] for r in rows}),
                                 largest_block_rows=max(counts.values()), largest_block_share=max(counts.values()) / len(rows))
            targets.append(dict(scenario=name, split=side, rows=len(rows), **target_summary(rows)))
            for low, high, label in ((0, 1, "(0,1]"), (1, 7, "(1,7]"), (7, 30, "(7,30]"),
                                     (30, 90, "(30,90]"), (90, 365, "(90,365]"), (365, math.inf, "(365,infinity)")):
                count = sum(low < r["target"] <= high for r in rows)
                bins.append(dict(scenario=name, split=side, elapsed_calendar_days_bin=label, rows=count, row_share=count/len(rows)))
        for dimension in ("project_type", "uk_region"):
            rows, checks = category_diagnostics(train, test, column, dimension)
            categories.extend(dict(scenario=name, **row) for row in rows)
            details[dimension] = checks
        containment = defaultdict(set)
        for row in records:
            containment[row["conservative_group"]].add(assignment[row[column]])
        details.update(conservative_blocks_crossing_sides=sum(len(s) > 1 for s in containment.values()),
                       shared_task_id_project_pairs_crossing=identity_crossings(list(groups.values()), assignment, column, task_pairs),
                       shared_wbs_id_project_pairs_crossing=identity_crossings(list(groups.values()), assignment, column, wbs_pairs),
                       scenario_block_overlap=0, composite_key_overlap=0, source_project_id_overlap=0,
                       development_fold_rows=scenario["development_fold_rows"])
        summary[name] = details
    write_csv(output / "category_distributions.csv", categories, tuple(categories[0]))
    write_csv(output / "target_distributions.csv", targets, tuple(targets[0]))
    write_csv(output / "target_bins.csv", bins, tuple(bins[0]))
    return summary


def protected_inputs():
    paths = []
    for root in ("data/raw", "data/processed", "models", "scripts"):
        paths.extend(p for p in (ROOT / root).rglob("*") if p.is_file() and not p.is_relative_to(OUT)
                     and "__pycache__" not in p.parts)
    paths.extend(ROOT.glob("*.py"))
    paths.extend(ROOT / "training" / name for name in ("train_model.py", "validate_model.py", "prepare_ghent_delays.py",
                 "verify_ghent_evidence.py", "audit_cambridge.py", "review_cambridge_feasibility.py"))
    return {p.relative_to(ROOT).as_posix(): hash_file(p) for p in sorted(set(paths)) if p.is_file()}


def verify_frozen(output, inputs):
    frozen = json.loads((output / "design_freeze.json").read_text(encoding="utf-8"))
    if frozen["protected_inputs"] != inputs:
        raise ValueError("Frozen design inputs changed; create a reviewed new protocol version, not a new holdout")
    for name, expected in frozen["outputs"].items():
        path = output / name
        if not path.is_file() or hash_file(path) != expected:
            raise ValueError(f"Frozen design output changed: {name}; silent regeneration refused")
    return json.loads((output / "design_summary.json").read_text(encoding="utf-8"))


def write_design(records, groups, scenarios, output, inputs, join_checks, prior_summary):
    feature_fields = ("composite_activity_key", *KEYS, *FEATURES)
    write_csv(output / "feature_matrix.csv", ({f: r[f] for f in feature_fields} for r in records), feature_fields)
    label_fields = ("composite_activity_key", *KEYS, TARGET, "label_class", "verified_ground_truth")
    write_csv(output / "exploratory_targets.csv", (dict(composite_activity_key=r["composite_activity_key"],
        project_key=r["project_key"], activity_key=r["activity_key"], **{TARGET: r["target"]},
        label_class="exploratory_reported_elapsed_calendar_time", verified_ground_truth=False) for r in records), label_fields)
    block_rows = []
    allocations = {}
    for name, scenario in scenarios.items():
        column, counts, assignment = scenario["column"], scenario["counts"], scenario["assignment"]
        assert_disjoint(records, column, assignment)
        fields = ("composite_activity_key", *KEYS, "block_id", "conservative_block_id", "split", "development_validation_fold")
        write_csv(output / f"split_manifest_{name}.csv", (dict(composite_activity_key=r["composite_activity_key"],
            project_key=r["project_key"], activity_key=r["activity_key"], block_id=r[column],
            conservative_block_id=r["conservative_group"], split=assignment[r[column]],
            development_validation_fold=scenario["development_folds"].get(r[column], "")) for r in records), fields)
        for block, count in sorted(counts.items()):
            projects = sorted({r["project_key"] for r in records if r[column] == block})
            block_rows.append(dict(scenario=name, block_id=block, split=assignment[block], rows=count,
                                   eligible_source_project_ids=len(projects), project_ids=canonical(projects),
                                   development_validation_fold=scenario["development_folds"].get(block, "")))
        allocations[name] = dict(test_rows=sum(n for g, n in counts.items() if assignment[g] == "test"),
                                  total_rows=len(records), test_blocks=sum(v == "test" for v in assignment.values()),
                                  total_blocks=len(counts), manifest=f"split_manifest_{name}.csv")
    write_csv(output / "block_assignments.csv", block_rows, tuple(block_rows[0]))
    artifact_hashes = {p.name: hash_file(p) for p in sorted(output.glob("*.csv"))}
    protocol = dict(version=VERSION, status="frozen_proposal_before_any_model_training", seed_namespace=SEED,
        target=dict(name=TARGET, formula="(Actual_Finish_Date - Actual_Start_Date).total_seconds()/86400",
                    unit="naive elapsed calendar days", verified_historical_ground_truth=False,
                    excludes_claims=["working duration", "adjusted AOD", "IFC-induced delay", "prospective forecast"]),
        features=list(FEATURES), feature_provenance="as-exported; original prediction-time availability unverified",
        label_provenance="exploratory reported timestamps; no verified historical labels released",
        eligibility="unchanged Stage 2.3C eligible population; no outcome trimming, imputation or new exclusions",
        primary="conservative", sensitivity=["content_supported", "task_id_only"],
        allocation=dict(method="exact subset-sum nearest 20% of eligible rows, intact evaluation blocks",
                        decision_inputs=["block IDs", "eligible row counts", "fixed namespace seed"],
                        tie_break="SHA-256 block order; nearest integer row target, lower row total on equal distance",
                        target_test_fraction=.2, exact_ratio_required=False, outcome_or_category_balancing=False,
                        seeds_searched=0, alternative_allocations_selected_using_diagnostics=False),
        validation=dict(scope="training rows only", folds=5, method="largest-block-first into smallest row-count fold; deterministic SHA-256 ties",
                        unequal_fold_sizes_allowed=True, holdout_in_transformer_fitting=False,
                        learned_text_vocabulary_and_category_mapping="fit inside each development training fold; unknown categories supported",
                        metrics=["MAE in elapsed calendar days", "RMSE in elapsed calendar days", "macro block MAE", "per-block errors"],
                        model_selection="training-only grouped validation, mean macro-block MAE; no holdout-based choices",
                        large_block="report validation with this block withheld separately; do not split it to balance folds"),
        holdout_rules=["No holdout outcomes for feature selection, model choice, tuning, early stopping, scaling or vocabulary fitting",
                       "Target/category tables are post-allocation descriptive diagnostics; no allocation reselection",
                       "Complete and lock primary models/configuration and primary final results before sensitivity fitting",
                       "Sensitivity train sets can contain primary holdout rows; sensitivity results must never feed back into primary choices",
                       "Freeze candidate models and hyperparameters using development data before opening test results",
                       "Report all predeclared scenarios; do not choose the best split or grouping by test performance",
                       "No inference about independently verified projects, historical ground truth, working days or deployment readiness"],
        diagnostics_credibility_rule=dict(checked_after_freeze=True, near_80_20_test_range=[.15,.25],
                                         minimum_train_and_test_blocks=20,
                                         use="structural limited-holdout feasibility only, not proof of generalization"),
        allocations=allocations, join_validation=join_checks,
        prior_stage_counts=prior_summary, protected_input_digest=fingerprint(inputs),
        frozen_data_artifacts=artifact_hashes, diagnostic_outcomes_used_for_protocol_selection=False,
        model_trained=False, hyperparameters_tuned=False, prediction_model_evaluated=False)
    # The protocol and data assignments are frozen before examining distributions.
    protocol["protocol_id"] = fingerprint(protocol)
    write_json(output / "holdout_protocol.json", protocol)
    return protocol


def dominant_review(records, scenarios, groups):
    counts = scenarios["conservative"]["counts"]
    dominant = min(counts, key=lambda g: (-counts[g], g))
    rows = [r for r in records if r["conservative_group"] == dominant]
    project_ids = sorted(r["project_key"] for r in groups.values() if r["conservative_group"] == dominant)
    return dict(block_id=dominant, eligible_rows=len(rows), eligible_row_share=len(rows)/len(records),
                all_source_project_ids=project_ids, all_source_project_id_count=len(project_ids),
                eligible_source_project_id_count=len({r["project_key"] for r in rows}),
                assigned=scenarios["conservative"]["assignment"][dominant],
                minimum_test_share_if_held_out=len(rows)/len(records),
                maximum_train_share_if_held_out=1-len(rows)/len(records),
                eligible_project_types=dict(sorted(Counter(r["project_type"] for r in rows).items())),
                eligible_regions=dict(sorted(Counter(r["uk_region"] for r in rows).items())),
                interpretation="Conservative connectivity component from uncertain shared IDs/histories; not a verified physical project",
                can_be_test_in_near_80_20=False,
                can_be_train_with_near_80_20="see conservative allocation; concentration persists in development",
                balanced_evaluation_of_all_blocks_possible=False)


def scope_assessment(primary):
    """Interpret diagnostics without changing features, assignments or protocol."""
    return dict(
        holdout_scope="limited_retrospective_distribution_shift_experiment",
        credible_representative_conservative_holdout=False,
        representative_holdout_limitation="An unseen 55.3% block cannot fit a near-20% test set; substantial category shift and missing test types remain",
        grouped_validation_required_for_broader_inference=True,
        observed_project_type_total_variation=primary["project_type"]["total_variation_distance"],
        diagnostic_review_changed_allocation_or_feature_policy=False)


def render_report(output, summary, protocol):
    decision = ("The conservative holdout is structurally valid and row-balanced. Training can proceed for a limited "
                "retrospective experiment under distribution shift. A credible representative near-80/20 holdout "
                "covering an unseen dominant block is unavailable. Use conservative grouped validation for broader inference. "
                if summary["structurally_credible_limited_conservative_holdout"] else
                "A credible conservative holdout failed the predeclared structural requirements. "
                "Use conservative group-based validation instead of weakening grouping or forcing 80/20. ")
    lines = ["# PMI Stage 2.3D — Cambridge retrospective experiment design", "", "## Decision", "",
        decision +
        "It evaluates exported activity text and context against reported elapsed calendar time. "
        "It cannot establish representative performance over all project histories or pre-execution forecasting accuracy.", "",
        f"The unchanged eligible population contains {summary['eligible_rows']:,} activities across "
        f"{summary['eligible_source_project_ids']} source IDs. Verified historical labels and verified baseline features remain zero.", "",
        "## Frozen allocations", "", "| Scenario | Train rows | Test rows | Test % | Train/test blocks | Conservative blocks crossing |", "|---|---:|---:|---:|---:|---:|"]
    for name, stats in summary["scenarios"].items():
        lines.append(f"| {name} | {stats['train']['rows']:,} | {stats['test']['rows']:,} | "
                     f"{stats['test']['row_share']:.4%} | {stats['train']['blocks']}/{stats['test']['blocks']} | "
                     f"{stats['conservative_blocks_crossing_sides']} |")
    d = summary["dominant_block"]
    primary = summary["scenarios"]["conservative"]
    lines += ["", "Conservative grouping is primary and retains all proposed identity/history links. "
        "Each sensitivity manifest preserves its own blocks, but can separate uncertain relationships retained by the conservative scenario. "
        "Sensitivity allocations are not equally strong evidence of leakage control or project independence.", "",
        "## Dominant block", "",
        f"`{d['block_id']}` contains {d['eligible_rows']:,} eligible rows ({d['eligible_row_share']:.1%}), "
        f"{d['eligible_source_project_id_count']} eligible source IDs and {d['all_source_project_id_count']} source IDs overall. "
        "It remains intact in training. If placed in test, the test fraction must be at least "
        f"{d['minimum_test_share_if_held_out']:.1%}, leaving at most {d['maximum_train_share_if_held_out']:.1%} for training. "
        "Thus it cannot be an approximately 20% test block.", "",
        f"Within the chosen primary training set its row share is {primary['train']['largest_block_share']:.1%}. "
        "Training can use an approximately 80/20 allocation, but it remains concentrated and tests the remaining blocks. "
        "The single holdout does not answer performance on an unseen dominant history. The block can span unrelated projects because shared IDs may collide.", "",
        "## Target, inputs and joins", "",
        "Target: `(Actual_Finish_Date - Actual_Start_Date).total_seconds()/86400`, restricted to the existing "
        "completed, temporally coherent eligible activities. Units are naive elapsed calendar days. "
        "No working-calendar conversion, causal delay attribution, target clipping or imputation is applied.", "",
        "Only `activity_description`, `project_type` and `uk_region` enter `feature_matrix.csv`. "
        "Composite JSON-array keys, IDs and block memberships are join/evaluation metadata. "
        "Targets reside separately in `exploratory_targets.csv` and carry an explicit unverified flag. "
        "The exported text/context may include later edits. Existing outcome-phrase exclusions remain unchanged and do not prove the remaining text is clean.", "",
        "Unique composite keys are checked on both sources before joining. Duplicate keys, missing matches, contradictory "
        "eligibility flags, group mismatches or incoherent target timestamps stop preparation. "
        "No source row is multiplied or silently resolved by first-match lookup.", "",
        "## Distribution diagnostics", "",
        "Allocation uses block IDs, row counts and a fixed hash namespace only. Exact subset-sum chooses the nearest "
        "achievable 20% row count. There is no seed search, target stratification or category-driven reselection. "
        "Protocol/manifests are written before calculating outcome and category diagnostics.", "",
        "`target_distributions.csv` reports min, p05, quartiles, p95, max, mean and standard deviation in calendar days. "
        "`target_bins.csv` uses fixed elapsed-time intervals. `category_distributions.csv` includes zero-count categories, "
        "row shares and source-ID/block counts for project type and region. `design_summary.json` reports category "
        "coverage gaps and total variation distances. Differences are reported without changing the holdout.", ""]
    target_rows = list(unique_rows(output / "target_distributions.csv", ("scenario", "split")))
    lines += ["| Primary side | Median days | p95 days | Mean days | Maximum days |", "|---|---:|---:|---:|---:|"]
    for row in target_rows:
        if row["scenario"] == "conservative":
            lines.append(f"| {row['split']} | {float(row['median']):.2f} | {float(row['p95']):.2f} | {float(row['mean']):.2f} | {float(row['max']):.2f} |")
    for dimension in ("project_type", "uk_region"):
        stats = primary[dimension]
        lines += ["", f"Primary {dimension}: row-share total variation distance {stats['total_variation_distance']:.3f}. "
            f"Train-only categories: {', '.join(stats['train_only_categories']) or 'none'}. "
            f"Test-only categories: {', '.join(stats['test_only_categories']) or 'none'}."]
    lines += ["", "The project-type imbalance is severe. The primary 80/20 row ratio does not provide balanced "
        "sector coverage: four types have no test observations. The dominant block accounts for 69.1% of development "
        "rows and cannot be represented as unseen test work in this allocation. Treat final holdout results as "
        "performance on this shifted collection of blocks, not a corpus-wide estimate. These diagnostics do not trigger "
        "a new allocation, feature change or weaker grouping."]
    lines += ["", "## Holdout and validation protocol", "",
        f"Protocol `{protocol['protocol_id']}` is frozen in `holdout_protocol.json`. "
        "`design_freeze.json` checksums the protocol, data, manifests and diagnostics. A rerun verifies these files and inputs "
        "without selecting another allocation. Input or output drift requires a separately reviewed new version.", "",
        "Fit text vocabularies, encoders, normalizers and category mappings within development training folds only. "
        "Use the five frozen development folds for model choice, hyperparameters and early stopping. "
        "Select using mean macro-block MAE, and report row-weighted MAE/RMSE plus per-block errors. "
        "Refit only on primary training rows after configuration is locked. Compute primary holdout prediction metrics once for the final report. "
        "Aggregate target statistics have already been inspected for this design review; the labels are not claimed to be fully blind. "
        "Holdout outcomes must not influence feature/model choice, tuning, early stopping or preprocessing.", "",
        f"Primary development fold sizes: {primary['development_fold_rows']}. "
        "A balanced fivefold partition is impossible when one block dominates development rows. "
        "The largest-block-first allocation keeps it intact and exposes it as one validation fold. "
        "Report that fold separately and aggregate errors per block. For broader generalization research, use conservative "
        "leave-one-block-out or these explicitly unequal grouped folds, with group-level reporting. "
        "A single representative balanced holdout covering an unseen dominant block is not available; never split it or switch "
        "to a weaker grouping to conceal this limitation.", "",
        "Sensitivity protocols are predeclared final analyses. Run them only after primary configuration and final results "
        "are locked, using the locked configuration without holdout-based tuning. Their training populations may include "
        "primary holdout rows, so no sensitivity result may feed back into primary decisions. "
        "Unknown shared histories and namespace collisions remain unresolved in all scenarios.", "",
        "No prediction model was trained, tuned or evaluated. No verified labels were released. "
        f"All {summary['protected_files_unchanged']} protected existing inputs were unchanged.", ""]
    (output / "design_report.md").write_text("\n".join(lines), encoding="utf-8")


def run(output=OUT):
    output = output.resolve()
    if not output.is_relative_to(OUT.resolve()):
        raise ValueError("Outputs must stay under cambridge_experiment_design")
    before = protected_inputs()
    if (output / "design_freeze.json").exists():
        summary = verify_frozen(output, before)
        print(f"Frozen design verified unchanged: {summary['eligible_rows']:,} rows", flush=True)
        return summary
    if output.exists() and any(output.iterdir()):
        raise ValueError("Nonempty unfrozen output directory; refusing to overwrite an existing proposal")
    prior = json.loads((FEASIBILITY / "feasibility_summary.json").read_text(encoding="utf-8"))
    # Read the report and previous history proposals explicitly; grouping is not rebuilt.
    if not (FEASIBILITY / "feasibility_report.md").read_text(encoding="utf-8").strip():
        raise ValueError("Missing feasibility report")
    records, groups, checks = load_records(FEASIBILITY / "exploratory_eligibility.csv",
        AUDIT / "candidate_features.csv", FEASIBILITY / "grouping_proposal.csv", FEASIBILITY / "feature_provenance_policy.csv")
    if (checks["eligible_rows"] != prior["exploratory_retrospective_eligible"]
            or checks["structural_rows"] != prior["structural_candidates"]
            or checks["feature_rows"] != prior["audited_records"]):
        raise ValueError("Population differs from Stage 2.3C")
    scenarios = split_records(records)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".build-", dir=output) as staging:
        work = Path(staging)
        protocol = write_design(records, groups, scenarios, work, before, checks, prior)
        print("Protocol and allocation manifests frozen; calculating descriptive diagnostics", flush=True)
        task_pairs = list(unique_rows(FEASIBILITY / "activity_identity_pair_review.csv", ("project_a", "project_b")))
        wbs_pairs = list(unique_rows(FEASIBILITY / "wbs_identity_pair_review.csv", ("project_a", "project_b")))
        diagnostics = diagnose(records, groups, scenarios, task_pairs, wbs_pairs, work)
        primary = diagnostics["conservative"]
        structural_feasible = (.15 <= primary["test"]["row_share"] <= .25
            and min(primary[s]["blocks"] for s in ("train", "test")) >= 20
            and primary["conservative_blocks_crossing_sides"] == 0
            and primary["shared_task_id_project_pairs_crossing"] == 0
            and primary["shared_wbs_id_project_pairs_crossing"] == 0)
        summary = dict(version=VERSION, protocol_id=protocol["protocol_id"], eligible_rows=len(records),
            eligible_source_project_ids=len({r["project_key"] for r in records}), scenarios=diagnostics,
            dominant_block=dominant_review(records, scenarios, groups), join_validation=checks,
            structurally_credible_limited_conservative_holdout=structural_feasible,
            representative_balanced_holdout_covering_unseen_dominant_block=False,
            training_can_proceed_for_limited_retrospective_scope=structural_feasible,
            verified_historical_labels_released=0, prospective_claim_supported=False,
            model_trained=False, hyperparameters_tuned=False, prediction_model_evaluated=False,
            protected_files_unchanged=len(before))
        summary.update(scope_assessment(primary))
        write_json(work / "design_summary.json", summary)
        render_report(work, summary, protocol)
        if protected_inputs() != before:
            raise RuntimeError("Protected inputs changed during design preparation")
        freeze = dict(version=VERSION, protocol_id=protocol["protocol_id"], protected_inputs=before,
                      outputs={p.name: hash_file(p) for p in sorted(work.iterdir()) if p.is_file()},
                      rule="Verify on rerun; no silent reseeding, new allocation, input update or output overwrite")
        write_json(work / "design_freeze.json", freeze)
        for path in sorted(work.iterdir(), key=lambda p: p.name == "design_freeze.json"):
            path.replace(output / path.name)
    print(json.dumps({"eligible_rows": len(records), "primary": primary,
                      "protected_files_unchanged": len(before)}, indent=2), flush=True)
    return summary


if __name__ == "__main__":
    run()
