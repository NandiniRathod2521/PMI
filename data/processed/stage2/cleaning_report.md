# PMI Stage 2.2 — Ghent building-duration preparation

Source: `C:\Users\ahmed\Documents\Codex\2026-11-04\n\PMI\data\raw\ghent\construction_excel\DSLIB_Analysis_Sheet.xlsx`, worksheet DSLIB, header row index 2.
Source SHA256: `3b513f16779f49e33264c36d8f4dd4f5f36bc11fbc91caf603cabb7bb6e7a483`. Excel files are never saved or modified.

## Counts and inclusion

- Overall valid project records: 231.
- Valid building records: 87.
- Building-category summary rows excluded: 3.
- Positive planned/real duration pairs: 68.
- G/G source-code candidates: 56 (not independently validated).
- Verified deviation targets: 0.
- Independently usable projects confirmed: 0.
- Duplicate building IDs: [].
- Provisional candidate groups after name/phase flags: 32 (NOT a verified independent count).

87 building-sector records include partial works and facilities, not necessarily 87 complete buildings.
All exclusions and source row numbers are in ghent_excluded_rows.csv; missing/invalid duration rows remain in the building audit.

## Source definitions and units

Overview B33:C33 defines PD (days) as planned project-schedule duration.
Overview B89:C89 defines Real duration as total duration known after project finish.
These definitions verify planned/real interpretation, but not a common working/calendar-day convention.
No calendar-day difference is substituted for working days, and no default eight-hour day is assumed.
Source raw values (including formulas if present) and cached values are retained separately.
Fields ending _days hold source-scale candidates; only nonempty duration_deviation_days is a verified day-based target.

## Authenticity and known issues

Overview rows 25–29 distinguish static-project and progress-tracking authenticity using a referenced colour-coded framework.
It does not explicitly decode G/O/Y. Missing codes, N/A and unexpected codes are not promoted to G.
Candidate project codes: {'G': 58, 'O': 1, 'missing': 9}.
Candidate tracking codes: {'missing': 11, 'Y': 1, 'G': 56}.
Candidate combinations: {'G/G': 56, 'G/Y': 1, 'G/missing': 1, 'O/missing': 1, 'missing/missing': 9}.
Known Problems project IDs: ['C2011-06']; none should be silently treated as a quality certificate for other records.
The known issue is that C2011-06 cannot be rescheduled; that project is outside the building filter.
Updates is also captured and linked by project ID so revised baselines/precedences can be reviewed.
Early/late checks: {'consistent_within_rounding': 58, 'mismatch': 10}; tolerance 0.0051 in fractional deviation.
Mismatched project IDs: ['C2013-16', 'C2014-06', 'C2015-35', 'C2016-06', 'C2016-07', 'C2019-02', 'C2023-04', 'C2023-07', 'C2025-10', 'C2025-13'].
This post-execution ratio is used only for auditing; it never enters baseline features.

## Target and independence gate

Signed total project duration deviation; real minus planned. Negative means early; not IFC-caused extra work or start-date slippage.
A target requires positive numeric durations, verified source definitions, units, day basis/calendar comparability, original baseline and reviewer evidence.
Duplicate IDs block release. Known problems or contradictory Early/late require explicit source-issue review evidence. No raw values are corrected automatically.
Use duration_verification_template.csv for documented per-project evidence, then pass it with --verification-file.
An independently usable count additionally requires G/G and an evidenced independence attestation. Do not mark this from unique IDs alone.
The numeric-pair candidates are not an independently usable training set. Related names/phases are review hints, never a split or proof of shared identity.

## Missing values and feature contract

Duration statuses: {'planned_duration': {'valid': 87}, 'real_duration': {'missing': 19, 'valid': 68}}.
Feature-level missing/invalid counts and every target blocker are in cleaning_report.json. Nothing is imputed.
ghent_baseline_features.csv is an explicit numeric baseline-only allowlist plus project_id for joins.
No actual outcome, EVM performance metric, tracking statistic, authenticity code, project name or reviewer metadata is a prediction input.
ghent_verified_labels.csv contains released labels only; its header-only default means no labels passed the verification gate.

## Unresolved assumptions

- Day-equivalence and project calendar comparability require project-level evidence; no hours/day conversion inferred.
- G/O/Y are preserved source codes; Overview provides no explicit code-to-authenticity legend. G/G is only a conservative screen.
- Updates include revised schedules/precedences: the baseline must be verified as the original prediction-time plan.
- Early/late disagreement is a review blocker; resolution requires source_issue_reviewed and evidence, never editing original durations.
- Name-based related groups can overgroup generic names and miss other shared projects; they do not prove independence.
- Absence from Known Problems does not certify a record. The sheet contains an out-of-scope project issue.
- Summary rows are never observations; missing outcomes and features stay missing. No split, imputation or model training.

No model was trained; no 80/20 split or change to Stage 1 models, IFC, CPM or Streamlit was made.
