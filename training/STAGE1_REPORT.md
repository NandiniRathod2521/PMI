# Stage 1 research validation

11 November 2026. The initial held-out experiment reported MLP R² 0.866 on ten
observations. This report investigates robustness without reopening that test
file for training, model selection or cross-validation. The original
`models/duration_v1/` artifacts are preserved.

## Evaluation design

The 40 development records are split with shuffled, grouped five-fold CV.
Records sharing a project name remain together. Every outer training fold has
its own grouped inner early-stopping subset; the outer evaluation fold never
selects the stopping epoch. Preprocessing and all three estimators use the same
24–25 inner fitting records. This is deliberately a small-sample stress test,
not an estimate of a model refitted using all 40 observations. Fixed nine
non-cost features and the original hyperparameters are retained. Three
repetitions use seeds 42, 43 and 44; no hyperparameters were tuned against CV.

## Results

First five-fold run, mean ± sample SD across evaluation folds:

| Model | MAE | RMSE | R² |
|---|---:|---:|---:|
| Mean | 7.491 ± 1.875 | 9.706 ± 1.737 | -0.255 ± 0.301 |
| Ridge | 6.078 ± 1.882 | 7.719 ± 1.944 | 0.183 ± 0.361 |
| MLP | 6.857 ± 2.150 | 9.359 ± 1.925 | -0.198 ± 0.423 |

Three repeated five-fold runs, mean ± sample SD across 15 evaluation folds:

| Model | MAE | RMSE | R² |
|---|---:|---:|---:|
| Mean | 7.263 ± 2.306 | 9.173 ± 2.653 | -0.322 ± 0.407 |
| Ridge | 6.254 ± 1.955 | 7.763 ± 2.212 | -0.182 ± 1.011 |
| MLP | 6.485 ± 1.665 | 8.470 ± 1.976 | -0.278 ± 0.755 |

Ridge has lower mean MAE and RMSE than the MLP in both experiments. Mean fold
R² is negative for all models in repeated CV. These are fold-average R² values,
not pooled out-of-fold R² or percentages of prediction accuracy. Fold scores
are correlated and their standard deviations are not confidence intervals.
The results do not establish that one model is statistically superior.

The residual plots show regression toward the middle: shorter durations tend
to be overestimated and longer durations underestimated. Per-fold learning
curves provide evidence of fitting/validation gaps. Combined with unstable
outer scores, this warrants concern about overfitting and sensitivity to the
split, without proving memorization. The initial ten-row test result does not
establish robust generalization. Further experimentation should stay on
development data; a genuinely new external test set is needed for new claims.

## External-data decision

Downloaded Cambridge and Ghent DSLIB 3.4 from their official sources, with
archive hashes, field inventories and source references recorded under
`data/processed/external_inventory/`. Cambridge contains 299 project identifiers
and 444,156 activities. Ghent provides 232 Excel workbooks including its analysis
sheet. Its analysis lists 231 project records, including 163 construction
records; 116 construction records have numeric positive Real Duration cells.
These cells still require authenticity/units checks before use as labels.
Construction workbooks are extracted separately for review.

Neither dataset currently establishes compatibility with Mendeley's nine
building-characteristic inputs, duration units and project population. They
are not concatenated or used to inflate the current sample count. No enlarged
Duration V1 retraining is justified at present. Cambridge is the preferred
candidate for a separate activity-duration/schedule-risk task. Ghent supports
planned/observed comparisons once authenticity codes, calendars, missing values,
related subprojects and licensing are verified. Neither supplies verified
IFC-change-to-delay labels for PMI V3.

## Reproduction and artifacts

```powershell
python training/validate_model.py
python training/validate_model.py --repeats 3 --output-dir data/processed/duration_validation_repeated
python training/inventory_datasets.py
python -m unittest discover -s tests -v
```

The two validation directories contain fold metrics, summaries, predictions,
split manifests, model checkpoints, preprocessing, learning curves and residual
plots. Training parameters, versions and source hashes are recorded per fold.
Inventory dependencies are listed in `training/requirements-inventory.txt`.
No IFC detection, CPM scheduling or Streamlit code was changed for this stage.

Outstanding source issues: Mendeley provenance/license and duration units,
two different records named Pr29, Cambridge calendar/estimate semantics and
some suspicious weather-field values, and Ghent authenticity and reuse terms.
