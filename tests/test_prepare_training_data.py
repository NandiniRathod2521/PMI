import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_training_data import prepare_rows
from schedule_engine import impact_of, load_assumptions


class PrepareTrainingDataTests(unittest.TestCase):
    def test_observed_targets_stay_empty_and_synthetic_matches_engine(self):
        events = [dict(global_id="window", ifc_type="IfcWindow", status="MODIFIED",
                       change_types=["property", "geometry"], geometry_changed=True),
                  dict(global_id="unknown", ifc_type="IfcUnknown", status="ADDED",
                       change_types=["added"])]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "revision.json"
            path.write_text(json.dumps({"changes": events}), encoding="utf-8")
            inputs = (path, ROOT / "data/activity_mapping.csv", ROOT / "data/baseline_schedule.csv",
                      ROOT / "data/assumptions.json")
            unlabeled = prepare_rows(*inputs)
            synthetic = prepare_rows(*inputs, synthetic=True)
        self.assertTrue(all(row["actual_extra_days"] == "" for row in synthetic + unlabeled))
        self.assertTrue(all(row["target_extra_days"] == "" for row in unlabeled))
        self.assertEqual(synthetic[0]["activity_id"], "A4")
        self.assertEqual(synthetic[0]["baseline_activity_duration_days"], 8)
        expected = impact_of(events[0], load_assumptions()["impact_rules"])["extra_days"]
        self.assertEqual(synthetic[0]["target_extra_days"], expected)
        self.assertEqual(synthetic[0]["label_source"], "synthetic_rule")
        self.assertEqual(synthetic[1]["mapping_status"], "manual_review")
        self.assertEqual(synthetic[1]["target_extra_days"], "")


if __name__ == "__main__":
    unittest.main()
