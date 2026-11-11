# PMI Stage 2.3D — Cambridge retrospective experiment design

## Decision

The conservative holdout is structurally valid and row-balanced. Training can proceed for a limited retrospective experiment under distribution shift. A credible representative near-80/20 holdout covering an unseen dominant block is unavailable. Use conservative grouped validation for broader inference. It evaluates exported activity text and context against reported elapsed calendar time. It cannot establish representative performance over all project histories or pre-execution forecasting accuracy.

The unchanged eligible population contains 180,137 activities across 268 source IDs. Verified historical labels and verified baseline features remain zero.

## Frozen allocations

| Scenario | Train rows | Test rows | Test % | Train/test blocks | Conservative blocks crossing |
|---|---:|---:|---:|---:|---:|
| conservative | 144,110 | 36,027 | 19.9998% | 70/99 | 0 |
| content_supported | 144,110 | 36,027 | 19.9998% | 255/13 | 2 |
| task_id_only | 144,110 | 36,027 | 19.9998% | 156/36 | 2 |

Conservative grouping is primary and retains all proposed identity/history links. Each sensitivity manifest preserves its own blocks, but can separate uncertain relationships retained by the conservative scenario. Sensitivity allocations are not equally strong evidence of leakage control or project independence.

## Dominant block

`C-5f73906a8795` contains 99,636 eligible rows (55.3%), 92 eligible source IDs and 96 source IDs overall. It remains intact in training. If placed in test, the test fraction must be at least 55.3%, leaving at most 44.7% for training. Thus it cannot be an approximately 20% test block.

Within the chosen primary training set its row share is 69.1%. Training can use an approximately 80/20 allocation, but it remains concentrated and tests the remaining blocks. The single holdout does not answer performance on an unseen dominant history. The block can span unrelated projects because shared IDs may collide.

## Target, inputs and joins

Target: `(Actual_Finish_Date - Actual_Start_Date).total_seconds()/86400`, restricted to the existing completed, temporally coherent eligible activities. Units are naive elapsed calendar days. No working-calendar conversion, causal delay attribution, target clipping or imputation is applied.

Only `activity_description`, `project_type` and `uk_region` enter `feature_matrix.csv`. Composite JSON-array keys, IDs and block memberships are join/evaluation metadata. Targets reside separately in `exploratory_targets.csv` and carry an explicit unverified flag. The exported text/context may include later edits. Existing outcome-phrase exclusions remain unchanged and do not prove the remaining text is clean.

Unique composite keys are checked on both sources before joining. Duplicate keys, missing matches, contradictory eligibility flags, group mismatches or incoherent target timestamps stop preparation. No source row is multiplied or silently resolved by first-match lookup.

## Distribution diagnostics

Allocation uses block IDs, row counts and a fixed hash namespace only. Exact subset-sum chooses the nearest achievable 20% row count. There is no seed search, target stratification or category-driven reselection. Protocol/manifests are written before calculating outcome and category diagnostics.

`target_distributions.csv` reports min, p05, quartiles, p95, max, mean and standard deviation in calendar days. `target_bins.csv` uses fixed elapsed-time intervals. `category_distributions.csv` includes zero-count categories, row shares and source-ID/block counts for project type and region. `design_summary.json` reports category coverage gaps and total variation distances. Differences are reported without changing the holdout.

| Primary side | Median days | p95 days | Mean days | Maximum days |
|---|---:|---:|---:|---:|
| train | 8.38 | 198.67 | 42.11 | 2087.71 |
| test | 11.33 | 256.00 | 52.45 | 2019.67 |

Primary project_type: row-share total variation distance 0.715. Train-only categories: Light Rail - Underground (inc. Tunnelling), Power Generation - Coal, Power Generation - Renewables, Waste Water Treatment. Test-only categories: none.

Primary uk_region: row-share total variation distance 0.133. Train-only categories: East Anglia, North England. Test-only categories: East & North East England.

The project-type imbalance is severe. The primary 80/20 row ratio does not provide balanced sector coverage: four types have no test observations. The dominant block accounts for 69.1% of development rows and cannot be represented as unseen test work in this allocation. Treat final holdout results as performance on this shifted collection of blocks, not a corpus-wide estimate. These diagnostics do not trigger a new allocation, feature change or weaker grouping.

## Holdout and validation protocol

Protocol `fbc2076978805d434b08e525b44bda4babe8509da6d494b2fa5b2c01fb27a848` is frozen in `holdout_protocol.json`. `design_freeze.json` checksums the protocol, data, manifests and diagnostics. A rerun verifies these files and inputs without selecting another allocation. Input or output drift requires a separately reviewed new version.

Fit text vocabularies, encoders, normalizers and category mappings within development training folds only. Use the five frozen development folds for model choice, hyperparameters and early stopping. Select using mean macro-block MAE, and report row-weighted MAE/RMSE plus per-block errors. Refit only on primary training rows after configuration is locked. Compute primary holdout prediction metrics once for the final report. Aggregate target statistics have already been inspected for this design review; the labels are not claimed to be fully blind. Holdout outcomes must not influence feature/model choice, tuning, early stopping or preprocessing.

Primary development fold sizes: [99636, 19001, 8818, 8328, 8327]. A balanced fivefold partition is impossible when one block dominates development rows. The largest-block-first allocation keeps it intact and exposes it as one validation fold. Report that fold separately and aggregate errors per block. For broader generalization research, use conservative leave-one-block-out or these explicitly unequal grouped folds, with group-level reporting. A single representative balanced holdout covering an unseen dominant block is not available; never split it or switch to a weaker grouping to conceal this limitation.

Sensitivity protocols are predeclared final analyses. Run them only after primary configuration and final results are locked, using the locked configuration without holdout-based tuning. Their training populations may include primary holdout rows, so no sensitivity result may feed back into primary decisions. Unknown shared histories and namespace collisions remain unresolved in all scenarios.

No prediction model was trained, tuned or evaluated. No verified labels were released. All 676 protected existing inputs were unchanged.
