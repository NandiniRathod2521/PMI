# PMI Stage 2.3B — Cambridge activity-level audit

Audited 299 project keys and 444,156 activities; 258,352 rows have both actual-date fields filled. Stage 1 inventory checks: {'projects': True, 'activities': True, 'filled_actual_pairs': True}.
Unique source identifiers are not certified independent projects. No model, split, tuning, imputation or label release was performed.

## Which task is supported?

Descriptive activity/schedule analysis is supported now. A conditional future target is **reported completed-activity elapsed calendar duration**, defined as (Actual_Finish_Date − Actual_Start_Date).total_seconds()/86400.
It is a reported historical timestamp proxy, not active working time, not a verified contractor measurement, and not IFC-change-caused delay. It requires 100% reported completion, coherent positive dates, matching IDs and finish no later than the project status date.
A future supervised experiment also needs original baseline feature provenance and project/snapshot grouping. No target is recommended for training immediately.

| Task | Structural activity candidates | Projects represented | Verified training-ready activities/projects |
|---|---:|---:|---|
| descriptive_analysis | 444,156 | 299 | 0 / 0 |
| reported_completed_elapsed_duration | 180,335 | 268 | 0 / 0 |
| recorded_at_completion_duration | 150,650 | 268 | 0 / 0 |
| elapsed_planned_vs_actual_deviation | 177,403 | 268 | 0 / 0 |
| stored_duration_growth | 105,783 | 267 | 0 / 0 |
| project_schedule_risk | 0 | 0 | 0 / 0 |

Structural counts are separate from verified eligibility. Project-risk zero does not mean no schedule risk; it means no defensible project-level supervised target is present.
Elapsed planned-versus-actual differences are audit values only: an exported planned date is not proof of the original issued baseline.

## Units, outcomes and source provenance

The [Cambridge repository](https://doi.org/10.17863/CAM.53890) supplies the archive under CC BY 4.0. The [linked paper](https://itcon.org/papers/2022_04-ITcon-Fitzsimmons.pdf) describes a historical P6 sample; its filtered 302/293263 counts differ from this 299/444156 export. Correspondence to that filtered sample is unverified.
Related [author extraction code](https://github.com/fitzsimmonsjp/fitzsimmons_method_data/blob/master/Simulation%20Algorithm.py) provides a warning about substituting planned dates for missing actuals. It does not prove this exact JSON's generation history, and was not executed.
Stored ODE and At_Completion_Duration have no explicit, recoverable calendar contract here. Calendar_ID is a reference, not a definition. Do not infer weekdays, holidays, eight-hour days or unit equivalence from it. Float headers explicitly mix hours and days.
Elapsed timestamp differences have explicit 24-hour calendar-day units; they must never replace working durations silently. Growth is audited as a fraction, despite its percentage name; zero ODE is never divided by or used as a duration-growth label.
Label provenance categories: {'at_completion_estimate_or_placeholder_unknown_not_observed': 185804, 'reported_historical_timestamps_not_independently_verified': 180335, 'reported_actual_dates_temporally_unresolved': 72624, 'incomplete_or_conflicting_progress_unknown': 5393}.
Completed/date-coherent rows are historical as reported, not independently verified; unfinished/missing-actual at-completion values remain estimated/placeholder/unknown. No row is certified simulated or historical merely from the paper's empirical context.

## Quality and relationships

Growth-ratio audit: {'not_computable': 150667, 'matches_fraction': 252802, 'mismatch': 40687}.
Task IDs reused across projects: 7718; WBS IDs reused: 1305; project pairs sharing task IDs: 96.
Use composite project/activity keys. Shared IDs can mean snapshots, shared work or identifier collisions, not necessarily independent observations. project_relationships.csv proposes conservative review, never a split or automatic merge.
Task_Type equals Task_ID in 444,156 rows, so it cannot identify task-dependent work or milestones. Zero durations are not proven milestones. Completion conflicts and date/zero-span checks remain in the label audit.
Stored growth disagrees with ACD/ODE minus one in 40,687 rows. Matching ordered baseline views (not proven duplicate projects): [['5415', '5416']].
Weather sanity flags: {'minimum_temperature_above_maximum': 346110, 'mean_temperature_outside_min_max': 346110}. No field realignment or value correction was attempted.
Explicit cost fields found: []. Actual cost would leak outcomes if later joined, but is not invented when absent.

## Prediction-time separation

candidate_features.csv uses a small allowlist of conceptual baseline descriptors, ODE and planned calendar span/month. All are as-exported, with original baseline timing still unverified; IDs are join metadata, never predictors.
Exclude actual dates, elapsed labels, at-completion duration, growth, progress, status/final project dates, float, task position, concurrency and realized weather. Also exclude pretrained GMM topics (unknown training corpus), unresolved weather alignment and market vintages. Recompute any learned/text/topology transforms from verified baseline inputs within future training groups only.
activity_label_audit.csv retains all raw source values, JSON pointers, completion/chronology eligibility and quality flags. It is not a ready-to-train dataset; no observed elapsed value is passed as an input feature.

## Deliverables and preservation

data_dictionary.csv covers every observed project, activity, WBS and relationship field with types, missingness, ranges, examples, timing and input policy. task_eligibility.csv and project_audit.csv provide activity/project counts; feature_contract.json documents the allowlist.
source_provenance.json records source locations and unresolved assumptions. protected_hashes.json checks raw sources, Stage 1 models, Ghent verification, IFC/CPM scripts and application files unchanged.
**0 verified/released labels. Descriptive analysis is defensible; conditional reported elapsed-duration research requires the listed provenance and grouping checks first.**
