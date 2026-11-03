"""
PMI - RUN THE WHOLE PIPELINE IN ONE CLICK
=========================================
VS Code: open this file and press Run (triangle, top right).   Terminal:

    python run_pipeline.py                                   # the models already in models/
    python run_pipeline.py --v1 "C:\\path\\old.ifc" --v2 "C:\\path\\new.ifc"   # import two other IFC files
    python run_pipeline.py --restore                         # back to the midterm test models
    python run_pipeline.py --demo-v3                         # demo: V2 -> V3 structural revision

Importing copies the two files to models/original.ifc and models/revised.ifc (the
midterm test pair is backed up once to models/test_case/ first).  Validation (step 4)
only makes sense for the test pair, so it is skipped automatically for imported models.

Steps
  0. installs missing packages into the current Python environment
  1. scripts/detect_changes.py   IFC V1 vs V2           -> data/changes.json
  2. scripts/export_geometry.py  IFC meshes for Rhino   -> grasshopper/pmi_geometry.json
  3. scripts/schedule_engine.py  CPM + scenarios        -> data/revised_schedule.csv
  4. scripts/validate.py         test cases vs ground truth / hand calculation
  5. scripts/make_evidence.py    PNG charts for slides  -> evidence/
  6. scripts/riba_risk.py        RIBA programme V1/V2, stage risk, handover check (Stage 4 issue + late issue)
  7. scripts/engineering_report.py  structural / MEP / envelope / fire screening for engineers -> docs/engineering_report.md
"""

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODELS = ROOT / "models"
TEST_CASE = MODELS / "test_case"
LOG = ROOT / "docs" / "pipeline_log.txt"
STATE = ROOT / "data" / "models_in_use.json"

STEPS = ["detect_changes.py", "export_geometry.py", "schedule_engine.py", "validate.py", "make_evidence.py",
         "riba_risk.py", "engineering_report.py"]


def ensure(packages):
    missing = [p for p in packages if importlib.util.find_spec(p) is None]
    if missing:
        print("Installing:", ", ".join(missing))
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])


def backup_test_case():
    """Keep the midterm test pair safe before anything overwrites it."""
    if not TEST_CASE.is_dir():
        TEST_CASE.mkdir(parents=True)
        for name in ("original.ifc", "revised.ifc"):
            if (MODELS / name).is_file():
                shutil.copy2(MODELS / name, TEST_CASE / name)
        print(f"Test models backed up to {TEST_CASE}")


def import_models(v1: Path, v2: Path, label: str):
    for p in (v1, v2):
        if not p.is_file():
            sys.exit(f"File not found: {p}")
        if p.suffix.lower() != ".ifc":
            sys.exit(f"Not an .ifc file: {p}")
    backup_test_case()
    # copy via temporary names so a source inside models/ is never overwritten half-way
    tmp1, tmp2 = MODELS / "_v1.tmp", MODELS / "_v2.tmp"
    shutil.copy2(v1, tmp1)
    shutil.copy2(v2, tmp2)
    tmp1.replace(MODELS / "original.ifc")
    tmp2.replace(MODELS / "revised.ifc")
    STATE.write_text(json.dumps({"v1": v1.name, "v2": v2.name, "label": label}, indent=2), encoding="utf-8")
    print(f"Imported  V1 = {v1}\n          V2 = {v2}")


def is_test_case() -> bool:
    if not STATE.is_file():
        return True
    return json.loads(STATE.read_text(encoding="utf-8")).get("label") == "test case"


def main():
    ap = argparse.ArgumentParser(description="Run the PMI pipeline")
    ap.add_argument("--v1", type=Path, help="original IFC model to import")
    ap.add_argument("--v2", type=Path, help="revised IFC model to import")
    ap.add_argument("--restore", action="store_true", help="go back to the midterm test models")
    ap.add_argument("--demo-v3", action="store_true",
                    help="demo: compare V2 -> V3 (structural revision made by scripts/create_v3.py)")
    ap.add_argument("--no-validate", action="store_true", help="skip step 4")
    args = ap.parse_args()

    print("Python:", sys.executable)
    ensure(["ifcopenshell", "pandas", "numpy", "matplotlib", "plotly", "streamlit"])

    if args.demo_v3:
        v3 = MODELS / "revised_v3.ifc"
        if not v3.is_file():
            subprocess.check_call([sys.executable, str(ROOT / "scripts" / "create_v3.py")], cwd=ROOT)
        backup_test_case()
        import_models(TEST_CASE / "revised.ifc", v3, "demo V2 -> V3 (structural revision)")
    elif args.restore:
        if not TEST_CASE.is_dir():
            sys.exit("No backup in models/test_case/ - the test models were never replaced.")
        import_models(TEST_CASE / "original.ifc", TEST_CASE / "revised.ifc", "test case")
    elif args.v1 or args.v2:
        if not (args.v1 and args.v2):
            sys.exit("Give both --v1 and --v2")
        import_models(args.v1.resolve(), args.v2.resolve(), "imported")

    steps = list(STEPS)
    if args.no_validate or not is_test_case():
        steps.remove("validate.py")
        print("Validation skipped (it checks the midterm test case only).")

    LOG.parent.mkdir(exist_ok=True)
    log, failed = [], []
    for step in steps:
        print(f"\n===== {step} =====", flush=True)
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / step)], cwd=ROOT,
                           capture_output=True, text=True)
        print(r.stdout)
        if r.returncode != 0:
            print(r.stderr)
            failed.append(step)
        log.append(f"===== {step} (exit {r.returncode}) =====\n{r.stdout}\n{r.stderr}")
    LOG.write_text("\n".join(log), encoding="utf-8")
    print(f"\nDone. Full log: {LOG}")
    if failed:
        print("FAILED:", ", ".join(failed))
        sys.exit(1)
    print("Next: run launch_app.py to open the Streamlit interface (or refresh it if it is open).")


if __name__ == "__main__":
    main()
