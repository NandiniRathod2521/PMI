# PMI Stage 2.3A — Ghent evidence verification

68 candidates inspected. This stage collects evidence and proposals only: no reviewer, approval flag, correction, label release, model or split is created.
The Stage 2.2 template, cleaning report, labels and release logic are unchanged.

## Requirement counts

| Requirement / evidence milestone | Supported or passed | Unresolved / not passed |
|---|---:|---:|
| positive_duration_pair_and_unique_id | 68 | 0 |
| planned_real_interpretation | 68 | 0 |
| planned_unit_days_source_header | 68 | 0 |
| real_unit_days_direct_card_label | 31 | 37 |
| planned_working_basis_direct_card_statement | 68 | 0 |
| project_calendar_settings_located_NOT_comparability | 68 | 0 |
| saved_hours_per_day_located | 68 | 0 |
| baseline_display_exact_summary_match | 53 | 15 |
| actual_display_exact_summary_match | 40 | 28 |
| source_ratio_consistent_at_stage22_tolerance | 58 | 10 |
| common_calendar_and_real_day_basis_verified | 0 | 68 |
| original_issued_baseline_verified | 0 | 68 |
| independence_verified | 0 | 68 |
| reviewer_signoff | 0 | 68 |
| all_label_release_requirements_passed | 0 | 68 |

Calendar settings and a displayed duration match do not establish original baseline identity, actual-data provenance or calendar comparability.
Counts distinguish directly supported facts from release approvals. The proposal CSV contains only observed unit statements and evidence notes; all approval/sign-off flags stay empty.
Existing template values were inspected, never overwritten. Explicit authorizations or evidence a reviewer adds later must still satisfy the unchanged Stage 2.2 gate.

## Main findings

- 5 cards expressly describe Real Duration/Cost as simulation-based; 3 have G/G in the summary. These conflicts need provenance review, not automatic approval or correction.
- 2 ProTrack sources contain simulated tracking-period descriptions; these markers need review alongside the card and supplied authenticity.
- Saved baseline display comparisons: {'within_half_day_rounding_only': 5, 'exact': 53, 'mismatch': 2, 'unresolved': 8}. Saved final-tracking display comparisons: {'within_half_day_rounding_only': 3, 'mismatch': 15, 'exact': 40, 'unresolved': 10}.
- Analysis sheet planned and real definitions are at Overview B33:C33 and B89:C89. Calendar settings are in each project's Agenda; explicit conversion defaults are recorded with ProTrack XML paths.
- A Baseline Schedule sheet documents the saved baseline, not necessarily the original issued pre-execution plan. Updates records revisions; absence of an update is not verification.
- Known Problems A4:C4 lists C2011-06 (out of scope); it cannot certify the remaining projects.

## Ten ratio discrepancies

| Project | Summary ratio | Supplied Early/late | Investigation |
|---|---:|---:|---|
| C2013-16 | -0.448980 | -0.440000 | Truncating the computed fractional ratio toward zero to two decimals reproduces the source; precision policy unverified |
| C2014-06 | 0.117002 | 0.064400 | Card PD=[574.0] differs from summary PD and reproduces the ratio; possible baseline/version or transcription conflict |
| C2015-35 | 0.118824 | 0.110000 | Truncating the computed fractional ratio toward zero to two decimals reproduces the source; precision policy unverified; Dividing by real rather than planned duration reproduces the source within tolerance; denominator inconsistent with Overview |
| C2016-06 | -0.079365 | -0.070000 | Truncating the computed fractional ratio toward zero to two decimals reproduces the source; precision policy unverified |
| C2016-07 | 0.410714 | 0.482143 | No uniquely supported correction; conflicting source values require owner/reviewer clarification |
| C2019-02 | 0.008523 | 0.002000 | No uniquely supported correction; conflicting source values require owner/reviewer clarification |
| C2023-04 | 0.276596 | 0.270000 | Truncating the computed fractional ratio toward zero to two decimals reproduces the source; precision policy unverified; Project workbook has no readable cached project-level duration for this comparison |
| C2023-07 | -0.268191 | 0.268100 | Opposite sign fits the summary pair; card and Updates must be reconciled before correcting; Project workbook has no readable cached project-level duration for this comparison |
| C2025-10 | -0.320611 | -0.470000 | Dividing by real rather than planned duration reproduces the source within tolerance; denominator inconsistent with Overview; Project workbook has no readable cached project-level duration for this comparison |
| C2025-13 | 0.066667 | 0.060000 | Truncating the computed fractional ratio toward zero to two decimals reproduces the source; precision policy unverified; Dividing by real rather than planned duration reproduces the source within tolerance; denominator inconsistent with Overview; Project workbook has no readable cached project-level duration for this comparison |

All ten remain unresolved. See duration_ratio_investigation.csv for summary, workbook, PDF and update references. No sign, rounding, denominator or version correction is accepted automatically.
Blank or unavailable project-level duration cells stay unresolved; no value is reconstructed from performance metrics. Half-day display matches are hypotheses, not repairs.

## Authenticity source search

The primary paper [Batselier & Vanhoucke (2015)](https://doi.org/10.1016/j.ijproman.2014.09.004), sections 2.1.1 and 2.1.4, printed pages 699–700, explicitly maps G/Y/O to green/yellow/orange.
Green means all relevant source data came from the owner; yellow and orange indicate successively more assumed data types. Project authenticity covers activity/resource/baseline-cost data; tracking authenticity covers actual starts/durations/costs. N/A denotes no real tracking data. Missing codes remain unknown.
Read via a [full-text mirror](https://iranarze.ir/storage/uploads/2016/09/4960-English.pdf); the [UGent record](https://biblio.ugent.be/publication/5978659) identifies the article but its institutional full text is restricted. The author-hosted UCL 2016 overview corroborates the framework in sections 4.1.1–4.1.2.
These documented meanings do not certify any individual record, fill missing codes, or override a simulation warning.

## Related projects

grouping_proposals.csv distinguishes suspected name families from confirmed identity. Numbered residences, structural/finishing packages and apartment-building phases warrant conservative same-fold grouping if splitting is later authorized. Generic names alone cannot establish a common parent. All relationship approvals remain manual-review items.

## Files and next verification work

- verification_matrix.csv: one row per candidate, cell references, source comparisons and outstanding questions.
- verification_evidence.csv and verification_source_extracts.json: detailed observations, worksheet/page/XML references and original extracted values.
- duration_verification_evidence_proposal.csv: supported field proposals only; NOT approved verification.
- verification_requirements.csv and verification_field_counts.csv: every existing release field, its scope and observed/unresolved counts.
- duration_ratio_investigation.csv and grouping_proposals.csv: separate discrepancy and relationship reviews.
- verification_protected_hashes.json: raw data, Stage 1 models, application scripts and existing Stage 2.2 artifacts were hash-checked unchanged.

Obtain original-issued baseline provenance, reconcile actual day/calendar conventions and inconsistent pairs, confirm historical rather than simulated outcomes, resolve parent identities, and obtain reviewer sign-off.
**0 labels released; 0 projects automatically approved; all 68 remain blocked.**
