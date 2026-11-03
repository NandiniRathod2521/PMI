#! python3
# r: ifcopenshell
"""
PMI - run IFC change detection + geometry export from INSIDE Rhino 8
(alternative to running run_pipeline.py in VS Code; Rhino installs ifcopenshell itself
 thanks to the '# r: ifcopenshell' line above).

Rhino command line:
    _-RunPythonScript "C:\\Users\\Chloe\\PMI\\PMI_MIDTERM_FINAL\\grasshopper\\pmi_rhino_run_detection.py"
"""
import sys

SCRIPTS = r"C:\Users\Chloe\PMI\PMI_MIDTERM_FINAL\scripts"
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import detect_changes  # noqa: E402
import export_geometry  # noqa: E402

detect_changes.main()
export_geometry.main()
print("PMI: detection + geometry export finished")
