import json
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_training_dataset import DATASET_FIELDS, build_dataset, load_labels, write_dataset  # noqa: E402


class BuildTrainingDatasetTests(unittest.TestCase):
    def test_rejects_malformed_report_features_even_without_labels(self):
        invalid_changes = [
            {"change_types": "geometry"},
            {"change_types": [["geometry"]]},
            {"change_types": ["unknown"]},
            {"geometry_changed": "false"},
            {"ifc_type": None},
        ]
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "revision.json"
            for override in invalid_changes:
                with self.subTest(override=override):
                    change = dict(global_id="wall-1", ifc_type="IfcWall", status="MODIFIED")
                    change.update(override)
                    report.write_text(json.dumps({"changes": [change]}), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        build_dataset([report], {})
            report.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "JSON object"):
                build_dataset([report], {})

    def test_exports_zero_duration_and_status_features(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "revision.json"
            report.write_text(json.dumps({"changes": [
                dict(global_id=status, ifc_type="IfcWall", status=status,
                     change_types=[status.lower()])
                for status in ("ADDED", "DELETED")
            ]}), encoding="utf-8")
            labels = Path(directory) / "labels.csv"
            labels.write_text(
                "revision_id,global_id,observed_extra_work_days\n"
                "revision,ADDED,0\nrevision,DELETED,1.5\n", encoding="utf-8")
            rows, skipped = build_dataset([report], load_labels(labels))
            output = Path(directory) / "nested" / "dataset.csv"
            write_dataset(output, rows)
            with output.open(newline="", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                self.assertEqual(reader.fieldnames, list(DATASET_FIELDS))
                exported = list(reader)
            self.assertEqual(skipped, 0)
            self.assertEqual(exported[0]["observed_extra_work_days"], "0.0")
            self.assertEqual(exported[0]["added"], "1")
            self.assertEqual(exported[1]["deleted"], "1")
            self.assertEqual(exported[1]["geometry_changed"], "0")

    def test_builds_numeric_change_features_with_observed_label(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "revision_02.json"
            report.write_text(
                json.dumps(
                    {
                        "changes": [
                            {
                                "global_id": "wall-1",
                                "ifc_type": "IfcWall",
                                "status": "MODIFIED",
                                "change_types": ["property", "geometry"],
                                "geometry_changed": True,
                            },
                            {
                                "global_id": "wall-2",
                                "ifc_type": "IfcWall",
                                "status": "UNCHANGED",
                                "change_types": [],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            rows, unlabeled = build_dataset(
                [report], {("revision_02", "wall-1"): 2.5}
            )

        self.assertEqual(unlabeled, 0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["revision_id"], "revision_02")
        self.assertEqual(rows[0]["property_changed"], 1)
        self.assertEqual(rows[0]["geometry_changed"], 1)
        self.assertEqual(rows[0]["modified"], 1)
        self.assertEqual(rows[0]["observed_extra_work_days"], 2.5)

    def test_counts_changed_elements_without_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "revision_01.json"
            report.write_text(
                json.dumps(
                    {
                        "changes": [
                            {
                                "global_id": "door-1",
                                "ifc_type": "IfcDoor",
                                "status": "ADDED",
                                "change_types": ["added"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            rows, unlabeled = build_dataset([report], {})

        self.assertEqual(rows, [])
        self.assertEqual(unlabeled, 1)

    def test_rejects_labels_that_do_not_match_a_changed_element(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "revision_01.json"
            report.write_text(json.dumps({"changes": []}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Labels do not match"):
                build_dataset([report], {("revision_01", "missing"): 1.0})

    def test_load_labels_rejects_negative_observed_duration(self):
        with tempfile.TemporaryDirectory() as directory:
            labels = Path(directory) / "labels.csv"
            labels.write_text(
                "revision_id,global_id,observed_extra_work_days\nrevision_01,wall-1,-1\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "non-negative"):
                load_labels(labels)


if __name__ == "__main__":
    unittest.main()
