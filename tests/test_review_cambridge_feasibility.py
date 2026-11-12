import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from review_cambridge_feasibility import (Groups, MINIMAL_FEATURES, OUT, build_group_proposals,
    compare_shared, eligibility_record, feature_policy, snapshot_signature)
from audit_cambridge import hash_file


def signature(description="install reinforced concrete retaining wall", **changes):
    project = {"Project_Type": "Highways", "UK_Region": "North"}
    activity = {"Activity_Description": description, "Planned_Start_Date": "2020-01-01", "Planned_Finish_Date": "2020-01-06",
                "Original_Duration_Estimate(ODE)": "5", "Actual_Start_Date": "2020-01-01", "Actual_Finish_Date": "2020-01-08"}
    activity.update(changes)
    return snapshot_signature(project, activity)


def label(key="A1", project="P1", **changes):
    row = dict(project_key=project, activity_key=key, task_id_source=key, source_pointer=f"/Projects/{project}/Activities/{key}",
        candidate_elapsed_duration="True", candidate_elapsed_calendar_days="7", actual_start_source="2020-01-01",
        actual_finish_source="2020-01-08", status_date_source="2020-01-10", original_duration_source="5",
        planned_start_source="2020-01-01", planned_finish_source="2020-01-06", physical_percent_source="100", label_quality_flags="")
    row.update(changes)
    return row


def features(project="P1", key="A1", description="install reinforced concrete retaining wall"):
    return dict(project_key=project, activity_key=key, project_type="Highways", uk_region="North", activity_description=description)


class CambridgeFeasibilityTests(unittest.TestCase):
    def test_groups_are_transitive_deterministic_and_do_not_prove_independence(self):
        first, second = Groups(["A", "B", "C"]), Groups(["C", "B", "A"])
        first.join("A", "B")
        first.join("B", "C")
        second.join("C", "B")
        second.join("B", "A")
        self.assertEqual(first.assignments("test-"), second.assignments("test-"))
        self.assertEqual(len(set(first.assignments("test-").values())), 1)

    def test_reused_id_with_different_text_is_not_content_supported_identity(self):
        details = {"P1": {"1": signature()}, "P2": {"1": signature("prepare access road")}}
        projects = [dict(project_key=k, project_type="Highways", status_date_source="2020-01-10") for k in details]
        pair = [dict(project_key_a="P1", project_key_b="P2", shared_task_ids="1", fraction_of_smaller_project="1")]
        rows, review, _, _, _ = build_group_proposals(projects, pair, details, {}, [])
        self.assertEqual(review[0]["classification"], "identifier_collision_plausible")
        self.assertFalse(review[0]["identity_verified"])
        self.assertEqual(rows[0]["conservative_group"], rows[1]["conservative_group"])
        self.assertNotEqual(rows[0]["content_supported_group"], rows[1]["content_supported_group"])
        self.assertTrue(all(not r["independence_verified"] for r in rows))

    def test_copy_evidence_and_actual_conflict_are_flags_not_approvals(self):
        left = {str(i): signature(description=f"install reinforced wall section {i}") for i in range(3)}
        right = dict(left)
        right["1"] = signature(description="install reinforced wall section 1", Actual_Finish_Date="2020-01-09")
        result = compare_shared(left, right)
        self.assertEqual(result["corroborated_baseline_rows"], 3)
        self.assertEqual(result["same_baseline_conflicting_actuals"], 1)
        self.assertEqual(result["affected_ids"], ["1"])

    def test_baseline_view_and_wbs_connections_have_distinct_group_scenarios(self):
        projects = [dict(project_key=k, project_type="Test", status_date_source="2020-01-10") for k in ("A", "B", "C")]
        rows, _, wbs, _, _ = build_group_proposals(projects, [], {}, {"10": {"B": "parent", "C": "parent"}}, [["A", "B"]])
        self.assertEqual(len({r["conservative_group"] for r in rows}), 1)
        self.assertEqual(len({r["content_supported_group"] for r in rows}), 2)
        self.assertEqual(len({r["task_ID_only_group"] for r in rows}), 3)
        self.assertTrue(wbs[0]["evidence_examples"])

    def test_exploratory_label_remains_unverified_and_exact_repeat_is_flagged(self):
        seen = {}
        first = eligibility_record(label(), features(), "group", set(), seen)
        second = eligibility_record(label(project="P2"), features(project="P2"), "group", set(), seen)
        self.assertTrue(first["exploratory_retrospective_eligible"])
        self.assertFalse(first["verified_ground_truth_released"])
        self.assertFalse(first["original_baseline_verified"])
        self.assertFalse(second["exploratory_retrospective_eligible"])
        self.assertTrue(second["exact_repeated_candidate"])

    def test_progress_dates_outcome_text_missing_context_and_alignment(self):
        for changes in (dict(physical_percent_source="50"), dict(actual_finish_source="2020-01-15"),
                        dict(candidate_elapsed_calendar_days="8"), dict(actual_finish_source="bad date")):
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, "contradicts"):
                    eligibility_record(label(**changes), features(), "group", set(), {})
        self.assertIsNone(eligibility_record(label(candidate_elapsed_duration="False"), features(), "group", set(), {}))
        row = eligibility_record(label(), features(description="actual duration 7 days"), "group", set(), {})
        self.assertFalse(row["exploratory_retrospective_eligible"])
        self.assertTrue(row["explicit_outcome_text_flag"])
        row = eligibility_record(label(), features(description=""), "group", set(), {})
        self.assertIn("minimal_context_missing", row["exploratory_exclusion_reasons"])
        with self.assertRaisesRegex(ValueError, "alignment"):
            eligibility_record(label(), features(key="other"), "group", set(), {})

    def test_feature_policy_never_certifies_original_baseline(self):
        policies = feature_policy()
        self.assertEqual(len(policies), 8)
        self.assertTrue(all(not p["verified_baseline_feature"] for p in policies))
        allowed = {p["feature"] for p in policies if p["allowed_in_minimal_retrospective_experiment"]}
        self.assertEqual(allowed, set(MINIMAL_FEATURES))
        self.assertNotIn("original_duration_source_units", allowed)
        self.assertTrue(all(not p["forward_prediction_claim_supported"] for p in policies))

    @unittest.skipUnless((OUT / "feasibility_summary.json").exists(), "Run Stage 2.3C first")
    def test_full_review_counts_no_split_and_input_preservation(self):
        summary = json.loads((OUT / "feasibility_summary.json").read_text())
        self.assertEqual(summary["audited_records"], 444156)
        self.assertEqual(summary["structural_candidates"], 180335)
        self.assertEqual(summary["exploratory_retrospective_eligible"], 180137)
        self.assertEqual(summary["fully_provenance_supported_candidates"], 0)
        self.assertEqual(summary["verified_labels_released"], 0)
        self.assertFalse(summary["model_trained"] or summary["split_performed"] or summary["hyperparameters_tuned"])
        self.assertTrue(summary["retrospective_exploratory_experiment_justified"])
        self.assertFalse(summary["prospective_pre_execution_prediction_justified"])
        with (OUT / "grouping_proposal.csv").open(newline="", encoding="utf-8") as file:
            groups = {r["project_key"]: r for r in csv.DictReader(file)}
        self.assertEqual(len(groups), 299)
        for scenario, expected in summary["grouping_scenarios"].items():
            self.assertEqual(len({r[scenario] for r in groups.values()}), expected)
        with (OUT / "activity_identity_pair_review.csv").open(newline="", encoding="utf-8") as file:
            for pair in csv.DictReader(file):
                self.assertEqual(groups[pair["project_a"]]["conservative_group"], groups[pair["project_b"]]["conservative_group"])
        count = eligible = 0
        with (OUT / "exploratory_eligibility.csv").open(newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                count += 1
                eligible += row["exploratory_retrospective_eligible"] == "True"
                self.assertEqual(row["verified_ground_truth_released"], "False")
        self.assertEqual((count, eligible), (180335, 180137))
        manifest = json.loads((OUT / "input_review_manifest.json").read_text())
        for name in ("models/duration_v1/model.pt", "data/processed/stage2/verification_report.md",
                     "data/processed/stage2/cambridge_audit/audit_summary.json", "scripts/schedule_engine.py", "app.py"):
            self.assertEqual(hash_file(ROOT / name), manifest["source_files"][name])


if __name__ == "__main__":
    unittest.main()
