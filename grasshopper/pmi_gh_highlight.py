#! python3
"""
PMI - GRASSHOPPER CHANGE HIGHLIGHT  (paste into a Rhino 8 "Script" / Python 3 component)
=======================================================================================

How to use
----------
1. Grasshopper > Maths > Script > Python 3 Script  (or double-click canvas, type "Python 3")
2. Double-click the component, paste this whole file, press OK.
3. Default inputs x and y are used:
       x  (optional) path to pmi_geometry.json  - leave empty to use the default below
       y  (optional) Boolean Toggle: True = highlight changes, False = everything grey ("original" view)
4. Output a  = coloured meshes  -> previews directly (vertex colours)
   Output out = summary text printed by the script (connect a Panel)

Colours: unchanged = neutral grey, wall = red, door = orange, window = blue.

Why JSON and not IFC?  The meshes are triangulated by IfcOpenShell in
scripts/export_geometry.py, so Grasshopper never has to read IFC itself
(this avoids the earlier "missing mesh" problems).
"""

import json
import os

import Rhino.Geometry as rg
import System.Drawing as sd

DEFAULT_PATH = r"C:\Users\Chloe\PMI\PMI_MIDTERM_FINAL\grasshopper\pmi_geometry.json"

COLOURS = {
    "wall": sd.Color.FromArgb(214, 69, 69),
    "door": sd.Color.FromArgb(240, 140, 46),
    "window": sd.Color.FromArgb(47, 128, 237),
    "other": sd.Color.FromArgb(122, 90, 201),
}
GREY = sd.Color.FromArgb(200, 203, 208)

# ---- read inputs (works even if the component still has the default x / y names) ----
try:
    path = x if x else DEFAULT_PATH  # noqa: F821
except NameError:
    path = DEFAULT_PATH
try:
    highlight = True if y is None else bool(y)  # noqa: F821
except NameError:
    highlight = True

meshes, report = [], []
if not os.path.isfile(path):
    report.append("File not found: " + path + "\nRun run_pipeline.py first.")
else:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for e in data["elements"]:
        m = rg.Mesh()
        for vx, vy, vz in e["vertices"]:
            m.Vertices.Add(vx, vy, vz)
        for a, b, c in e["faces"]:
            m.Faces.AddFace(a, b, c)
        m.Normals.ComputeNormals()
        m.Compact()
        changed = e["status"] != "UNCHANGED"
        colour = COLOURS.get(e["category"], COLOURS["other"]) if (changed and highlight) else GREY
        m.VertexColors.CreateMonotoneMesh(colour)
        meshes.append(m)
        if changed:
            report.append("{}  {}  {}  [{}]".format(e["ifc_type"], e["global_id"], e["name"], e["status"]))
    report.insert(0, "PMI: {} elements loaded, {} changed{}".format(
        len(meshes), len(report), "" if highlight else "  (highlight OFF - original view)"))

a = meshes
print("\n".join(report))   # shows on the "out" output - connect a Panel
