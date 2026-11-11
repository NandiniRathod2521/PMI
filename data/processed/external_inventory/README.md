# External schedule data inventory

Inspection date: 11 November 2026. Sources are kept separate from Mendeley.

| Source | Provenance and rights | Intended use |
|---|---|---|
| Cambridge | Brilakis, Fitzsimmons and Lu; [repository](https://doi.org/10.17863/CAM.53890); repository license CC BY 4.0; cite the associated [research](https://doi.org/10.36680/j.itcon.2022.004) | Activity-duration/schedule-risk research, not direct enrichment of the building-characteristic regression |
| Ghent DSLIB 3.4 | [Official release](https://github.com/MarioVanhoucke/DSLIB-Dynamic-Scheduling-Empirical-Project-Library/releases/tag/DSLIB_v3.4), reached through the [university catalogue](https://www.projectmanagement.ugent.be/research/data/realdata). Cite Batselier & Vanhoucke (2015), DOI 10.1016/j.ijproman.2014.09.004. An explicit redistribution/reuse license has not been established. | Planned/observed project performance and activity scheduling; review authenticity and calendar semantics first |
| Existing MENDLEY CSV | Original supplied local file; publication identifier, source license and duration units still require confirmation | Duration V1 only; 50 records, 49 distinct project names |

`dataset_inventory.json` records archive hashes, fields, counts and decisions.
`cambridge_projects.csv` counts activities, filled dates and relationships per
project. Filled date pairs are not automatically valid observations or proven
independent projects. Project codes identify source records, not verified entities.

Cambridge has no matching AreaSite/BuiltArea/TowerNum feature schema and no
explicit IFC GlobalId field in the inspected activity schema. Its duration
growth and at-completion fields must not be mistaken for universally observed
delay. There are mixed hour/day fields and calendar identifiers. Planned
durations, at-completion estimates and actual date differences must stay distinct.
Some weather columns in the first inspected records look semantically unusual;
verify field alignment against source documentation before using them.

Ghent `ghent_projects_for_review.csv` is a summary inventory, not a training set.
It retains project and tracking authenticity codes alongside planned duration
and the source Real Duration cell. Numeric values alone do not establish verified
historical labels. `ghent_sheets.csv` inventories sheet schemas and sample rows;
`ghent_files.csv` inventories archive members. Construction Excel files plus the
analysis workbook are extracted under `data/raw/ghent/construction_excel/`.
The raw archives remain unchanged; Mac metadata is not treated as project data.

## Compatibility decision

Do not concatenate either external dataset with Mendeley. Neither provides the
current nine building features with established matching definitions and units.
Consequently, no defensible enlarged Duration V1 training run is possible yet.
Prioritize Cambridge for a separate Schedule V2 experiment, after checking
completed activities, units, calendars, leakage and grouping. Ghent is useful
for an independent planned-versus-observed analysis after filtering construction
and interpreting authenticity. Group related subprojects together. Neither source
establishes causation between an IFC modification and additional work days, so
PMI V3 still needs linked IFC revision and verified schedule-impact records.

The other three suggestions (integrated planning, time-motion and simulated
risk data) have not been downloaded or verified in this stage. They are not
silently included in sample counts or real-world validation evidence.

Regenerate with `python training/inventory_datasets.py` after installing
`training/requirements-inventory.txt`. This reads the supplied archives, streams
Cambridge project objects, and reads Ghent Excel in read-only mode. It creates
review inventories only and does not fit a model or infer compatible labels.
