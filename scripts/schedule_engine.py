"""
PMI - STEP 3: SCHEDULE ENGINE  (rule-based mapping + Critical Path Method)
==========================================================================

Pipeline
--------
    IFC change (data/changes.json)
        -> 1. map element type to a construction activity      (data/activity_mapping.csv)
        -> 2. look up the ASSUMED duration / cost impact         (data/assumptions.json)
        -> 3. add the extra days to that activity
        -> 4. recalculate every start/finish with CPM            (forward + backward pass)
        -> 5. new project finish date, critical path and float
        -> 6. optional mitigation scenario (cost / environmental / alternative)

Important for the defence:
    * The extra days per change are DOCUMENTED ASSUMPTIONS (scenario inputs).
    * What PMI *calculates* is how those days PROPAGATE through the dependency
      network - e.g. a delay on an activity with float may cause no project delay.
    * No machine learning is used in this file.

Can be imported (used by app.py, validate.py) or run directly:
    python scripts/schedule_engine.py
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


# ----------------------------------------------------------------------------
# Reading quantities from an IFC file (plain text - works with any IFC2x3 / IFC4 file)
# ----------------------------------------------------------------------------
V1_IFC = ROOT / "models" / "original.ifc"
_SUFFIXES = ("STANDARDCASE", "ELEMENTEDCASE")


def base_type(ifc_type: str) -> str:
    """IfcWallStandardCase -> IfcWall, IfcDoorStandardCase -> IfcDoor (IFC2x3 / IFC4 variants)."""
    for suf in ("StandardCase", "ElementedCase"):
        if ifc_type.endswith(suf):
            return ifc_type[: -len(suf)]
    return ifc_type


def count_ifc(path: Path = V1_IFC) -> dict:
    """{'IFCWALL': 57, ...}: number of instances of every entity in the file, read from its text."""
    if not path.is_file():
        return {}
    counts = {}
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            m = re.match(r"\s*#\d+\s*=\s*(IFC[A-Z0-9]+)\s*\(", line)
            if m:
                counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    return counts


def quantity(counts: dict, types: list) -> int:
    """Instances of the given IFC types, including their StandardCase / ElementedCase variants."""
    total = 0
    for t in types:
        T = t.upper()
        total += sum(n for name, n in counts.items() if name == T or (name.startswith(T) and name[len(T):] in _SUFFIXES))
    return total


# ----------------------------------------------------------------------------
# Loading inputs
# ----------------------------------------------------------------------------
def build_baseline(template: Path = DATA / "schedule_template.csv", ifc: Path = V1_IFC) -> pd.DataFrame:
    """Baseline schedule GENERATED from Model V1:  duration = max(min_days, round(quantity x days_per_unit)).
    Nothing in this function is specific to one model; change the rates in data/schedule_template.csv."""
    t = pd.read_csv(template, dtype={"predecessors": str, "quantity_types": str}).fillna(
        {"predecessors": "", "quantity_types": ""})
    counts = count_ifc(ifc)
    rows = []
    for r in t.itertuples():
        types = [x for x in r.quantity_types.split(";") if x]
        q = quantity(counts, types) if types else 0
        d = max(int(r.min_days), int(round(q * float(r.days_per_unit)))) if types else int(r.min_days)
        rows.append({"id": r.id, "activity": r.activity, "duration_days": d, "predecessors": r.predecessors,
                     "phase": r.phase, "quantity": q, "quantity_types": r.quantity_types,
                     "days_per_unit": r.days_per_unit, "min_days": r.min_days,
                     "rule": (f"max({r.min_days}, {q} x {r.days_per_unit})" if types else f"fixed {r.min_days}")})
    df = pd.DataFrame(rows)
    df.to_csv(DATA / "baseline_schedule.csv", index=False)      # written for transparency
    return df


def load_baseline(path: Path | None = None) -> pd.DataFrame:
    """The baseline schedule. Default: generated from models/original.ifc + data/schedule_template.csv.
    Pass a CSV path to load a fixed schedule instead."""
    if path is None and (DATA / "schedule_template.csv").is_file() and V1_IFC.is_file():
        df = build_baseline()
    else:
        df = pd.read_csv(path or DATA / "baseline_schedule.csv", dtype={"predecessors": str})
    df = df.fillna({"predecessors": ""})
    df["predecessors"] = df["predecessors"].apply(lambda s: [p for p in str(s).split(";") if p])
    return df


def load_mapping(path: Path = DATA / "activity_mapping.csv") -> dict:
    df = pd.read_csv(path)
    return {r.ifc_type: (r.activity_id, r.possible_impact) for r in df.itertuples()}


def load_assumptions(path: Path = DATA / "assumptions.json") -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_changes(path: Path = DATA / "changes.json") -> list:
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("changes", [])


# ----------------------------------------------------------------------------
# Step 1+2: changes -> affected activities  (rules by IFC type x change channel)
# ----------------------------------------------------------------------------
def impact_of(change: dict, rules: dict) -> dict:
    """Extra days / cost / CO2 for one change = sum over its change channels of the rule for its
    IFC type (falls back to '_default').  Attribute-only changes (rename, new description) = 0."""
    t = base_type(change["ifc_type"])
    table = rules.get(t) or rules["_default"]
    channels = change.get("change_types", [])
    if change.get("status") in ("ADDED", "DELETED"):
        channels = [change["status"].lower()]
    days = cost = co2 = 0.0
    why = []
    for ch in channels:
        r = table.get(ch, rules["_default"].get(ch))
        if not r or not isinstance(r, dict):
            continue
        days += r["days"]; cost += r["cost_eur"]; co2 += r.get("tco2e", 0.0)
        if r["days"] or r["cost_eur"]:
            why.append(r["why"])
    if not why:
        why = ["Attribute-only change (name / description) -> no construction impact"
               if set(channels) <= {"attribute"} else "No rule for this change -> no impact assumed"]
    return {"extra_days": int(round(days)), "extra_cost_eur": round(cost), "material_tco2e": round(co2, 3),
            "rationale": "; ".join(why)}


def map_changes_to_activities(changes: list, mapping: dict, assumptions: dict) -> pd.DataFrame:
    """One row per detected change with the activity it affects and its rule-based impact."""
    rows = []
    for c in changes:
        if c.get("status") == "UNCHANGED":
            continue
        act, impact = mapping.get(c["ifc_type"]) or mapping.get(base_type(c["ifc_type"])) \
            or (None, "No mapping - manual review")
        imp = impact_of(c, assumptions["impact_rules"])
        rows.append({
            "global_id": c["global_id"],
            "ifc_type": c["ifc_type"],
            "element": c.get("element", ""),
            "change_types": ", ".join(c.get("change_types", [])),
            "activity_id": act,
            "possible_impact": impact,
            "extra_days": imp["extra_days"] if act else 0,
            "extra_cost_eur": imp["extra_cost_eur"],
            "material_tco2e": imp["material_tco2e"],
            "rationale": imp["rationale"],
            "source": "Rule: IFC type x change channel (data/assumptions.json)",
        })
    return pd.DataFrame(rows, columns=["global_id", "ifc_type", "element", "change_types", "activity_id",
                                       "possible_impact", "extra_days", "extra_cost_eur", "material_tco2e",
                                       "rationale", "source"])


# ----------------------------------------------------------------------------
# Step 3+4: CPM
# ----------------------------------------------------------------------------
@dataclass
class Network:
    """Activities with durations and finish-to-start links (with optional lag)."""
    activities: pd.DataFrame                    # id, activity, duration_days, predecessors, phase
    lags: dict = field(default_factory=dict)    # {(pred, succ): lag_days}
    added_days: dict = field(default_factory=dict)  # {activity_id: days added by design changes}


def cpm(net: Network) -> pd.DataFrame:
    """Forward + backward pass. Days are 0-based working days; EF is exclusive."""
    df = net.activities.set_index("id")
    dur = {i: int(df.at[i, "duration_days"]) + int(net.added_days.get(i, 0)) for i in df.index}
    preds = {i: df.at[i, "predecessors"] for i in df.index}
    succs = {i: [j for j in df.index if i in preds[j]] for i in df.index}

    # topological order (Kahn)
    order, indeg = [], {i: len(preds[i]) for i in df.index}
    queue = [i for i in df.index if indeg[i] == 0]
    while queue:
        n = queue.pop(0)
        order.append(n)
        for s in succs[n]:
            indeg[s] -= 1
            if indeg[s] == 0:
                queue.append(s)
    if len(order) != len(df):
        raise ValueError("Schedule has a dependency loop")

    es, ef = {}, {}
    for i in order:
        es[i] = max([ef[p] + net.lags.get((p, i), 0) for p in preds[i]], default=0)
        es[i] = max(es[i], 0)
        ef[i] = es[i] + dur[i]
    project_end = max(ef.values())

    ls, lf = {}, {}
    for i in reversed(order):
        lf[i] = min([ls[s] - net.lags.get((i, s), 0) for s in succs[i]], default=project_end)
        ls[i] = lf[i] - dur[i]

    out = df.reset_index()[["id", "activity", "phase"]].copy()
    out["base_duration"] = [int(df.at[i, "duration_days"]) for i in out["id"]]
    out["added_days"] = [int(net.added_days.get(i, 0)) for i in out["id"]]
    out["duration"] = [dur[i] for i in out["id"]]
    out["ES"] = [es[i] for i in out["id"]]
    out["EF"] = [ef[i] for i in out["id"]]
    out["LS"] = [ls[i] for i in out["id"]]
    out["LF"] = [lf[i] for i in out["id"]]
    out["float"] = out["LS"] - out["ES"]
    out["critical"] = out["float"] == 0
    return out


def add_dates(sched: pd.DataFrame, start: date) -> pd.DataFrame:
    """Convert working-day offsets to calendar dates (Mon-Fri)."""
    s = sched.copy()
    start64 = np.datetime64(start, "D")
    s["start_date"] = pd.to_datetime(np.busday_offset(start64, s["ES"].to_numpy(), roll="forward"))
    s["finish_date"] = pd.to_datetime(np.busday_offset(start64, (s["EF"] - 1).to_numpy(), roll="forward"))
    return s


def project_duration(sched: pd.DataFrame) -> int:
    return int(sched["EF"].max())


# ----------------------------------------------------------------------------
# Step 5+6: scenarios
# ----------------------------------------------------------------------------
def build_network(baseline: pd.DataFrame, impacts: pd.DataFrame | None = None) -> Network:
    net = Network(activities=baseline.copy())
    if impacts is not None and not impacts.empty:
        for act, days in impacts.groupby("activity_id")["extra_days"].sum().items():
            if act:
                net.added_days[act] = net.added_days.get(act, 0) + int(days)
    return net


def apply_operations(net: Network, operations: list) -> Network:
    n = copy.deepcopy(net)
    for op in operations:
        if op["op"] == "set_lag":
            n.lags[(op["predecessor"], op["activity"])] = int(op["lag_days"])
        elif op["op"] == "reduce_added_days":
            # a mitigation can only remove delay that a change introduced - never below baseline
            a = op["activity"]
            n.added_days[a] = max(0, n.added_days.get(a, 0) - int(op["days"]))
        else:
            raise ValueError(f"Unknown operation {op['op']}")
    return n


def run_all(changes: list | None = None, start: date | None = None,
            selected_ids: list | None = None, target: date | None = None) -> dict:
    """Everything the app needs, in one call."""
    baseline = load_baseline()
    mapping = load_mapping()
    A = load_assumptions()
    changes = load_changes() if changes is None else changes
    if selected_ids is not None:
        changes = [c for c in changes if c["global_id"] in selected_ids]
    start = start or date.fromisoformat(A["project_start"])

    impacts = map_changes_to_activities(changes, mapping, A)
    base_net = build_network(baseline)
    rev_net = build_network(baseline, impacts)

    base = add_dates(cpm(base_net), start)
    revised = add_dates(cpm(rev_net), start)
    base_days = project_duration(base)

    change_cost = float(impacts["extra_cost_eur"].sum()) if not impacts.empty else 0.0
    change_co2 = float(impacts["material_tco2e"].sum()) if not impacts.empty else 0.0

    def kpis(key, label, desc, sched, mit_cost=0.0, mit_co2=0.0, risk="-", tested=True):
        days = project_duration(sched)
        delay = days - base_days
        finish = sched["finish_date"].max().date()
        return {
            "key": key, "scenario": label, "description": desc,
            "duration_days": days, "delay_days": delay, "finish_date": finish,
            "extra_cost_eur": round(change_cost * (key != "baseline") + mit_cost + delay * A["daily_overhead_eur"]),
            "extra_tco2e": round(change_co2 * (key != "baseline") + mit_co2 + delay * A["site_emissions_tco2e_per_day"], 2),
            "risk": risk,
            "meets_target": (finish <= target) if target else None,
            "engine_tested": tested,
        }

    scenarios = {"baseline": base, "revised": revised}
    table = [
        kpis("baseline", "Baseline (Model V1)", "Original schedule before design changes", base),
        kpis("revised", "Revised - no mitigation", "Design changes applied, nothing else changed", revised),
    ]
    for key, sc in A["scenarios"].items():
        s = add_dates(cpm(apply_operations(rev_net, sc["operations"])), start)
        scenarios[key] = s
        table.append(kpis(key, sc["label"], sc["description"], s,
                          sc["mitigation_cost_eur"], sc["material_tco2e"], sc["risk"]))

    return {
        "start": start,
        "impacts": impacts,
        "schedules": scenarios,
        "comparison": pd.DataFrame(table),
        "assumptions": A,
        "baseline_days": base_days,
    }


def main():
    r = run_all()
    print("\nPMI - SCHEDULE IMPACT")
    print("---------------------")
    if r["impacts"].empty:
        print("No changes found - run scripts/detect_changes.py first.")
    else:
        print(r["impacts"][["ifc_type", "element", "activity_id", "extra_days", "source"]].to_string(index=False))
    for key in ("baseline", "revised"):
        s = r["schedules"][key]
        print(f"\n{key.upper()}: {project_duration(s)} working days, finish {s['finish_date'].max().date()}")
        print(s[["id", "activity", "duration", "ES", "EF", "float", "critical"]].to_string(index=False))
    print("\nSCENARIO COMPARISON")
    print(r["comparison"][["scenario", "duration_days", "delay_days", "finish_date",
                           "extra_cost_eur", "extra_tco2e"]].to_string(index=False))

    # save the revised schedule for the submission folder
    r["schedules"]["baseline"].to_csv(DATA / "baseline_schedule_calculated.csv", index=False)
    r["schedules"]["revised"].to_csv(DATA / "revised_schedule.csv", index=False)
    r["comparison"].to_csv(DATA / "scenario_comparison.csv", index=False)
    print(f"\nSaved data/revised_schedule.csv and data/scenario_comparison.csv")


if __name__ == "__main__":
    main()
