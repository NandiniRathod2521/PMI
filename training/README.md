# Duration experiment v1

From the PMI root, activate `.venv`, then run:

```powershell
python -m pip install -r training/requirements.txt
python training/train_model.py
```

Outputs are saved under `models/duration_v1/`. The MLP has 9 numeric inputs,
16 and 8 ReLU hidden units, and one linear duration output. Identifiers and
the target are excluded from inputs. Cost features are excluded by default;
`--include-costs` is available only after verifying prediction-time availability.

The 40-row training file is split into fitting and validation subsets by project
name (seed 42). The median imputer, feature scaler and target scaler are fitted
only on the fitting subset. Adam trains for at most 2000 epochs with patience
150. The best validation checkpoint is restored. It is not refitted on all 40
rows; mean and Ridge (alpha 1) use the same fitting rows for a fair comparison.
The ten held-out test rows are used only for final evaluation, never selection.
Loss curves use standardized-target MSE; test metrics use original source units.

`metrics.json` records metrics, feature order, split row IDs, parameters,
input hashes and package versions. `model.pt` stores weights and architecture;
`preprocessing.joblib` stores feature and target transforms. To predict, apply
the saved feature transformer in saved feature order, run `make_model()` with
the restored weights in evaluation mode, then inverse-transform its output
with the saved target scaler. `baselines.joblib` stores the comparison models.
Use only trusted local checkpoint/joblib files.

The source has two different records named Pr29; these stay grouped, pending
identity verification. ProjDura is total project duration, its unit remains
unverified, and this model does not estimate delay caused by IFC changes.
Ten test observations provide limited evidence; compare the baselines and do
not tune the model repeatedly against this test set. No CPM or UI integration
is performed in this experiment.

## Development validation

```powershell
python training/validate_model.py
python training/validate_model.py --repeats 3 --output-dir data/processed/duration_validation_repeated
```

Five grouped outer folds use only `mendeley_train.csv`. Each independently calls
the existing trainer, which creates a grouped inner validation split and fits
preprocessing only on its inner fitting rows. The evaluation fold never chooses
the stopping epoch. Baselines use those same fitting rows. Optional repetitions
shuffle project groups using successive seeds. Fold CSVs, checkpoints, learning
curves, split manifests, out-of-fold predictions, summary metrics and a research
report are saved under `data/processed/duration_validation/` by default. Fold
artifacts retain the trainer's generic `test_*` filenames; in this context they
refer exclusively to outer development folds, never the original test set.

External dataset inspection uses a separate optional dependency file:

```powershell
python -m pip install -r training/requirements-inventory.txt
python training/inventory_datasets.py
```

The Cambridge JSON is streamed one project at a time. The Ghent archive is
inspected for Excel schemas without merging records or deriving labels.

## Stage 2.2 — Ghent building-duration deviations

```powershell
python training/prepare_ghent_delays.py
python -m unittest discover -s tests -p test_prepare_ghent_delays.py -v
```

Requires only `openpyxl` beyond the standard library (already listed in
`requirements-inventory.txt`). Reads the original analysis workbook, including
`Overview`, `Known Problems` and `Updates`, without saving any Excel files.
All outputs are written under `data/processed/stage2/`; no model or split is made.

The default run retains 87 valid building-sector records, including 68 positive
planned/real duration pairs. It excludes summary rows and nonbuilding projects,
preserves raw durations and source row numbers, flags duplicate IDs, names/phases
that may be related, authenticity gaps and inconsistent duration ratios.
`ghent_baseline_features.csv` is the only potential input feature table; actual
durations, tracking/performance metrics and authenticity are audit metadata, not
predictors. Its duration column is still in source-scale candidate day units,
not certified common working days. No missing values are imputed.

Numeric pairs alone do not verify labels. `duration_deviation_days` stays empty
unless the source definitions, common day units, calendar comparability and the
original prediction-time baseline are verified with evidence. A reviewed known
problem or contradictory Early/late additionally requires a documented source
issue resolution. Fill a copy of `duration_verification_template.csv` after
actually verifying these points, then run:

```powershell
python training/prepare_ghent_delays.py --verification-file path/to/verified_evidence.csv
```

The template is preserved on repeat runs. See `cleaning_report.md` and
`cleaning_report.json` for candidate counts versus verified labels and confirmed
independent usable projects. The baseline-only table is not a released training
dataset. A strict usable-record screen additionally requires source codes G/G
and evidence of independence; even those codes are not treated as proof of
historical authenticity without the missing source legend. The target, when
released, is signed real-minus-planned total duration (early results may be
negative), not delay caused by IFC modifications.

## Stage 2.3A — source evidence, without approval

```powershell
python -m pip install -r training/requirements-evidence.txt
python training/verify_ghent_evidence.py
python -m unittest discover -s tests -p test_verify_ghent_evidence.py -v
```

Reads all 68 candidate project Excel/PDF/ProTrack sources and the analysis
Overview/Updates/Known Problems. Writes `verification_report.md`, a per-project
matrix, detailed cell/page/XML evidence, a separate ten-ratio investigation,
grouping proposals, field requirements/counts and an evidence-only proposal CSV
under `data/processed/stage2/`. The original template, release logic and labels
are unchanged. No reviewer or approval flags are auto-filled. The proposal file
is not an approved verification file and does not release any label.

Project cards are extracted in both text and physical-layout modes to avoid
silently assigning numbers from adjacent table columns. Raw display durations
are compared only with explicit saved conversion settings; exact matches and
rounding hypotheses remain distinct. The highest-numbered tracking sheet is
inspected, without treating its mere existence as proof of final observed data.
Protected raw files, Stage 1 artifacts, existing Stage 2.2 outputs and application
scripts are hash-checked. The authenticity code research is separately documented
with primary-paper URLs/sections; the script does not browse or infer a legend.

## Stage 2.3B — Cambridge activity audit

```powershell
python -m pip install -r training/requirements-cambridge-audit.txt
python training/audit_cambridge.py
python -m unittest discover -s tests -p test_audit_cambridge.py -v
```

Streams the 1.29 GB Cambridge JSON one project at a time and writes only under
`data/processed/stage2/cambridge_audit/`. It checks the Stage 1 source archive
hash, preserves other source/model/application/Ghent artifacts, and creates no
model, split, fitted transformer or tuning run.

Read `audit_report.md` and `task_eligibility.csv` before using the data. Counts
distinguish structural candidates from verified training-ready observations.
`data_dictionary.csv` profiles every observed field at project, activity, WBS
and predecessor-link levels. `candidate_features.csv` contains only a small
conditional baseline allowlist plus composite join keys; original baseline
availability is unverified. `activity_label_audit.csv` retains source values,
JSON pointers, temporal/quality flags and candidate elapsed-calendar values.
That large file intentionally covers all activities, not just successful cases.

Completion must be explicitly reported as 100%, actual dates must be coherent
and finish no later than the status date for the strict elapsed candidate.
Timestamp differences measure calendar time; stored source durations and growth
never become verified working-day delay labels without calendars/provenance.
At-completion estimates and missing actuals are not filled using planned dates.
Weather fields, precomputed topics, progress, actual/final dates and duration
outcomes are excluded from baseline inputs. Shared-ID and baseline-view matches
are review hints, not approved project merges or independence claims.

## Stage 2.3C — feasibility and provenance review

```powershell
python training/review_cambridge_feasibility.py
python -m unittest discover -s tests -p test_review_cambridge_feasibility.py -v
```

Uses the existing Cambridge audit, then streams the raw JSON to compare reused
IDs against descriptions, context, planned dates/ODE and actual timestamps.
Requires the same `ijson` dependency as Stage 2.3B. Results are written only to
`data/processed/stage2/cambridge_feasibility/`.

The report distinguishes numeric structural candidates, fully supported
prospective-training provenance, and an explicitly retrospective exploratory
scope. `exploratory_eligibility.csv` contains reported calendar-elapsed research
values, not verified historical ground truth; `excluded_activity_index.csv`
identifies the nonstructural records and their original audit flags. No label
release, training, split, learned transformation or model tuning is performed.

`grouping_proposal.csv` and `evaluation_blocks.csv` propose conservative
containment blocks from all reused task/WBS IDs and matching baseline views.
Shared IDs often collide across unrelated text; these blocks deliberately
overgroup and are not certified physical projects. A separate content-supported
scenario and detailed pair evidence make this uncertainty reviewable. The
largest block's dominance must be considered in any later evaluation.

`feature_provenance_policy.csv` reviews all eight candidate inputs. The minimal
retrospective policy permits only project type, region and activity text, with
outcome-text exclusions. No field is certified as an original-issued baseline;
duration/planned-date/topology features remain excluded from that minimal scope.
Publication/code evidence and remaining provenance questions are in
`provenance_review.json`. Protected raw, audit, Stage 1, Ghent and application
files are hash-checked without modifying them.

## Stage 2.3D — retrospective protocol and grouped splits

```powershell
python training/design_cambridge_experiment.py
python -m unittest discover -s tests -p test_design_cambridge_experiment.py -v
```

Reads the unchanged Stage 2.3C eligible population, allowlist and grouping
proposals. Writes only under `data/processed/stage2/cambridge_experiment_design/`.
The target is reported completed-activity elapsed calendar days. Only exported
activity description, project type and region enter the separate feature table.
Labels remain exploratory and unverified.

Three manifests retain intact conservative (primary), content-supported and
task-ID-only (sensitivity) blocks. A deterministic subset-sum allocation seeks
20% of rows without using target values or category distributions. Training-only
grouped validation folds are included, with unequal sizes when large blocks
prevent balance. IDs and block fields are metadata, never predictors.

Read `design_report.md` and `holdout_protocol.json` before training. The protocol
is frozen before descriptive target/category diagnostics. Sensitivity analyses
must follow locked primary results because their training rows may include the
primary holdout. `design_freeze.json` checksums protected inputs and outputs;
reruns verify the existing design rather than silently choosing another split.
No model fitting, tuning, prediction evaluation or verified-label release occurs.
