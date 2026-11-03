"""
PMI - STEP 6: RIBA STAGE PROGRAMME + PHASE RISK PREDICTION
==========================================================

Question it answers
-------------------
"Model V2 has just been issued. Which RIBA Plan of Work stage is now at risk, and why?"

What it does
------------
1. Builds a whole-project programme by RIBA stage (data/riba_programme.csv):
   Stages 0-4 (design), Stage 5 (procurement + the 7 construction activities used in
   the rest of PMI), Stage 6 (handover).  Quantities in the bar labels come from Model V1.
2. V1 programme  -> CPM -> evidence/riba_gantt_v1.png
3. Takes the changes detected between V1 and V2 (data/changes.json) and, with the rules in
   data/riba_rules.json, adds the extra work each change causes in each stage:
       Stage 4  design change package (re-detail / re-issue)   - by change channel
       Stage 5  longer procurement lead time (doors, windows)  - by change channel
       Stage 5  extra construction days                        - data/assumptions.json
4. V2 programme  -> CPM -> evidence/riba_gantt_v2.png, with the issues and the stages at risk
5. Risk per stage (data/riba_risk.csv, docs/riba_risk_report.md):
       HIGH    the stage finishes later AND is on the critical path after the change
       MEDIUM  extra work or >= 50 % of its float consumed, but it does not drive the finish
       LOW     extra work fully absorbed by float
       NONE    untouched
   plus a 0-100 score to rank stages (slip 60 %, float consumed 25 %, change exposure 15 %).

About the word "prediction"
---------------------------
This is a RULE-BASED, explainable forecast: documented rules + the Critical Path Method.
No machine learning is used.  Every number can be traced to a rule in data/riba_rules.json
or data/assumptions.json.  The planned LLM layer would propose these rules per change;
the engine would still calculate the result.

Run (after detect_changes.py):   python scripts/riba_risk.py
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import schedule_engine as se  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA, EV, DOCS = ROOT / "data", ROOT / "evidence", ROOT / "docs"
V1_IFC = ROOT / "models" / "original.ifc"

STAGE_COL = {"Stage 0": "#6C7A89", "Stage 1": "#00A8AA", "Stage 2": "#447EB9", "Stage 3": "#7A5AC9",
             "Stage 4": "#1F4E9E", "Stage 5": "#D99A1E", "Stage 6": "#2E8B57"}
RISK_COL = {"HIGH": "#C0392B", "MEDIUM": "#E67E22", "LOW": "#7F8C8D", "NONE": "#B8C0CA"}
INK, RED, GHOST = "#1B2430", "#D64545", "#D5DAE1"
plt.rcParams.update({"font.family": ["Poppins", "DejaVu Sans"], "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False})


# ----------------------------------------------------------------------------
# Inputs
# ----------------------------------------------------------------------------
def ifc_counts(path: Path) -> dict:
    """Count building elements in an IFC file by reading its text (no IfcOpenShell needed)."""
    c = se.count_ifc(path)
    q = lambda *t: se.quantity(c, list(t))  # noqa: E731
    return {"walls": q("IfcWall"), "doors": q("IfcDoor"), "windows": q("IfcWindow"), "slabs": q("IfcSlab"),
            "footings": q("IfcFooting"), "beams/columns": q("IfcBeam", "IfcColumn"), "coverings": q("IfcCovering")}


def build_programme(rules: dict) -> pd.DataFrame:
    """RIBA programme = design stages + procurement + handover (data/riba_programme.csv)
    wrapped around the construction schedule GENERATED from Model V1 (schedule_engine.load_baseline)."""
    stages = se.load_baseline(DATA / "riba_programme.csv")
    cons = se.load_baseline()[["id", "activity", "duration_days", "predecessors", "phase"]].copy()
    cons["phase"] = "Stage 5"
    succ = {p for ps in cons.predecessors for p in ps}
    ends = [i for i in cons.id if i not in succ]
    cons["predecessors"] = [ps if ps else ["S4"] for ps in cons.predecessors]       # construction starts after Stage 4
    feeds = rules.get("procurement_feeds", ["A4"])
    cons["predecessors"] = [ps + [rules["procurement_activity"]] if i in feeds else ps
                            for i, ps in zip(cons.id, cons.predecessors)]
    stages["predecessors"] = [sum(([*ends] if p == "@construction_end" else [p] for p in ps), [])
                              for ps in stages.predecessors]
    df = pd.concat([stages, cons], ignore_index=True)
    order = ["S0", "S1", "S2", "S3", "S4", "P1"] + list(cons.id) + ["H6"]
    df["o"] = df["id"].map({k: i for i, k in enumerate(order)})
    return df.sort_values("o").drop(columns="o").reset_index(drop=True)


def quantity_label(act_id: str, q: dict) -> str:
    return {"A1": f"{q.get('footings', 0)} footings", "A2": f"{q.get('slabs', 0)} slabs, {q.get('beams/columns', 0)} beams/cols",
            "A3": f"{q.get('walls', 0)} walls", "A4": f"{q.get('doors', 0)} doors, {q.get('windows', 0)} windows",
            "P1": f"{q.get('doors', 0)} doors, {q.get('windows', 0)} windows",
            "A6": f"{q.get('coverings', 0)} coverings"}.get(act_id, "")


# ----------------------------------------------------------------------------
# Change -> extra work per stage (the "prediction" rules)
# ----------------------------------------------------------------------------
def stage_impacts(changes: list, rules: dict, assumptions: dict) -> tuple[pd.DataFrame, list]:
    """One row per (change, stage, activity) with the extra days and the reason."""
    rows = []
    rw = rules["design_rework_days_per_channel"]
    proc = rules["procurement_extra_days"]
    R4 = rules["design_rework_activity"]["id"]
    design = {}
    for c in changes:
        if c.get("status") == "UNCHANGED":
            continue
        types = [c["status"].lower()] if c.get("status") in ("ADDED", "DELETED") else c["change_types"]
        ch = [t for t in types if t in rw]
        short = se.base_type(c["ifc_type"]).replace("Ifc", "")
        # Stage 4 - design re-issue: similar elements are revised together, so the package counts
        # ONE design effort per IFC type (the largest), not one per element
        d = sum(rw[t] for t in ch)
        if d:
            g = design.setdefault(short, {"days": 0, "n": 0, "ch": set(), "gids": []})
            g["days"] = max(g["days"], d); g["n"] += 1; g["ch"].update(t for t in ch if rw[t]); g["gids"].append(c["global_id"])
        # Stage 5 - procurement lead time
        bt = se.base_type(c["ifc_type"])
        if bt in rules["procured_types"]:
            p = sum(proc.get(bt, {}).get(t, 0) for t in ch)
            if p:
                rows.append({"global_id": c["global_id"], "element": short, "stage": "Stage 5",
                             "activity": rules["procurement_activity"], "extra_days": p, "channels": "+".join(ch),
                             "issue": f"{short}: new spec{'/size' if 'geometry' in ch else ''} -> longer lead time (+{p} d)"})
    for short, g in design.items():
        many = f" x{g['n']} (revised together)" if g["n"] > 1 else ""
        rows.append({"global_id": g["gids"][0], "element": short, "stage": "Stage 4", "activity": R4,
                     "extra_days": g["days"], "channels": "+".join(sorted(g["ch"])),
                     "issue": f"{short}{many}: {'+'.join(sorted(g['ch']))} change -> Stage 4 information re-issued "
                              f"(+{g['days']} d)"})
    # Stage 5 - construction (same assumptions as the rest of PMI)
    imp = se.map_changes_to_activities([c for c in changes if c.get("status") != "UNCHANGED"],
                                       se.load_mapping(), assumptions)
    for r in imp.itertuples():
        if r.activity_id and r.extra_days:
            short = r.ifc_type.replace("Ifc", "").replace("StandardCase", "")
            rows.append({"global_id": r.global_id, "element": short, "stage": "Stage 5", "activity": r.activity_id,
                         "extra_days": int(r.extra_days), "channels": r.change_types.replace(", ", "+"),
                         "issue": f"{short}: {r.rationale.split('->')[-1].strip()} (+{int(r.extra_days)} d on {r.activity_id})"})
    return pd.DataFrame(rows, columns=["global_id", "element", "stage", "activity", "extra_days", "channels", "issue"])


def build_v2_network(programme: pd.DataFrame, impacts: pd.DataFrame, changes: list, rules: dict,
                     v1: pd.DataFrame | None = None, scenario: dict | None = None) -> se.Network:
    """V2 network for one ISSUE SCENARIO: when the revised model reaches the project team.
    scenario['issue_after'] = the activity after which V2 is issued (default S4 = end of Technical Design).
    Work that is ALREADY COMPLETE at that moment cannot simply get extra days - it must be redone:
        built construction work  -> new 'RW_<id>' rework activity = extra days x rework_factor
        completed procurement    -> new 'P2' re-order activity   = full lead time + extra days
    Everything else gets its extra days as in the standard case."""
    scenario = scenario or {"issue_after": "S4", "rework_factor": 1.0}
    issue = scenario["issue_after"]
    df = programme.copy()
    df["predecessors"] = df["predecessors"].apply(list)
    R = rules["design_rework_activity"]
    net = se.Network(activities=df)
    if impacts.empty:
        return net
    t_issue = int(v1.set_index("id").at[issue, "EF"]) if v1 is not None else 0
    v1_ef = v1.set_index("id")["EF"].to_dict() if v1 is not None else {}
    base_dur = dict(zip(df.id, df.duration_days))
    succ = {i: [j for j, ps in zip(df.id, df.predecessors) if i in ps] for i in df.id}
    new_rows, extra_preds = [], {}                     # extra_preds: activity -> [new predecessors]

    r4_days = int(impacts.loc[impacts.activity == R["id"], "extra_days"].sum())
    if r4_days:
        new_rows.append({"id": R["id"], "activity": R["activity"], "duration_days": r4_days,
                         "predecessors": [issue], "phase": R["phase"]})
        changed_types = {se.base_type(c["ifc_type"]) for c in changes if c.get("status") != "UNCHANGED"}
        for a in {a for t in changed_types for a in rules["design_feeds"].get(t, [])}:
            if v1_ef.get(a, 1e9) > t_issue:            # not yet done: it waits for the revised design
                extra_preds.setdefault(a, []).append(R["id"])
    gate = [R["id"]] if r4_days else [issue]

    added = {}
    for act, days in impacts[impacts.activity != R["id"]].groupby("activity")["extra_days"].sum().items():
        if v1_ef.get(act, 1e9) <= t_issue:              # already complete when V2 arrives
            if act == rules["procurement_activity"]:
                nid, name, dur = "P2", "Re-order changed doors / windows", base_dur[act] + int(days)
            else:
                nid = f"RW_{act}"
                name = f"Rework of built {df.set_index('id').at[act, 'activity'].lower()}"
                dur = int(np.ceil(days * scenario.get("rework_factor", 1.0)))
            new_rows.append({"id": nid, "activity": name, "duration_days": dur, "predecessors": list(gate),
                             "phase": "Stage 5"})
            # the rework holds up only work that has NOT started yet (finished work cannot wait for it)
            todo, seen = list(succ[act]), set()
            while todo:
                s_ = todo.pop()
                if s_ in seen:
                    continue
                seen.add(s_)
                if v1_ef.get(s_, 1e9) <= t_issue:
                    todo.extend(succ.get(s_, []))
                else:
                    extra_preds.setdefault(s_, []).append(nid)
        else:
            added[act] = added.get(act, 0) + int(days)

    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
    df["predecessors"] = [p + [x for x in extra_preds.get(i, []) if x not in p] for i, p in zip(df.id, df.predecessors)]
    net = se.Network(activities=df)
    net.added_days.update(added)
    return net


def handover_check(v1: pd.DataFrame, v2: pd.DataFrame, rules: dict) -> dict:
    """Is the contractual handover date still met?  Contract date = V1 handover + contract buffer."""
    buf = int(rules.get("contract_handover_buffer_days", 25))
    end1, end2 = int(v1.EF.max()), int(v2.EF.max())
    contract = end1 + buf
    slip = end2 - end1
    if end2 > contract:
        verdict = f"HANDOVER AT RISK - misses the contract date by {end2 - contract} working days"
        level = "AT RISK"
    elif slip > 0.5 * buf:
        verdict = f"TIGHT - uses {slip} of the {buf} buffer days"
        level = "TIGHT"
    else:
        verdict = f"OK - uses {max(slip, 0)} of the {buf} buffer days"
        level = "OK"
    return {"handover_v1_day": end1, "handover_v2_day": end2, "contract_day": contract, "buffer_days": buf,
            "slip_days": slip, "level": level, "verdict": verdict}


# ----------------------------------------------------------------------------
# Risk per stage
# ----------------------------------------------------------------------------
def stage_risk(v1: pd.DataFrame, v2: pd.DataFrame, impacts: pd.DataFrame, changes: list, rules: dict) -> pd.DataFrame:
    weight = rules["severity_weight"]
    sev = {c["global_id"]: sum(weight.get(t, 1) for t in c["change_types"]) for c in changes}
    rows = []
    for stage, name in rules["stages"].items():
        a1, a2 = v1[v1.phase == stage], v2[v2.phase == stage]
        if a1.empty and a2.empty:
            continue
        f1, f2 = int(a1.EF.max()), int(a2.EF.max())
        fl1, fl2 = int(a1["float"].min()), int(a2["float"].min())
        imp = impacts[impacts.stage == stage]
        added = int(imp.extra_days.sum())
        crit = bool(a2.critical.any())
        slip = f2 - f1
        float_used = (fl1 - fl2) / fl1 if fl1 > 0 else 0.0
        if slip > 0 and crit:
            level = "HIGH"
        elif added > 0 and (float_used >= 0.5 or slip > 0):
            level = "MEDIUM"
        elif added > 0:
            level = "LOW"
        else:
            level = "NONE"
        role = "origin" if added else ("knock-on" if slip > 0 else "-")
        exposure = sum(sev.get(g, 0) for g in imp.global_id.unique())
        rows.append({"stage": stage, "name": name, "risk": level, "role": role,
                     "finish_v1_day": f1, "finish_v2_day": f2, "slip_days": slip,
                     "min_float_v1": fl1, "min_float_v2": fl2, "added_work_days": added,
                     "critical_after_change": crit, "exposure": exposure,
                     "changes": ", ".join(sorted(imp.element.unique())) or "-",
                     "issues": " | ".join(imp.issue) if not imp.empty else ("finish moves with upstream delay" if slip > 0 else "-")})
    df = pd.DataFrame(rows)
    mx_slip, mx_exp = max(df.slip_days.max(), 1), max(df.exposure.max(), 1)
    fu = [(r.min_float_v1 - r.min_float_v2) / r.min_float_v1 if r.min_float_v1 > 0 else (1.0 if r.slip_days > 0 else 0.0)
          for r in df.itertuples()]
    df["risk_score"] = [int(round(60 * s / mx_slip + 25 * max(0, min(1, f)) + 15 * e / mx_exp))
                        for s, f, e in zip(df.slip_days, fu, df.exposure)]
    return df


# ----------------------------------------------------------------------------
# Charts
# ----------------------------------------------------------------------------
def wd_to_date(start: np.datetime64, d: int) -> str:
    return pd.Timestamp(np.busday_offset(start, int(d), roll="forward")).strftime("%b %y")


def riba_gantt(sched: pd.DataFrame, title: str, out: Path, start64, q: dict, base: pd.DataFrame | None = None,
               risk: pd.DataFrame | None = None, issues: list | None = None, handover: dict | None = None,
               issue_day: int | None = None):
    s = sched.copy()
    ids = list(s["id"])
    anchors = {"R4": "S4", "P2": "P1"}
    anchors.update({i: i[3:] for i in ids if i.startswith("RW_")})
    for new, after in anchors.items():    # show new activities right after the work they redo
        if new in ids and after in ids:
            ids.remove(new); ids.insert(ids.index(after) + 1, new)
    s["o"] = s["id"].map({k: i for i, k in enumerate(ids)})
    s = s.sort_values("o").reset_index(drop=True)
    n = len(s)
    end = int(s.EF.max())
    box_in = (0.75 + 0.19 * len(issues)) if issues else 0
    h = 1.3 + 0.42 * n + box_in
    fig, ax = plt.subplots(figsize=(15, h))
    risk_map = {} if risk is None else risk.set_index("stage").to_dict("index")

    # stage bands on the left
    for stage, g in s.groupby("phase", sort=False):
        ys = [n - 1 - i for i in g.index]
        r = risk_map.get(stage, {})
        at_risk = r.get("risk") in ("HIGH", "MEDIUM")
        ax.axhspan(min(ys) - 0.5, max(ys) + 0.5, color=RISK_COL[r["risk"]] if at_risk else "#F2F4F7",
                   alpha=0.10 if at_risk else 0.6, lw=0, zorder=0)
        ax.text(-0.01, (min(ys) + max(ys)) / 2, stage.replace("Stage ", "RIBA "), transform=ax.get_yaxis_transform(),
                ha="right", va="center", fontsize=9, fontweight="bold", color=STAGE_COL.get(stage, INK))

    for i, r in s.iterrows():
        y = n - 1 - i
        col = STAGE_COL.get(r.phase, INK)
        if base is not None:
            b = base[base.id == r.id]
            if not b.empty:
                ax.barh(y + 0.22, int(b.duration.iloc[0]), left=int(b.ES.iloc[0]), height=0.22, color=GHOST, zorder=2)
        new = base is not None and base[base.id == r.id].empty
        ax.barh(y - (0.06 if base is not None else 0), r.duration - r.added_days, left=r.ES,
                height=0.42 if base is not None else 0.55, color=col, zorder=3,
                edgecolor=INK if r.critical else "none", lw=1.1 if r.critical else 0,
                hatch="///" if new else None)
        if new:
            ax.barh(y - 0.06, r.duration, left=r.ES, height=0.42, color="#FBE3E3", zorder=3, hatch="///",
                    edgecolor=RED, lw=1.1)
        elif r.added_days:
            ax.barh(y - 0.06, r.added_days, left=r.EF - r.added_days, height=0.42, color=RED, zorder=3,
                    edgecolor=INK if r.critical else "none", lw=1.1 if r.critical else 0)
        lab = quantity_label(r.id, q)
        txt = f"+{r.added_days} d" if r.added_days else ""
        if new:
            txt = f"NEW +{r.duration} d"
        ax.text(r.EF + 1.2, y - (0.06 if base is not None else 0),
                "  ".join(t for t in (txt, lab) if t), va="center", fontsize=8.5,
                color=RED if (r.added_days or new) else "#5A6677", fontweight="bold" if (r.added_days or new) else None)

    ax.set_yticks(range(n))
    ax.set_yticklabels([f"{r.id}  {r.activity}" for r in s.itertuples()][::-1], fontsize=9)
    ax.tick_params(axis="y", pad=58)
    # one tick per calendar month (working-day index of each month's first working day)
    first = pd.Timestamp(start64)
    months = pd.date_range(first.replace(day=1) + pd.offsets.MonthBegin(1), periods=24, freq="MS")
    ticks = [int(np.busday_count(start64, np.datetime64(m.date(), "D"))) for m in months]
    keep = [(t, m) for t, m in zip(ticks, months) if t <= end + 30]
    ax.set_xticks([t for t, _ in keep])
    ax.set_xticklabels([m.strftime("%b %y") for _, m in keep], fontsize=8.5)
    ax.set_xlim(0, end + 34)
    ax.set_ylim(-0.6, n - 0.4)
    ax.axvline(end, color=RED if base is not None else INK, ls="--", lw=1)
    if base is not None:
        b_end = int(base.EF.max())
        ax.axvline(b_end, color="#9AA3AF", ls="--", lw=1)
        ax.text(end + 0.8, n - 0.6, f"V2 finish\n{pd.Timestamp(np.busday_offset(start64, end - 1, roll='forward')):%d %b %Y}\n+{end - b_end} working days",
                color=RED, fontsize=9, fontweight="bold", va="top")
    else:
        ax.text(end + 0.8, n - 0.6, f"finish\n{pd.Timestamp(np.busday_offset(start64, end - 1, roll='forward')):%d %b %Y}", color=INK, fontsize=9, va="top")

    # risk badges (right edge)
    for stage, g in s.groupby("phase", sort=False):
        r = risk_map.get(stage)
        if not r or r["risk"] == "NONE":
            continue
        ys = [n - 1 - i for i in g.index]
        ax.text(1.005, (min(ys) + max(ys)) / 2, f" {r['risk']} \n {r['role']} ", transform=ax.get_yaxis_transform(),
                ha="left", va="center", fontsize=8.5, fontweight="bold", color="white",
                bbox=dict(boxstyle="round,pad=0.35", fc=RISK_COL[r["risk"]], ec="none"))

    if handover:
        c = handover["contract_day"]
        hc = {"AT RISK": "#C0392B", "TIGHT": "#E67E22", "OK": "#2E8B57"}[handover["level"]]
        ax.axvline(c, color=hc, ls="-", lw=2)
        ax.text(c + 0.8, n - 2.2, f"contract handover\n{pd.Timestamp(np.busday_offset(start64, c - 1, roll='forward')):%d %b %Y}",
                color=hc, fontsize=8.5, fontweight="bold")
        ax.text(0, 1.045, handover["verdict"], transform=ax.transAxes, ha="left", fontsize=10.5, fontweight="bold",
                color="white", bbox=dict(boxstyle="round,pad=0.4", fc=hc, ec="none"))
    if issue_day:
        ax.axvline(issue_day, color="#7A5AC9", ls=":", lw=1.6)
        ax.text(issue_day - 0.8, n - 0.6, "V2 issued", color="#7A5AC9", fontsize=8.5, fontweight="bold",
                ha="right", va="top")
    ax.set_title(title, loc="left", fontweight="bold", color=INK, fontsize=12, pad=52 if handover else 26)
    sub = "Black outline = critical path.  Bar labels: quantities from Model V1."
    if base is not None:
        sub = "Grey = V1 programme.  Red = extra work caused by the V2 changes.  Hatched = new activity.  " + sub
    ax.text(0, 1.012, sub, transform=ax.transAxes, fontsize=8.5, color="#5A6677")
    if issues:
        fig.text(0.01, 0.012, "Issues detected in V2:\n" + "\n".join("  - " + t for t in issues), fontsize=8.5,
                 color=INK, va="bottom", ha="left",
                 bbox=dict(boxstyle="round,pad=0.5", fc="#FDF1F1", ec="#E7B3B3"))
        fig.subplots_adjust(left=0.25, right=0.9, top=1 - (1.25 if handover else 0.75) / h, bottom=(box_in + 0.45) / h)
    else:
        fig.subplots_adjust(left=0.25, right=0.9, top=1 - 0.75 / h, bottom=0.45 / h)
    fig.savefig(out, dpi=200)
    plt.close(fig)


# ----------------------------------------------------------------------------
def run_scenario(key: str, sc: dict, programme, v1, impacts, changes, rules, start64, q) -> dict:
    v2 = se.cpm(build_v2_network(programme, impacts, changes, rules, v1, sc))
    risk = stage_risk(v1, v2, impacts, changes, rules)
    ho = handover_check(v1, v2, rules)
    m = v1.set_index("id")["float"]
    newly = [f"{r.id} {r.activity} becomes critical (float {int(m[r.id])} -> 0)" for r in v2.itertuples()
             if r.critical and r.id in m and m[r.id] > 0]
    new_acts = [f"{r.id} {r.activity}: NEW {r.duration} d (work already done when V2 arrived)"
                for r in v2.itertuples() if r.id not in m and r.id != "R4"]
    top = risk[risk.risk == "HIGH"]
    headline = ", ".join(f"{r.stage} ({r.role})" for r in top.itertuples()) or "none"
    suffix = "" if key == "stage4" else f"_{key}"
    riba_gantt(v2, f"PMI - Model V2, {sc['label']} - stages at risk: {headline}", EV / f"riba_gantt_v2{suffix}.png",
               start64, q, base=v1, risk=risk, issues=list(impacts.issue) + new_acts + newly, handover=ho,
               issue_day=int(v1.set_index("id").at[sc["issue_after"], "EF"]))
    risk.to_csv(DATA / f"riba_risk{suffix}.csv", index=False)
    crit = " -> ".join(v2.sort_values("ES")[v2.sort_values("ES").critical].id)
    return {"key": key, "label": sc["label"], "v2": v2, "risk": risk, "handover": ho, "critical": crit,
            "newly": newly, "new_acts": new_acts}


def main():
    rules = json.loads((DATA / "riba_rules.json").read_text(encoding="utf-8"))
    assumptions = se.load_assumptions()
    changes = se.load_changes()
    if not changes:
        sys.exit("data/changes.json not found - run scripts/detect_changes.py first")
    programme = build_programme(rules)
    q = ifc_counts(V1_IFC)
    v1 = se.cpm(se.Network(activities=programme))
    impacts = stage_impacts(changes, rules, assumptions)

    # calendar: anchor so that construction (A1) starts on the date used in the rest of PMI
    a1 = int(v1.loc[v1.id == "A1", "ES"].iloc[0])
    start64 = np.busday_offset(np.datetime64(date.fromisoformat(rules["construction_start"]), "D"), -a1, roll="backward")
    day = lambda d: f"{pd.Timestamp(np.busday_offset(start64, d - 1, roll='forward')):%d %b %Y}"  # noqa: E731

    EV.mkdir(exist_ok=True); DOCS.mkdir(exist_ok=True)
    riba_gantt(v1, "PMI - RIBA programme from Model V1 (baseline)", EV / "riba_gantt_v1.png", start64, q)
    impacts.to_csv(DATA / "riba_impacts.csv", index=False)
    results = [run_scenario(k, sc, programme, v1, impacts, changes, rules, start64, q)
               for k, sc in rules["issue_scenarios"].items()]
    pd.DataFrame([{"scenario": r["key"], "label": r["label"], **r["handover"],
                   "handover_v1_date": day(r["handover"]["handover_v1_day"]),
                   "handover_v2_date": day(r["handover"]["handover_v2_day"]),
                   "contract_date": day(r["handover"]["contract_day"]),
                   "stages_high": ", ".join(r["risk"][r["risk"].risk == "HIGH"].stage)} for r in results]
                 ).to_csv(DATA / "handover_scenarios.csv", index=False)

    construction_only = (se.project_duration(se.run_all()["schedules"]["revised"])
                         - se.project_duration(se.run_all()["schedules"]["baseline"]))
    md = ["# PMI - RIBA stage risk report", "",
          "*Rule-based forecast (documented rules in data/riba_rules.json + CPM, no machine learning).*", "",
          f"Model V1 quantities: {', '.join(f'{v} {k}' for k, v in q.items())}", "",
          f"V1 handover: {day(int(v1.EF.max()))} (day {int(v1.EF.max())}). Contract handover = V1 + "
          f"{rules.get('contract_handover_buffer_days', 25)} working days buffer. "
          f"Construction-only analysis (schedule_engine.py): +{construction_only} days.", "",
          "| Issue scenario | V2 handover | Slip | Verdict | Stages HIGH |", "|---|---|---|---|---|"]
    for r in results:
        h = r["handover"]
        md.append(f"| {r['label']} | {day(h['handover_v2_day'])} | +{h['slip_days']} d | **{h['verdict']}** | "
                  f"{', '.join(r['risk'][r['risk'].risk == 'HIGH'].stage)} |")
    for r in results:
        md += ["", f"## {r['label']}", "", f"**Critical path:** {r['critical']}", "",
               f"**Newly critical:** {'; '.join(r['newly']) or 'none'}", "",
               f"**New activities (work already done when V2 arrived):** {'; '.join(r['new_acts']) or 'none'}", "",
               "| Stage | Risk | Score | Role | Slip (d) | Min float V1 -> V2 | Changes | Why |",
               "|---|---|---|---|---|---|---|---|"]
        for x in r["risk"].itertuples():
            md.append(f"| {x.stage} {x.name} | **{x.risk}** | {x.risk_score} | {x.role} | {x.slip_days} | "
                      f"{x.min_float_v1} -> {x.min_float_v2} | {x.changes} | {x.issues} |")
    md += ["", "## Issues (extra work per change)", ""] + [f"- {t}" for t in impacts.issue]
    md += ["", "## Risk levels", ""] + [f"- **{k}**: {v}" for k, v in rules["risk_levels"].items()]
    (DOCS / "riba_risk_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    pd.set_option("display.width", 200)
    print("\nPMI - RIBA STAGE RISK (rule-based forecast)")
    print("-------------------------------------------")
    for r in results:
        print(f"\n[{r['label']}]")
        print(r["risk"][["stage", "name", "risk", "risk_score", "role", "slip_days", "min_float_v1",
                         "min_float_v2"]].to_string(index=False))
        print("Handover:", r["handover"]["verdict"], f"(V2 {day(r['handover']['handover_v2_day'])})")
        print("Critical path:", r["critical"])
        if r["new_acts"]:
            print("New:", "; ".join(r["new_acts"]))
    print("\nSaved evidence/riba_gantt_v1.png, riba_gantt_v2*.png, data/riba_risk*.csv, data/handover_scenarios.csv,"
          " docs/riba_risk_report.md")


if __name__ == "__main__":
    main()
