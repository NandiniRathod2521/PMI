# PMI midterm — step-by-step guide

Everything below is already built. Your job tonight and tomorrow is to **run it on your laptop, capture the
real screenshots and rehearse**. Steps are in order. Rough times in brackets.

---

## Part A — Run the prototype (VS Code) [30 min]

1. **Open the folder.** VS Code → *File → Open Folder* → `C:\Users\Chloe\PMI\PMI_MIDTERM_FINAL`.
2. **Pick the Python that has IfcOpenShell.** `Ctrl+Shift+P` → *Python: Select Interpreter* →
   *Enter interpreter path* → `C:\Users\Chloe\PMI\PMI\.venv\Scripts\python.exe`
   (it already has ifcopenshell 0.9, streamlit, plotly, pandas).
3. **Rebuild the revised model** (optional — `models\revised.ifc` is already the new one).
   Open `scripts\create_v2.py` → ▶ Run. Expected output: 3 lines (wall, door, window) and `5 new entities`.
4. **Run the whole pipeline.** Open `run_pipeline.py` → ▶ Run. It runs five scripts; check in the terminal:
   * `detect_changes.py` → `MODIFIED 3   UNCHANGED 154`, and for each element a *what changed* line, e.g.
     `FireRating: 'Fire Rating' -> 'EI 60'`. The window must list `geometry`.
   * `export_geometry.py` → `Exported 154 element meshes (3 changed)`.
   * `schedule_engine.py` → baseline 70 days, revised 79 days.
   * `validate.py` → every row `PASS` (two tables: detection + schedule).
   * `make_evidence.py` → PNGs in `evidence\`.
   * `riba_risk.py` → Stages 4, 5, 6 = HIGH; handover TIGHT (+23 d) for a Stage 4 issue and HANDOVER AT RISK
     (+65 d, 40 d past contract) for a late issue; `evidence\riba_gantt_v2.png` and `riba_gantt_v2_late.png`.
   * `engineering_report.py` → 5 checks (MEP ×2, envelope, structural, fire) → `docs\engineering_report.md`.
   If anything says FAIL or an error appears, the full log is `docs\pipeline_log.txt` — send it to me.
5. **Open the app.** Open `launch_app.py` → ▶ Run (or in the terminal `python -m streamlit run app.py`).
   The browser opens at `http://localhost:8501`.
6. **Check the app** (this is the plan's Step 5 checklist):
   * Section 1 shows 3 modified elements, *Geometry changed = 1*, and the 3D view with red / orange / blue.
   * Section 2: +9 days, finish 22 Apr 2027. (Controlled cases A, B, C — one change at a time — are in the validation output.)
   * Section 3: click each of the three scenarios — the metrics and the second Gantt chart change.
   * Change *Preferred completion date* in the sidebar → the "Meets …" column updates.
   * Stop the app with `Ctrl+C` in the terminal, start it again from a fresh terminal → still works.

### Using your own two IFC files
* **In the app:** sidebar → *Models* → *Import IFC models (V1 + V2)* → choose the two files → **Run PMI on these
  models**. It runs the whole pipeline (about a minute) and the page reloads with the new results.
  **Restore the midterm test models** brings the test pair back.
* **In VS Code terminal:** `python run_pipeline.py --v1 "C:\path\old.ifc" --v2 "C:\path\new.ifc"` and
  `python run_pipeline.py --restore`.
* The first import backs the test pair up to `models\test_case\`. Validation is skipped for imported models
  (it only knows the test case's right answers). Both files must be versions of the same model, so the
  GlobalIds match. Changes the rule tables don't know get generic default impacts, labelled as such.
* After importing, re-run the Grasshopper component / bake script to see the new model in Rhino.

### Demo: Model V3, a structural revision that puts the timeline at risk
`scripts\create_v3.py` makes `models\revised_v3.ifc` from V2: the two Level 2 timber floors (305 mm) become
400 mm concrete slabs and all 7 strip footings go from 900 × 300 to 1200 × 450 mm (geometry + property changes).
In the app: sidebar → *Import IFC models* → **Demo: V2 -> V3 structural revision** (about a minute). Expected:
* Section 1: 9 modified elements (2 IfcSlab, 7 IfcFooting), all with geometry.
* Section 2/3: construction 70 → 94 days (+24) — foundations and structure are on the critical path.
* Section 4: RIBA Stages 4, 5, 6 HIGH; **HANDOVER AT RISK** — misses the contract date by 11 working days even
  when issued at the end of Stage 4 (15 days if issued late).
* Section 5: 25 structural checks, e.g. each concrete floor adds ≈ +500 kN dead load; footings ×1.33 bearing width.
Then **Restore the midterm test models** to go back. Terminal alternative: `python run_pipeline.py --demo-v3`.

## Part B — 3D highlight in Rhino / Grasshopper [45 min]

**Why JSON, not IFC?** Rhino's IFC import was what gave missing meshes before. Now IfcOpenShell (in Python)
triangulates every element and writes `grasshopper\pmi_geometry.json`, tagged with each element's change status.
Rhino only reads that JSON. So step 4 in Part A must have run first (it re-exports the widened window).

### Option 1 — Grasshopper (live toggle, best for the demo)
1. Rhino 8 → `Grasshopper`.
2. Double-click the canvas → type **Python 3 Script** → place it.
3. Double-click the component → delete the template → paste all of `grasshopper\pmi_gh_highlight.py` → OK.
4. Add a **Boolean Toggle** → connect to input `y`. Add a **Panel** → connect to output `out`.
5. Toggle **True**: wall red, door orange, window blue, everything else grey. Toggle **False**: all grey
   (= "original model" view). The Panel lists the three changed elements with GlobalIds.
6. Leave input `x` empty (it uses the default path). If you move the folder, connect a Panel with the new path
   to the JSON.

### Option 2 — Bake into Rhino layers (best for clean screenshots)
1. Rhino command line: `_-RunPythonScript "C:\Users\Chloe\PMI\PMI_MIDTERM_FINAL\grasshopper\pmi_rhino_bake.py"`
2. Layers `PMI::Unchanged / Changed_Wall / Changed_Door / Changed_Window / Labels` appear.
   Click an element → *Properties → Name* shows its IFC GlobalId; *Attribute User Text* shows type and status.
3. For the "original" screenshot set `HIGHLIGHT = False` at the top of the script and run it again.

### Screenshots to save in `evidence\` (plan Step 8)
| File | What |
|---|---|
| `original_model.png` | Rhino, all grey, Shaded or Arctic view, perspective |
| `changed_elements.png` | Rhino, highlight on, labels visible |
| `app_changes.png` | Streamlit section 1 (table + 3D) |
| `app_gantt.png` | Streamlit section 2 Gantt |
| `app_scenarios.png` | Streamlit section 3 with a scenario selected |

Tips: maximise the window, hide the Rhino command history, `Ctrl+Shift+click` nothing selected, use
`_ViewCaptureToFile` with width 2400 for Rhino. Also record a 60–90 s screen video (Win+G → record) of:
run app → scroll sections 1–4 → switch scenarios → import/restore models in the sidebar. It is your backup if the live demo fails.

If Grasshopper misbehaves for more than 30 minutes: use `evidence\model_3d_changes.png` (made by the pipeline
from the same meshes) and move on.

---

## What each part does (in your own words for the review)

**`create_v2.py` — the test case.** Makes Model V2 from V1 with three changes I know in advance (the ground
truth): wall gets a new insulation U-value, door becomes fire-rated EI 60, window gets 0.6 m wider with better
glazing. It edits the IFC text directly so the GlobalIds stay the same, and writes the expected changes to
`data\revision_log.csv`.

**`detect_changes.py` — what changed.** Matches every element between V1 and V2 by its GlobalId (a permanent
ID that survives re-export), then checks five separate channels: attributes (name/description), properties
(Psets), materials, type, and geometry (a fingerprint of placement + shape, 0.1 mm tolerance). Output: which
elements changed, through which channel, and a readable line of what changed. A renamed element is only an
*attribute* change — never counted as a geometric modification.

**Automatic for any model (no editing per IFC).** The baseline schedule is generated from Model V1: each
activity's duration = number of elements of its IFC types in V1 × a rate (e.g. 57 walls × 0.21 = 12 days;
`data\schedule_template.csv`). Each change's extra days = the rule for its IFC type and each detected channel
(e.g. window property 1 + geometry 2 = 3 days; `data\assumptions.json`). Unknown types use a generic `_default`
rule. So next week, import the other IFC pair and run — only change the rates if you want different
productivity assumptions.

**`export_geometry.py` — meshes for Rhino.** IfcOpenShell turns each element into a triangle mesh in world
coordinates and saves them with their change status. Grasshopper only reads that file.

**`schedule_engine.py` — the consequence.** (1) Builds the baseline from V1 quantities. (2) Rule table maps the IFC type to an activity: wall → Wall
construction, door/window → Door and window installation. (3) Applies the rule for that type and change channel
(e.g. window +3 days). (3) Adds the days. (4) Recalculates the whole network with CPM: forward pass
(earliest start/finish), backward pass (latest), float = latest − earliest, critical path = float 0.
(5) Gives the new finish date. (6) Applies mitigation scenarios as operations on the network: overlap two
activities (negative lag) or shorten the added delay (extra crew, prefabrication), and compares duration,
cost and CO₂.

**`riba_risk.py` — which RIBA stage is at risk?** Puts the schedule into a whole-project programme by RIBA
stage (Stage 0 Strategic Definition → Stage 6 Handover; bar labels count the walls, doors, windows… in V1). It
assumes V2 arrives at the end of Stage 4, then adds extra work where each change really lands: a new Stage 4
"design change package" (0 days for a rename, 2 for a property change, 4 for a geometry change), longer Stage 5
lead times for doors and windows (spec change +5, size change +10), and the construction days. CPM recalculates
everything; a stage is HIGH when it finishes later *and* sits on the critical path. Result: Stage 4 and 5 are
HIGH as the origin, Stage 6 HIGH as knock-on, +23 days — because window procurement, which had 12 days of float,
becomes critical. That is something the construction-only view (+9 days) cannot see. Call it a **rule-based
forecast**, not machine learning; the rules are in `data\riba_rules.json`.

**Late issue — the option that puts handover at risk.** In the app's RIBA section choose *V2 issued late,
after wall construction*. Work already done when V2 arrives can't just "take longer": the built walls are reworked
(4 days × 2 for opening up and rebuilding) and the doors/windows already ordered are re-ordered (30 + 20 = 50
days lead time). Handover moves +65 days and misses the contract date (V1 + 25 days buffer) by 40 days. The
message: the same design change costs ~3× more programme if it is issued late.

**`engineering_report.py` — for certified engineers.** For every changed element it lists V1 → V2 values and
runs screening checks: heat loss Q = U × A × ΔT for the room the element bounds (MEP), window-to-wall ratio
(facade/energy), lintel span ratios — a 12 % wider opening means +26 % bending moment and +60 % deflection for
the same load (structural), and the door's new EI 60 rating against the host wall (fire). Anything missing in the
model is flagged ASSUMED/MISSING; the report ends with a sign-off table. Say clearly: *screening, not design* —
PMI tells the engineers exactly what to check, they verify and sign.

**`validate.py` — is it right?** Checks detection against the ground truth (expected channels = detected
channels, and zero false positives among the other 154 elements) and the CPM result against a hand
calculation for scenarios A (wall), B (door), C (window), all three, and D (a delay on a non-critical
activity that float absorbs → 0 days delay).

**`app.py` — the interface.** Four sections, top to bottom: model changes, schedule impact, scenario
comparison, role of AI. No tabs (they were the cause of the invisible sections before).

---

## Questions you will get — short answers

**Q1. How is PMI different from BIM?** BIM is the model and the process of producing it. PMI takes *two
versions* of the BIM model as input and works out the downstream consequence of the difference for the
construction schedule and the project decision.

**Q2. Why do you need AI?** For the parts that are deterministic — detecting IFC differences, recalculating
the schedule — we don't, and we don't pretend to. AI is needed where the input is ambiguous: a change
described as "revised for fire safety" has to be interpreted (which activities, procurement or rework?) and
turned into mitigation options with explanations. That is the LLM layer I will test next; its suggestions are
always checked by the CPM engine.

**Q3. Are you using deep learning?** Not in this prototype. The comparison and scheduling are conventional
algorithms. The planned AI layer uses a pretrained LLM (a transformer); I am not training a neural network.

**Q4. How does PMI know a changed wall causes a delay?** It doesn't predict it. The wall is mapped to its
activity by a rule; a documented assumption (+4 days) is the input; the engine *calculates* how that
propagates. Proof that the propagation matters: +5 days on MEP rough-in gives 0 days delay because of float.

**Q5. How do you know the results are accurate?** Detection: compared with a ground truth I created
(3/3 elements, correct channels, 0 false positives; and the names-only V2 is correctly reported as
attribute-only). Schedule: compared with hand calculations for 5 cases, all match. Real-project validation is
future work.

**Q6. What is your contribution?** An explainable, end-to-end workflow that connects a BIM design change to its
schedule impact and to alternative responses — and a clear separation between what algorithms calculate, what
is an assumption, and where AI adds value.

**Q6b. You say "prediction" — is that AI?** It is a rule-based forecast: documented rules for how much extra work
each kind of change causes per RIBA stage, plus CPM. It is explainable line by line. The LLM layer would propose
those rules for changes the table doesn't cover; the engine still does the calculation.

**Q6c. Can engineers trust the calculations?** They are not meant to be trusted blindly: they are standard
first-order formulas with every input shown, so an engineer can verify each line in minutes. PMI's value is
finding *which* elements need checking and *why*, straight from the model difference.

**Q7. Why not just use ALICE / Buildots / Synchro?** They optimise or track a schedule; they don't start from
the IFC difference between two design versions and explain which change causes which delay. (Check the
state-of-the-art slide wording against your literature review before presenting.)

---

## Tomorrow — order of work
1. 09:00 Run Part A once more from a fresh terminal. Capture the app screenshots.
2. 09:30 Part B screenshots in Rhino. Record the backup video.
3. 10:30 Replace the placeholder images in the slides with your screenshots; check every number on the slides
   against `data\scenario_comparison.csv` and `data\validation_results.csv`.
4. 13:00 Rehearse the 5-minute demo twice (app sections 1→2→3, then Rhino toggle).
5. 16:00 Export slides to PDF → `presentation\PMI_Midterm.pdf`. Push to GitHub (see README). Submit early.
