
from pathlib import Path
import csv
import ifcopenshell

# 1. Define project paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]

V1_PATH = PROJECT_ROOT / "data" / "raw" / "model_v1.ifc"
V2_PATH = PROJECT_ROOT / "data" / "raw" / "model_v2.ifc"

OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "changes.csv"


# 2. Extract IFC building elements by GlobalId
def get_elements(model):
    return {
        element.GlobalId: element
        for element in model.by_type("IfcBuildingElement")
        if element.GlobalId
    }


# 3. Compare the two IFC models
def main():

    if not V1_PATH.exists():
        raise FileNotFoundError(f"Missing V1: {V1_PATH}")

    if not V2_PATH.exists():
        raise FileNotFoundError(f"Missing V2: {V2_PATH}")

    model_v1 = ifcopenshell.open(str(V1_PATH))
    model_v2 = ifcopenshell.open(str(V2_PATH))

    elements_v1 = get_elements(model_v1)
    elements_v2 = get_elements(model_v2)

    changes = []

    all_ids = sorted(set(elements_v1) | set(elements_v2))

    for global_id in all_ids:

        old = elements_v1.get(global_id)
        new = elements_v2.get(global_id)

        if old is None:
            status = "ADDED"

        elif new is None:
            status = "DELETED"

        elif (
            old.Name != new.Name
            or old.Description != new.Description
        ):
            status = "MODIFIED"

        else:
            status = "UNCHANGED"

        element = new if new is not None else old

        changes.append({
            "global_id": global_id,
            "ifc_type": element.is_a(),
            "name": element.Name or "",
            "status": status,
            "old_name": (old.Name or "") if old is not None else "",
            "new_name": (new.Name or "") if new is not None else "",
            "old_description": (
                old.Description or ""
            ) if old is not None else "",
            "new_description": (
                new.Description or ""
            ) if new is not None else ""
        })

    # 4. Export CSV
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "global_id",
                "ifc_type",
                "name",
                "status",
                "old_name",
                "new_name",
                "old_description",
                "new_description"
            ]
        )

        writer.writeheader()
        writer.writerows(changes)

    # 5. Print summary
    print("\nPMI - BIM CHANGE DETECTION")
    print("-------------------------")

    for status in ["ADDED", "DELETED", "MODIFIED", "UNCHANGED"]:
        count = sum(
            row["status"] == status
            for row in changes
        )
        print(f"{status}: {count}")

    print(f"\nCSV saved to: {OUTPUT_PATH}")

    print("\nModified elements:")

    for row in changes:
        if row["status"] == "MODIFIED":
            print(
                row["ifc_type"],
                row["global_id"],
                row["name"]
            )


if __name__ == "__main__":
    main()
