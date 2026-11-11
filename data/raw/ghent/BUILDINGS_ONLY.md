# Ghent: buildings only

The active subset contains 87 project codes classified in the original analysis:
54 residential, 18 commercial and 15 institutional building projects.
Other sectors, including civil infrastructure and ambiguous industrial projects,
were removed at the user's request. This is a sector filter, not a check that
each retained record represents a complete building or a verified actual outcome.

Project Excel, ProTrack and cards are retained where available under
`buildings/DSLIB 3.4/`. `construction_excel/` now also contains only these
building Excel files plus the analysis workbook. Summary workbooks and source
metadata are retained for traceability and still describe the original full data.

The mixed-sector ZIP and Mac metadata were removed. The source can be downloaded
again from https://github.com/MarioVanhoucke/DSLIB-Dynamic-Scheduling-Empirical-Project-Library/releases/tag/DSLIB_v3.4.
Its original SHA256 was 19f87632c589f5d49f72b5f071992efc6379df2beb35f1efd3a60ac1381dc277.

`data/processed/external_inventory/ghent_buildings.csv` lists the retained projects.
`ghent_removed_files.csv` records deleted file paths and reasons. The earlier
Ghent inventory CSVs/JSON describe the original archive and are preserved as
provenance; they must not be interpreted as the size of the current local subset.
