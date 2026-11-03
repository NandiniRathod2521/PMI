"""
PMI - STEP 2: EXPORT GEOMETRY FOR RHINO / GRASSHOPPER
=====================================================

Rhino does not read IFC reliably on its own (that is what caused the earlier
"missing meshes" problems).  So we let IfcOpenShell triangulate every element
in Python and save plain meshes (vertices + faces) to a JSON file, tagged with
the change status from data/changes.json.

Grasshopper / Rhino then only has to read a JSON file - no IFC plug-in needed.

Output: grasshopper/pmi_geometry.json
        {"elements": [{"global_id", "ifc_type", "name", "status", "category",
                       "vertices": [[x,y,z],...], "faces": [[a,b,c],...]}]}

Run (after detect_changes.py):
    python scripts/export_geometry.py
"""

from __future__ import annotations

import json
import multiprocessing
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "models" / "revised.ifc"
CHANGES = ROOT / "data" / "changes.json"
OUT = ROOT / "grasshopper" / "pmi_geometry.json"


def category(ifc_type: str) -> str:
    t = ifc_type.lower()
    if "wall" in t:
        return "wall"
    if "door" in t:
        return "door"
    if "window" in t:
        return "window"
    return "other"


def make_settings():
    s = ifcopenshell.geom.settings()
    try:
        s.set("use-world-coords", True)          # IfcOpenShell 0.8 / 0.9
    except Exception:
        s.set(s.USE_WORLD_COORDS, True)          # IfcOpenShell 0.7
    return s


def main():
    status = {}
    if CHANGES.is_file():
        data = json.loads(CHANGES.read_text(encoding="utf-8"))
        status = {c["global_id"]: c["status"] for c in data["changes"]}
    else:
        print("WARNING: data/changes.json not found - run detect_changes.py first. Exporting all as UNCHANGED.")

    model = ifcopenshell.open(str(MODEL))
    elements = model.by_type("IfcBuildingElement")
    settings = make_settings()

    out, failed = [], []
    it = ifcopenshell.geom.iterator(settings, model, multiprocessing.cpu_count(), include=elements)
    if it.initialize():
        while True:
            shape = it.get()
            el = model.by_id(shape.id)
            v = shape.geometry.verts
            f = shape.geometry.faces
            verts = [[round(v[i], 4), round(v[i + 1], 4), round(v[i + 2], 4)] for i in range(0, len(v), 3)]
            faces = [[f[i], f[i + 1], f[i + 2]] for i in range(0, len(f), 3)]
            out.append({
                "global_id": el.GlobalId,
                "ifc_type": el.is_a(),
                "name": el.Name or "",
                "status": status.get(el.GlobalId, "UNCHANGED"),
                "category": category(el.is_a()),
                "vertices": verts,
                "faces": faces,
            })
            if not it.next():
                break

    exported = {e["global_id"] for e in out}
    failed = [e.GlobalId for e in elements if e.GlobalId not in exported]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"source": MODEL.name, "units": "metres", "elements": out}), encoding="utf-8")

    n_changed = sum(e["status"] != "UNCHANGED" for e in out)
    print(f"Exported {len(out)} element meshes ({n_changed} changed) -> {OUT}")
    if failed:
        print(f"{len(failed)} elements had no 3D body (e.g. no representation): {failed[:5]}...")


if __name__ == "__main__":
    main()
