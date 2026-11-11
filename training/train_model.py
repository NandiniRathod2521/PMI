"""Train a duration MLP and evaluate once on PMI's held-out Mendeley test set."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import random
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
import torch
from sklearn.dummy import DummyRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from torch import nn

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ["AreaSite", "BuiltArea", "TowerNum", "TowerHgt", "TowerFlr",
            "BasementNum", "AreaBase", "UnitNum", "AreaUnit"]


def make_model(inputs: int) -> nn.Sequential:
    return nn.Sequential(nn.Linear(inputs, 16), nn.ReLU(), nn.Linear(16, 8),
                         nn.ReLU(), nn.Linear(8, 1))


def load_data(path: Path, features: list[str]) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = ["Sl.no", "ProjName", "ProjDura", *features]
    if set(required) - set(frame.columns):
        raise ValueError(f"{path}: missing required columns")
    if frame[["Sl.no", "ProjName"]].isna().any().any() or frame["Sl.no"].duplicated().any():
        raise ValueError(f"{path}: missing or duplicate row identifiers")
    for name in [*features, "ProjDura"]:
        frame[name] = pd.to_numeric(frame[name], errors="raise")
        if np.isinf(frame[name]).any() or (frame[name].dropna() < 0).any():
            raise ValueError(f"{path}: invalid values in {name}")
    if frame["ProjDura"].isna().any() or (frame["ProjDura"] <= 0).any():
        raise ValueError(f"{path}: target must be present and positive")
    return frame


def score(actual, predicted) -> dict:
    return {"MAE": float(mean_absolute_error(actual, predicted)),
            "RMSE": float(np.sqrt(mean_squared_error(actual, predicted))),
            "R2": float(r2_score(actual, predicted))}


def train(train_path: Path, test_path: Path, output: Path, *, seed: int = 42,
          epochs: int = 2000, patience: int = 150, include_costs: bool = False) -> dict:
    if epochs < 1 or patience < 1:
        raise ValueError("epochs and patience must be positive")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    features = FEATURES + (["SellCost", "ConstCost"] if include_costs else [])
    training = load_data(train_path, features)
    testing = load_data(test_path, features)
    if set(training.ProjName) & set(testing.ProjName) or set(training["Sl.no"]) & set(testing["Sl.no"]):
        raise ValueError("Training/test project or row identifiers overlap")
    if len(testing) < 2 or training.ProjName.nunique() < 3:
        raise ValueError("Insufficient projects for training, validation and R2 evaluation")
    fit_idx, val_idx = next(GroupShuffleSplit(n_splits=1, test_size=.2, random_state=seed)
                            .split(training, groups=training.ProjName))
    fit, validation = training.iloc[fit_idx], training.iloc[val_idx]
    if fit[features].isna().all().any():
        raise ValueError("A feature is entirely missing in the fitting subset")
    preprocessing = make_pipeline(SimpleImputer(strategy="median"), StandardScaler())
    x_fit = preprocessing.fit_transform(fit[features])
    x_val = preprocessing.transform(validation[features])
    target_scaler = StandardScaler().fit(fit[["ProjDura"]])
    y_fit = target_scaler.transform(fit[["ProjDura"]])
    y_val = target_scaler.transform(validation[["ProjDura"]])
    tensors = [torch.tensor(array, dtype=torch.float32) for array in (x_fit, x_val, y_fit, y_val)]
    tx, vx, ty, vy = tensors
    model = make_model(len(features))
    optimizer = torch.optim.Adam(model.parameters(), lr=.001, weight_decay=.001)
    loss_fn = nn.MSELoss()
    best_loss, best_epoch, stale, best_state = float("inf"), 0, 0, None
    history = []
    for epoch in range(1, epochs + 1):
        model.train()
        optimizer.zero_grad()
        loss = loss_fn(model(tx), ty)
        loss.backward()
        optimizer.step()
        model.eval()
        with torch.no_grad():
            train_loss = loss_fn(model(tx), ty).item()
            val_loss = loss_fn(model(vx), vy).item()
        if not np.isfinite([train_loss, val_loss]).all():
            raise ValueError("Training produced non-finite loss")
        history.append(dict(epoch=epoch, train_mse_scaled=train_loss, validation_mse_scaled=val_loss))
        if val_loss < best_loss - 1e-6:
            best_loss, best_epoch, stale = val_loss, epoch, 0
            best_state = copy.deepcopy(model.state_dict())
        else:
            stale += 1
        if stale >= patience:
            break
    model.load_state_dict(best_state)
    model.eval()
    # Fixed baseline settings; no test-set tuning. Same fitting rows as the MLP.
    mean = DummyRegressor(strategy="mean").fit(x_fit, fit.ProjDura)
    ridge = Ridge(alpha=1.0).fit(x_fit, fit.ProjDura)
    x_test = preprocessing.transform(testing[features])
    with torch.no_grad():
        scaled = model(torch.tensor(x_test, dtype=torch.float32)).numpy()
    predictions = {"mlp": target_scaler.inverse_transform(scaled).ravel(),
                   "mean": mean.predict(x_test), "ridge": ridge.predict(x_test)}
    metrics = {name: score(testing.ProjDura, prediction) for name, prediction in predictions.items()}
    metadata = dict(target="ProjDura", task="total_project_duration", duration_unit="unverified",
                    features=features, seed=seed, rows_train_file=len(training), rows_fit=len(fit),
                    rows_validation=len(validation), rows_test=len(testing), best_epoch=best_epoch,
                    epochs_run=len(history), max_epochs=epochs, patience=patience,
                    best_validation_mse_scaled=best_loss, learning_rate=.001, weight_decay=.001,
                    ridge_alpha=1.0, architecture=[len(features), 16, 8, 1],
                    preprocessing_fit="fitting subset only; validation and test excluded",
                    fit_row_ids=fit["Sl.no"].tolist(), validation_row_ids=validation["Sl.no"].tolist(),
                    test_row_ids=testing["Sl.no"].tolist(),
                    input_sha256={str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                                  for path in (train_path, test_path)},
                    versions=dict(python=platform.python_version(), torch=str(torch.__version__),
                                  sklearn=sklearn.__version__, numpy=np.__version__, pandas=pd.__version__),
                    limitations=["Small sample; single held-out split is not strong generalization evidence",
                                 "Repeated Pr29 identity requires source verification",
                                 "Duration units unverified; not an IFC-change delay estimator",
                                 "Cost availability unverified" if include_costs else "Cost features excluded by default"])
    result = {"test_metrics": metrics, "experiment": metadata}
    output.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": best_state, "features": features, "architecture": metadata["architecture"],
                "target": "ProjDura", "duration_unit": "unverified"}, output / "model.pt")
    joblib.dump(dict(features=features, feature_transformer=preprocessing, target_scaler=target_scaler),
                output / "preprocessing.joblib")
    joblib.dump(dict(mean=mean, ridge=ridge), output / "baselines.joblib")
    (output / "metrics.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    table = testing[["Sl.no", "ProjName", "ProjDura"]].copy()
    for name, prediction in predictions.items():
        table[f"predicted_{name}"] = prediction
    table.to_csv(output / "test_predictions.csv", index=False)
    pd.DataFrame(history).to_csv(output / "loss_history.csv", index=False)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot([h["epoch"] for h in history], [h["train_mse_scaled"] for h in history], label="Train")
    ax.plot([h["epoch"] for h in history], [h["validation_mse_scaled"] for h in history], label="Validation")
    ax.axvline(best_epoch, color="gray", linestyle="--", label="Saved epoch")
    ax.set(xlabel="Epoch", ylabel="MSE (standardized target)", title="MLP learning curve")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "loss_curve.png", dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(6, 6))
    for name, prediction in predictions.items():
        ax.scatter(testing.ProjDura, prediction, label=name, alpha=.75)
    limits = [min(testing.ProjDura.min(), *(p.min() for p in predictions.values())),
              max(testing.ProjDura.max(), *(p.max() for p in predictions.values()))]
    ax.plot(limits, limits, "k--", label="Perfect prediction")
    ax.set(xlabel="Actual duration (source units, unverified)", ylabel="Predicted duration",
           title="Held-out project durations")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "actual_vs_predicted.png", dpi=160)
    plt.close(fig)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, default=ROOT / "data/processed/mendeley_train.csv")
    parser.add_argument("--test", type=Path, default=ROOT / "data/processed/mendeley_test.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "models/duration_v1")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=2000)
    parser.add_argument("--patience", type=int, default=150)
    parser.add_argument("--include-costs", action="store_true", help="Only if costs are available at prediction time")
    args = parser.parse_args()
    result = train(args.train, args.test, args.output_dir, seed=args.seed, epochs=args.epochs,
                   patience=args.patience, include_costs=args.include_costs)
    print(f"PyTorch {torch.__version__}; saved best epoch {result['experiment']['best_epoch']}")
    print("Model       MAE       RMSE       R2")
    for name, values in result["test_metrics"].items():
        print(f"{name:8} {values['MAE']:9.3f} {values['RMSE']:9.3f} {values['R2']:9.3f}")
    print(f"Artifacts: {args.output_dir}")
    print("Target is total project duration, units unverified; test sample is small.")


if __name__ == "__main__":
    main()
