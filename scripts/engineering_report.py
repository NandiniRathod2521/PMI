"""
PMI - STEP 7: ENGINEERING VERIFICATION REPORT (structural / MEP / envelope / fire)
=================================================================================

Purpose
-------
For every element that changed between Model V1 and Model V2, list WHAT changed (old -> new
values read from both IFC files) and run simple, transparent SCREENING calculations so that
certified engineers can verify and sign off the change:

    structural  opening widened in a wall -> lintel span, bending moment and deflection ratios;
                structural element changed / added / removed -> load-path check
    MEP/energy  U-value or area change of an envelope element -> fabric heat loss Q = U x A x dT
                per element and the room it bounds (heating load / emitter sizing)
    envelope    window size change -> window-to-wall ratio of the host wall
    fire        fire rating change -> rating of the hosting wall, compartmentation
    services    MEP element changed -> coordination / capacity check

Everything is generic (rules in data/engineering_rules.json), so any IFC pair works.

THIS IS NOT A DESIGN CALCULATION. Every check is marked "REVIEW REQUIRED" with the discipline
that must sign it off.  Values not present in the model are flagged ASSUMED or MISSING.

Outputs:  docs/engineering_report.md   (report with sign-off table - open in VS Code, print to PDF)
          data/engineering_checks.csv  (one row per check)
Run:      python scripts/engineering_report.py   (after detect_changes.py)
"""

from __future__ import annotations

import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

import ifcopenshell
import ifcopenshell.util.element as eutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
import schedule_engine as se  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
V1_PATH, V2_PATH = ROOT / "models" / "original.ifc", ROOT / "models" / "revised.ifc"
DATA, DOCS = ROOT / "data", ROOT / "docs"
RULES = json.loads((DATA / "engineering_rules.json").read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------
# Reading context from an IFC model
# ----------------------------------------------------------------------------
class ModelIndex:
    """Relationships looked up once: storey, bounded spaces, host wall of an opening."""

    def __init__(self, path: Path):
        self.m = ifcopenshell.open(str(path))
        self.by_gid = {e.GlobalId: e for e in self.m.by_type("IfcBuildingElement")}
        self.storey, self.spaces, self.host = {}, {}, {}
        for r in self.m.by_type("IfcRelContainedInSpatialStructure"):
            for e in r.RelatedElements or []:
                self.storey[e.id()] = r.RelatingStructure
        for r in self.m.by_type("IfcRelSpaceBoundary"):
            if r.RelatedBuildingElement is not None and r.RelatingSpace is not None:
                self.spaces.setdefault(r.RelatedBuildingElement.id(), set()).add(r.RelatingSpace)
        voids = {r.RelatedOpeningElement.id(): r.RelatingBuildingElement for r in self.m.by_type("IfcRelVoidsElement")}
        for r in self.m.by_type("IfcRelFillsElement"):
            w = voids.get(r.RelatingOpeningElement.id())
            if w is not None:
                self.host[r.RelatedBuildingElement.id()] = w

    def context(self, el) -> dict:
        st = self.storey.get(el.id())
        sp = sorted({f"{s.Name} {getattr(s, 'LongName', '') or ''}".strip() for s in self.spaces.get(el.id(), [])})
        return {"storey": (st.Name if st is not None else "-"), "spaces": ", ".join(sp) or "-",
                "host": self.host.get(el.id())}


def props(el) -> dict:
    """Flattened property sets {'Pset_WallCommon.ThermalTransmittance': 0.18, ...}."""
    try:
        ps = eutil.get_psets(el)
    except Exception:
        return {}
    return {f"{n}.{k}": v for n, d in ps.items() for k, v in d.items() if k != "id"}


def find(p: dict, *names):
    """First property whose name (after the dot) matches one of names."""
    for n in names:
        for k, v in p.items():
            if k.split(".", 1)[-1] == n and v not in (None, ""):
                return v
    return None


def real(v):
    return None if (v is None or str(v).strip() in RULES["placeholder_values"]) else v


def dims(el, p: dict) -> dict:
    w = getattr(el, "OverallWidth", None) if el.is_a() in ("IfcWindow", "IfcDoor") else None
    h = getattr(el, "OverallHeight", None) if el.is_a() in ("IfcWindow", "IfcDoor") else None
    area = round(w * h, 3) if (w and h) else find(p, "NetSideArea", "GrossSideArea", "Area", "NetArea", "GrossArea")
    return {"width": w, "height": h, "area": area, "length": find(p, "Length"),
            "volume": find(p, "NetVolume", "GrossVolume", "Volume"),
            "U": find(p, "ThermalTransmittance"), "fire": real(find(p, "FireRating")),
            "load_bearing": find(p, "LoadBearing"), "external": find(p, "IsExternal")}


def unit_weight(el, name_source) -> tuple:
    """(kN/m3, material word) guessed from the element / type name - flagged ASSUMED in the report."""
    uw = RULES.get("unit_weight_kN_m3", {"_default": 25.0})
    for text in (el.Name or "", getattr(el, "ObjectType", "") or ""):      # the element's own name first
        for k, v in uw.items():
            if not k.startswith("_") and k in text.lower():
                return v, k
    return uw.get("_default", 25.0), "concrete (default)"


def minutes(rating) -> int | None:
    m = re.search(r"(\d{2,3})", str(rating or ""))
    return int(m.group(1)) if m else None


def fmt(v, unit="", nd=3):
    if v is None:
        return "not in model"
    if isinstance(v, float):
        v = round(v, nd)
    return f"{v}{(' ' + unit) if unit else ''}"


# ----------------------------------------------------------------------------
# Checks
# ----------------------------------------------------------------------------
def checks_for(c: dict, old, new, i1: ModelIndex, i2: ModelIndex) -> tuple[list, dict]:
    t = se.base_type(c["ifc_type"])
    el = new if new is not None else old
    p1, p2 = (props(old) if old is not None else {}), (props(new) if new is not None else {})
    d1, d2 = (dims(old, p1) if old is not None else {}), (dims(new, p2) if new is not None else {})
    ctx = (i2 if new is not None else i1).context(el)
    host = ctx["host"]
    hp = props(host) if host is not None else {}
    hd = dims(host, hp) if host is not None else {}
    R, dT = RULES["reviewers"], RULES["design_delta_T_K"]
    out = []

    def add(disc, check, inputs, formula, result, flags="", status="REVIEW REQUIRED"):
        out.append({"discipline": disc, "reviewer": R[disc], "check": check, "inputs": inputs,
                    "formula": formula, "result": result, "flags": flags, "status": status})

    # 1. thermal - envelope element with a U-value or area change
    u1, u2 = d1.get("U"), d2.get("U")
    a1, a2 = d1.get("area"), d2.get("area")
    if t in RULES["envelope_types"] and new is not None and (u1 != u2 or a1 != a2) and (u2 is not None or u1 is not None):
        flags = []
        if u1 is None:
            u1 = RULES["assumed_previous_U"].get(t)
            flags.append(f"previous U ASSUMED {u1} (not in V1)")
        if a2 is None:
            flags.append("area MISSING in model")
        else:
            a1 = a1 if a1 is not None else a2
            q1, q2 = u1 * a1 * dT, (u2 if u2 is not None else u1) * a2 * dT
            add("mep", "Fabric heat loss of the element (heating load of the room)",
                f"U {fmt(u1)} -> {fmt(u2)} W/m2K; A {fmt(a1)} -> {fmt(a2)} m2; dT {dT} K (assumed); room: {ctx['spaces']}",
                "Q = U x A x dT", f"{q1:.0f} W -> {q2:.0f} W  (dQ = {q2 - q1:+.0f} W) - update the room heat-load "
                f"calculation and emitter sizing for {ctx['spaces']}", "; ".join(flags))

    # 2. window-to-wall ratio of the host wall
    if t == "IfcWindow" and a1 and a2 and a1 != a2 and hd.get("area"):
        add("envelope", "Window-to-wall ratio of the host wall (solar gain, daylight, overheating)",
            f"window {fmt(a1)} -> {fmt(a2)} m2; host wall area {fmt(hd['area'])} m2 ({host.Name})",
            "WWR = A_window / A_wall", f"{a1 / hd['area']:.1%} -> {a2 / hd['area']:.1%}"
            + (" - very high glazing ratio: check overheating, energy compliance and facade structure"
               if a2 / hd["area"] > 0.6 else ""),
            "host wall area from its property set - confirm whether it is gross or net of openings")

    # 3. structural - opening widened / narrowed in a wall
    w1, w2 = d1.get("width"), d2.get("width")
    if t in RULES["opening_types"] and w1 and w2 and abs(w2 - w1) > 1e-3:
        lb = hd.get("load_bearing")
        r = w2 / w1
        add("structural", "Lintel / header over the opening (span change)",
            f"clear span {fmt(w1, 'm')} -> {fmt(w2, 'm')}; host wall {host.Name if host is not None else 'not found'} "
            f"(load-bearing: {fmt(lb)}); storey {ctx['storey']}",
            "M = w L^2 / 8 ; deflection = 5 w L^4 / (384 E I) -> ratios for the same load w",
            f"span x{r:.3f}; bending moment x{r ** 2:.2f} ({(r ** 2 - 1):+.0%}); deflection x{r ** 4:.2f} "
            f"({(r ** 4 - 1):+.0%}) - lintel to be re-checked / re-sized",
            "load-bearing status NOT DEFINED - assume load-bearing until confirmed" if lb is None else "",
            "REVIEW REQUIRED" if lb in (None, True) else "CHECK (non load-bearing host - facade support only)")

    # 4. fire - rating change
    f1, f2 = d1.get("fire"), d2.get("fire")
    if new is not None and f1 != f2 and f2 is not None:
        hf = hd.get("fire") if host is not None else d2.get("fire")
        need, have = minutes(f2), minutes(hf)
        res = (f"new rating {f2}; host wall rating {fmt(hf)}"
               + ("" if host is None else (" - host wall rating LOWER than the door/window: compartmentation fails"
                                           if (need and have and have < need) else
                                           (" - compatible" if (need and have) else " - host wall rating must be confirmed"))))
        add("fire", "Fire resistance and compartmentation",
            f"FireRating {fmt(f1)} -> {f2}; element bounds: {ctx['spaces']}; storey {ctx['storey']}",
            "rating of the opening <= rating of the wall it sits in; check the fire strategy / escape route",
            res, "" if have else "host wall fire rating NOT DEFINED in model")

    # 5. structural element changed / added / removed
    lb2 = d2.get("load_bearing") if new is not None else d1.get("load_bearing")
    structural_change = (t in RULES["structural_types"] and
                         (c["status"] in ("ADDED", "DELETED") or "geometry" in c["change_types"] or
                          "material" in c["change_types"] or "type" in c["change_types"]))
    if t == "IfcWall" and lb2 is False and c["status"] == "MODIFIED":
        structural_change = structural_change and "geometry" in c["change_types"]
    if structural_change and old is not None and new is not None:
        v1_, v2_ = d1.get("volume"), d2.get("volume")
        if v1_ and v2_ and abs(v2_ - v1_) > 1e-6:
            g1, m1 = unit_weight(old, old)
            g2, m2 = unit_weight(new, old)
            G1, G2 = v1_ * g1, v2_ * g2
            add("structural", "Self-weight / extra dead load on supports and foundations",
                f"V {fmt(v1_, 'm3')} ({m1}, {g1} kN/m3) -> {fmt(v2_, 'm3')} ({m2}, {g2} kN/m3); storey {ctx['storey']}",
                "G = V x unit weight", f"{G1:.0f} kN -> {G2:.0f} kN (dG = {G2 - G1:+.0f} kN) to be carried by the "
                "supporting walls / beams and the foundations", "unit weights ASSUMED from the element name")
        wd1, wd2 = find(p1, "Width"), find(p2, "Width")
        if t == "IfcFooting" and wd1 and wd2 and abs(wd2 - wd1) > 1e-6:
            add("structural", "Foundation bearing width (ground pressure)",
                f"width {fmt(wd1, 'm')} -> {fmt(wd2, 'm')}; length {fmt(d2.get('length'), 'm')}",
                "q = N / (B x L) -> for the same load N, q scales with B_old / B_new",
                f"bearing width x{wd2 / wd1:.2f}; ground pressure x{wd1 / wd2:.2f} for the same load - but the load "
                "itself increases (heavier floors): geotechnical / structural check of bearing capacity and settlement",
                "allowable bearing pressure NOT in model")
    if structural_change:
        add("structural", "Load path / member check",
            f"{c['status'].lower()} ({', '.join(c['change_types'])}); length {fmt(d2.get('length') or d1.get('length'), 'm')}; "
            f"area {fmt(d2.get('area') or d1.get('area'), 'm2')}; volume {fmt(d2.get('volume') or d1.get('volume'), 'm3')}; "
            f"load-bearing {fmt(lb2)}; storey {ctx['storey']}",
            "verify supports, loads and connections for the revised member",
            "structural engineer to confirm the member and the load path", "" if lb2 is not None else "load-bearing NOT DEFINED")

    # 6. MEP element
    if any(c["ifc_type"].startswith(pfx) for pfx in RULES["mep_prefixes"]):
        add("mep", "Services coordination and capacity", f"{c['status'].lower()} ({', '.join(c['change_types'])})",
            "check routing clashes, capacity and commissioning", "MEP engineer to confirm", "")

    # 7. nothing engineering-relevant but still a design change
    if not out and set(c["change_types"]) - {"attribute"}:
        add("general", "General design review", ", ".join(c["change_types"]), "-",
            "no structural / MEP / fire rule applies - architect to confirm", "")

    info = {"type": t, "storey": ctx["storey"], "spaces": ctx["spaces"],
            "host": f"{host.Name} ({host.GlobalId})" if host is not None else "-",
            "diff": [(k, fmt(d1.get(k)), fmt(d2.get(k))) for k in ("width", "height", "area", "U", "fire", "load_bearing")
                     if d1.get(k) != d2.get(k)]}
    return out, info


# ----------------------------------------------------------------------------
def main():
    changes = se.load_changes()
    if not changes:
        sys.exit("data/changes.json not found - run scripts/detect_changes.py first")
    i1, i2 = ModelIndex(V1_PATH), ModelIndex(V2_PATH)
    rows, sections = [], []
    n = 0
    for c in changes:
        if c["status"] == "UNCHANGED" or (set(c["change_types"]) <= {"attribute"}):
            continue                                             # renames need no engineering check
        old, new = i1.by_gid.get(c["global_id"]), i2.by_gid.get(c["global_id"])
        if old is None and new is None:
            continue                                             # element not found in either file
        chk, info = checks_for(c, old, new, i1, i2)
        ids = []
        for k in chk:
            n += 1
            k = {"id": f"C{n:02d}", "element": c["element"], "global_id": c["global_id"], "ifc_type": c["ifc_type"],
                 "storey": info["storey"], **k}
            rows.append(k); ids.append(k)
        sections.append((c, info, ids))

    DATA.mkdir(exist_ok=True); DOCS.mkdir(exist_ok=True)
    cols = ["id", "discipline", "reviewer", "element", "global_id", "ifc_type", "storey", "check", "inputs", "formula",
            "result", "flags", "status"]
    with (DATA / "engineering_checks.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)

    md = ["# PMI - Engineering verification report", "",
          f"**Models:** V1 `{V1_PATH.name}` -> V2 `{V2_PATH.name}`  |  **Generated:** {date.today():%d %b %Y} by PMI "
          f"(scripts/engineering_report.py)  |  **Design dT:** {RULES['design_delta_T_K']} K (assumed)", "",
          "> **Screening only - not a design calculation.** PMI lists what changed between the two model versions and "
          "runs simple, transparent checks so that the responsible **certified engineers** can verify them. Values that "
          "are not in the model are flagged *ASSUMED* or *MISSING*. Nothing here may be used for construction until "
          "it is checked and signed below.", "",
          "## 1. Summary", "", "| Check | Discipline | Element | Check | Result | Status |", "|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['id']} | {r['reviewer']} | {r['element']} ({r['ifc_type']}) | {r['check']} | {r['result']} | "
                  f"**{r['status']}** |")
    if not rows:
        md.append("| - | - | - | No engineering-relevant change detected | - | - |")
    md += ["", "## 2. Changes and calculations", ""]
    for c, info, chk in sections:
        md += [f"### {c['element']}  ·  {c['ifc_type']}  ·  `{c['global_id']}`", "",
               f"Storey: **{info['storey']}**  ·  Bounds: {info['spaces']}  ·  Host: {info['host']}  ·  "
               f"Detected change: {c.get('summary', ', '.join(c['change_types']))}", ""]
        if info["diff"]:
            md += ["| Value | V1 | V2 |", "|---|---|---|"] + [f"| {k} | {a} | {b} |" for k, a, b in info["diff"]] + [""]
        for k in chk:
            md += [f"**{k['id']} - {k['check']}**  ({k['reviewer']})", "",
                   f"- Inputs: {k['inputs']}", f"- Method: `{k['formula']}`", f"- Result: {k['result']}"]
            if k["flags"]:
                md.append(f"- Flags: *{k['flags']}*")
            md += [f"- Status: **{k['status']}**", ""]
    md += ["## 3. Sign-off", "", "| Discipline | Checks | Name | Registration no. | Signature | Date |",
           "|---|---|---|---|---|---|"]
    for disc, who in RULES["reviewers"].items():
        ids = [r["id"] for r in rows if r["discipline"] == disc]
        if ids:
            md.append(f"| {who} | {', '.join(ids)} |  |  |  |  |")
    md += ["", "*Parameters: data/engineering_rules.json. Change detection: data/changes.json.*"]
    (DOCS / "engineering_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print("\nPMI - ENGINEERING VERIFICATION REPORT (screening)")
    print("-------------------------------------------------")
    for r in rows:
        print(f"{r['id']}  {r['reviewer']:<34} {r['element']:<28} {r['check']}")
        print(f"      {r['result']}" + (f"   [{r['flags']}]" if r["flags"] else ""))
    print(f"\n{len(rows)} checks for {len(sections)} changed elements -> docs/engineering_report.md, data/engineering_checks.csv")


if __name__ == "__main__":
    main()
