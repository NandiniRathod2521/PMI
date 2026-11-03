"""
PMI - DEMO MODEL V3: A STRUCTURAL REVISION (built on Model V2)
==============================================================

Story for the demonstration
---------------------------
After V2, the structural engineer issues a revision:
  * the two Level 2 timber-joist floors (305 mm) become 400 mm concrete slabs (acoustic / fire upgrade)
  * the heavier floors need bigger foundations: all 7 strip footings go from 900 x 300 mm to 1200 x 450 mm

So V3 = V2 + 9 structural changes (2 slabs + 7 footings), each with a GEOMETRY change
(extrusion depth / footing width) and a PROPERTY change (thickness, width, volume).
Foundations and structural works sit at the start of the critical path, so PMI should
flag a timeline risk.

    python scripts/create_v3.py          -> models/revised_v3.ifc + data/revision_log_v3.csv

Demo in the app:  sidebar -> Import IFC models ->  V1 = models/revised.ifc (V2),  V2 = models/revised_v3.ifc
(or V1 = models/original.ifc to see all changes together).  "Restore the midterm test models" afterwards.

Like create_v2.py it edits the IFC text directly (no IfcOpenShell needed); GlobalIds stay the same.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from create_v2 import Step, ids, set_name_description, pset_of, add_or_replace_property  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "models" / "test_case" / "revised.ifc"     # V2 of the test case (backed up on first import)
if not SRC.is_file():
    SRC = ROOT / "models" / "revised.ifc"
OUT = ROOT / "models" / "revised_v3.ifc"
LOG = ROOT / "data" / "revision_log_v3.csv"

SLAB_TYPE = "Floor:Residential - Wood Joist with Subflooring"
SLAB_NEW_T = 0.40                       # m
FOOT_NEW_W, FOOT_NEW_D = 1.20, 0.45     # m (was 0.90 x 0.30)


def body_solid(step: Step, element_id: int) -> int:
    """The IfcExtrudedAreaSolid of the element's Body representation (must not be shared)."""
    shape = ids(step.get(element_id))[2]
    for rep in ids(step.get(shape)):
        if "'Body'" in step.get(rep):
            for it in ids(step.get(rep))[1:]:
                if step.get(it).startswith("IFCEXTRUDEDAREASOLID("):
                    users = [r for r in step.refs_to(it) if not step.get(r).startswith("IFCSTYLEDITEM(")]
                    if len(users) != 1:
                        raise RuntimeError(f"solid #{it} is shared - refusing to edit")
                    return it
    raise KeyError(f"no extruded body for #{element_id}")


def set_depth(step: Step, solid: int, depth: float) -> float:
    body = step.get(solid)
    old = float(re.search(r",([\d.Ee+-]+)\)$", body).group(1))
    step.set(solid, re.sub(r",[\d.Ee+-]+\)$", f",{depth})", body))
    return old


def set_rect_ydim(step: Step, solid: int, ydim: float) -> float:
    prof = ids(step.get(solid))[0]
    body = step.get(prof)
    if not body.startswith("IFCRECTANGLEPROFILEDEF(") or step.refs_to(prof) != [solid]:
        raise RuntimeError(f"profile #{prof} is not an unshared rectangle")
    old = float(re.search(r",([\d.Ee+-]+)\)$", body).group(1))
    step.set(prof, re.sub(r",[\d.Ee+-]+\)$", f",{ydim})", body))
    return old


def prop_value(step: Step, pset: int, name: str):
    for p in ids(step.get(pset).rsplit(",(", 1)[-1]):
        b = step.get(p)
        if b.startswith(f"IFCPROPERTYSINGLEVALUE('{name}'"):
            m = re.search(r"\(([-\d.Ee+]+)\)", b.split(",", 2)[2])
            return float(m.group(1)) if m else None
    return None


def main():
    if not SRC.is_file():
        sys.exit(f"Model V2 not found: {SRC}")
    step = Step(SRC)
    log = []

    def gid_of(eid):
        return re.match(r"^\w+\('([^']*)'", step.get(eid)).group(1)

    # ---- 1. Level 2 timber floors -> 400 mm concrete slabs -------------------------
    slabs = [e for e, n in step.index.items() if n is not None
             and step.get(e).startswith("IFCSLAB(") and SLAB_TYPE in step.get(e)]
    for k, e in enumerate(slabs, 1):
        old_n, _ = set_name_description(step, e, f"PMI_V3_Concrete_Floor_{k}",
                                        "Level 2 floor changed from timber joists to a 400 mm concrete slab")
        t_old = set_depth(step, body_solid(step, e), SLAB_NEW_T)
        dims = pset_of(step, e, "PSet_Revit_Dimensions")
        v_old = prop_value(step, dims, "Volume")
        v_new = round(v_old * SLAB_NEW_T / t_old, 4) if v_old else None
        add_or_replace_property(step, dims, "Thickness", f"IFCLENGTHMEASURE({SLAB_NEW_T})")
        if v_new:
            add_or_replace_property(step, dims, "Volume", f"IFCVOLUMEMEASURE({v_new})")
        log.append([gid_of(e), "IfcSlab", old_n, f"PMI_V3_Concrete_Floor_{k}", "attribute;geometry;property",
                    f"thickness {t_old:.3f} -> {SLAB_NEW_T:.3f} m; volume {v_old:.2f} -> {v_new:.2f} m3"])

    # ---- 2. all strip footings 900 x 300 -> 1200 x 450 ------------------------------
    footings = [e for e, n in step.index.items() if n is not None and step.get(e).startswith("IFCFOOTING(")]
    for k, e in enumerate(footings, 1):
        old_n, _ = set_name_description(step, e, f"PMI_V3_Footing_Widened_{k}",
                                        "Strip footing enlarged to 1200 x 450 mm for the heavier concrete floors")
        solid = body_solid(step, e)
        d_old = set_depth(step, solid, FOOT_NEW_D)
        w_old = set_rect_ydim(step, solid, FOOT_NEW_W)
        dims = pset_of(step, e, "PSet_Revit_Dimensions")
        v_old = prop_value(step, dims, "Volume")
        f = (FOOT_NEW_W / w_old) * (FOOT_NEW_D / d_old)
        v_new = round(v_old * f, 4) if v_old else None
        add_or_replace_property(step, dims, "Width", f"IFCLENGTHMEASURE({FOOT_NEW_W})")
        if v_new:
            add_or_replace_property(step, dims, "Volume", f"IFCVOLUMEMEASURE({v_new})")
        log.append([gid_of(e), "IfcFooting", old_n, f"PMI_V3_Footing_Widened_{k}", "attribute;geometry;property",
                    f"width {w_old:.2f} -> {FOOT_NEW_W:.2f} m; depth {d_old:.2f} -> {FOOT_NEW_D:.2f} m; "
                    f"volume {v_old:.2f} -> {v_new:.2f} m3"])

    step.save(OUT)
    with LOG.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["global_id", "ifc_type", "old_name", "new_name", "expected_channels", "change"])
        w.writerows(log)
    print(f"Model V3 written: {OUT}  (from {SRC.name}, {len(step.new)} new entities)")
    for r in log:
        print(f"  {r[1]:<10} {r[0]}  {r[3]:<28} {r[5]}")
    print(f"Ground truth: {LOG}")


if __name__ == "__main__":
    main()
