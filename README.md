# PMI — Project Management Intelligence
*IAAC Research Studio · midterm prototype · November 2026*

**From a BIM design change to its construction-schedule consequence.**

PMI compares two versions of an IFC model, detects which building elements changed and *how* they changed,
maps each change to the construction activity it affects, and recalculates the schedule with the Critical Path
Method (CPM). It then compares mitigation scenarios (cost-efficient, environmentally efficient, accelerated).

> **Research question.** How can design changes detected between successive BIM (IFC) model versions be
> translated automatically and explainably into their consequences for construction scheduling, and where can
> AI support the project manager in that process?

---

## 1. Pipeline

```
models/original.ifc ─┐
                     ├─► 1 detect_changes.py ──► data/changes.json ─┬─► 2 export_geometry.py ─► grasshopper/pmi_geometry.json ─► Rhino / Grasshopper (3D highlight)
models/revised.ifc ──┘   (GlobalId, 5 channels)                     │
                                                                    └─► 3 schedule_engine.py ─► revised schedule + scenarios ─► app.py (Streamlit)
                                                                          (mapping + CPM)        4 validate.py  ─► test results
                                                                                                 5 make_evidence.py ─► evidence/*.png
```

| Step | File | Method | AI? |
|---|---|---|---|
| 0 | `scripts/create_v2.py` | Writes V2 from V1 with 3 documented revisions (ground truth) | No |
| 1 | `scripts/detect_changes.py` | Matches elements by IFC **GlobalId**, compares 5 channels: attribute, property, material, type, geometry | No — deterministic |
| 2 | `scripts/export_geometry.py` | IfcOpenShell triangulates every element → plain meshes for Rhino (avoids IFC import / missing-mesh problems) | No |
| 3 | `scripts/schedule_engine.py` | Rule table IFC type → activity; assumed impact per change; CPM forward/backward pass; scenarios | No — rule-based + CPM |
| 4 | `scripts/validate.py` | Detection vs ground truth; schedule vs hand calculation | No |
| 5 | `scripts/make_evidence.py` | Gantt, scenario, change-table and 3D images for the slides | No |
| 6 | `scripts/riba_risk.py` | Whole-project programme by RIBA stage from V1; adds the extra work each V2 change causes per stage (rules in `data/riba_rules.json`); CPM; risk level + score per stage | No — rule-based forecast |
| 7 | `scripts/engineering_report.py` | Structural / MEP / envelope / fire screening of every changed element (old → new values, Q = U·A·ΔT, lintel span ratios, WWR, fire-rating match) with a sign-off table for certified engineers | No — deterministic screening |
| UI | `app.py` | Streamlit: model changes · schedule impact · scenarios · role of AI | No |
| Next | LLM layer (proposed) | Interpret ambiguous changes, suggest affected activities and mitigation text | **Yes — not connected yet** |

PMI is presented as a **hybrid AI-assisted, rule-based scheduling system**. Every number in this prototype comes
from a transparent algorithm; the LLM layer is the next development stage.

## 2. Automatic for any IFC pair

Nothing in the code is specific to one model. Two editable rule files drive everything:

| File | Rule | Example (test model) |
|---|---|---|
| `data/schedule_template.csv` | **Baseline** duration = max(minimum, count in V1 × days per element) | 57 walls × 0.21 = 12 days |
| `data/assumptions.json` → `impact_rules` | **Impact** of a change = sum over its detected channels of the rule for its IFC type (`_default` for others) | window: property 1 d + geometry 2 d = 3 d |
| `data/activity_mapping.csv` | IFC type → construction activity | IfcWindow → A4 |
| `data/riba_rules.json` | Extra Stage 4 / procurement work per channel | geometry → +4 d design re-issue |

IFC2x3 and IFC4 variants (`IfcWallStandardCase`, `IfcDoorStandardCase`…) use the base type. A rename
(attribute-only) never adds work; added and deleted elements have their own rules. The rates are calibrated so
the midterm test model reproduces its documented results; for a real project, replace them with productivity
and cost data — once, not per model.

## 3. The test case (ground truth)

`create_v2.py` makes three revisions to the Revit sample model (IFC2x3, 157 building elements):

| Element | GlobalId | Change | Channels |
|---|---|---|---|
| External wall | `2O2Fr$t4X7Zf8NOew3FKau` | New insulation spec, U-value 0.18 W/m²K | attribute, property |
| Door A101 | `1hOSvn6df7F8_7GcBWlRGQ` | FireRating → `EI 60` | attribute, property |
| Fixed window | `1hOSvn6df7F8_7GcBWlR72` | 0.6 m wider (4.835 → 5.435 m), opening widened, U-value 1.1 | attribute, property, **geometry** |

`models/revised_names_only.ifc` is the earlier V2 that only renamed the elements; PMI correctly reports it as
*attribute-only* (no geometry change) — a rename is not treated as a design modification.

## 4. Results (illustrative assumptions)

| Scenario | Duration | Delay | Finish |
|---|---|---|---|
| Baseline (V1) | 70 working days | – | 9 Apr 2027 |
| Revised, no mitigation | 79 | +9 | 22 Apr 2027 |
| Cost-efficient (overlap finishes) | 76 | +6 | 19 Apr 2027 |
| Environmentally efficient (prefab panels) | 77 | +7 | 20 Apr 2027 |
| Alternative (2nd crew + overlap) | 73 | +3 | 14 Apr 2027 |

Validation: all detection checks and all 5 schedule test cases (A wall, B door, C window, all three, D float)
match the ground truth / hand calculation — see `data/detection_validation.csv` and `data/validation_results.csv`.

**The extra days, costs and emissions per change are documented assumptions** (`data/assumptions.json`), not
AI predictions and not measured data. What PMI calculates is how they propagate through the dependency network
(e.g. +5 days on MEP rough-in causes no delay because it has 10 days of float).

### RIBA stage risk (forecast)

`riba_risk.py` places the construction schedule inside a RIBA Plan of Work programme (Stages 0–6, quantities from
Model V1) and assumes V2 is issued at the end of Stage 4. Each change adds work where it really lands:
a Stage 4 design change package (by change channel), longer Stage 5 procurement lead times for doors/windows, and
the Stage 5 construction days above.

| Stage | Risk | Score | Role | Slip |
|---|---|---|---|---|
| 4 Technical Design | HIGH | 66 | origin | +10 d |
| 5 Manufacturing and Construction | HIGH | 100 | origin | +23 d |
| 6 Handover | HIGH | 85 | knock-on | +23 d |
| 0–3 | NONE | 0 | – | 0 |

**Issue-timing option (handover at risk).** The same changes are also run as if V2 arrived *late*, after the
walls are built: built work is reworked (× 2) and ordered doors/windows are re-ordered (full lead time again).
Contract handover = V1 handover + 25 working days.

| V2 issued | Handover | Verdict |
|---|---|---|
| End of Stage 4 | 26 May 2027 (+23 d) | TIGHT — 23 of 25 buffer days |
| Late, after wall construction | 23 Jul 2027 (+65 d) | **HANDOVER AT RISK** — misses contract by 40 d |

Key finding: procurement (float 12 d in V1) becomes critical, so the whole-project delay is **+23 working days**
versus +9 in the construction-only view. The names-only V2 gives NONE for every stage. Outputs:
`evidence/riba_gantt_v1.png`, `evidence/riba_gantt_v2.png`, `data/riba_risk.csv`, `docs/riba_risk_report.md`.

### Engineering verification report

`docs/engineering_report.md` (+ `data/engineering_checks.csv`, download button in the app) lists, per changed
element, the V1 → V2 values and screening checks: window — heat loss 608 → 289 W (B102 Living Room), WWR,
lintel span ×1.12 → moment +26 %, deflection +60 %; door — EI 60 vs host-wall rating (not in model); wall —
heat loss 269 → 138 W. Previous U-values missing in V1 are flagged ASSUMED. **Screening only — every check
must be verified and signed by the responsible certified engineer.** Parameters: `data/engineering_rules.json`.

### Demo model V3 (structural revision)

`scripts/create_v3.py` → `models/revised_v3.ifc`: V2 + Level 2 timber floors → 400 mm concrete slabs, 7 strip
footings 900 × 300 → 1200 × 450 mm. V2 → V3: 9 elements detected; construction +24 days; handover misses the
contract date by 11 working days (Stage 4 issue) / 15 (late issue); 25 structural screening checks.
Run it with the app's *Demo: V2 -> V3* button or `python run_pipeline.py --demo-v3`; `--restore` goes back.

## 5. How to run

Requirements: Python ≥ 3.10 with the packages in `requirements.txt`. The existing environment
`C:\Users\Chloe\PMI\PMI\.venv` already has them.

```powershell
cd C:\Users\Chloe\PMI\PMI_MIDTERM_FINAL
..\PMI\.venv\Scripts\Activate.ps1          # or: python -m venv .venv ; .venv\Scripts\Activate.ps1 ; python -m pip install -r requirements.txt
python scripts\create_v2.py                # only if you want to rebuild models\revised.ifc
python run_pipeline.py                     # steps 1-6
python -m streamlit run app.py             # opens http://localhost:8501

# your own two models (same project, two versions):
python run_pipeline.py --v1 "C:\path\old.ifc" --v2 "C:\path\new.ifc"
python run_pipeline.py --restore           # back to the midterm test pair (backed up in models\test_case)
```

Or in the app: sidebar → *Import IFC models (V1 + V2)* → *Run PMI on these models*.

In VS Code: *Ctrl+Shift+P → Python: Select Interpreter →* `PMI\.venv\Scripts\python.exe`, then open
`run_pipeline.py` and press ▶, then `launch_app.py` and press ▶.

### Rhino 8 / Grasshopper
* **Alternative to VS Code for steps 1–2:** Rhino command line →
  `_-RunPythonScript "C:\Users\Chloe\PMI\PMI_MIDTERM_FINAL\grasshopper\pmi_rhino_run_detection.py"`
  (Rhino installs IfcOpenShell itself via the `# r: ifcopenshell` line).
* **Live highlight in Grasshopper:** add a *Python 3 Script* component, paste
  `grasshopper/pmi_gh_highlight.py`, connect a Boolean Toggle to `y` (True = highlight, False = original grey
  view) and a Panel to `out`. Output `a` previews the coloured meshes.
* **Bake for screenshots:** `_-RunPythonScript ".../grasshopper/pmi_rhino_bake.py"` creates layers
  `PMI::Unchanged` (grey), `PMI::Changed_Wall` (red), `PMI::Changed_Door` (orange), `PMI::Changed_Window` (blue)
  and text dots; each mesh carries its GlobalId as the object name.

## 6. Folder

```
app.py  launch_app.py  run_pipeline.py  requirements.txt
models/       original.ifc  revised.ifc  revised_names_only.ifc
scripts/      create_v2.py  detect_changes.py  export_geometry.py  schedule_engine.py  validate.py  make_evidence.py
data/         baseline_schedule.csv  activity_mapping.csv  assumptions.json  revision_log.csv
              changes.json/.csv  revised_schedule.csv  scenario_comparison.csv  validation_results.csv  detection_validation.csv
grasshopper/  pmi_gh_highlight.py  pmi_rhino_bake.py  pmi_rhino_run_detection.py  pmi_geometry.json
evidence/     gantt_before.png  gantt_after.png  scenario_comparison.png  change_table.png  model_3d_*.png  (+ Rhino screenshots)
docs/         PMI_MIDTERM_GUIDE.md  pipeline_log.txt
```

## 7. Limitations and next steps

* One sample building, three controlled changes, a 7-activity schedule — a proof of the workflow, not a
  validated estimator.
* Rates and impact rules are generic assumptions calibrated on one model; activity mapping is by IFC type only.
* Geometry change is detected as *changed / not changed* (hash with 0.1 mm tolerance), not yet measured
  (e.g. "+0.6 m width"); the host wall's widened opening is reported through the window.
* Scenario operations (overlap, extra crew, prefabrication) are parametric what-ifs, not optimised.
* **Next:** connect an LLM to interpret change descriptions and propose activity links / mitigations, always
  checked by the CPM engine; link to a real project schedule (MS Project / P6 export); test on real model
  revisions; quantify geometry deltas; validate impact assumptions with a contractor.
