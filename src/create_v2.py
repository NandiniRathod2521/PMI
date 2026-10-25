
from pathlib import Path
import csv
import ifcopenshell

PROJECT_ROOT = Path(__file__).resolve().parents[1]

V1_PATH = PROJECT_ROOT / "data" / "raw" / "model_v1.ifc"
V2_PATH = PROJECT_ROOT / "data" / "raw" / "model_v2.ifc"
LOG_PATH = PROJECT_ROOT / "data" / "processed" / "revision_log.csv"

def main():
    if not V1_PATH.is_file():
        raise FileNotFoundError(V1_PATH)

    model = ifcopenshell.open(str(V1_PATH))

    walls = model.by_type("IfcWall")
    doors = model.by_type("IfcDoor")
    windows = model.by_type("IfcWindow")

    revisions = []

    def revise(element, new_name, new_description):
        revisions.append({
            "global_id": element.GlobalId,
            "ifc_type": element.is_a(),
            "old_name": element.Name or "",
            "new_name": new_name,
            "old_description": element.Description or "",
            "new_description": new_description
        })

        element.Name = new_name
        element.Description = new_description

    # Revision 1: Wall
    if walls:
        revise(
            walls[0],
            "PMI_External_Wall_Revised",
            "External wall revised with new insulation specification"
        )

    # Revision 2: Door
    if doors:
        revise(
            doors[0],
            "PMI_Fire_Rated_Door",
            "Door specification revised for fire safety"
        )

    # Revision 3: Window
    if windows:
        revise(
            windows[0],
            "PMI_Window_Revised",
            "Window specification revised for improved glazing"
        )

    V2_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    model.write(str(V2_PATH))

    with LOG_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "global_id",
                "ifc_type",
                "old_name",
                "new_name",
                "old_description",
                "new_description"
            ]
        )
        writer.writeheader()
        writer.writerows(revisions)

    print("Model V2 created:", V2_PATH)
    print("Revisions recorded:", len(revisions))

    for revision in revisions:
        print(
            revision["ifc_type"],
            revision["global_id"],
            revision["new_name"]
        )

if __name__ == "__main__":
    main()
