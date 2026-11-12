"""Stage 2.3A: collect source evidence without approving or releasing labels.

Read-only XLSX/PDF/ProTrack inspection. Outputs are separate from Stage 2.2.
Requires openpyxl and pypdf. No network access, training, splitting or approvals.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import unicodedata
import warnings
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from pypdf import PdfReader

from prepare_ghent_delays import ROOT, SOURCE, OUT, VERIFICATION_FIELDS, load_verification, process_records, read_source, target_blockers, text, write_csv

RAW = ROOT / "data/raw/ghent"
ORIGINALS = RAW / "buildings/DSLIB 3.4"
PAPER_URL = "https://iranarze.ir/storage/uploads/2016/09/4960-English.pdf"
PAPER_DOI = "https://doi.org/10.1016/j.ijproman.2014.09.004"


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).replace("\x00", "").strip()


def project_code(name: str) -> str:
    match = re.match(r"(C\d{4})-(\d{1,2})(?:\D|$)", name)
    return f"{match[1]}-{int(match[2]):02d}" if match else ""


def one_source(folder: Path, code: str, suffixes: tuple[str, ...]) -> Path | None:
    matches = [p for p in folder.iterdir() if project_code(p.name) == code and p.name.lower().endswith(suffixes)]
    if len(matches) > 1:
        raise ValueError(f"Ambiguous source files for {code}: {matches}")
    return matches[0] if matches else None


def parse_duration(value, hours_per_day: float | None) -> float | None:
    """Read explicit d/h display tokens; never assume hours per day or numeric units."""
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\s*(?:(\d+(?:\.\d+)?)d)?\s*(?:(\d+(?:\.\d+)?)h)?\s*", value)
    if not match or not any(match.groups()):
        return None
    days, hours = map(lambda v: float(v) if v is not None else 0., match.groups())
    if hours and (hours_per_day is None or hours_per_day <= 0):
        return None
    return days + (hours / hours_per_day if hours else 0)


def duration_match(display, expected, hours_per_day) -> str:
    value = parse_duration(display, hours_per_day)
    if value is None:
        return "unresolved"
    if math.isclose(value, float(expected), abs_tol=1e-6):
        return "exact"
    if abs(value - float(expected)) <= .500001:
        return "within_half_day_rounding_only"
    return "mismatch"


def inspect_protrack(path: Path | None) -> dict:
    if path is None:
        return {}
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            names = [n for n in archive.namelist() if n.lower().endswith(".p2x") and not n.startswith("__MACOSX/")]
            if len(names) != 1:
                raise ValueError(f"Ambiguous ProTrack XML in {path}")
            root = ET.fromstring(archive.read(names[0]))
            member = names[0]
    else:
        root = ET.fromstring(path.read_bytes())
        member = ""
    defaults = root.find("Defaults")
    hours = defaults.findtext("DefaultWorkingHoursPerDay") if defaults is not None else None
    agenda = root.find("Agenda")
    simulation_markers = [dict(xpath=f".//TrackingPeriod[{i}]/Description", value=node.findtext("Description"))
                          for i, node in enumerate(root.findall(".//TrackingPeriod"), 1)
                          if "simulat" in (node.findtext("Description") or "").lower()]
    return dict(path=relative(path), member=member, hours_per_day=float(hours) if hours else None,
                hours_reference="/Project/Defaults/DefaultWorkingHoursPerDay",
                agenda=ET.tostring(agenda, encoding="unicode") if agenda is not None else "",
                simulation_markers=simulation_markers)


def populated_cells(sheet, max_row=None, max_col=None) -> list[dict]:
    return [dict(cell=c.coordinate, value=c.value) for row in sheet.iter_rows(max_row=max_row, max_col=max_col)
            for c in row if c.value is not None]


def inspect_workbook(path: Path | None) -> dict:
    if path is None:
        return {}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            result = dict(path=relative(path), sheet_names=workbook.sheetnames)
            baseline = workbook["Baseline Schedule"] if "Baseline Schedule" in workbook.sheetnames else None
            if baseline is not None:
                result["baseline_cells"] = populated_cells(baseline, max_row=5, max_col=18)
                headers = list(baseline.iter_rows(min_row=2, max_row=2, values_only=True))[0]
                roots = [row for row in baseline.iter_rows(min_row=3, max_row=8) if row[0].value == 0]
                if roots and "Duration" in headers:
                    index = headers.index("Duration")
                    result["baseline_duration"] = dict(cell=roots[0][index].coordinate, value=roots[0][index].value)
                    result["baseline_start"] = dict(cell=roots[0][5].coordinate, value=roots[0][5].value)
                    result["baseline_end"] = dict(cell=roots[0][6].coordinate, value=roots[0][6].value)
            if "Agenda" in workbook.sheetnames:
                cells = populated_cells(workbook["Agenda"], max_col=7)
                result["agenda_cells"] = cells
                by_ref = {c["cell"]: c["value"] for c in cells}
                active_hours = [str(by_ref.get(f"A{i}", "")) for i in range(2, 26) if by_ref.get(f"B{i}") == "Yes"]
                result["calendar"] = dict(active_hour_slots=active_hours, active_hour_count=len(active_hours),
                    working_days=[by_ref.get(f"D{i}") for i in range(2, 9) if by_ref.get(f"E{i}") == "Yes"],
                    holidays=[c for c in cells if re.fullmatch(r"G\d+", c["cell"]) and c["cell"] != "G1"])
            tps = [(int(match[1]), name) for name in workbook.sheetnames
                   if (match := re.fullmatch(r"(?:Project Control\s*-\s*)?TP\s*(\d+)", name, re.I))]
            if tps:
                name = max(tps)[1]
                sheet = workbook[name]
                result["last_tracking_sheet"] = name
                result["last_tracking_cells"] = populated_cells(sheet, max_row=7, max_col=24)
                rows = list(sheet.iter_rows(min_row=1, max_row=8))
                for i, row in enumerate(rows):
                    headers = [cell.value for cell in row]
                    if "Actual Duration" not in headers or "ID" not in headers:
                        continue
                    for root in rows[i + 1:]:
                        if root[headers.index("ID")].value == 0:
                            for field, label in (("actual_duration", "Actual Duration"), ("completion", "Percentage Completed")):
                                if label in headers:
                                    c = root[headers.index(label)]
                                    result[field] = dict(sheet=name, cell=c.coordinate, value=c.value)
                            break
        finally:
            workbook.close()
        result["reader_warnings"] = sorted({str(w.message) for w in caught})
    return result


def inspect_card(path: Path | None) -> dict:
    if path is None:
        return {}
    reader = PdfReader(path)
    pages = [normalize(page.extract_text() or "") for page in reader.pages]
    layouts = [normalize(page.extract_text(extraction_mode="layout") or "") for page in reader.pages]
    result = dict(path=relative(path), pages=[dict(page=i, text=value, layout=layouts[i-1]) for i, value in enumerate(pages, 1)])
    # Explicit prose only: do not treat unselected checkbox labels or risk-analysis simulations as tracking evidence.
    simulation = []
    observed = []
    for i, page in enumerate(pages, 1):
        compact = re.sub(r"\s+", " ", page)
        for match in re.finditer(r"(?:Real Duration and Real Cost|real duration and real cost).{0,180}?simulation results", compact):
            simulation.append(dict(page=i, text=match[0]))
        for match in re.finditer(r"(?:tracking data|tracking information|tracking was|tracking is|actual activity start dates).{0,220}", compact, re.I):
            statement = match[0]
            if any(term in statement.lower() for term in ("project owner", "actual", "company", "contractor", "real data")):
                observed.append(dict(page=i, text=statement))
    result.update(explicit_simulated_outcome_statements=simulation, tracking_prose_for_review=observed)
    return result


def guard_hashes() -> dict:
    paths = list(RAW.rglob("*")) + list((ROOT / "models/duration_v1").glob("*"))
    paths += list((ROOT / "scripts").glob("*.py"))
    paths += [ROOT / "app.py", ROOT / "training/train_model.py", ROOT / "training/prepare_ghent_delays.py"]
    paths += [OUT / "duration_verification_template.csv", OUT / "ghent_verified_labels.csv", OUT / "cleaning_report.md"]
    return {relative(p): sha(p) for p in paths if p.is_file()}


def evidence_row(code, requirement, source, worksheet, reference, value, status, interpretation):
    return dict(project_id=code, requirement=requirement, source=source, worksheet=worksheet,
                cell_or_page_or_xpath=reference, source_value=value, status=status, interpretation=interpretation)


def run(output: Path = OUT) -> dict:
    output = output.resolve()
    if not output.is_relative_to(OUT.resolve()):
        raise ValueError("Evidence outputs must stay under data/processed/stage2")
    before = guard_hashes()
    records, docs = read_source(SOURCE)
    buildings, _, old_groups = process_records(records, docs)
    candidates = [r for r in buildings if r["planned_duration_status"] == r["real_duration_status"] == "valid"]
    if len(candidates) != 68 or any(r["duplicate_id"] for r in candidates):
        raise ValueError("Expected 68 unique positive-duration candidates; review the source before verification")
    template = load_verification(OUT / "duration_verification_template.csv")
    if set(template) != {r["project_id"] for r in candidates}:
        raise ValueError("Verification template does not match the 68 positive-duration candidates")
    output.mkdir(parents=True, exist_ok=True)
    evidence, matrix, proposed, details = [], [], [], {}
    problems = docs["Known Problems"]
    for row in candidates:
        code = row["project_id"]
        workbook_path = one_source(ORIGINALS / "Excel", code, (".xlsx",))
        card_path = one_source(ORIGINALS / "Project Card", code, (".pdf",))
        track_path = one_source(ORIGINALS / "Protrack", code, (".p2x", ".p2x.zip"))
        w = inspect_workbook(workbook_path)
        c = inspect_card(card_path)
        p = inspect_protrack(track_path)
        details[code] = dict(workbook=w, project_card=c, protrack=p)
        n = row["source_excel_row"]
        for requirement, ref, value in (("planned_duration", f"L{n}", row["planned_duration_source"]),
                                        ("real_duration", f"CE{n}", row["real_duration_source"]),
                                        ("source_ratio", f"R{n}", row["early_late_source"]),
                                        ("project_authenticity", f"I{n}", row["project_authenticity_raw"]),
                                        ("tracking_authenticity", f"J{n}", row["tracking_authenticity_raw"])):
            evidence.append(evidence_row(code, requirement, relative(SOURCE), "DSLIB", ref, value, "supported_source_value",
                                         "Original source value; no verification approval implied"))
        for field, ref in (("planned_real_interpretation", "B33:C33;B89:C89"),
                           ("authenticity_definitions", "B25:C29")):
            evidence.append(evidence_row(code, field, relative(SOURCE), "Overview", ref, "See source documentation snapshot",
                                         "supported", "Overview identifies planned/real meaning; no calendar equivalence or authenticity approval"))
        updates = [cell for cell in docs.get("Updates", []) if text(cell["value"]) == code]
        for cell in updates:
            r = cell["row"]
            values = [v for v in docs["Updates"] if v["row"] == r]
            evidence.append(evidence_row(code, "baseline_history_or_tracking_updates", relative(SOURCE), "Updates",
                f"A{r}:G{r}", " | ".join(text(v["value"]) for v in values), "requires_review", "May affect version or duration comparability"))
        evidence.append(evidence_row(code, "known_problems", relative(SOURCE), "Known Problems", "A1:C4",
            json.dumps(problems, default=str), "no_listed_issue_for_this_id", "Absence is not a quality certificate"))
        hours = p.get("hours_per_day")
        planned = w.get("baseline_duration", {})
        actual = w.get("actual_duration", {})
        planned_match = duration_match(planned.get("value"), row["planned_duration_days"], hours)
        actual_match = duration_match(actual.get("value"), row["real_duration_days"], hours)
        for requirement, info, sheet, comparison in (("baseline_root_duration", planned, "Baseline Schedule", planned_match),
            ("last_tracking_root_duration", actual, actual.get("sheet", ""), actual_match)):
            evidence.append(evidence_row(code, requirement, w.get("path", ""), sheet, info.get("cell", ""),
                info.get("value"), comparison, "Comparison uses explicit ProTrack hours/day when needed; half-day tolerance is a rounding hypothesis, not approval"))
        calendar = w.get("calendar", {})
        if calendar:
            evidence.append(evidence_row(code, "calendar_settings", w["path"], "Agenda", "A1:B25;D1:E8;G:G",
                json.dumps(calendar, default=str), "supported_calendar_settings", "Recorded project calendar; not proof of unchanged historical baseline or actual-day equivalence"))
        if hours:
            evidence.append(evidence_row(code, "display_day_conversion_setting", p["path"], p["member"], p["hours_reference"],
                hours, "supported_setting", "An explicit saved setting, not an assumed universal eight-hour working day"))
        for marker in p.get("simulation_markers", [])[:3]:
            evidence.append(evidence_row(code, "tracking_provenance", p["path"], p["member"], marker["xpath"], marker["value"],
                "simulation_marker_requires_review", "A tracking-period marker is evidence to investigate, not proof every observed value is simulated"))
        for statement in c.get("explicit_simulated_outcome_statements", []):
            evidence.append(evidence_row(code, "tracking_provenance", c["path"], "PDF", f"page {statement['page']}",
                statement["text"], "explicit_simulated_outcome", "Card expressly attributes the Real Duration/Cost to simulation; not verified historical outcome"))
        for statement in c.get("tracking_prose_for_review", []):
            evidence.append(evidence_row(code, "tracking_provenance", c["path"], "PDF", f"page {statement['page']}",
                statement["text"], "prose_for_manual_review", "Tracking narrative located; human review needed before accepting actual provenance"))
        combined_text = " ".join(page["text"] + " " + page["layout"] for page in c.get("pages", []))
        # A day unit is directly visible in the card only if it labels the real duration itself.
        real_units = list(re.finditer(r"Real\s+Duration\s+([0-9.,]+)\s+days", combined_text, re.I))
        real_unit_supported = bool(real_units)
        working_footnote = re.search(r"(?:eight.hour|8.hour|\d+.hour|standard).{0,35}working days", combined_text, re.I)
        proposal = dict.fromkeys(VERIFICATION_FIELDS, "")
        proposal.update(project_id=code, planned_unit="days")
        unit_refs = [f"{relative(SOURCE)}!DSLIB!L3; Overview!B33:C33"]
        if real_unit_supported:
            proposal["real_unit"] = "days"
            for page in c["pages"]:
                match = re.search(r"Real\s+Duration\s+[0-9.,]+\s+days", page["layout"] + " " + page["text"], re.I)
                if match:
                    unit_refs.append(f"{c['path']} page {page['page']}: {match[0]}")
                    evidence.append(evidence_row(code, "real_duration_unit", c["path"], "PDF", f"page {page['page']}", match[0],
                        "supported_unit_label", "Unit label only; the value, day basis and historical authenticity still need reconciliation"))
                    break
        if working_footnote:
            proposal["planned_day_basis"] = "working"
            for page in c["pages"]:
                if working_footnote[0] in page["text"]:
                    evidence.append(evidence_row(code, "planned_day_basis", c["path"], "PDF", f"page {page['page']}",
                        working_footnote[0], "supported_planned_basis", "Footnote for planned duration; do not extrapolate to real duration"))
                    break
        proposal["unit_evidence"] = "; ".join(unit_refs)
        if calendar:
            proposal["calendar_evidence"] = f"{w['path']}!Agenda!A1:B25;D1:E8;G:G records {calendar['active_hour_count']} active hourly slots and {calendar['working_days']}; shared basis unresolved"
        proposal["baseline_evidence"] = f"{w.get('path', 'workbook missing')}!Baseline Schedule!{planned.get('cell', 'root missing')}={planned.get('value')}; summary match={planned_match}; original issue/version not verified"
        proposed.append(proposal)
        blockers = target_blockers(row, proposal, docs["definitions"])
        questions = ["Identify the original issued baseline and any later revisions", "Verify actual duration uses the same day/calendar convention",
                     "Review outcome provenance and source authenticity", "Review parent-project/phase identity", "Independent reviewer sign-off remains blank"]
        if row["early_late_check"] == "mismatch":
            questions.append("Reconcile duration pair with Early/late; do not correct values automatically")
        matrix.append(dict(project_id=code, project_name=row["project_name"], source_excel_row=n,
            workbook=w.get("path", ""), project_card=c.get("path", ""), protrack=p.get("path", ""),
            planned_duration_source=row["planned_duration_source"], real_duration_source=row["real_duration_source"],
            planned_duration_ref=f"DSLIB!L{n}", real_duration_ref=f"DSLIB!CE{n}",
            baseline_root_ref=f"Baseline Schedule!{planned.get('cell', '')}", baseline_root_value=planned.get("value"),
            last_tracking_ref=f"{actual.get('sheet', '')}!{actual.get('cell', '')}", last_tracking_value=actual.get("value"),
            last_tracking_completion=w.get("completion", {}).get("value"),
            baseline_comparison=planned_match, actual_comparison=actual_match,
            explicit_hours_per_day=hours, calendar_settings_found=bool(calendar),
            real_unit_directly_documented=real_unit_supported, planned_working_basis_documented=bool(working_footnote),
            project_authenticity=row["project_authenticity"], tracking_authenticity=row["tracking_authenticity"],
            explicit_simulated_outcome=bool(c.get("explicit_simulated_outcome_statements")),
            tracking_simulation_marker=bool(p.get("simulation_markers")),
            early_late_check=row["early_late_check"], update_notes=row["update_notes"],
            review_group_id=row["review_group_id"], potential_related_projects=row["potential_related_projects"],
            original_baseline_verified="", calendar_comparable="", independence_verified="", verified_by="",
            label_release_status="blocked", release_blockers=";".join(blockers),
            unresolved_questions="; ".join(questions)))
        print(f"Inspected {code}: baseline={planned_match}, actual={actual_match}", flush=True)
    inconsistencies = investigate_ratios(candidates, matrix, details)
    group_proposals = propose_groups(candidates, old_groups, details)
    write_csv(output / "verification_matrix.csv", matrix)
    write_csv(output / "verification_evidence.csv", evidence)
    write_csv(output / "duration_verification_evidence_proposal.csv", proposed, VERIFICATION_FIELDS)
    write_csv(output / "duration_ratio_investigation.csv", inconsistencies)
    write_csv(output / "grouping_proposals.csv", group_proposals)
    (output / "verification_source_extracts.json").write_text(json.dumps(dict(summary_sheets=docs, projects=details),
        indent=2, default=str) + "\n", encoding="utf-8")
    requirements = release_requirements()
    write_csv(output / "verification_requirements.csv", requirements)
    write_csv(output / "verification_field_counts.csv", field_counts(proposed, candidates))
    write_authenticity_search(output)
    counts = requirement_counts(matrix)
    write_csv(output / "verification_requirement_counts.csv", counts)
    after = guard_hashes()
    if before != after:
        raise RuntimeError("A protected source, existing label artifact or Stage 1/application file changed")
    (output / "verification_protected_hashes.json").write_text(json.dumps(before, indent=2) + "\n", encoding="utf-8")
    summary = dict(projects=len(matrix), requirements=counts, released_labels=0, automatically_approved_projects=0,
                   explicit_simulated_outcomes=sum(r["explicit_simulated_outcome"] for r in matrix),
                   gg_with_simulation_conflict=sum(r["explicit_simulated_outcome"] and r["project_authenticity"] == r["tracking_authenticity"] == "G" for r in matrix),
                   tracking_simulation_markers=sum(r["tracking_simulation_marker"] for r in matrix),
                   baseline_comparisons=dict(Counter(r["baseline_comparison"] for r in matrix)),
                   actual_comparisons=dict(Counter(r["actual_comparison"] for r in matrix)),
                   ratio_inconsistencies=len(inconsistencies), protected_files_unchanged=len(before))
    (output / "verification_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_verification_report(output, summary, inconsistencies)
    return summary


def investigate_ratios(candidates, matrix, details) -> list[dict]:
    lookup = {r["project_id"]: r for r in matrix}
    result = []
    for row in candidates:
        if row["early_late_check"] != "mismatch":
            continue
        code = row["project_id"]
        m, d = lookup[code], details[code]
        card_lines = []
        card_baselines = []
        for page in d["project_card"].get("pages", []):
            compact = re.sub(r"\s+", " ", page.get("layout", page["text"]))
            # Physical layout separates labelled duration values from forecasting prose.
            for match in re.finditer(r"\bPD\s+([0-9.,]+)(?:\s+days)?\s+Real\s+Duration\s+([0-9.,]+)(?:\s+days)?", compact, re.I):
                card_lines.append(f"page {page['page']}: {match[0]}")
                card_baselines.append(float(match[1].replace(",", ".")))
        planned_value = parse_duration(m["baseline_root_value"], m["explicit_hours_per_day"])
        actual_value = parse_duration(m["last_tracking_value"], m["explicit_hours_per_day"])
        display_ratio = actual_value / planned_value - 1 if planned_value and actual_value is not None else None
        ratio = float(row["early_late_source"])
        alternative = (row["real_duration_days"] - row["planned_duration_days"]) / row["real_duration_days"]
        alternatives_from_card = [v for v in card_baselines if not math.isclose(v, row["planned_duration_days"], abs_tol=1e-6)
                                  and abs(row["real_duration_days"] / v - 1 - ratio) <= .0051]
        findings = []
        if alternatives_from_card:
            findings.append(f"Card PD={alternatives_from_card} differs from summary PD and reproduces the ratio; possible baseline/version or transcription conflict")
        if math.isclose(math.trunc(row["audit_computed_duration_ratio"] * 100) / 100, ratio, abs_tol=1e-8):
            findings.append("Truncating the computed fractional ratio toward zero to two decimals reproduces the source; precision policy unverified")
        if math.isclose(row["audit_computed_duration_ratio"], -ratio, abs_tol=.0051):
            findings.append("Opposite sign fits the summary pair; card and Updates must be reconciled before correcting")
        if abs(alternative - ratio) <= .0051:
            findings.append("Dividing by real rather than planned duration reproduces the source within tolerance; denominator inconsistent with Overview")
        if display_ratio is not None and abs(display_ratio - ratio) <= .0051:
            findings.append("Saved workbook displays reproduce the ratio more closely; verify baseline version")
        if not findings:
            findings.append("No uniquely supported correction; conflicting source values require owner/reviewer clarification")
        if planned_value is None or actual_value is None:
            findings.append("Project workbook has no readable cached project-level duration for this comparison")
        hypothesis = "; ".join(findings)
        result.append(dict(project_id=code, workbook=m["workbook"], summary_ref=f"DSLIB!L{row['source_excel_row']};CE{row['source_excel_row']};R{row['source_excel_row']}",
            planned_summary=row["planned_duration_source"], real_summary=row["real_duration_source"], early_late_summary=ratio,
            ratio_from_summary_pair=row["audit_computed_duration_ratio"], baseline_display=m["baseline_root_value"],
            baseline_cell=m["baseline_root_ref"], actual_display=m["last_tracking_value"], actual_cell=m["last_tracking_ref"],
            explicit_hours_per_day=m["explicit_hours_per_day"], ratio_from_display_pair=display_ratio,
            ratio_with_actual_denominator=alternative, conflicting_card_baselines=";".join(map(str, alternatives_from_card)),
            project_card=m["project_card"], project_card_evidence=" | ".join(card_lines), update_evidence=m["update_notes"],
            hypothesis=hypothesis, resolution_status="unresolved_manual_review", source_issue_reviewed="",
            proposed_value_correction="", question="Which baseline/version and duration convention underlie the supplied Early/late?"))
    return result


def propose_groups(candidates, old_groups, details) -> list[dict]:
    result = []
    candidate_ids = {r["project_id"] for r in candidates}
    for group in old_groups:
        ids = [code for code in group["project_ids"].split(";") if code in candidate_ids]
        if len(ids) < 2:
            continue
        evidence = []
        for code in ids:
            for page in details[code]["project_card"].get("pages", []):
                compact = re.sub(r"\s+", " ", page["text"])
                # Narrative evidence only; never assert a parent match from generic names.
                for match in re.finditer(r".{0,55}(?:same (?:project|building|company)|part of|phase|several houses|residential area).{0,100}", compact, re.I):
                    evidence.append(f"{code} {details[code]['project_card']['path']} page {page['page']}: {match[0]}")
        phase = group["review_group_id"] in ("name:residential house", "name:apartment building")
        members = [r for r in candidates if r["project_id"] in ids]
        collection_cohorts = defaultdict(list)
        for member in members:
            collection_cohorts[f"{member['project_id'][1:5]} / {text(member.get('submitted_by'))}"].append(member["project_id"])
        result.append(dict(proposed_group_id=group["review_group_id"], project_ids=";".join(ids),
            evidence=" | ".join(evidence) or group["evidence"],
            summary_identity_refs="; ".join(f"{r['project_id']}: DSLIB!A{r['source_excel_row']}:D{r['source_excel_row']}" for r in members),
            collection_cohorts=json.dumps(dict(collection_cohorts)),
            proposed_decision="Keep same-fold until parent identity is resolved" if phase else "Review shared identity; conservatively keep same-fold if splitting later",
            relationship_status="uncertain_manual_review", grouping_verified="", independence_verified="",
            question="Review each collection cohort first; do not merge across years/collectors on generic names alone. Are these separate buildings or phases of one parent?"))
    return result


def release_requirements():
    conditions = {
        "project_id": "Present valid unique building project ID with positive planned and real durations",
        "planned_unit": "days", "real_unit": "days", "planned_day_basis": "working or calendar",
        "real_day_basis": "same as planned_day_basis", "planned_calendar": "Documented calendar identifier",
        "real_calendar": "Documented calendar identifier", "calendar_comparable": "Explicit true with supporting evidence",
        "original_baseline_verified": "Explicit true with original prediction-time baseline evidence",
        "unit_evidence": "Nonempty direct evidence", "calendar_evidence": "Nonempty evidence of comparability, not merely calendar presence",
        "baseline_evidence": "Nonempty original-baseline evidence", "verified_by": "Identified reviewer; never auto-filled",
        "source_issue_reviewed": "True if known issue or ratio contradiction applies", "source_issue_evidence": "Required to resolve source issue",
        "independence_verified": "Additional true attestation for independently usable count", "independence_evidence": "Additional documented identity/parent review",
    }
    return [dict(field=field, requirement=conditions[field], scope="independently_usable_additional" if field.startswith("independence") else "label_release",
                 authority="training/prepare_ghent_delays.py: target_blockers / process_records; unchanged") for field in VERIFICATION_FIELDS]


def field_counts(proposed, candidates):
    issue_ids = {r["project_id"] for r in candidates if r["early_late_check"] == "mismatch" or r["known_problem_notes"]}
    result = []
    for field in VERIFICATION_FIELDS:
        applicable = [r for r in proposed if r["project_id"] in issue_ids] if field.startswith("source_issue") else proposed
        populated = sum(bool(text(r[field])) for r in applicable)
        result.append(dict(field=field, applicable_projects=len(applicable), populated_from_observations=populated,
                           missing_or_unresolved=len(applicable)-populated, not_applicable=len(proposed)-len(applicable),
                           note="Populated notes or unit labels are observations, not an attestation or approval. See requirement milestones for substantive verification."))
    return result


def write_authenticity_search(output):
    search = dict(checked_date="2026-11-11", sources=[
        dict(source=relative(SOURCE), location="Overview!B25:C29", finding="Colour-coded framework referenced, no explicit G/Y/O legend"),
        dict(source=relative(ORIGINALS / "Readme.rtf"), location="Citation and versioning sections", finding="Points to Batselier & Vanhoucke 2015; no code legend"),
        dict(source="https://biblio.ugent.be/publication/5978659", location="Downloads", finding="Original article identified; full text UGent-only"),
        dict(source=PAPER_URL, canonical_source=PAPER_DOI, location="Printed pp. 699–700, sections 2.1.1 and 2.1.4",
             finding="Explicit G=green, Y=yellow, O=orange; project/tracking authenticity definitions and N/A documented"),
        dict(source="https://discovery.ucl.ac.uk/id/eprint/1506266/1/Vanhoucke_Vanhoucke%20et%20al,%20JMPM,%202016.pdf",
             location="Sections 4.1.1–4.1.2, printed pp. 15–16", finding="Author paper corroborates colour-based framework and static/tracking distinction"),
    ], code_to_colour={"G": "green", "Y": "yellow", "O": "orange"},
    interpretation_limit="Dictionary meaning only; no project codes or authenticity approvals changed. Individual cards contain contradictory provenance claims.")
    (output / "authenticity_source_search.json").write_text(json.dumps(search, indent=2) + "\n", encoding="utf-8")


def requirement_counts(matrix):
    total = len(matrix)
    supported = {
        "positive_duration_pair_and_unique_id": total,
        "planned_real_interpretation": total,
        "planned_unit_days_source_header": total,
        "real_unit_days_direct_card_label": sum(r["real_unit_directly_documented"] for r in matrix),
        "planned_working_basis_direct_card_statement": sum(r["planned_working_basis_documented"] for r in matrix),
        "project_calendar_settings_located_NOT_comparability": sum(r["calendar_settings_found"] for r in matrix),
        "saved_hours_per_day_located": sum(r["explicit_hours_per_day"] is not None for r in matrix),
        "baseline_display_exact_summary_match": sum(r["baseline_comparison"] == "exact" for r in matrix),
        "actual_display_exact_summary_match": sum(r["actual_comparison"] == "exact" for r in matrix),
        "source_ratio_consistent_at_stage22_tolerance": sum(r["early_late_check"] != "mismatch" for r in matrix),
        "common_calendar_and_real_day_basis_verified": 0, "original_issued_baseline_verified": 0,
        "independence_verified": 0, "reviewer_signoff": 0, "all_label_release_requirements_passed": 0,
    }
    return [dict(requirement=name, supported_or_passed=count, unresolved_or_not_passed=total-count,
                 note="Evidence milestone only; not an approval" if name not in ("all_label_release_requirements_passed",) else "No projects automatically approved")
            for name, count in supported.items()]


def write_verification_report(output, summary, inconsistencies):
    lines = ["# PMI Stage 2.3A — Ghent evidence verification", "",
        "68 candidates inspected. This stage collects evidence and proposals only: no reviewer, approval flag, correction, label release, model or split is created.",
        "The Stage 2.2 template, cleaning report, labels and release logic are unchanged.", "",
        "## Requirement counts", "", "| Requirement / evidence milestone | Supported or passed | Unresolved / not passed |", "|---|---:|---:|"]
    lines += [f"| {r['requirement']} | {r['supported_or_passed']} | {r['unresolved_or_not_passed']} |" for r in summary["requirements"]]
    lines += ["", "Calendar settings and a displayed duration match do not establish original baseline identity, actual-data provenance or calendar comparability.",
        "Counts distinguish directly supported facts from release approvals. The proposal CSV contains only observed unit statements and evidence notes; all approval/sign-off flags stay empty.",
        "Existing template values were inspected, never overwritten. Explicit authorizations or evidence a reviewer adds later must still satisfy the unchanged Stage 2.2 gate.", "",
        "## Main findings", "",
        f"- {summary['explicit_simulated_outcomes']} cards expressly describe Real Duration/Cost as simulation-based; {summary['gg_with_simulation_conflict']} have G/G in the summary. These conflicts need provenance review, not automatic approval or correction.",
        f"- {summary['tracking_simulation_markers']} ProTrack sources contain simulated tracking-period descriptions; these markers need review alongside the card and supplied authenticity.",
        f"- Saved baseline display comparisons: {summary['baseline_comparisons']}. Saved final-tracking display comparisons: {summary['actual_comparisons']}.",
        "- Analysis sheet planned and real definitions are at Overview B33:C33 and B89:C89. Calendar settings are in each project's Agenda; explicit conversion defaults are recorded with ProTrack XML paths.",
        "- A Baseline Schedule sheet documents the saved baseline, not necessarily the original issued pre-execution plan. Updates records revisions; absence of an update is not verification.",
        "- Known Problems A4:C4 lists C2011-06 (out of scope); it cannot certify the remaining projects.", "",
        "## Ten ratio discrepancies", "", "| Project | Summary ratio | Supplied Early/late | Investigation |", "|---|---:|---:|---|"]
    lines += [f"| {r['project_id']} | {r['ratio_from_summary_pair']:.6f} | {r['early_late_summary']:.6f} | {r['hypothesis']} |" for r in inconsistencies]
    lines += ["", "All ten remain unresolved. See duration_ratio_investigation.csv for summary, workbook, PDF and update references. No sign, rounding, denominator or version correction is accepted automatically.",
        "Blank or unavailable project-level duration cells stay unresolved; no value is reconstructed from performance metrics. Half-day display matches are hypotheses, not repairs.", "",
        "## Authenticity source search", "",
        f"The primary paper [Batselier & Vanhoucke (2015)]({PAPER_DOI}), sections 2.1.1 and 2.1.4, printed pages 699–700, explicitly maps G/Y/O to green/yellow/orange.",
        "Green means all relevant source data came from the owner; yellow and orange indicate successively more assumed data types. Project authenticity covers activity/resource/baseline-cost data; tracking authenticity covers actual starts/durations/costs. N/A denotes no real tracking data. Missing codes remain unknown.",
        f"Read via a [full-text mirror]({PAPER_URL}); the [UGent record](https://biblio.ugent.be/publication/5978659) identifies the article but its institutional full text is restricted. The author-hosted UCL 2016 overview corroborates the framework in sections 4.1.1–4.1.2.",
        "These documented meanings do not certify any individual record, fill missing codes, or override a simulation warning.", "",
        "## Related projects", "",
        "grouping_proposals.csv distinguishes suspected name families from confirmed identity. Numbered residences, structural/finishing packages and apartment-building phases warrant conservative same-fold grouping if splitting is later authorized. Generic names alone cannot establish a common parent. All relationship approvals remain manual-review items.", "",
        "## Files and next verification work", "",
        "- verification_matrix.csv: one row per candidate, cell references, source comparisons and outstanding questions.",
        "- verification_evidence.csv and verification_source_extracts.json: detailed observations, worksheet/page/XML references and original extracted values.",
        "- duration_verification_evidence_proposal.csv: supported field proposals only; NOT approved verification.",
        "- verification_requirements.csv and verification_field_counts.csv: every existing release field, its scope and observed/unresolved counts.",
        "- duration_ratio_investigation.csv and grouping_proposals.csv: separate discrepancy and relationship reviews.",
        "- verification_protected_hashes.json: raw data, Stage 1 models, application scripts and existing Stage 2.2 artifacts were hash-checked unchanged.",
        "", "Obtain original-issued baseline provenance, reconcile actual day/calendar conventions and inconsistent pairs, confirm historical rather than simulated outcomes, resolve parent identities, and obtain reviewer sign-off.",
        "**0 labels released; 0 projects automatically approved; all 68 remain blocked.**"]
    (output / "verification_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    result = run(args.output_dir)
    print(json.dumps(result, indent=2))
