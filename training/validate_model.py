"""Group-aware development-only CV with inner early stopping for the MLP."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.model_selection import GroupKFold

from train_model import FEATURES, ROOT, load_data, score, train


def validate(source: Path, output: Path, *, epochs=2000, patience=150,
             seed=42, repeats=1) -> pd.DataFrame:
    if repeats < 1:
        raise ValueError("repeats must be positive")
    data = load_data(source, FEATURES)
    if data.ProjName.nunique() < 5:
        raise ValueError("Five distinct project groups are required")
    output.mkdir(parents=True, exist_ok=True)
    results, predictions, manifests = [], [], []
    for repeat in range(1, repeats + 1):
        cv = GroupKFold(n_splits=5, shuffle=True, random_state=seed + repeat - 1)
        for fold, (development_idx, evaluation_idx) in enumerate(cv.split(data, groups=data.ProjName), 1):
            folder = output / f"repeat_{repeat}_fold_{fold}"
            folder.mkdir(parents=True, exist_ok=True)
            development, evaluation = data.iloc[development_idx], data.iloc[evaluation_idx]
            dev_path, eval_path = folder / "development.csv", folder / "evaluation.csv"
            development.to_csv(dev_path, index=False)
            evaluation.to_csv(eval_path, index=False)
            result = train(dev_path, eval_path, folder, seed=seed + repeat - 1,
                           epochs=epochs, patience=patience)
            info = result["experiment"]
            manifests.append(dict(repeat=repeat, fold=fold, **info))
            for model, metrics in result["test_metrics"].items():
                results.append(dict(repeat=repeat, fold=fold, model=model, **metrics,
                                    rows_fit=info["rows_fit"], rows_inner_validation=info["rows_validation"],
                                    rows_evaluation=len(evaluation), best_epoch=info["best_epoch"]))
            table = pd.read_csv(folder / "test_predictions.csv")
            table["repeat"], table["fold"] = repeat, fold
            predictions.append(table)
            print(f"Repeat {repeat}, fold {fold}: " + "; ".join(
                f"{name} MAE={metrics['MAE']:.3f}" for name, metrics in result["test_metrics"].items()), flush=True)
    results = pd.DataFrame(results)
    combined = pd.concat(predictions, ignore_index=True)
    results.to_csv(output / "cross_validation.csv", index=False)
    results[results.model == "ridge"].to_csv(output / "ridge_cross_validation.csv", index=False)
    combined.to_csv(output / "out_of_fold_predictions.csv", index=False)
    summary = results.groupby("model")[["MAE", "RMSE", "R2"]].agg(["mean", "std"])
    summary.to_csv(output / "summary.csv")
    (output / "fold_manifest.json").write_text(json.dumps(manifests, indent=2) + "\n", encoding="utf-8")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for model in ("mean", "ridge", "mlp"):
        part = results[results.model == model]
        axes[0].plot(range(1, len(part) + 1), part.MAE, marker="o", label=model)
        axes[1].scatter(combined.ProjDura, combined[f"predicted_{model}"] - combined.ProjDura,
                        alpha=.6, label=model)
    axes[0].set(xlabel="Evaluation fold", ylabel="MAE (source duration units)", title="Development CV errors")
    axes[1].axhline(0, color="black", linestyle="--")
    axes[1].set(xlabel="Actual duration", ylabel="Prediction minus actual", title="Out-of-fold residuals")
    for ax in axes:
        ax.legend()
    fig.tight_layout()
    fig.savefig(output / "validation_errors.png", dpi=160)
    plt.close(fig)
    lines = ["# Duration V1 development validation", "",
             f"{repeats} repetition(s) of grouped five-fold CV on {len(data)} development records.",
             "Original ten-row test file is not loaded. Existing duration_v1 artifacts are unchanged.",
             "MLP stopping uses an inner grouped split; outer evaluation rows never select an epoch.",
             "Preprocessing and all three estimators fit only on the inner fitting subset.",
             "Costs excluded; fixed hyperparameters; no fold-result tuning performed.", "",
             "| Model | MAE mean ± SD | RMSE mean ± SD | R² mean ± SD |",
             "|---|---|---|---|"]
    for model in summary.index:
        values = [f"{summary.loc[model, (metric, 'mean')]:.3f} ± {summary.loc[model, (metric, 'std')]:.3f}"
                  for metric in ("MAE", "RMSE", "R2")]
        lines.append("| " + " | ".join([model, *values]) + " |")
    lines += ["", "## Interpretation and limitations", "",
              "Fold standard deviations describe variation, not confidence intervals; folds share training records.",
              "The initial held-out R² of 0.866 is a different experiment and is not directly comparable to mean CV R².",
              "Inspect each fold's loss_curve.png and loss_history.csv for training/inner-validation gaps.",
              "A lower training loss alone is not evidence of generalization. Outer fold performance is the relevant comparison.",
              "Only 40 records, with uncertain repeated Pr29 identity; units and source license remain unverified.",
              "These are total-duration estimates, not IFC change-related delay estimates.",
              "No new external records have been merged; schema and target compatibility must be established first."]
    (output / "validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(summary.to_string())
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data/processed/mendeley_train.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/processed/duration_validation")
    parser.add_argument("--epochs", type=int, default=2000)
    parser.add_argument("--patience", type=int, default=150)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--repeats", type=int, default=1)
    args = parser.parse_args()
    validate(args.data, args.output_dir, epochs=args.epochs, patience=args.patience,
             seed=args.seed, repeats=args.repeats)
