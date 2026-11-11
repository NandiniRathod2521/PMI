# PMI Stage 2.3C — Cambridge supervised-learning feasibility

## Decision

A narrowly scoped **retrospective exploratory supervised experiment is justified in principle**, subject to the grouping and feature policy below. It would ask whether exported task descriptions and coarse context relate to reported elapsed calendar time. This is not a pre-execution schedule forecast or a validation against independently verified historical ground truth.
No experiment was performed here: no split, fitting, tuning or verified-label release.

## Candidate and provenance counts

| Category | Count |
|---|---:|
| Source activities audited | 444,156 |
| Structural completed-timestamp candidates | 180,335 |
| Source project IDs represented by structural candidates | 268 |
| Exploratory eligible after the explicit review filters | 180,137 |
| Project IDs / conservative blocks with exploratory candidates | 268 / 169 |
| Fully provenance-supported prospective-training candidates | 0 |
| Structural candidates unresolved as verified ground truth | 180,335 |
| Verified baseline features / independently verified project groups | 0 / 0 |
| Verified labels released | 0 |

These categories overlap: exploratory eligibility is a research scope, not a provenance approval. Traceability to a raw JSON pointer supports what was reported, not that the report was measured correctly or available before execution.
Exploratory exclusions (may overlap): {'minimal_context_missing': 75, 'explicit_outcome_phrase_in_description': 123}.

## Project/history grouping proposal

There are 7,718 reused task IDs, 1,305 reused WBS IDs and 33 project pairs sharing WBS IDs.
Shared task-ID pair evidence: {'identifier_collision_plausible': 95, 'mixed_shared_ID_evidence_manual_review': 1}.
0 pairs have matching distinctive text but changed planned fields: possible revision or copied scope, not proven revision history.
Comparisons check task text, project type/region, planned dates/ODE and actual dates. Shared numeric identifiers with unrelated text suggest namespace collisions; corroborated content suggests snapshots or copied work. Neither proves physical-project identity.
Scenario block counts across 299 source IDs: {'task_ID_only_group': 217, 'content_supported_group': 298, 'conservative_group': 192}.
The largest conservative block contains 96 source project IDs. The largest exploratory block holds 99,636 activities (55.3% of eligible rows). Future evaluation must report both row-weighted and group-level performance; block counts are not effective sample sizes.
Default future evaluation containment: connect all shared task IDs, shared WBS IDs and matching ordered baseline views, including uncertain edges. This deliberately overgroups possible collisions to reduce known cross-evaluation contamination. The content-supported scenario is a sensitivity proposal, not an approved independent grouping.
These are scenario-based evaluation-block counts, not a confidence interval, effective sample size or verified count of independent projects. Hidden shared histories can remain. No IDs were merged in the raw data and no split was created.

## Feature timing and recommended target

The reviewed primary publication and author-code references are recorded with locations in provenance_review.json. The paper's adjusted AOD is not our raw elapsed-time target. A field named original estimate, or a planned date, is not an original-issued version certificate.
All eight Stage 2.3B candidate features are reviewed in feature_provenance_policy.csv. **None is verified as an original baseline field.**
For retrospective exploration only, permit project_type, uk_region and activity_description as exported; their precise prediction-time provenance remains uncertain. Exclude explicit outcome phrases. WBS description is sensitivity-only because it may encode parent identity or revised scope.
Keyword exclusions are precautions: an as-built drawing can be planned work, so a matching phrase is not proof of leakage. Review these exclusions before a later experiment; do not reinterpret them as confirmed post-execution edits.
Exclude ODE, planned span/month and exported predecessor counts until baseline provenance is resolved. Exclude outcomes, actual/final dates, progress, stored growth/at-completion duration, learned GMM topics, float, concurrency, weather, market vintages and IDs from inputs. Any future text encoder must fit only within future training groups.
Target: `(Actual_Finish_Date - Actual_Start_Date).total_seconds()/86400` for reported 100%-complete activities with positive coherent timestamps and finish no later than the status date. It measures naive elapsed calendar time, not working time, adjusted CPM duration, causation or delay attributable to IFC changes.
The eligibility CSV carries this exploratory research value and unresolved provenance flags; it is not an approved historical-ground-truth dataset. Calendar/timezone interpretation and data-collection authenticity still require source review.

## Ambiguity and next step

Exact repeated candidate records flagged: 0; possible same-baseline/conflicting-actual records: 0. These are quarantined or reduced to a documented first-source representative for exploratory counting only.
Raw/candidate feature and label rows are joined by composite keys with no imputation. excluded_activity_index.csv identifies nonstructural records and their Stage 2.3B quality flags, including incomplete/conflicting progress and incoherent dates. Growth inconsistencies are flagged even when unused by the minimal experiment.
Next, review the highest-content-overlap histories and conflicts in activity_identity_pair_review.csv/shared_history_evidence.json. Seek original-issued schedules and parent registries for a prospective claim. If separately authorized, predeclare a retrospective-only experiment with the minimal feature policy and conservative grouped evaluation; preserve a grouped holdout and compare simple baselines before a neural network. Do not integrate predictions into CPM or claim working-day delay accuracy on this evidence.
Protected input checks passed for 432 files, including Stage 1, Ghent, Stage 2.3B, raw IFC/schedule sources and application files.
