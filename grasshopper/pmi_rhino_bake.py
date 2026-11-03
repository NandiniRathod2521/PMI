#! python3
"""
PMI - BAKE MODEL INTO RHINO WITH CHANGE LAYERS  (for clean presentation screenshots)
===================================================================================
Run inside Rhino 8:   command line ->  _-RunPythonScript "C:\\Users\\Chloe\\PMI\\PMI_MIDTERM_FINAL\\grasshopper\\pmi_rhino_bake.py"
                      or ScriptEditor -> open this file -> Run

Creates layers
    PMI::Unchanged         grey
    PMI::Changed_Wall      red
    PMI::Changed_Door      orange
    PMI::Changed_Window    blue
    PMI::Labels            text dots with element names
Each mesh gets the IFC GlobalId as its object name (select it -> Properties shows it).

For the "original model" screenshot: turn the PMI::Labels layer off and set the three
Changed_ layers to grey - or simply run with HIGHLIGHT = False below.
"""

import json
import os

import Rhino
import Rhino.Geometry as rg
import scriptcontext as sc
import System.Drawing as sd

PATH = r"C:\Users\Chloe\PMI\PMI_MIDTERM_FINAL\grasshopper\pmi_geometry.json"
HIGHLIGHT = True

LAYERS = {
    "unchanged": ("PMI::Unchanged", sd.Color.FromArgb(200, 203, 208)),
    "wall": ("PMI::Changed_Wall", sd.Color.FromArgb(214, 69, 69)),
    "door": ("PMI::Changed_Door", sd.Color.FromArgb(240, 140, 46)),
    "window": ("PMI::Changed_Window", sd.Color.FromArgb(47, 128, 237)),
    "other": ("PMI::Changed_Other", sd.Color.FromArgb(122, 90, 201)),
    "labels": ("PMI::Labels", sd.Color.FromArgb(27, 36, 48)),
}


def layer_index(full_name, colour):
    doc = sc.doc
    idx = doc.Layers.FindByFullPath(full_name, -1)
    if idx >= 0:
        return idx
    parent_name, child = full_name.split("::")
    p = doc.Layers.FindByFullPath(parent_name, -1)
    if p < 0:
        pl = Rhino.DocObjects.Layer()
        pl.Name = parent_name
        p = doc.Layers.Add(pl)
    layer = Rhino.DocObjects.Layer()
    layer.Name = child
    layer.Color = colour
    layer.ParentLayerId = doc.Layers[p].Id
    return doc.Layers.Add(layer)


def main():
    if not os.path.isfile(PATH):
        print("PMI: geometry file not found - run run_pipeline.py first:", PATH)
        return
    with open(PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # remove a previous PMI bake so the script can be re-run
    for name, _ in LAYERS.values():
        idx = sc.doc.Layers.FindByFullPath(name, -1)
        if idx >= 0:
            for obj in sc.doc.Objects.FindByLayer(sc.doc.Layers[idx]) or []:
                sc.doc.Objects.Delete(obj, True)

    idx = {k: layer_index(n, c) for k, (n, c) in LAYERS.items()}
    n_changed = 0
    for e in data["elements"]:
        m = rg.Mesh()
        for vx, vy, vz in e["vertices"]:
            m.Vertices.Add(vx, vy, vz)
        for a, b, c in e["faces"]:
            m.Faces.AddFace(a, b, c)
        m.Normals.ComputeNormals()
        m.Compact()
        changed = e["status"] != "UNCHANGED"
        key = e["category"] if (changed and HIGHLIGHT) else "unchanged"
        attr = Rhino.DocObjects.ObjectAttributes()
        attr.LayerIndex = idx[key]
        attr.Name = e["global_id"]
        attr.SetUserString("ifc_type", e["ifc_type"])
        attr.SetUserString("ifc_name", e["name"])
        attr.SetUserString("pmi_status", e["status"])
        sc.doc.Objects.AddMesh(m, attr)
        if changed:
            n_changed += 1
            if HIGHLIGHT:
                bb = m.GetBoundingBox(True)
                top = rg.Point3d(bb.Center.X, bb.Center.Y, bb.Max.Z + 0.6)
                la = Rhino.DocObjects.ObjectAttributes()
                la.LayerIndex = idx["labels"]
                sc.doc.Objects.AddTextDot(e["name"], top, la)

    sc.doc.Views.Redraw()
    print("PMI: baked {} elements, {} changed (highlight={})".format(len(data["elements"]), n_changed, HIGHLIGHT))


main()
