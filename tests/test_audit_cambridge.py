import csv
import io
import json
import sys
import unittest
from pathlib import Path

import ijson

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from audit_cambridge import (ACD, DATES, FEATURES, GROWTH, ODE, OUT, PROGRESS, FieldAudit,
    RejectDuplicateKeys, audit_activity, date_value, elapsed, field_policy, hash_file, numeric,
    iter_projects, pointer, source_mapping, weather_flags)


def example(**overrides):
    data = {"Task_ID": "A1", "Task_Type:": "A1", ODE: "5", ACD: "7", GROWTH: ".4", PROGRESS: "100",
            DATES[0]: "2020-01-01 08:00", DATES[1]: "2020-01-08 08:00",
            DATES[2]: "2020-01-01 08:00", DATES[3]: "2020-01-06 08:00",
            "Activity_Relationships": "null", "Activity_Description": "Install", "Calendar_ID": 10}
    data.update(overrides)
    return data


PROJECT = {"Project_ID": "P1", "Status_Data_Date": "2020-01-10 00:00", "Project_Type": "Test", "UK_Region": "Test"}


class CambridgeAuditTests(unittest.TestCase):
    def test_complete_dates_create_calendar_proxy_not_verified_working_label(self):
        row, features = audit_activity("P1", PROJECT, "A1", example())
        self.assertEqual(row["candidate_elapsed_calendar_days"], 7)
        self.assertEqual(row["audit_elapsed_deviation_calendar_days"], 2)
        self.assertEqual(row["growth_ratio_check"], "matches_fraction")
        self.assertTrue(row["candidate_elapsed_duration"])
        self.assertFalse(row["verified_working_duration_label"])
        self.assertEqual(set(features), set(FEATURES))
        self.assertIsNone(features["predecessor_count_as_exported"])
        _, no_edges = audit_activity("P1", PROJECT, "A1", example(Activity_Relationships={}))
        self.assertEqual(no_edges["predecessor_count_as_exported"], 0)
        self.assertEqual(row["original_duration_source"], "5")

    def test_missing_actuals_and_unfinished_work_never_use_at_completion_as_actual(self):
        for overrides in ({DATES[0]: "", DATES[1]: ""}, {PROGRESS: "50"}, {PROGRESS: None},
                          {DATES[1]: "2020-01-15 08:00"}, {DATES[1]: "2019-12-30 08:00"}):
            with self.subTest(overrides=overrides):
                row, _ = audit_activity("P1", PROJECT, "A1", example(**overrides))
                self.assertFalse(row["candidate_elapsed_duration"])
                self.assertFalse(row["candidate_stored_duration"])
                self.assertIsNone(row["candidate_elapsed_calendar_days"])
                self.assertEqual(row["at_completion_duration_source"], "7")

    def test_zero_ode_invalid_numbers_and_missing_status_are_audited(self):
        row, _ = audit_activity("P1", PROJECT, "A1", example(**{ODE: "0"}))
        self.assertFalse(row["candidate_stored_growth"])
        self.assertIsNone(row["audit_computed_growth_fraction"])
        self.assertIn("nonpositive_or_invalid_ode", row["label_quality_flags"])
        row, _ = audit_activity("P1", PROJECT | {"Status_Data_Date": ""}, "A1", example())
        self.assertFalse(row["candidate_elapsed_duration"])
        self.assertIsNone(numeric("inf"))
        self.assertIsNone(numeric(True))
        self.assertIsNone(date_value("bad date"))
        self.assertIsNone(date_value("2020-01-01T00:00:00+01:00"))

    def test_fraction_is_not_mislabeled_as_percentage_and_negative_deviation_is_valid(self):
        row, _ = audit_activity("P1", PROJECT, "A1", example(**{GROWTH: "40"}))
        self.assertEqual(row["growth_ratio_check"], "mismatch")
        self.assertFalse(row["candidate_stored_growth"])
        row, _ = audit_activity("P1", PROJECT, "A1", example(**{ACD: "3", GROWTH: "-.4", DATES[1]: "2020-01-04 08:00"}))
        self.assertEqual(row["audit_elapsed_deviation_calendar_days"], -2)
        self.assertEqual(row["growth_ratio_check"], "matches_fraction")

    def test_id_and_feature_leakage_controls(self):
        row, _ = audit_activity("P1", PROJECT, "different", example())
        self.assertFalse(row["candidate_elapsed_duration"])
        _, first = audit_activity("P1", PROJECT, "A1", example())
        _, second = audit_activity("P1", PROJECT | {"Latest_Project_Finish_Date": "2099-01-01"}, "A1",
            example(**{ACD: "900", PROGRESS: "20", GROWTH: "300", DATES[0]: "2099-01-01", DATES[1]: "2099-01-02"}))
        self.assertEqual(first, second)
        for field in (ACD, GROWTH, PROGRESS, DATES[0], DATES[1]):
            self.assertIn("exclude", field_policy("activity", field)[1])

    def test_duplicate_json_keys_rejected_and_null_container_not_a_predecessor(self):
        quote = chr(34)
        value = "{" + quote + "Projects" + quote + ":{" + quote + "P1" + quote + ":{" + quote + "x" + quote + ":1," + quote + "x" + quote + ":2}}}"
        with self.assertRaises(ValueError):
            list(iter_projects(io.BytesIO(value.encode())))
        self.assertEqual(source_mapping("null"), {})
        self.assertEqual(source_mapping(None), {})
        with self.assertRaises(ValueError):
            source_mapping("not a container")
        self.assertEqual(pointer("Projects", "a/b", "~x"), "/Projects/a~1b/~0x")

    def test_dictionary_counts_absent_and_explicit_missing_and_dates(self):
        stats = FieldAudit()
        stats.add("activity", {ODE: "-1", "Actual_Start_Date": "not-a-date"})
        stats.add("activity", {ODE: ""})
        stats.add("activity", {})
        rows = {r["field"]: r for r in stats.rows()}
        self.assertEqual(rows[ODE]["missing_or_absent"], 2)
        self.assertEqual(rows[ODE]["negative_count"], 1)
        self.assertEqual(rows["Actual_Start_Date"]["date_invalid"], 1)
        self.assertEqual(rows["Actual_Start_Date"]["absent"], 2)
        self.assertEqual(elapsed(date_value("2020-01-01T12:00"), date_value("2020-01-02T00:00")), .5)

    def test_weather_mapping_anomalies_are_flagged_not_repaired(self):
        weather = {"Maximum_Monthly_Temperature(C)": "6", "Minimum_Monthly_Temperature(C)": "10.6",
                   "Mean_Monthly_Temperature": "211.9"}
        flags = weather_flags(weather)
        self.assertIn("minimum_temperature_above_maximum", flags)
        self.assertIn("mean_temperature_outside_min_max", flags)
        self.assertEqual(weather["Mean_Monthly_Temperature"], "211.9")

    @unittest.skipUnless((OUT / "audit_summary.json").exists(), "Run the full Cambridge audit first")
    def test_generated_counts_candidates_and_preserved_artifacts(self):
        summary = json.loads((OUT / "audit_summary.json").read_text())
        self.assertEqual(summary["project_records"], 299)
        self.assertEqual(summary["activities"], 444156)
        self.assertEqual(summary["filled_actual_date_pairs"], 258352)
        self.assertTrue(all(summary["inventory_match"].values()))
        inventory = json.loads((ROOT / "data/processed/external_inventory/cambridge_inventory.json").read_text())
        self.assertEqual(summary["source_archive_sha256"], inventory["archive_sha256"])
        self.assertEqual(summary["verified_labels"], 0)
        self.assertEqual(summary["released_labels"], 0)
        contract = json.loads((OUT / "feature_contract.json").read_text())
        self.assertTrue(contract["no_fit_or_split"])
        self.assertEqual(contract["columns"], list(FEATURES))
        with (OUT / "data_dictionary.csv").open(newline="", encoding="utf-8") as file:
            dictionary = list(csv.DictReader(file))
        relationship_missing = next(int(r["missing_or_absent"]) for r in dictionary
                                    if r["level"] == "activity" and r["field"] == "Activity_Relationships")
        with (OUT / "candidate_features.csv").open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            self.assertEqual(reader.fieldnames, list(FEATURES))
            feature_rows = missing_maps = 0
            for feature in reader:
                feature_rows += 1
                missing_maps += feature["predecessor_count_as_exported"] == ""
        self.assertEqual(feature_rows, 444156)
        self.assertEqual(missing_maps, relationship_missing)
        counts = CounterForCandidates()
        with (OUT / "activity_label_audit.csv").open(newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                counts.add(row)
        self.assertEqual(counts.rows, 444156)
        expected = {r["task"]: r for r in summary["task_eligibility"]}
        self.assertEqual(counts.elapsed, expected["reported_completed_elapsed_duration"]["structural_candidate_activities"])
        hashes = json.loads((OUT / "protected_hashes.json").read_text())
        for path in ("data/raw/cambridge/JPF_Anonymised_Project_Data.json.zip", "models/duration_v1/model.pt",
                     "data/processed/stage2/verification_report.md", "scripts/schedule_engine.py", "app.py"):
            self.assertEqual(hash_file(ROOT / path), hashes[path])


class CounterForCandidates:
    def __init__(self):
        self.rows = self.elapsed = 0

    def add(self, row):
        self.rows += 1
        self.elapsed += row["candidate_elapsed_duration"] == "True"
        if row["candidate_elapsed_duration"] == "True":
            assert row["reported_complete"] == "True"
            assert row["actual_finish_after_status"] == "False"
            assert float(row["candidate_elapsed_calendar_days"]) > 0
        assert row["verified_working_duration_label"] == "False"


if __name__ == "__main__":
    unittest.main()
