import csv
import itertools
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from design_cambridge_experiment import (FEATURES, KEYS, OUT, SCENARIOS, TARGET,
    allocate_blocks, assert_disjoint, canonical, composite_key, development_folds,
    hash_file, load_records, split_records, unique_rows, verify_frozen, write_csv)
from design_cambridge_experiment import scope_assessment


def fixture_files(folder):
    eligibility = dict(project_key="P1", activity_key="A1", conservative_group="C1",
        exploratory_retrospective_eligible="True", verified_ground_truth_released="False",
        original_baseline_verified="False", per_record_historical_provenance_verified="False",
        structural_candidate="True", traceable_to_export="True", exploratory_exclusion_reasons="",
        exact_repeated_candidate="False", possible_actual_history_conflict="False", explicit_outcome_text_flag="False",
        actual_start_source="2020-01-01", actual_finish_source="2020-01-08", status_date_source="2020-01-10",
        reported_elapsed_calendar_days="7", source_pointer="/Projects/P1/Activities/A1")
    features = dict(project_key="P1", activity_key="A1", activity_description="install concrete wall",
                    project_type="Buildings", uk_region="North", original_duration_source_units="secret excluded value")
    groups = dict(project_key="P1", conservative_group="C1", content_supported_group="E1", task_ID_only_group="T1")
    policy = [dict(feature=f, allowed_in_minimal_retrospective_experiment="True") for f in FEATURES]
    paths = [folder / name for name in ("eligible.csv", "features.csv", "groups.csv", "policy.csv")]
    for path, rows in zip(paths, ([eligibility], [features], [groups], policy)):
        write_csv(path, rows, tuple(rows[0]))
    return paths, eligibility, features, groups


class CambridgeExperimentDesignTests(unittest.TestCase):
    def test_exact_subset_target_and_intact_dominant_block(self):
        counts = {"dominant": 55, "other": 25, "b": 12, "c": 8}
        allocation = allocate_blocks(counts)
        self.assertEqual(sum(counts[g] for g in counts if allocation[g] == "test"), 20)
        self.assertEqual(allocation["dominant"], "train")
        records = [dict(project_key=g, activity_key=str(i), conservative_group=g)
                   for g, n in counts.items() for i in range(n)]
        assert_disjoint(records, "conservative_group", allocation)

    def test_nearest_feasible_ratio_matches_exhaustive_subsets(self):
        counts = {"a": 56, "b": 29, "c": 11, "d": 4}
        result = allocate_blocks(counts)
        chosen = sum(n for g, n in counts.items() if result[g] == "test")
        sums = {sum(c) for size in range(1, len(counts)) for c in itertools.combinations(counts.values(), size)}
        self.assertEqual(chosen, min(sums, key=lambda n: (abs(n - 20), n)))
        self.assertNotEqual(chosen, 20)

    def test_allocation_is_deterministic_under_input_reordering(self):
        counts = {f"group-{i}": (i % 8) + 1 for i in range(50)}
        self.assertEqual(allocate_blocks(counts), allocate_blocks(dict(reversed(list(counts.items())))))

    def test_empty_single_block_and_invalid_weights_rejected(self):
        for counts in ({}, {"a": 1}, {"a": 0, "b": 2}, {"a": True, "b": 2}, {"a": 1.5, "b": 2}):
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                allocate_blocks(counts)

    def test_validation_folds_never_include_holdout_and_keep_blocks_intact(self):
        counts = {f"g{i}": (100 if i == 0 else 5) for i in range(20)}
        allocation = allocate_blocks(counts)
        folds, loads = development_folds(counts, allocation)
        self.assertEqual(set(folds), {g for g in counts if allocation[g] == "train"})
        self.assertEqual(sum(loads), sum(counts[g] for g in folds))
        self.assertEqual(folds, development_folds(dict(reversed(list(counts.items()))), allocation)[0])

    def test_composite_keys_are_unambiguous_and_not_task_ids_alone(self):
        self.assertNotEqual(canonical(composite_key(dict(project_key="a/b", activity_key="c"))),
                            canonical(composite_key(dict(project_key="a", activity_key="b/c"))))
        self.assertNotEqual(composite_key(dict(project_key="P1", activity_key="1")),
                            composite_key(dict(project_key="P2", activity_key="1")))
        with self.assertRaises(ValueError):
            composite_key(dict(project_key=" P1", activity_key="1"))

    def test_duplicate_feature_and_label_keys_cannot_multiply_join(self):
        for duplicate_index in (0, 1, 2, 3):
            with self.subTest(source=duplicate_index), tempfile.TemporaryDirectory() as temporary:
                paths, _, _, _ = fixture_files(Path(temporary))
                with paths[duplicate_index].open(newline="", encoding="utf-8") as source:
                    rows = list(csv.DictReader(source))
                write_csv(paths[duplicate_index], rows + [rows[0]], tuple(rows[0]))
                with self.assertRaisesRegex(ValueError, "Duplicate key"):
                    load_records(*paths)

    def test_join_uses_allowlist_and_does_not_promote_labels(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths, _, _, _ = fixture_files(Path(temporary))
            rows, groups, checks = load_records(*paths)
            self.assertEqual(checks["eligible_rows"], 1)
            self.assertEqual(rows[0]["target"], 7)
            self.assertTrue(set(FEATURES) <= set(rows[0]))
            self.assertNotIn("original_duration_source_units", rows[0])
            self.assertEqual(groups["P1"]["conservative_group"], "C1")

    def test_missing_join_conflicting_group_and_target_fail_closed(self):
        for change in ("missing_feature", "group", "target", "approval", "extra_feature"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                paths, label, features, groups = fixture_files(Path(temporary))
                if change == "missing_feature":
                    features["activity_key"] = "other"
                    write_csv(paths[1], [features], tuple(features))
                elif change == "group":
                    groups["conservative_group"] = "different"
                    write_csv(paths[2], [groups], tuple(groups))
                elif change == "target":
                    label["reported_elapsed_calendar_days"] = "8"
                    write_csv(paths[0], [label], tuple(label))
                elif change == "approval":
                    label["verified_ground_truth_released"] = "True"
                    write_csv(paths[0], [label], tuple(label))
                else:
                    policies = [dict(feature=f, allowed_in_minimal_retrospective_experiment="True")
                                for f in (*FEATURES, "actual_finish")]
                    write_csv(paths[3], policies, tuple(policies[0]))
                with self.assertRaises(ValueError):
                    load_records(*paths)

    def test_splitting_cannot_depend_on_outcomes_or_categories(self):
        rows = [dict(project_key=str(i), activity_key="1", conservative_group=f"C{i}",
                     content_supported_group=f"E{i}", task_ID_only_group=f"T{i}", target=i + 1,
                     activity_description="wall", project_type="Buildings", uk_region="North") for i in range(40)]
        original = split_records(rows)
        changed = [dict(r, target=10000-r["target"], project_type="different", uk_region="different",
                        activity_description="different") for r in reversed(rows)]
        for name, scenario in split_records(changed).items():
            self.assertEqual(scenario["assignment"], original[name]["assignment"])
            self.assertEqual(scenario["development_folds"], original[name]["development_folds"])

    def test_duplicate_manifest_rows_and_project_overlap_rejected(self):
        row = dict(project_key="P", activity_key="1", block="A")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            assert_disjoint([row, row], "block", {"A": "train"})
        other = dict(project_key="P", activity_key="2", block="B")
        with self.assertRaisesRegex(ValueError, "overlap"):
            assert_disjoint([row, other], "block", {"A": "train", "B": "test"})

    def test_freeze_refuses_input_drift_or_output_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / "design_summary.json").write_text('{"eligible_rows": 1}')
            frozen = dict(protected_inputs={"raw": "original"},
                          outputs={"design_summary.json": hash_file(folder / "design_summary.json")})
            (folder / "design_freeze.json").write_text(json.dumps(frozen))
            self.assertEqual(verify_frozen(folder, {"raw": "original"})["eligible_rows"], 1)
            with self.assertRaisesRegex(ValueError, "inputs changed"):
                verify_frozen(folder, {"raw": "changed"})
            (folder / "design_summary.json").write_text('{}')
            with self.assertRaisesRegex(ValueError, "output changed"):
                verify_frozen(folder, {"raw": "original"})

    def test_row_balance_does_not_certify_representative_holdout(self):
        primary = {"project_type": {"total_variation_distance": .715}}
        review = scope_assessment(primary)
        self.assertFalse(review["credible_representative_conservative_holdout"])
        self.assertTrue(review["grouped_validation_required_for_broader_inference"])
        self.assertFalse(review["diagnostic_review_changed_allocation_or_feature_policy"])

    @unittest.skipUnless((OUT / "design_freeze.json").exists(), "Run Stage 2.3D first")
    def test_full_manifests_preserve_population_no_overlap_and_frozen_protocol(self):
        summary = json.loads((OUT / "design_summary.json").read_text())
        protocol = json.loads((OUT / "holdout_protocol.json").read_text())
        self.assertEqual(summary["eligible_rows"], 180137)
        self.assertEqual(summary["eligible_source_project_ids"], 268)
        self.assertEqual(protocol["features"], list(FEATURES))
        self.assertFalse(summary["model_trained"] or summary["hyperparameters_tuned"] or summary["prediction_model_evaluated"])
        self.assertEqual(summary["verified_historical_labels_released"], 0)
        self.assertEqual(summary["scenarios"]["conservative"]["conservative_blocks_crossing_sides"], 0)
        self.assertEqual(summary["scenarios"]["conservative"]["shared_task_id_project_pairs_crossing"], 0)
        self.assertEqual(summary["scenarios"]["conservative"]["shared_wbs_id_project_pairs_crossing"], 0)
        self.assertFalse(summary["credible_representative_conservative_holdout"])
        prior_keys = None
        for scenario in SCENARIOS:
            rows = list(unique_rows(OUT / f"split_manifest_{scenario}.csv"))
            keys = {composite_key(r) for r in rows}
            self.assertEqual(len(keys), 180137)
            if prior_keys is not None:
                self.assertEqual(keys, prior_keys)
            prior_keys = keys
            groups = {side: {r["block_id"] for r in rows if r["split"] == side} for side in ("train", "test")}
            projects = {side: {r["project_key"] for r in rows if r["split"] == side} for side in ("train", "test")}
            self.assertFalse(groups["train"] & groups["test"])
            self.assertFalse(projects["train"] & projects["test"])
            self.assertTrue(all(r["development_validation_fold"] == "" for r in rows if r["split"] == "test"))
            self.assertTrue(all(json.loads(r["composite_activity_key"]) == list(composite_key(r)) for r in rows))
        with (OUT / "feature_matrix.csv").open(newline="", encoding="utf-8") as source:
            reader = csv.DictReader(source)
            self.assertEqual(reader.fieldnames, ["composite_activity_key", *KEYS, *FEATURES])
            self.assertEqual({composite_key(r) for r in reader}, prior_keys)
        with (OUT / "exploratory_targets.csv").open(newline="", encoding="utf-8") as source:
            rows = list(csv.DictReader(source))
            self.assertTrue(all(r["verified_ground_truth"] == "False" and float(r[TARGET]) > 0 for r in rows))
        freeze = json.loads((OUT / "design_freeze.json").read_text())
        for name, digest in freeze["outputs"].items():
            self.assertEqual(hash_file(OUT / name), digest)
        for name in ("models/duration_v1/model.pt", "app.py", "scripts/schedule_engine.py",
                     "data/processed/stage2/verification_report.md",
                     "data/processed/stage2/cambridge_feasibility/feasibility_summary.json"):
            self.assertEqual(hash_file(ROOT / name), freeze["protected_inputs"][name])


if __name__ == "__main__":
    unittest.main()
