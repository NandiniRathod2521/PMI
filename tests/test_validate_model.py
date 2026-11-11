import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from validate_model import validate


class ValidationTests(unittest.TestCase):
    def test_group_isolation_coverage_and_no_original_test_file(self):
        source = ROOT / "data/processed/mendeley_train.csv"
        data = pd.read_csv(source).set_index("Sl.no")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = validate(source, output, epochs=1, patience=1)
            self.assertEqual(len(result), 15)
            prediction = pd.read_csv(output / "out_of_fold_predictions.csv")
            self.assertEqual(set(prediction["Sl.no"]), set(data.index))
            self.assertTrue((prediction.groupby("Sl.no").size() == 1).all())
            manifest = json.loads((output / "fold_manifest.json").read_text())
            for fold in manifest:
                fit, inner, outer = [set(data.loc[fold[key], "ProjName"]) for key in
                                     ("fit_row_ids", "validation_row_ids", "test_row_ids")]
                self.assertFalse(fit & inner or fit & outer or inner & outer)
                self.assertFalse(any("mendeley_test.csv" in path for path in fold["input_sha256"]))


if __name__ == "__main__":
    unittest.main()
