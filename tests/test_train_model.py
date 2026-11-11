import sys
import tempfile
import unittest
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from train_model import make_model, train


class DurationTrainingTests(unittest.TestCase):
    def test_saved_model_reproduces_predictions_and_preprocessing_excludes_validation(self):
        train_path = ROOT / "data/processed/mendeley_train.csv"
        test_path = ROOT / "data/processed/mendeley_test.csv"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = train(train_path, test_path, output, epochs=4, patience=2)
            checkpoint = torch.load(output / "model.pt", weights_only=True)
            preprocessing = joblib.load(output / "preprocessing.joblib")
            model = make_model(len(checkpoint["features"]))
            model.load_state_dict(checkpoint["state_dict"])
            model.eval()
            data = pd.read_csv(test_path)
            x = preprocessing["feature_transformer"].transform(data[checkpoint["features"]])
            with torch.no_grad():
                prediction = model(torch.tensor(x, dtype=torch.float32)).numpy()
            prediction = preprocessing["target_scaler"].inverse_transform(prediction).ravel()
            saved = pd.read_csv(output / "test_predictions.csv")
            np.testing.assert_allclose(prediction, saved.predicted_mlp, rtol=1e-6)
            training = pd.read_csv(train_path)
            info = result["experiment"]
            fit = training[training["Sl.no"].isin(info["fit_row_ids"])]
            validation = training[training["Sl.no"].isin(info["validation_row_ids"])]
            self.assertFalse(set(fit.ProjName) & set(validation.ProjName))
            np.testing.assert_allclose(preprocessing["target_scaler"].mean_, [fit.ProjDura.mean()])
            np.testing.assert_allclose(preprocessing["feature_transformer"].named_steps["standardscaler"].mean_,
                                       fit[checkpoint["features"]].mean().to_numpy())
            self.assertEqual(set(result["test_metrics"]), {"mlp", "mean", "ridge"})

    def test_rejects_overlapping_test_projects(self):
        path = ROOT / "data/processed/mendeley_train.csv"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "overlap"):
                train(path, path, Path(directory), epochs=1)


if __name__ == "__main__":
    unittest.main()
