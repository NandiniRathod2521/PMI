# Mendeley project-duration preparation

Regenerate from the project root:

```powershell
python scripts/prepare_mendeley_data.py
```

The script uses Python's standard library; no additional packages are required.
The raw CSV is preserved. Its malformed header is reconstructed and checked
against the 14 expected columns. Numeric cells are converted, exact duplicate
records removed, and serial identifiers checked. Negative feature values are
reported and replaced with missing values; other missing feature cells stay
empty. Invalid or missing targets stop processing.

Outputs: `mendeley_clean.csv`, `mendeley_train.csv`, `mendeley_test.csv`, and
`mendeley_quality_report.json`. The split uses seed 42 and keeps every occurrence
of a project name together. The current source has 50 records, 49 distinct
project names: `Pr29` occurs at serials 15 and 46 with different measurements.
Both records are retained pending source verification; no corrected identity
is invented. The split contains 40 training records and 10 test records.

The target `ProjDura` represents total project duration, not delay attributable
to an IFC change. Its unit is unverified. Confirm the availability of `SellCost`
and `ConstCost` at prediction time before choosing model features. `Sl.no` and
`ProjName` are identifiers, not predictive features. No scaling or imputation
is fitted here; fit those on training data only in the future training module.
With this small sample, compare the neural network with simple regression and
avoid strong claims based on ten test records.
