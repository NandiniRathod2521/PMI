"""
PMI - Project Management Intelligence  |  Streamlit interface
=============================================================
Sections, top to bottom (no tabs - they were unreliable before).  Sidebar: import two IFC models.
    1. Model changes        what changed between IFC V1 and V2 (+ 3D view)
    2. Schedule impact      baseline vs revised Gantt, delay, affected activities
    3. Scenario comparison  cost-efficient / environmental / alternative, vs preferred completion date
    4. Role of AI           what is deterministic today and what the AI layer will add

Run:  python -m streamlit run app.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
import schedule_engine as se  # noqa: E402

BLUE, LIGHT, RED, GREY, INK = "#1F4E9E", "#A9C1E8", "#D64545", "#B8BEC7", "#1B2430"
CAT_COLOR = {"wall": "#D64545", "door": "#F08C2E", "window": "#2F80ED", "other": "#7A5AC9"}

st.set_page_config(page_title="PMI - Project Management Intelligence", layout="wide")
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');
    html, body, [class*="css"], .stMarkdown, h1, h2, h3 { font-family: 'Poppins', sans-serif; }
    h1, h2, h3 { color: #1F4E9E; }
    div[data-testid="stMetricValue"] { color: #1F4E9E; }
    .pmi-note { background:#EEF3FB; color:#1B2430; border-left:4px solid #1F4E9E; padding:10px 14px; border-radius:6px; font-size:0.92rem; }
    .pmi-warn { background:#FDF1F1; color:#1B2430; border-left:4px solid #D64545; padding:10px 14px; border-radius:6px; font-size:0.92rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ----------------------------------------------------------------------------
# Data loading (cached)
# ----------------------------------------------------------------------------
@st.cache_data
def load_detection():
    p = ROOT / "data" / "changes.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


@st.cache_data
def load_geometry():
    p = ROOT / "grasshopper" / "pmi_geometry.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


detection = load_detection()
if detection is None:
    st.error("data/changes.json not found. Run `python run_pipeline.py` (or scripts/detect_changes.py) first.")
    st.stop()
changes = detection["changes"]
assumptions = se.load_assumptions()

# ----------------------------------------------------------------------------
# Sidebar - inputs
# ----------------------------------------------------------------------------
with st.sidebar:
    logo = ROOT / "assets" / "logo" / "pmi-logo.png"
    if logo.is_file():
        st.image(str(logo), width="stretch")
    st.markdown("### Project inputs")
    start = st.date_input("Project start", date.fromisoformat(assumptions["project_start"]))
    target = st.date_input("Preferred completion date", date.fromisoformat(assumptions["project_start"]) + timedelta(days=105))

    # ---- Import two IFC models and re-run the whole pipeline ----------------------
    st.markdown("### Models")
    state_file = ROOT / "data" / "models_in_use.json"
    in_use = json.loads(state_file.read_text(encoding="utf-8")) if state_file.is_file() else {"label": "test case"}
    st.caption(f"In use: **{in_use.get('label')}**"
               + (f" - V1 `{in_use['v1']}`, V2 `{in_use['v2']}`" if in_use.get("v1") else ""))
    with st.expander("Import IFC models (V1 + V2)"):
        up1 = st.file_uploader("V1 - original model", type=["ifc"], key="up_v1")
        up2 = st.file_uploader("V2 - revised model", type=["ifc"], key="up_v2")
        run_args = None
        if st.button("Run PMI on these models", disabled=not (up1 and up2), type="primary"):
            dest = ROOT / "models" / "uploads"
            dest.mkdir(parents=True, exist_ok=True)
            p1, p2 = dest / f"V1_{up1.name}", dest / f"V2_{up2.name}"
            p1.write_bytes(up1.getbuffer())
            p2.write_bytes(up2.getbuffer())
            run_args = ["--v1", str(p1), "--v2", str(p2)]
        if st.button("Demo: V2 -> V3 structural revision"):
            run_args = ["--demo-v3"]
        if st.button("Restore the midterm test models", disabled=not (ROOT / "models" / "test_case").is_dir()):
            run_args = ["--restore"]
        if run_args:
            with st.spinner("Running detection, geometry, schedule, evidence and RIBA risk... (about 1 minute)"):
                r = subprocess.run([sys.executable, str(ROOT / "run_pipeline.py"), *run_args], cwd=ROOT,
                                   capture_output=True, text=True)
            if r.returncode == 0:
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("The pipeline stopped - see the log below and docs/pipeline_log.txt")
                st.code((r.stdout + r.stderr)[-3000:])

result = se.run_all(changes=changes, start=start, target=target)   # every change detected in the loaded IFC pair
base = result["schedules"]["baseline"]
rev = result["schedules"]["revised"]
comp = result["comparison"]
base_days, rev_days = se.project_duration(base), se.project_duration(rev)
target_wd = int(np.busday_count(np.datetime64(start, "D"), np.datetime64(target + timedelta(days=1), "D")))


def gantt(sched_a, name_a, color_a, sched_b=None, name_b=None, color_b=None, title=""):
    """Grouped horizontal Gantt on a working-day axis; red segment = days added by design change."""
    fig = go.Figure()
    y = sched_a["activity"]
    fig.add_bar(y=y, x=sched_a["duration"], base=sched_a["ES"], orientation="h", name=name_a,
                marker_color=color_a, offsetgroup="a",
                hovertemplate="%{y}<br>day %{base} - %{customdata}<extra>" + name_a + "</extra>",
                customdata=sched_a["EF"])
    if sched_b is not None:
        fig.add_bar(y=sched_b["activity"], x=sched_b["duration"] - sched_b["added_days"], base=sched_b["ES"],
                    orientation="h", name=name_b, marker_color=color_b, offsetgroup="b",
                    hovertemplate="%{y}<extra>" + name_b + "</extra>")
        added = sched_b[sched_b["added_days"] > 0]
        if not added.empty:
            fig.add_bar(y=added["activity"], x=added["added_days"], base=added["EF"] - added["added_days"],
                        orientation="h", name="Added by design change", marker_color=RED, offsetgroup="b",
                        hovertemplate="%{y}: +%{x} days<extra></extra>")
    end_a = int(sched_a["EF"].max())
    fig.add_vline(x=end_a, line_dash="dash", line_color=GREY)
    if sched_b is not None:
        fig.add_vline(x=int(sched_b["EF"].max()), line_dash="dash", line_color=RED)
    fig.add_vline(x=target_wd, line_dash="dot", line_color="#2E8B57",
                  annotation_text="preferred completion", annotation_position="top")
    fig.update_layout(barmode="group", height=420, title=title, xaxis_title="Working days from project start",
                      yaxis=dict(autorange="reversed"), legend=dict(orientation="h", y=-0.2),
                      margin=dict(l=10, r=10, t=50, b=10), font=dict(family="Poppins"))
    return fig


# ----------------------------------------------------------------------------
# Header
# ----------------------------------------------------------------------------
st.title("PMI - Project Management Intelligence")
st.markdown("**From a BIM design change to its construction-schedule consequence.**  "
            "IAAC Research Studio - midterm prototype.")

# ----------------------------------------------------------------------------
# 1. MODEL CHANGES
# ----------------------------------------------------------------------------
st.header("1  Model changes")
s = detection["summary"]
geo_changed = sum(c.get("geometry_changed", False) for c in changes)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Modified elements", s["MODIFIED"])
c2.metric("Added / deleted", f"{s['ADDED']} / {s['DELETED']}")
c3.metric("Geometry changed", geo_changed)
c4.metric("Elements compared", sum(s.values()))

table = pd.DataFrame([{
    "IFC type": c["ifc_type"], "GlobalId": c["global_id"], "Element (V2)": c["element"],
    "Previous name (V1)": c.get("old_name", ""), "Change channel": ", ".join(c["change_types"]),
    "What changed": c.get("summary", ""),
    "Geometry changed": c.get("geometry_changed", False),
} for c in changes])
st.dataframe(table, width="stretch", hide_index=True)
if changes and geo_changed == 0:
    st.markdown("<div class='pmi-note'>The V2 model changes the <b>specification</b> (name / description) of these "
                "elements - not their geometry. PMI reports this explicitly: a renamed element is not treated as a "
                "geometric modification.</div>", unsafe_allow_html=True)

geom = load_geometry()
with st.expander("3D view - changed elements highlighted", expanded=geom is not None):
    if geom is None:
        img = ROOT / "evidence" / "changed_elements.png"
        if img.is_file():
            st.image(str(img), caption="Rhino / Grasshopper screenshot", width="stretch")
        else:
            st.info("Run scripts/export_geometry.py to enable the 3D view.")
    else:
        groups = {}
        for e in geom["elements"]:
            key = e["category"] if e["status"] != "UNCHANGED" else "unchanged"
            g = groups.setdefault(key, {"x": [], "y": [], "z": [], "i": [], "j": [], "k": [], "n": 0})
            off = g["n"]
            for vx, vy, vz in e["vertices"]:
                g["x"].append(vx); g["y"].append(vy); g["z"].append(vz)
            for a, b, c_ in e["faces"]:
                g["i"].append(a + off); g["j"].append(b + off); g["k"].append(c_ + off)
            g["n"] += len(e["vertices"])
        fig3d = go.Figure()
        for key, g in groups.items():
            fig3d.add_mesh3d(x=g["x"], y=g["y"], z=g["z"], i=g["i"], j=g["j"], k=g["k"], name=key,
                             color=GREY if key == "unchanged" else CAT_COLOR.get(key, RED),
                             opacity=0.18 if key == "unchanged" else 1.0, flatshading=True, showlegend=True)
        fig3d.update_layout(height=560, scene=dict(aspectmode="data", xaxis_visible=False,
                                                   yaxis_visible=False, zaxis_visible=False),
                            margin=dict(l=0, r=0, t=0, b=0), legend=dict(orientation="h"))
        st.plotly_chart(fig3d, width="stretch")
        st.caption("Grey = unchanged, red = wall, orange = door, blue = window. Geometry triangulated with IfcOpenShell.")

# ----------------------------------------------------------------------------
# 2. SCHEDULE IMPACT
# ----------------------------------------------------------------------------
st.header("2  Schedule impact")
d1, d2, d3, d4 = st.columns(4)
d1.metric("Baseline duration", f"{base_days} days")
d2.metric("Revised duration", f"{rev_days} days", delta=f"+{rev_days - base_days} days", delta_color="inverse")
d3.metric("Baseline finish", f"{base['finish_date'].max():%d %b %Y}")
d4.metric("Revised finish", f"{rev['finish_date'].max():%d %b %Y}")

imp = result["impacts"]
if imp.empty:
    st.info("No design changes detected between V1 and V2 - the revised schedule equals the baseline.")
else:
    st.markdown("**IFC change → construction activity** (rule-based mapping, duration impact = assumed scenario input)")
    st.dataframe(imp[["ifc_type", "element", "activity_id", "possible_impact", "extra_days", "extra_cost_eur",
                      "rationale", "source"]].rename(columns={
                          "ifc_type": "IFC type", "element": "Element", "activity_id": "Activity",
                          "possible_impact": "Possible impact", "extra_days": "+days (assumed)",
                          "extra_cost_eur": "+cost EUR (assumed)", "rationale": "Why", "source": "Source"}),
                 width="stretch", hide_index=True)

st.plotly_chart(gantt(base, "Baseline", LIGHT, rev, "Revised", BLUE, "Baseline vs revised schedule"),
                width="stretch")
with st.expander("How the baseline was built from Model V1 (quantities x rates)"):
    bl = se.load_baseline()
    st.dataframe(bl[["id", "activity", "quantity_types", "quantity", "days_per_unit", "min_days", "rule",
                     "duration_days"]].rename(columns={
                         "quantity_types": "Counted IFC types", "quantity": "Count in V1",
                         "days_per_unit": "Days per element", "min_days": "Minimum", "rule": "Rule",
                         "duration_days": "Duration (days)"}), width="stretch", hide_index=True)
    st.caption("Rates are in data/schedule_template.csv and impacts per IFC type x change channel in "
               "data/assumptions.json - generic rules, so any IFC pair runs without editing the code.")
with st.expander("Calculated schedule (CPM: early/late start, float, critical path)"):
    show = rev[["id", "activity", "base_duration", "added_days", "duration", "ES", "EF", "LS", "LF", "float",
                "critical", "start_date", "finish_date"]].copy()
    show["start_date"] = show["start_date"].dt.date
    show["finish_date"] = show["finish_date"].dt.date
    st.dataframe(show, width="stretch", hide_index=True)
    st.caption("MEP rough-in has float: a delay there would not move the finish date - "
               "this is what dependency propagation adds beyond simply summing days.")

# ----------------------------------------------------------------------------
# 3. SCENARIO COMPARISON
# ----------------------------------------------------------------------------
st.header("3  Scenario comparison")
view = comp.copy()
view["finish_date"] = pd.to_datetime(view["finish_date"]).dt.strftime("%d %b %Y")
view["meets_target"] = view["meets_target"].map({True: "Yes", False: "No"})
st.dataframe(view[["scenario", "duration_days", "delay_days", "finish_date", "extra_cost_eur", "extra_tco2e",
                   "meets_target", "risk"]].rename(columns={
                       "scenario": "Scenario", "duration_days": "Duration (days)", "delay_days": "Delay",
                       "finish_date": "Finish", "extra_cost_eur": "Extra cost EUR", "extra_tco2e": "Extra tCO2e",
                       "meets_target": f"Meets {target:%d %b}", "risk": "Risk"}),
             width="stretch", hide_index=True)

options = {r.scenario: r.key for r in comp.itertuples() if r.key not in ("baseline", "revised")}
choice = st.radio("Inspect a mitigation scenario", list(options), horizontal=True)
key = options[choice]
row = comp.set_index("key").loc[key]
sc = result["schedules"][key]
e1, e2, e3, e4 = st.columns(4)
e1.metric("Duration", f"{row.duration_days} days", delta=f"{row.duration_days - rev_days} vs revised",
          delta_color="inverse")
e2.metric("Finish", f"{pd.to_datetime(row.finish_date):%d %b %Y}")
e3.metric("Extra cost vs baseline", f"€{row.extra_cost_eur:,.0f}")
e4.metric("Extra emissions", f"{row.extra_tco2e:.2f} tCO2e")
st.markdown(f"<div class='pmi-note'><b>{choice}</b> - {row.description}<br><b>Risk:</b> {row.risk}</div>",
            unsafe_allow_html=True)
st.plotly_chart(gantt(rev, "Revised (no mitigation)", LIGHT, sc, choice, "#2E8B57", f"Revised vs {choice}"),
                width="stretch")
st.markdown("<div class='pmi-warn'>All durations, costs and emissions are <b>illustrative assumptions</b> "
            "(data/assumptions.json), not AI predictions or measured project data. The engine calculates how they "
            "propagate through the schedule.</div>", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# 5. RIBA STAGE RISK (from scripts/riba_risk.py)
# ----------------------------------------------------------------------------
st.header("4  RIBA stage risk and handover")
ho_csv = ROOT / "data" / "handover_scenarios.csv"
if not ho_csv.is_file():
    st.info("Run `python scripts/riba_risk.py` (or run_pipeline.py) to forecast which RIBA stage is at risk.")
else:
    hos = pd.read_csv(ho_csv)
    pick = st.radio("When does Model V2 reach the team?", list(hos.label), horizontal=True, key="issue_pick")
    h = hos.set_index("label").loc[pick]
    suffix = "" if h.scenario == "stage4" else f"_{h.scenario}"
    k1, k2, k3 = st.columns(3)
    k1.metric("Handover V1 -> V2", h.handover_v2_date, delta=f"+{h.slip_days} working days", delta_color="inverse")
    k2.metric("Contract handover", h.contract_date, delta=f"{h.buffer_days} days buffer", delta_color="off")
    k3.metric("Handover", h.level)
    box = {"AT RISK": "pmi-warn", "TIGHT": "pmi-warn", "OK": "pmi-note"}[h.level]
    st.markdown(f"<div class='{box}'><b>{h.verdict}</b> - stages HIGH: {h.stages_high}</div>", unsafe_allow_html=True)
    rk = pd.read_csv(ROOT / "data" / f"riba_risk{suffix}.csv")
    st.dataframe(rk[["stage", "name", "risk", "risk_score", "role", "slip_days", "min_float_v1", "min_float_v2",
                     "changes", "issues"]], width="stretch", hide_index=True)
    img = ROOT / "evidence" / f"riba_gantt_v2{suffix}.png"
    if img.is_file():
        st.image(str(img), caption=f"RIBA programme for Model V2 - {pick}", width="stretch")
    with st.expander("RIBA programme from Model V1 (baseline)"):
        if (ROOT / "evidence" / "riba_gantt_v1.png").is_file():
            st.image(str(ROOT / "evidence" / "riba_gantt_v1.png"), width="stretch")
    st.markdown("<div class='pmi-note'>Rule-based forecast: documented rules (data/riba_rules.json) + CPM, no machine "
                "learning. A late issue means built work must be reworked and ordered items re-ordered - the option "
                "that puts handover at risk.</div>", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# ENGINEERING VERIFICATION REPORT (scripts/engineering_report.py)
# ----------------------------------------------------------------------------
st.header("5  Engineering verification report")
eng_csv, eng_md = ROOT / "data" / "engineering_checks.csv", ROOT / "docs" / "engineering_report.md"
if not eng_csv.is_file():
    st.info("Run `python scripts/engineering_report.py` (or run_pipeline.py) to create the report for engineers.")
else:
    ec = pd.read_csv(eng_csv)
    if ec.empty:
        st.success("No structural, MEP, envelope or fire relevant change detected.")
    else:
        cnt = ec.groupby("reviewer").size()
        cols = st.columns(len(cnt))
        for col, (who, k) in zip(cols, cnt.items()):
            col.metric(who, f"{k} check{'s' if k > 1 else ''}")
        st.dataframe(ec[["id", "reviewer", "element", "check", "result", "flags", "status"]], width="stretch",
                     hide_index=True)
    if eng_md.is_file():
        st.download_button("Download the report (Markdown) for the engineers", eng_md.read_bytes(),
                           file_name="PMI_engineering_report.md", mime="text/markdown")
        with st.expander("Read the full report"):
            st.markdown(eng_md.read_text(encoding="utf-8"))
    st.markdown("<div class='pmi-warn'><b>Screening only - not a design calculation.</b> Every check must be verified "
                "and signed by the responsible certified engineer (sign-off table at the end of the report).</div>",
                unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# 4. ROLE OF AI
# ----------------------------------------------------------------------------
st.header("6  What is AI and what is not")
st.table(pd.DataFrame([
    ["IFC parsing", "IfcOpenShell / Python", "Deterministic", "Working"],
    ["Change detection", "GlobalId comparison, 5 channels", "Deterministic", "Working"],
    ["Activity mapping", "Rule table (IFC type → activity)", "Rule-based; AI-assisted next", "Working (rules)"],
    ["Scheduling", "Dependency graph + CPM", "Deterministic", "Working"],
    ["Scenario comparison", "Parametric what-if on the CPM network", "Deterministic", "Working"],
    ["RIBA stage risk + handover", "Rules per change + CPM, issue-timing scenarios", "Rule-based", "Working"],
    ["Engineering screening", "Q = U·A·dT, span ratios, fire-rating match", "Deterministic", "Working - for engineer sign-off"],
    ["Interpretation & mitigation advice", "LLM (pretrained transformer)", "AI", "Proposed - not connected"],
], columns=["Component", "Method", "Type", "Status in this prototype"]))
st.markdown("PMI is a **hybrid AI-assisted, rule-based scheduling system**. Today every number is produced by "
            "transparent algorithms. The proposed LLM layer will (1) interpret ambiguous changes such as "
            "*'revised for fire safety'* and suggest which activities they affect, and (2) draft mitigation options "
            "with explanations - always checked by the deterministic engine and the project manager.")
with st.expander("All assumptions (data/assumptions.json)"):
    st.json(assumptions)
