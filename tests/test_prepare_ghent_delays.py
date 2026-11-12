import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from prepare_ghent_delays import (FEATURE_COLUMNS, NUMERIC_FEATURES, SOURCE, VERIFICATION_FIELDS,
                                 load_verification, number, overview_definitions, prepare, process_records)


def record(code="C2020-01", **overrides):
    row = dict(project_id=code, project_name="House", sector="Construction (residential building)",
               planned_duration_source=100, real_duration_source=120, planned_duration_original=100,
               real_duration_original=120, project_authenticity="G", tracking_authenticity="G",
               early_late_source=.2, source_excel_row=4, **dict.fromkeys(NUMERIC_FEATURES, 1))
    row.update(overrides)
    return row


def verified():
    return dict(planned_unit="days", real_unit="days", planned_day_basis="working", real_day_basis="working",
                planned_calendar="source calendar A", real_calendar="source calendar A", calendar_comparable="true",
                original_baseline_verified="true", unit_evidence="project metadata: both durations use day units",
                calendar_evidence="same project working-day calendar confirmed",
                baseline_evidence="original issued schedule confirmed", verified_by="test reviewer",
                independence_verified="true", independence_evidence="separate project entity verified")


DOCS = {"definitions": {"planned_real_interpretation_verified": True}}


class PrepareGhentDelaysTests(unittest.TestCase):
    def test_filters_sectors_ids_and_summary_rows(self):
        rows = [record(), record("C2020-02", sector="Construction (commercial building)"),
                record("C2020-03", sector="Construction (institutional building)"),
                record("C2020-04", sector="Construction (civil)"),
                record("C2020-05", sector="Construction (industrial)"),
                record(None), record("C2020-06-extra"), record("2020-07")]
        included, excluded, _ = process_records(rows, DOCS)
        self.assertEqual([r["project_id"] for r in included], ["C2020-01", "C2020-02", "C2020-03"])
        self.assertEqual(len(excluded), 5)
        self.assertTrue(all(r["exclusion_reason"] for r in excluded))

    def test_missing_and_invalid_durations_never_become_zero_targets(self):
        for value, expected in [(None, "missing"), ("N/A", "missing"), ("-", "missing"), ("", "missing"),
                                ("bad", "not_numeric"), (float("inf"), "non_finite"),
                                (True, "not_numeric"), (0, "not_positive"), (-2, "not_positive")]:
            with self.subTest(value=value):
                rows, _, _ = process_records([record(real_duration_source=value)], DOCS, {"C2020-01": verified()})
                self.assertEqual(rows[0]["real_duration_status"], expected)
                self.assertIsNone(rows[0]["real_duration_days"])
                self.assertIsNone(rows[0]["duration_deviation_days"])
                self.assertEqual(rows[0]["real_duration_source"], value)
        self.assertEqual(number(" 120.5 ", positive=True), (120.5, "valid"))

    def test_target_requires_units_calendar_baseline_and_source_definitions(self):
        cases = [({}, DOCS), (verified() | {"real_unit": "hours"}, DOCS),
                 (verified() | {"real_day_basis": "calendar"}, DOCS),
                 (verified() | {"calendar_comparable": "false"}, DOCS),
                 (verified() | {"unit_evidence": ""}, DOCS),
                 (verified() | {"original_baseline_verified": "false"}, DOCS),
                 (verified() | {"verified_by": ""}, DOCS), (verified(), {"definitions": {}})]
        for evidence, docs in cases:
            with self.subTest(evidence=evidence, docs=docs):
                rows, _, _ = process_records([record()], docs, {"C2020-01": evidence})
                self.assertIsNone(rows[0]["duration_deviation_days"])
                self.assertFalse(rows[0]["independently_usable"])

    def test_signed_targets_preserve_original_values(self):
        for actual, expected in [(120, 20), (80, -20), (100, 0)]:
            with self.subTest(actual=actual):
                row = record(real_duration_source=actual, real_duration_original=actual,
                             early_late_source=(actual - 100) / 100)
                rows, _, _ = process_records([row], DOCS, {"C2020-01": verified()})
                self.assertEqual(rows[0]["duration_deviation_days"], expected)
                self.assertEqual(rows[0]["real_duration_original"], actual)
                self.assertEqual(rows[0]["planned_duration_source"], 100)
                self.assertTrue(rows[0]["independently_usable"])

    def test_authenticity_and_independence_are_not_inferred(self):
        row = record(tracking_authenticity="N/A")
        rows, _, _ = process_records([row], DOCS, {"C2020-01": verified()})
        self.assertEqual(rows[0]["tracking_authenticity"], "")
        self.assertEqual(rows[0]["tracking_authenticity_raw"], "N/A")
        self.assertFalse(rows[0]["independently_usable"])
        rows, _, _ = process_records([record()], DOCS,
                                      {"C2020-01": verified() | {"independence_verified": "false"}})
        self.assertEqual(rows[0]["duration_deviation_days"], 20)
        self.assertFalse(rows[0]["independently_usable"])

    def test_duplicate_ids_and_related_phases_are_flagged(self):
        rows, _, _ = process_records([record(), record()], DOCS, {"C2020-01": verified()})
        self.assertTrue(all(r["duplicate_id"] for r in rows))
        self.assertTrue(all(r["duration_deviation_days"] is None for r in rows))
        rows, _, related = process_records([
            record(project_name="Residential House Structural Work"),
            record("C2020-02", project_name="Residential House Finishing Works (2)")], DOCS)
        self.assertEqual(len(related), 1)
        self.assertEqual(rows[0]["review_group_id"], rows[1]["review_group_id"])
        self.assertTrue(all(r["potential_related_projects"] for r in rows))

    def test_contradictory_ratio_and_known_problem_need_documented_resolution(self):
        docs = DOCS | {"Known Problems": [dict(row=4, column=1, value="2020-01"),
                                          dict(row=4, column=3, value="Baseline issue")]}
        row = record(early_late_source=-.5)
        rows, _, _ = process_records([row], docs, {"C2020-01": verified()})
        self.assertEqual(rows[0]["early_late_check"], "mismatch")
        self.assertIn("known_problem_requires_review", rows[0]["target_blockers"])
        self.assertIsNone(rows[0]["duration_deviation_days"])
        attestation = verified() | {"source_issue_reviewed": "true", "source_issue_evidence": "duration pair independently checked"}
        rows, _, _ = process_records([row], docs, {"C2020-01": attestation})
        self.assertEqual(rows[0]["duration_deviation_days"], 20)
        self.assertEqual(rows[0]["early_late_source"], -.5)

    def test_overview_must_explicitly_define_both_durations(self):
        cells = [dict(row=33, column=2, value="PD (days)"),
                 dict(row=33, column=3, value="The planned duration of the project schedule"),
                 dict(row=89, column=2, value="Real duration"),
                 dict(row=89, column=3, value="The real total project duration (known after the project's finish)")]
        self.assertTrue(overview_definitions(cells)["planned_real_interpretation_verified"])
        self.assertFalse(overview_definitions(cells[:2])["planned_real_interpretation_verified"])

    def test_verification_rejects_duplicates_unknown_ids_and_invalid_booleans(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "verification.csv"
            with path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=VERIFICATION_FIELDS)
                writer.writeheader()
                writer.writerows([dict.fromkeys(VERIFICATION_FIELDS, "") | {"project_id": "C2020-01"}] * 2)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_verification(path)
        with self.assertRaisesRegex(ValueError, "absent"):
            process_records([record()], DOCS, {"C2020-09": verified()})
        with self.assertRaisesRegex(ValueError, "boolean"):
            process_records([record()], DOCS, {"C2020-01": verified() | {"calendar_comparable": "maybe"}})

    @unittest.skipUnless(SOURCE.is_file(), "local Ghent source not available")
    def test_real_workbook_counts_outputs_and_source_preservation(self):
        before = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            report = prepare(SOURCE, out)
            self.assertEqual(report["valid_project_records"], 231)
            self.assertEqual(report["valid_building_records"], 87)
            self.assertEqual(report["positive_numeric_duration_pairs"], 68)
            self.assertEqual(report["building_summary_rows_excluded"], 3)
            self.assertEqual(report["project_authenticity_candidates"], {"G": 58, "O": 1, "missing": 9})
            self.assertEqual(report["tracking_authenticity_candidates"], {"G": 56, "Y": 1, "missing": 11})
            self.assertEqual(report["duplicate_ids"], [])
            self.assertEqual(report["independently_usable_projects_confirmed"], 0)
            self.assertEqual(report["verified_target_records"], 0)
            self.assertEqual(report["early_late_checks"]["mismatch"], 10)
            with (out / "ghent_baseline_features.csv").open() as file:
                reader = csv.DictReader(file)
                self.assertEqual(reader.fieldnames, list(FEATURE_COLUMNS))
                self.assertEqual(len(list(reader)), 68)
            with (out / "ghent_verified_labels.csv").open() as file:
                self.assertEqual(list(csv.DictReader(file)), [])
            template = out / "duration_verification_template.csv"
            # Existing evidence templates must survive repeat preparation unchanged.
            original_template = template.read_bytes()
            prepare(SOURCE, out)
            self.assertEqual(template.read_bytes(), original_template)
            docs = json.loads((out / "source_documentation.json").read_text())
            self.assertTrue(docs["Overview"] and docs["Known Problems"])
            self.assertFalse(any("train" in p.stem or "test" in p.stem for p in out.iterdir()))
        self.assertEqual(hashlib.sha256(SOURCE.read_bytes()).hexdigest(), before)


if __name__ == "__main__":
    unittest.main()
