# Duration V1 development validation

3 repetition(s) of grouped five-fold CV on 40 development records.
Original ten-row test file is not loaded. Existing duration_v1 artifacts are unchanged.
MLP stopping uses an inner grouped split; outer evaluation rows never select an epoch.
Preprocessing and all three estimators fit only on the inner fitting subset.
Costs excluded; fixed hyperparameters; no fold-result tuning performed.

| Model | MAE mean ± SD | RMSE mean ± SD | R² mean ± SD |
|---|---|---|---|
| mean | 7.263 ± 2.306 | 9.173 ± 2.653 | -0.322 ± 0.407 |
| mlp | 6.485 ± 1.665 | 8.470 ± 1.976 | -0.278 ± 0.755 |
| ridge | 6.254 ± 1.955 | 7.763 ± 2.212 | -0.182 ± 1.011 |

## Interpretation and limitations

Fold standard deviations describe variation, not confidence intervals; folds share training records.
The initial held-out R² of 0.866 is a different experiment and is not directly comparable to mean CV R².
Inspect each fold's loss_curve.png and loss_history.csv for training/inner-validation gaps.
A lower training loss alone is not evidence of generalization. Outer fold performance is the relevant comparison.
Only 40 records, with uncertain repeated Pr29 identity; units and source license remain unverified.
These are total-duration estimates, not IFC change-related delay estimates.
No new external records have been merged; schema and target compatibility must be established first.
