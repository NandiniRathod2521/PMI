"""
PMI - STEP 0: CREATE THE REVISED MODEL (V2) FROM THE ORIGINAL (V1)
==================================================================

Why this script exists
----------------------
To test PMI we need two versions of the same building where we KNOW exactly what
changed (a "ground truth").  This script takes models/original.ifc and writes
models/revised.ifc with three documented design revisions:

    Element                       IFC type   Change channel(s)            What changes
    ----------------------------  ---------  ---------------------------  -------------------------------------------
    External wall (party wall)    IfcWall    attribute + PROPERTY         new insulation spec: U-value 0.18 W/m2K added
    Single-flush door A101        IfcDoor    attribute + PROPERTY         FireRating: placeholder -> 'EI 60'
    Fixed window (mark 9)         IfcWindow  attribute + PROPERTY + GEOM  0.6 m wider (4.835 -> 5.435 m), opening widened,
                                                                          improved glazing U-value 1.1 W/m2K

The earlier version of V2 only renamed the three elements.  A rename alone is not
proof of a design modification, so this version adds real property and geometry
changes.  The names-only version is kept as models/revised_names_only.ifc
(script: scripts/create_v2_names_only.py).

How it works (no IfcOpenShell needed)
-------------------------------------
An IFC file is plain text (STEP format): one entity per line, e.g.
    #6426=IFCWINDOW('1hOSvn6df7F8_7GcBWlR72',#33,'M_Fixed:...',$,...);
We edit the specific lines and ADD new entities at the end, so GlobalIds stay the
same and every unchanged element stays byte-identical.  Property values that are
shared by several elements (e.g. IsExternal) are never edited in place - new
property entities are created instead, so only the target element changes.

Run:    python scripts/create_v2.py
Output: models/revised.ifc
        data/revision_log.csv   (the ground truth used in validation)
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "models" / "original.ifc"
V2 = ROOT / "models" / "revised.ifc"
LOG = ROOT / "data" / "revision_log.csv"

# GlobalIds of the three elements we revise (stable across versions)
WALL, DOOR, WINDOW = "2O2Fr$t4X7Zf8NOew3FKau", "1hOSvn6df7F8_7GcBWlRGQ", "1hOSvn6df7F8_7GcBWlR72"

WIDEN_M = 0.60            # window becomes 0.6 m wider, centred on the old opening
OLD_WIDTH = 4.834999999999996
NEW_WIDTH = round(OLD_WIDTH + WIDEN_M, 6)

LINE = re.compile(r"^#(\d+)=(.*);\s*$")


class Step:
    """Minimal editor for an IFC STEP file: read lines, edit entities, add new ones."""

    def __init__(self, path: Path):
        self.lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        self.index = {}
        for n, line in enumerate(self.lines):
            m = LINE.match(line)
            if m:
                self.index[int(m.group(1))] = n
        self.next_id = max(self.index) + 1
        self.new = []
        self.new_bodies = {}

    def get(self, eid: int) -> str:
        if self.index.get(eid) is None and eid in self.new_bodies:      # an entity added in this run
            return self.new_bodies[eid]
        return LINE.match(self.lines[self.index[eid]]).group(2)

    def set(self, eid: int, body: str):
        self.lines[self.index[eid]] = f"#{eid}={body};"

    def find(self, prefix: str, global_id: str) -> int:
        for eid, n in self.index.items():
            body = LINE.match(self.lines[n]).group(2)
            if body.startswith(prefix + "(") and f"'{global_id}'" in body:
                return eid
        raise KeyError(f"{prefix} {global_id} not found")

    def add(self, body: str) -> int:
        eid = self.next_id
        self.next_id += 1
        self.new.append(f"#{eid}={body};")
        self.new_bodies[eid] = body
        self.index[eid] = None  # placeholder so ids stay unique
        return eid

    def refs_to(self, eid: int) -> list:
        pat = re.compile(rf"#{eid}(?!\d)")
        return [k for k, n in self.index.items()
                if n is not None and k != eid and pat.search(self.lines[n])]

    def save(self, path: Path):
        end = max(i for i, l in enumerate(self.lines) if l.strip() == "ENDSEC;")
        out = self.lines[:end] + self.new + self.lines[end:]
        path.write_text("\n".join(out) + "\n", encoding="utf-8")


def ids(body: str) -> list:
    return [int(x) for x in re.findall(r"#(\d+)", body)]


def set_name_description(step: Step, eid: int, name: str, description: str) -> tuple:
    """Replace attribute 3 (Name) and 4 (Description) of an IfcRoot entity."""
    body = step.get(eid)
    m = re.match(r"^(\w+\('[^']*',#\d+,)('(?:[^']|'')*'|\$),('(?:[^']|'')*'|\$),(.*)$", body)
    if not m:
        raise ValueError(f"Cannot parse #{eid}")
    old_name, old_desc = m.group(2).strip("'"), m.group(3).strip("'")
    step.set(eid, f"{m.group(1)}'{name}','{description}',{m.group(4)}")
    return old_name, ("" if old_desc == "$" else old_desc)


def pset_of(step: Step, element_id: int, pset_name: str) -> int:
    """The property set with this name attached ONLY to this element."""
    for rel in step.refs_to(element_id):
        body = step.get(rel)
        if not body.startswith("IFCRELDEFINESBYPROPERTIES("):
            continue
        related = re.search(r",\((#[\d,#]+)\),#(\d+)\)$", body)
        if related and related.group(1) == f"#{element_id}":
            pset = int(related.group(2))
            if f"'{pset_name}'" in step.get(pset):
                return pset
    raise KeyError(f"{pset_name} for #{element_id} not found")


def add_or_replace_property(step: Step, pset: int, prop_name: str, value: str) -> str:
    """Point the pset at a NEW IfcPropertySingleValue (never edits a shared one)."""
    m = re.match(r"^(.*,)\(([#\d,]+)\)\)$", step.get(pset))
    head, props = m.group(1), ids(m.group(2))
    old_value, keep = "(not defined)", []
    for p in props:
        body = step.get(p)
        if body.startswith(f"IFCPROPERTYSINGLEVALUE('{prop_name}'"):
            old_value = body.split(",", 2)[2].rsplit(",", 1)[0]
        else:
            keep.append(p)
    new = step.add(f"IFCPROPERTYSINGLEVALUE('{prop_name}',$,{value},$)")
    step.set(pset, head + "(" + ",".join(f"#{p}" for p in keep + [new]) + "))")
    return old_value


def widen_window(step: Step, window_id: int) -> str:
    """Scale the window body along its local X (width) and widen its opening to match."""
    # 1) window body = mapped item -> give it its own non-uniform transformation
    shape = ids(step.get(window_id))[2]                       # Representation attribute
    rep_body = next(r for r in ids(step.get(shape)) if "'Body'" in step.get(r))
    mapped = ids(step.get(rep_body))[-1]
    op = ids(step.get(mapped))[-1]
    if step.refs_to(op) != [mapped]:
        raise RuntimeError("transformation operator is shared - refusing to edit")
    sx = NEW_WIDTH / OLD_WIDTH
    origin = step.add(f"IFCCARTESIANPOINT(({-WIDEN_M / 2:.4f},0.,0.))")   # keeps it centred
    new_op = step.add(f"IFCCARTESIANTRANSFORMATIONOPERATOR3DNONUNIFORM($,$,#{origin},{sx:.6f},$,1.,1.)")
    step.set(mapped, re.sub(rf"#{op}\)$", f"#{new_op})", step.get(mapped)))

    # 2) OverallWidth attribute (last attribute of IfcWindow)
    step.set(window_id, re.sub(r",[\d.]+\)$", f",{NEW_WIDTH})", step.get(window_id)))

    # 3) the opening the window fills: rectangle profile YDim = width
    fills = next(r for r in step.refs_to(window_id) if step.get(r).startswith("IFCRELFILLSELEMENT("))
    opening = ids(step.get(fills))[1]
    o_shape = ids(step.get(opening))[2]
    o_rep = ids(step.get(o_shape))[0]
    solid = ids(step.get(o_rep))[-1]
    profile = ids(step.get(solid))[0]
    if step.refs_to(profile) != [solid]:
        raise RuntimeError("opening profile is shared - refusing to edit")
    step.set(profile, re.sub(r",[\d.]+\)$", f",{NEW_WIDTH})", step.get(profile)))
    return f"width {OLD_WIDTH:.3f} m -> {NEW_WIDTH:.3f} m (opening widened)"


def main():
    if not V1.is_file():
        raise FileNotFoundError(V1)
    step = Step(V1)
    log = []

    # ---- Revision 1: wall - new insulation specification ------------------------
    w = step.find("IFCWALL", WALL)
    old_n, _ = set_name_description(step, w, "PMI_External_Wall_Revised",
                                    "External wall revised with new insulation specification")
    old_u = add_or_replace_property(step, pset_of(step, w, "Pset_WallCommon"),
                                    "ThermalTransmittance", "IFCTHERMALTRANSMITTANCEMEASURE(0.18)")
    log.append([WALL, "IfcWall", old_n, "PMI_External_Wall_Revised", "attribute;property",
                f"Pset_WallCommon.ThermalTransmittance {old_u} -> 0.18 W/m2K"])

    # ---- Revision 2: door - fire rating -----------------------------------------
    d = step.find("IFCDOOR", DOOR)
    old_n, _ = set_name_description(step, d, "PMI_Fire_Rated_Door", "Door specification revised for fire safety")
    old_fr = add_or_replace_property(step, pset_of(step, d, "Pset_DoorCommon"), "FireRating", "IFCLABEL('EI 60')")
    log.append([DOOR, "IfcDoor", old_n, "PMI_Fire_Rated_Door", "attribute;property",
                f"Pset_DoorCommon.FireRating {old_fr} -> 'EI 60'"])

    # ---- Revision 3: window - wider, better glazing ------------------------------
    wi = step.find("IFCWINDOW", WINDOW)
    old_n, _ = set_name_description(step, wi, "PMI_Window_Revised",
                                    "Window enlarged by 0.6 m and glazing improved (U 1.1)")
    old_wu = add_or_replace_property(step, pset_of(step, wi, "Pset_WindowCommon"),
                                     "ThermalTransmittance", "IFCTHERMALTRANSMITTANCEMEASURE(1.1)")
    geo = widen_window(step, wi)
    log.append([WINDOW, "IfcWindow", old_n, "PMI_Window_Revised", "attribute;property;geometry",
                f"{geo}; Pset_WindowCommon.ThermalTransmittance {old_wu} -> 1.1 W/m2K"])

    step.save(V2)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["global_id", "ifc_type", "old_name", "new_name", "expected_channels", "change"])
        wr.writerows(log)

    print(f"Model V2 written: {V2}  ({len(step.new)} new entities)")
    for row in log:
        print(f"  {row[1]:<10} {row[0]}  [{row[4]}]  {row[5]}")
    print(f"Ground truth: {LOG}")


if __name__ == "__main__":
    main()
