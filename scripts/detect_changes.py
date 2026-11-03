"""
PMI - STEP 1: IFC CHANGE DETECTION  (deterministic - no AI involved)
=====================================================================

What it does
------------
Compares models/original.ifc (V1) with models/revised.ifc (V2) element by element,
matching elements by their IFC GlobalId (a stable unique id that survives re-export).

For every element it checks FIVE separate "change channels", so PMI can say not
only *that* something changed but *what kind* of change it is:

    1. attribute  - Name, Description, ObjectType, Tag
    2. property   - property sets / quantity sets (Psets, Qtos)
    3. material   - assigned material names
    4. type       - assigned element type (e.g. door type)
    5. geometry   - placement + shape representation (hashed, 0.1 mm tolerance)

An element is ADDED (only in V2), DELETED (only in V1), MODIFIED (any channel differs)
or UNCHANGED.  A renamed element is reported as an *attribute* change only - a new
name is NOT treated as proof of a geometric modification.

Outputs
-------
    data/changes.json   structured result used by the schedule engine, app and Grasshopper
    data/changes.csv    one row per element (easy to open in Excel)

Run
---
    python scripts/detect_changes.py
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

import ifcopenshell
import ifcopenshell.util.element as eutil

ROOT = Path(__file__).resolve().parents[1]
V1_PATH = ROOT / "models" / "original.ifc"
V2_PATH = ROOT / "models" / "revised.ifc"
OUT_JSON = ROOT / "data" / "changes.json"
OUT_CSV = ROOT / "data" / "changes.csv"

ATTRIBUTES = ["Name", "Description", "ObjectType", "Tag"]


# ----------------------------------------------------------------------------
# Helpers - each returns a comparable "fingerprint" for one change channel
# ----------------------------------------------------------------------------
def get_elements(model) -> dict:
    """All physical building elements keyed by GlobalId."""
    return {e.GlobalId: e for e in model.by_type("IfcBuildingElement") if e.GlobalId}


def attributes_of(element) -> dict:
    return {a: getattr(element, a, None) for a in ATTRIBUTES}


def properties_of(element) -> dict:
    """Psets + Qtos without the internal entity ids (ids differ between files)."""
    try:
        psets = eutil.get_psets(element)
    except Exception:
        return {}
    clean = {}
    for pset_name, props in psets.items():
        clean[pset_name] = {k: v for k, v in props.items() if k != "id"}
    return clean


def materials_of(element) -> list:
    try:
        mats = eutil.get_materials(element)
        return sorted({m.Name for m in mats if getattr(m, "Name", None)})
    except Exception:
        return []


def type_of(element) -> str:
    try:
        t = eutil.get_type(element)
        return t.Name if t is not None else ""
    except Exception:
        return ""


def _canon(value, memo: dict) -> str:
    """Canonical text of an IFC entity tree that ignores the #ids (file order)."""
    if isinstance(value, ifcopenshell.entity_instance):
        key = value.id()
        if key in memo:
            return memo[key]
        parts = [value.is_a()] + [_canon(value[i], memo) for i in range(len(value))]
        digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
        memo[key] = digest
        return digest
    if isinstance(value, (list, tuple)):
        return "(" + ",".join(_canon(v, memo) for v in value) + ")"
    if isinstance(value, float):
        return f"{round(value, 4):.4f}"  # 0.1 mm tolerance (model units = metres)
    return repr(value)


def geometry_hash(element, memo: dict) -> str:
    """Hash of where the element is (placement) and what shape it has (representation)."""
    parts = [
        _canon(element.ObjectPlacement, memo) if element.ObjectPlacement else "",
        _canon(element.Representation, memo) if element.Representation else "",
    ]
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()


def flatten_psets(psets: dict) -> dict:
    """{'Pset_DoorCommon': {'FireRating': 'EI 60'}} -> {'Pset_DoorCommon.FireRating': 'EI 60'}
    so the diff reports exactly which property changed, not the whole property set."""
    return {f"{ps}.{k}": v for ps, props in psets.items() for k, v in props.items()}


def describe(details: dict) -> str:
    """One readable line per change, e.g. "FireRating: 'Fire Rating' -> 'EI 60'; geometry"."""
    parts = []
    for field in ("Name", "Description", "ObjectType", "Tag"):
        if field in details.get("attribute", {}):
            parts.append(f"{field} changed")
    for key, d in details.get("property", {}).items():
        old = "not defined" if d["old"] is None else repr(d["old"])
        parts.append(f"{key.split('.', 1)[-1]}: {old} -> {d['new']!r}")
    if "material" in details:
        parts.append("material changed")
    if "type" in details:
        parts.append("element type changed")
    if "geometry" in details:
        parts.append("geometry (shape / position) changed")
    return "; ".join(parts)


def dict_diff(old: dict, new: dict) -> dict:
    """{key: {'old': .., 'new': ..}} for keys whose values differ."""
    out = {}
    for k in sorted(set(old) | set(new)):
        if old.get(k) != new.get(k):
            out[k] = {"old": old.get(k), "new": new.get(k)}
    return out


# ----------------------------------------------------------------------------
# Main comparison
# ----------------------------------------------------------------------------
def compare(v1_path: Path = V1_PATH, v2_path: Path = V2_PATH) -> dict:
    for p in (v1_path, v2_path):
        if not p.is_file():
            raise FileNotFoundError(p)

    m1, m2 = ifcopenshell.open(str(v1_path)), ifcopenshell.open(str(v2_path))
    e1, e2 = get_elements(m1), get_elements(m2)
    memo1, memo2 = {}, {}

    rows = []
    for gid in sorted(set(e1) | set(e2)):
        old, new = e1.get(gid), e2.get(gid)
        el = new if new is not None else old
        row = {
            "global_id": gid,
            "ifc_type": el.is_a(),
            "element": el.Name or "",
            "old_name": (old.Name or "") if old else "",
            "new_name": (new.Name or "") if new else "",
            "status": "UNCHANGED",
            "change_types": [],
            "details": {},
        }

        if old is None:
            row["status"] = "ADDED"
            row["change_types"] = ["added"]
        elif new is None:
            row["status"] = "DELETED"
            row["change_types"] = ["deleted"]
        else:
            checks = {
                "attribute": dict_diff(attributes_of(old), attributes_of(new)),
                "property": dict_diff(flatten_psets(properties_of(old)), flatten_psets(properties_of(new))),
                "material": dict_diff({"materials": materials_of(old)}, {"materials": materials_of(new)}),
                "type": dict_diff({"type": type_of(old)}, {"type": type_of(new)}),
            }
            g_old, g_new = geometry_hash(old, memo1), geometry_hash(new, memo2)
            if g_old != g_new:
                checks["geometry"] = {"hash": {"old": g_old[:10], "new": g_new[:10]}}

            changed = {k: v for k, v in checks.items() if v}
            if changed:
                row["status"] = "MODIFIED"
                row["change_types"] = list(changed)
                row["details"] = changed
        row["geometry_changed"] = "geometry" in row["change_types"]
        row["summary"] = describe(row["details"]) or row["status"].lower()
        rows.append(row)

    summary = {s: sum(r["status"] == s for r in rows) for s in ["ADDED", "DELETED", "MODIFIED", "UNCHANGED"]}
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "original_model": v1_path.name,
        "revised_model": v2_path.name,
        "method": "Deterministic GlobalId comparison over 5 channels (attribute, property, material, type, geometry)",
        "summary": summary,
        "changes": [r for r in rows if r["status"] != "UNCHANGED"],
        "all_elements": [
            {k: r[k] for k in ("global_id", "ifc_type", "element", "status")} for r in rows
        ],
    }


def main():
    result = compare()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    with OUT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["global_id", "ifc_type", "element", "status", "change_types", "geometry_changed", "what_changed"])
        changed = {c["global_id"]: c for c in result["changes"]}
        for r in result["all_elements"]:
            c = changed.get(r["global_id"], {})
            w.writerow([r["global_id"], r["ifc_type"], r["element"], r["status"],
                        ";".join(c.get("change_types", [])), c.get("geometry_changed", False),
                        c.get("summary", "")])

    print("\nPMI - BIM CHANGE DETECTION")
    print("--------------------------")
    for k, v in result["summary"].items():
        print(f"{k:<10}{v}")
    print("\nChanged elements:")
    for c in result["changes"]:
        print(f"  {c['ifc_type']:<20}{c['global_id']}  {c['element']}")
        print(f"      channels: {', '.join(c['change_types'])}   geometry changed: {c['geometry_changed']}")
        print(f"      what changed: {c['summary']}")
    print(f"\nSaved: {OUT_JSON}\nSaved: {OUT_CSV}")


if __name__ == "__main__":
    main()
