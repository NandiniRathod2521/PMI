
from pathlib import Path
import ifcopenshell

ROOT = Path(__file__).resolve().parents[1]

v1 = ifcopenshell.open(str(ROOT / "data/raw/model_v1.ifc"))
v2 = ifcopenshell.open(str(ROOT / "data/raw/model_v2.ifc"))

original = {
    e.GlobalId: e
    for e in v1.by_type("IfcBuildingElement")
}

modified = []

for element in v2.by_type("IfcBuildingElement"):
    previous = original.get(element.GlobalId)

    if previous is None:
        continue

    if (
        previous.Name != element.Name
        or previous.Description != element.Description
    ):
        modified.append(element)

print("Modified elements:", len(modified))

for element in modified:
    print(
        element.is_a(),
        element.GlobalId,
        element.Name
    )

