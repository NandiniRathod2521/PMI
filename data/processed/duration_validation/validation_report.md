# Duration V1 development validation

1 repetition(s) of grouped five-fold CV on 40 development records.
Original ten-row test file is not loaded. Existing duration_v1 artifacts are unchanged.
MLP stopping uses an inner grouped split; outer evaluation rows never select an epoch.
Preprocessing and all three estimators fit only on the inner fitting subset.
Costs excluded; fixed hyperparameters; no fold-result tuning performed.

| Model | MAE mean ± SD | RMSE mean ± SD | R² mean ± SD |
|---|---|---|---|
| mean | 7.491 ± 1.875 | 9.706 ± 1.737 | -0.255 ± 0.301 |
| mlp | 6.857 ± 2.150 | 9.359 ± 1.925 | -0.198 ± 0.423 |
| ridge | 6.078 ± 1.882 | 7.719 ± 1.944 | 0.183 ± 0.361 |

## Interpretation and limitations

Fold standard deviations describe variation, not confidence intervals; folds share training records.
The initial held-out R² of 0.866 is a different experiment and is not directly comparable to mean CV R².
Inspect each fold's loss_curve.png and loss_history.csv for training/inner-validation gaps.
A lower training loss alone is not evidence of generalization. Outer fold performance is the relevant comparison.
Only 40 records, with uncertain repeated Pr29 identity; units and source license remain unverified.
These are total-duration estimates, not IFC change-related delay estimates.
No new external records have been merged; schema and target compatibility must be established first.
