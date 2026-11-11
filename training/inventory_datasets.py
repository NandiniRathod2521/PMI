"""Inventory downloaded schedule data without merging or inventing training labels."""
import csv
import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path

import ijson
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/external_inventory"


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def cambridge():
    path = ROOT / "data/raw/cambridge/JPF_Anonymised_Project_Data.json.zip"
    rows, fields, activity_fields = [], set(), set()
    with zipfile.ZipFile(path) as archive:
        member = "JPF_Anonymised_Project_Data.json"
        # Extract only the data member; never execute or extract archive paths.
        destination = path.parent / member
        if not destination.exists():
            import shutil
            with archive.open(member) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)
        with destination.open("rb") as source:
            for identifier, project in ijson.kvitems(source, "Projects"):
                fields.update(project)
                activities = project.get("Activities", {})
                counts = Counter()
                for activity in activities.values():
                    activity_fields.update(activity)
                    for name in ("Actual_Start_Date", "Actual_Finish_Date", "Planned_Start_Date", "Planned_Finish_Date",
                                 "Original_Duration_Estimate(ODE)", "At_Completion_Duration"):
                        counts[name] += activity.get(name) not in (None, "")
                    counts["actual_date_pairs"] += bool(activity.get("Actual_Start_Date") and activity.get("Actual_Finish_Date"))
                    counts["relationships"] += len(activity.get("Activity_Relationships", {}))
                rows.append(dict(project_id=identifier, project_type=project.get("Project_Type", ""),
                                 activity_count=len(activities), **{key: counts[key] for key in
                                 ("Actual_Start_Date", "Actual_Finish_Date", "Planned_Start_Date", "Planned_Finish_Date",
                                  "Original_Duration_Estimate(ODE)", "At_Completion_Duration", "actual_date_pairs", "relationships")}))
    write_csv(OUT / "cambridge_projects.csv", rows)
    return dict(source="https://doi.org/10.17863/CAM.53890", license="CC BY 4.0 (repository item)",
                archive_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                project_records=len(rows), unique_project_ids=len({r["project_id"] for r in rows}),
                activity_records=sum(r["activity_count"] for r in rows),
                actual_date_pairs=sum(r["actual_date_pairs"] for r in rows),
                project_fields=sorted(fields), activity_fields=sorted(activity_fields),
                units="Mixed explicit hrs/d field names; duration and lag calendar semantics require verification",
                ifc_link="No explicit IFC GlobalId field found in inspected field names",
                decision="Separate Schedule V2 candidate; do not merge into building-feature Duration V1",
                caveat="At-completion duration is not necessarily observed actual duration; dates and completion status need checks")


def ghent():
    folder = ROOT / "data/raw/ghent"
    archive_path = folder / "DSLIB3.4.zip"
    if not archive_path.exists() and (folder / "BUILDINGS_ONLY.md").exists():
        # Keep the original archive inventory as provenance, but expose the active subset.
        original = json.loads((OUT / "ghent_inventory.json").read_text(encoding="utf-8"))
        with (OUT / "ghent_buildings.csv").open(newline="", encoding="utf-8-sig") as source:
            buildings = list(csv.DictReader(source))
        original.update(local_scope="Buildings only: residential, commercial, institutional",
                        retained_project_records=len(buildings),
                        archive_present=False,
                        inventory_scope="Original archive counts retained for provenance; local subset is ghent_buildings.csv")
        return original
    files, sheets, projects = [], [], []
    with zipfile.ZipFile(archive_path) as archive:
        analysis = load_workbook(archive.open("DSLIB 3.4/DSLIB_Analysis_Sheet.xlsx"), read_only=True, data_only=True)
        headers = next(analysis["DSLIB"].iter_rows(min_row=3, max_row=3, values_only=True))
        actual_duration_index = headers.index("Duration")
        for row in analysis["DSLIB"].iter_rows(min_row=4, values_only=True):
            if not isinstance(row[0], str) or not row[0].startswith("C20"):
                continue
            actual = row[actual_duration_index]
            projects.append(dict(project_code=row[0], project_name=row[1], sector=row[3],
                                 project_authenticity=row[8], tracking_authenticity=row[9],
                                 activity_count=row[10], planned_duration_days=row[11],
                                 real_duration_source=actual,
                                 numeric_real_duration=isinstance(actual, (int, float)) and actual > 0))
        analysis.close()
        construction_codes = {row["project_code"] for row in projects
                              if str(row["sector"]).lower().startswith("construction")}
        excel_folder = folder / "construction_excel"
        excel_folder.mkdir(exist_ok=True)
        for item in archive.infolist():
            if item.is_dir():
                continue
            files.append(dict(path=item.filename, bytes=item.file_size))
            if item.filename.lower().endswith(".xlsx") and not item.filename.startswith("__MACOSX/"):
                name = Path(item.filename).name
                if name[:8] in construction_codes or name == "DSLIB_Analysis_Sheet.xlsx":
                    destination = (excel_folder / name).resolve()
                    if destination.parent != excel_folder.resolve():
                        raise ValueError("Unsafe archive filename")
                    if not destination.exists():
                        destination.write_bytes(archive.read(item))
                with archive.open(item) as source:
                    workbook = load_workbook(source, read_only=True, data_only=True)
                    for sheet in workbook:
                        sample = []
                        for row in sheet.iter_rows(values_only=True):
                            values = [str(cell) for cell in row if cell is not None]
                            if values:
                                sample.append(values[:25])
                            if len(sample) == 5:
                                break
                        sheets.append(dict(file=item.filename, sheet=sheet.title, max_rows=sheet.max_row,
                                           max_columns=sheet.max_column, first_nonempty_rows=json.dumps(sample)))
                    workbook.close()
    write_csv(OUT / "ghent_files.csv", files)
    write_csv(OUT / "ghent_sheets.csv", sheets)
    write_csv(OUT / "ghent_projects_for_review.csv", projects)
    return dict(source="https://github.com/MarioVanhoucke/DSLIB-Dynamic-Scheduling-Empirical-Project-Library/releases/tag/DSLIB_v3.4",
                archive_sha256=hashlib.sha256(archive_path.read_bytes()).hexdigest(),
                file_count=len(files), excel_files=len({row["file"] for row in sheets}),
                license="No explicit reuse license established; citation requested in repository README",
                project_records=len(projects), unique_project_codes=len({row["project_code"] for row in projects}),
                construction_records=sum(str(row["sector"]).lower().startswith("construction") for row in projects),
                construction_with_numeric_real_duration=sum(row["numeric_real_duration"] and str(row["sector"]).lower().startswith("construction") for row in projects),
                project_count_caveat="Rows and numeric durations are not verified independent historical labels; authenticity codes require interpretation",
                units="Inspect project calendars and Excel field definitions before deriving delays",
                ifc_link="Not established",
                decision="Separate Schedule V2 candidate; no compatible building-feature schema established",
                caveat="Related subprojects and rescheduled versions must be grouped; planned durations are not observed outcomes")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    inventory = {"cambridge": cambridge(), "ghent": ghent()}
    (OUT / "dataset_inventory.json").write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(inventory, indent=2))
