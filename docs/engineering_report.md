# PMI - Engineering verification report

**Models:** V1 `original.ifc` -> V2 `revised.ifc`  |  **Generated:** 03 Nov 2026 by PMI (scripts/engineering_report.py)  |  **Design dT:** 20 K (assumed)

> **Screening only - not a design calculation.** PMI lists what changed between the two model versions and runs simple, transparent checks so that the responsible **certified engineers** can verify them. Values that are not in the model are flagged *ASSUMED* or *MISSING*. Nothing here may be used for construction until it is checked and signed below.

## 1. Summary

| Check | Discipline | Element | Check | Result | Status |
|---|---|---|---|---|---|
| C01 | Structural engineer | PMI_V3_Footing_Widened_5 (IfcFooting) | Self-weight / extra dead load on supports and foundations | 28 kN -> 57 kN (dG = +28 kN) to be carried by the supporting walls / beams and the foundations | **REVIEW REQUIRED** |
| C02 | Structural engineer | PMI_V3_Footing_Widened_5 (IfcFooting) | Foundation bearing width (ground pressure) | bearing width x1.33; ground pressure x0.75 for the same load - but the load itself increases (heavier floors): geotechnical / structural check of bearing capacity and settlement | **REVIEW REQUIRED** |
| C03 | Structural engineer | PMI_V3_Footing_Widened_5 (IfcFooting) | Load path / member check | structural engineer to confirm the member and the load path | **REVIEW REQUIRED** |
| C04 | Structural engineer | PMI_V3_Footing_Widened_6 (IfcFooting) | Self-weight / extra dead load on supports and foundations | 15 kN -> 30 kN (dG = +15 kN) to be carried by the supporting walls / beams and the foundations | **REVIEW REQUIRED** |
| C05 | Structural engineer | PMI_V3_Footing_Widened_6 (IfcFooting) | Foundation bearing width (ground pressure) | bearing width x1.33; ground pressure x0.75 for the same load - but the load itself increases (heavier floors): geotechnical / structural check of bearing capacity and settlement | **REVIEW REQUIRED** |
| C06 | Structural engineer | PMI_V3_Footing_Widened_6 (IfcFooting) | Load path / member check | structural engineer to confirm the member and the load path | **REVIEW REQUIRED** |
| C07 | Structural engineer | PMI_V3_Footing_Widened_7 (IfcFooting) | Self-weight / extra dead load on supports and foundations | 22 kN -> 44 kN (dG = +22 kN) to be carried by the supporting walls / beams and the foundations | **REVIEW REQUIRED** |
| C08 | Structural engineer | PMI_V3_Footing_Widened_7 (IfcFooting) | Foundation bearing width (ground pressure) | bearing width x1.33; ground pressure x0.75 for the same load - but the load itself increases (heavier floors): geotechnical / structural check of bearing capacity and settlement | **REVIEW REQUIRED** |
| C09 | Structural engineer | PMI_V3_Footing_Widened_7 (IfcFooting) | Load path / member check | structural engineer to confirm the member and the load path | **REVIEW REQUIRED** |
| C10 | Structural engineer | PMI_V3_Footing_Widened_4 (IfcFooting) | Self-weight / extra dead load on supports and foundations | 51 kN -> 101 kN (dG = +51 kN) to be carried by the supporting walls / beams and the foundations | **REVIEW REQUIRED** |
| C11 | Structural engineer | PMI_V3_Footing_Widened_4 (IfcFooting) | Foundation bearing width (ground pressure) | bearing width x1.33; ground pressure x0.75 for the same load - but the load itself increases (heavier floors): geotechnical / structural check of bearing capacity and settlement | **REVIEW REQUIRED** |
| C12 | Structural engineer | PMI_V3_Footing_Widened_4 (IfcFooting) | Load path / member check | structural engineer to confirm the member and the load path | **REVIEW REQUIRED** |
| C13 | Structural engineer | PMI_V3_Footing_Widened_1 (IfcFooting) | Self-weight / extra dead load on supports and foundations | 123 kN -> 247 kN (dG = +123 kN) to be carried by the supporting walls / beams and the foundations | **REVIEW REQUIRED** |
| C14 | Structural engineer | PMI_V3_Footing_Widened_1 (IfcFooting) | Foundation bearing width (ground pressure) | bearing width x1.33; ground pressure x0.75 for the same load - but the load itself increases (heavier floors): geotechnical / structural check of bearing capacity and settlement | **REVIEW REQUIRED** |
| C15 | Structural engineer | PMI_V3_Footing_Widened_1 (IfcFooting) | Load path / member check | structural engineer to confirm the member and the load path | **REVIEW REQUIRED** |
| C16 | Structural engineer | PMI_V3_Footing_Widened_2 (IfcFooting) | Self-weight / extra dead load on supports and foundations | 57 kN -> 113 kN (dG = +57 kN) to be carried by the supporting walls / beams and the foundations | **REVIEW REQUIRED** |
| C17 | Structural engineer | PMI_V3_Footing_Widened_2 (IfcFooting) | Foundation bearing width (ground pressure) | bearing width x1.33; ground pressure x0.75 for the same load - but the load itself increases (heavier floors): geotechnical / structural check of bearing capacity and settlement | **REVIEW REQUIRED** |
| C18 | Structural engineer | PMI_V3_Footing_Widened_2 (IfcFooting) | Load path / member check | structural engineer to confirm the member and the load path | **REVIEW REQUIRED** |
| C19 | Structural engineer | PMI_V3_Footing_Widened_3 (IfcFooting) | Self-weight / extra dead load on supports and foundations | 117 kN -> 235 kN (dG = +117 kN) to be carried by the supporting walls / beams and the foundations | **REVIEW REQUIRED** |
| C20 | Structural engineer | PMI_V3_Footing_Widened_3 (IfcFooting) | Foundation bearing width (ground pressure) | bearing width x1.33; ground pressure x0.75 for the same load - but the load itself increases (heavier floors): geotechnical / structural check of bearing capacity and settlement | **REVIEW REQUIRED** |
| C21 | Structural engineer | PMI_V3_Footing_Widened_3 (IfcFooting) | Load path / member check | structural engineer to confirm the member and the load path | **REVIEW REQUIRED** |
| C22 | MEP / building services engineer | PMI_Window_Revised (IfcWindow) | Fabric heat loss of the element (heating load of the room) | 608 W -> 289 W  (dQ = -319 W) - update the room heat-load calculation and emitter sizing for B102 Living Room | **REVIEW REQUIRED** |
| C23 | Facade / energy consultant | PMI_Window_Revised (IfcWindow) | Window-to-wall ratio of the host wall (solar gain, daylight, overheating) | 86.0% -> 96.6% - very high glazing ratio: check overheating, energy compliance and facade structure | **REVIEW REQUIRED** |
| C24 | Structural engineer | PMI_Window_Revised (IfcWindow) | Lintel / header over the opening (span change) | span x1.124; bending moment x1.26 (+26%); deflection x1.60 (+60%) - lintel to be re-checked / re-sized | **CHECK (non load-bearing host - facade support only)** |
| C25 | Fire safety engineer | PMI_Fire_Rated_Door (IfcDoor) | Fire resistance and compartmentation | new rating EI 60; host wall rating not in model - host wall rating must be confirmed | **REVIEW REQUIRED** |
| C26 | Structural engineer | PMI_V3_Concrete_Floor_1 (IfcSlab) | Self-weight / extra dead load on supports and foundations | 90 kN -> 592 kN (dG = +502 kN) to be carried by the supporting walls / beams and the foundations | **REVIEW REQUIRED** |
| C27 | Structural engineer | PMI_V3_Concrete_Floor_1 (IfcSlab) | Load path / member check | structural engineer to confirm the member and the load path | **REVIEW REQUIRED** |
| C28 | Structural engineer | PMI_V3_Concrete_Floor_2 (IfcSlab) | Self-weight / extra dead load on supports and foundations | 90 kN -> 593 kN (dG = +503 kN) to be carried by the supporting walls / beams and the foundations | **REVIEW REQUIRED** |
| C29 | Structural engineer | PMI_V3_Concrete_Floor_2 (IfcSlab) | Load path / member check | structural engineer to confirm the member and the load path | **REVIEW REQUIRED** |
| C30 | MEP / building services engineer | PMI_External_Wall_Revised (IfcWall) | Fabric heat loss of the element (heating load of the room) | 269 W -> 138 W  (dQ = -131 W) - update the room heat-load calculation and emitter sizing for A202 Bedroom 1, A203 Bedroom 2, B202 Bedroom 1, B203 Bedroom 2 | **REVIEW REQUIRED** |

## 2. Changes and calculations

### PMI_V3_Footing_Widened_5  ·  IfcFooting  ·  `0kF45Qs8L9PAM9kmb1lT2B`

Storey: **T/FDN**  ·  Bounds: -  ·  Host: -  ·  Detected change: Name changed; Description changed; Volume: 1.131705 -> 2.2634; Width: 0.9 -> 1.2; geometry (shape / position) changed

**C01 - Self-weight / extra dead load on supports and foundations**  (Structural engineer)

- Inputs: V 1.132 m3 (concrete (default), 25.0 kN/m3) -> 2.263 m3 (concrete (default), 25.0 kN/m3); storey T/FDN
- Method: `G = V x unit weight`
- Result: 28 kN -> 57 kN (dG = +28 kN) to be carried by the supporting walls / beams and the foundations
- Flags: *unit weights ASSUMED from the element name*
- Status: **REVIEW REQUIRED**

**C02 - Foundation bearing width (ground pressure)**  (Structural engineer)

- Inputs: width 0.9 m -> 1.2 m; length 4.2 m
- Method: `q = N / (B x L) -> for the same load N, q scales with B_old / B_new`
- Result: bearing width x1.33; ground pressure x0.75 for the same load - but the load itself increases (heavier floors): geotechnical / structural check of bearing capacity and settlement
- Flags: *allowable bearing pressure NOT in model*
- Status: **REVIEW REQUIRED**

**C03 - Load path / member check**  (Structural engineer)

- Inputs: modified (attribute, property, geometry); length 4.2 m; area not in model; volume 2.263 m3; load-bearing not in model; storey T/FDN
- Method: `verify supports, loads and connections for the revised member`
- Result: structural engineer to confirm the member and the load path
- Flags: *load-bearing NOT DEFINED*
- Status: **REVIEW REQUIRED**

### PMI_V3_Footing_Widened_6  ·  IfcFooting  ·  `0kF45Qs8L9PAM9kmb1lT2N`

Storey: **T/FDN**  ·  Bounds: -  ·  Host: -  ·  Detected change: Name changed; Description changed; Volume: 0.5940000000000077 -> 1.188; Width: 0.9 -> 1.2; geometry (shape / position) changed

**C04 - Self-weight / extra dead load on supports and foundations**  (Structural engineer)

- Inputs: V 0.594 m3 (concrete (default), 25.0 kN/m3) -> 1.188 m3 (concrete (default), 25.0 kN/m3); storey T/FDN
- Method: `G = V x unit weight`
- Result: 15 kN -> 30 kN (dG = +15 kN) to be carried by the supporting walls / beams and the foundations
- Flags: *unit weights ASSUMED from the element name*
- Status: **REVIEW REQUIRED**

**C05 - Foundation bearing width (ground pressure)**  (Structural engineer)

- Inputs: width 0.9 m -> 1.2 m; length 1.765 m
- Method: `q = N / (B x L) -> for the same load N, q scales with B_old / B_new`
- Result: bearing width x1.33; ground pressure x0.75 for the same load - but the load itself increases (heavier floors): geotechnical / structural check of bearing capacity and settlement
- Flags: *allowable bearing pressure NOT in model*
- Status: **REVIEW REQUIRED**

**C06 - Load path / member check**  (Structural engineer)

- Inputs: modified (attribute, property, geometry); length 1.765 m; area not in model; volume 1.188 m3; load-bearing not in model; storey T/FDN
- Method: `verify supports, loads and connections for the revised member`
- Result: structural engineer to confirm the member and the load path
- Flags: *load-bearing NOT DEFINED*
- Status: **REVIEW REQUIRED**

### PMI_V3_Footing_Widened_7  ·  IfcFooting  ·  `0kF45Qs8L9PAM9kmb1lT2Z`

Storey: **T/FDN**  ·  Bounds: -  ·  Host: -  ·  Detected change: Name changed; Description changed; Volume: 0.8887049999999972 -> 1.7774; Width: 0.9 -> 1.2; geometry (shape / position) changed

**C07 - Self-weight / extra dead load on supports and foundations**  (Structural engineer)

- Inputs: V 0.889 m3 (concrete (default), 25.0 kN/m3) -> 1.777 m3 (concrete (default), 25.0 kN/m3); storey T/FDN
- Method: `G = V x unit weight`
- Result: 22 kN -> 44 kN (dG = +22 kN) to be carried by the supporting walls / beams and the foundations
- Flags: *unit weights ASSUMED from the element name*
- Status: **REVIEW REQUIRED**

**C08 - Foundation bearing width (ground pressure)**  (Structural engineer)

- Inputs: width 0.9 m -> 1.2 m; length 4.2 m
- Method: `q = N / (B x L) -> for the same load N, q scales with B_old / B_new`
- Result: bearing width x1.33; ground pressure x0.75 for the same load - but the load itself increases (heavier floors): geotechnical / structural check of bearing capacity and settlement
- Flags: *allowable bearing pressure NOT in model*
- Status: **REVIEW REQUIRED**

**C09 - Load path / member check**  (Structural engineer)

- Inputs: modified (attribute, property, geometry); length 4.2 m; area not in model; volume 1.777 m3; load-bearing not in model; storey T/FDN
- Method: `verify supports, loads and connections for the revised member`
- Result: structural engineer to confirm the member and the load path
- Flags: *load-bearing NOT DEFINED*
- Status: **REVIEW REQUIRED**

### PMI_V3_Footing_Widened_4  ·  IfcFooting  ·  `0kF45Qs8L9PAM9kmb1lT5$`

Storey: **T/FDN**  ·  Bounds: -  ·  Host: -  ·  Detected change: Name changed; Description changed; Volume: 2.02041 -> 4.0408; Width: 0.9 -> 1.2; geometry (shape / position) changed

**C10 - Self-weight / extra dead load on supports and foundations**  (Structural engineer)

- Inputs: V 2.02 m3 (concrete (default), 25.0 kN/m3) -> 4.041 m3 (concrete (default), 25.0 kN/m3); storey T/FDN
- Method: `G = V x unit weight`
- Result: 51 kN -> 101 kN (dG = +51 kN) to be carried by the supporting walls / beams and the foundations
- Flags: *unit weights ASSUMED from the element name*
- Status: **REVIEW REQUIRED**

**C11 - Foundation bearing width (ground pressure)**  (Structural engineer)

- Inputs: width 0.9 m -> 1.2 m; length 8.8 m
- Method: `q = N / (B x L) -> for the same load N, q scales with B_old / B_new`
- Result: bearing width x1.33; ground pressure x0.75 for the same load - but the load itself increases (heavier floors): geotechnical / structural check of bearing capacity and settlement
- Flags: *allowable bearing pressure NOT in model*
- Status: **REVIEW REQUIRED**

**C12 - Load path / member check**  (Structural engineer)

- Inputs: modified (attribute, property, geometry); length 8.8 m; area not in model; volume 4.041 m3; load-bearing not in model; storey T/FDN
- Method: `verify supports, loads and connections for the revised member`
- Result: structural engineer to confirm the member and the load path
- Flags: *load-bearing NOT DEFINED*
- Status: **REVIEW REQUIRED**

### PMI_V3_Footing_Widened_1  ·  IfcFooting  ·  `0kF45Qs8L9PAM9kmb1lT5d`

Storey: **T/FDN**  ·  Bounds: -  ·  Host: -  ·  Detected change: Name changed; Description changed; Volume: 4.936409999999995 -> 9.8728; Width: 0.9 -> 1.2; geometry (shape / position) changed

**C13 - Self-weight / extra dead load on supports and foundations**  (Structural engineer)

- Inputs: V 4.936 m3 (concrete (default), 25.0 kN/m3) -> 9.873 m3 (concrete (default), 25.0 kN/m3); storey T/FDN
- Method: `G = V x unit weight`
- Result: 123 kN -> 247 kN (dG = +123 kN) to be carried by the supporting walls / beams and the foundations
- Flags: *unit weights ASSUMED from the element name*
- Status: **REVIEW REQUIRED**

**C14 - Foundation bearing width (ground pressure)**  (Structural engineer)

- Inputs: width 0.9 m -> 1.2 m; length 17.383 m
- Method: `q = N / (B x L) -> for the same load N, q scales with B_old / B_new`
- Result: bearing width x1.33; ground pressure x0.75 for the same load - but the load itself increases (heavier floors): geotechnical / structural check of bearing capacity and settlement
- Flags: *allowable bearing pressure NOT in model*
- Status: **REVIEW REQUIRED**

**C15 - Load path / member check**  (Structural engineer)

- Inputs: modified (attribute, property, geometry); length 17.383 m; area not in model; volume 9.873 m3; load-bearing not in model; storey T/FDN
- Method: `verify supports, loads and connections for the revised member`
- Result: structural engineer to confirm the member and the load path
- Flags: *load-bearing NOT DEFINED*
- Status: **REVIEW REQUIRED**

### PMI_V3_Footing_Widened_2  ·  IfcFooting  ·  `0kF45Qs8L9PAM9kmb1lT5l`

Storey: **T/FDN**  ·  Bounds: -  ·  Host: -  ·  Detected change: Name changed; Description changed; Volume: 2.263409999999996 -> 4.5268; Width: 0.9 -> 1.2; geometry (shape / position) changed

**C16 - Self-weight / extra dead load on supports and foundations**  (Structural engineer)

- Inputs: V 2.263 m3 (concrete (default), 25.0 kN/m3) -> 4.527 m3 (concrete (default), 25.0 kN/m3); storey T/FDN
- Method: `G = V x unit weight`
- Result: 57 kN -> 113 kN (dG = +57 kN) to be carried by the supporting walls / beams and the foundations
- Flags: *unit weights ASSUMED from the element name*
- Status: **REVIEW REQUIRED**

**C17 - Foundation bearing width (ground pressure)**  (Structural engineer)

- Inputs: width 0.9 m -> 1.2 m; length 8.383 m
- Method: `q = N / (B x L) -> for the same load N, q scales with B_old / B_new`
- Result: bearing width x1.33; ground pressure x0.75 for the same load - but the load itself increases (heavier floors): geotechnical / structural check of bearing capacity and settlement
- Flags: *allowable bearing pressure NOT in model*
- Status: **REVIEW REQUIRED**

**C18 - Load path / member check**  (Structural engineer)

- Inputs: modified (attribute, property, geometry); length 8.383 m; area not in model; volume 4.527 m3; load-bearing not in model; storey T/FDN
- Method: `verify supports, loads and connections for the revised member`
- Result: structural engineer to confirm the member and the load path
- Flags: *load-bearing NOT DEFINED*
- Status: **REVIEW REQUIRED**

### PMI_V3_Footing_Widened_3  ·  IfcFooting  ·  `0kF45Qs8L9PAM9kmb1lT5t`

Storey: **T/FDN**  ·  Bounds: -  ·  Host: -  ·  Detected change: Name changed; Description changed; Volume: 4.693409999999997 -> 9.3868; Width: 0.9 -> 1.2; geometry (shape / position) changed

**C19 - Self-weight / extra dead load on supports and foundations**  (Structural engineer)

- Inputs: V 4.693 m3 (concrete (default), 25.0 kN/m3) -> 9.387 m3 (concrete (default), 25.0 kN/m3); storey T/FDN
- Method: `G = V x unit weight`
- Result: 117 kN -> 235 kN (dG = +117 kN) to be carried by the supporting walls / beams and the foundations
- Flags: *unit weights ASSUMED from the element name*
- Status: **REVIEW REQUIRED**

**C20 - Foundation bearing width (ground pressure)**  (Structural engineer)

- Inputs: width 0.9 m -> 1.2 m; length 16.966 m
- Method: `q = N / (B x L) -> for the same load N, q scales with B_old / B_new`
- Result: bearing width x1.33; ground pressure x0.75 for the same load - but the load itself increases (heavier floors): geotechnical / structural check of bearing capacity and settlement
- Flags: *allowable bearing pressure NOT in model*
- Status: **REVIEW REQUIRED**

**C21 - Load path / member check**  (Structural engineer)

- Inputs: modified (attribute, property, geometry); length 16.966 m; area not in model; volume 9.387 m3; load-bearing not in model; storey T/FDN
- Method: `verify supports, loads and connections for the revised member`
- Result: structural engineer to confirm the member and the load path
- Flags: *load-bearing NOT DEFINED*
- Status: **REVIEW REQUIRED**

### PMI_Window_Revised  ·  IfcWindow  ·  `1hOSvn6df7F8_7GcBWlR72`

Storey: **Level 1**  ·  Bounds: B102 Living Room  ·  Host: Basic Wall:Exterior - Brick on Block:138062 (2O2Fr$t4X7Zf8NOew3FNtn)  ·  Detected change: Name changed; Description changed; ThermalTransmittance: not defined -> 1.1; geometry (shape / position) changed

| Value | V1 | V2 |
|---|---|---|
| width | 4.835 | 5.435 |
| area | 11.701 | 13.153 |
| U | not in model | 1.1 |

**C22 - Fabric heat loss of the element (heating load of the room)**  (MEP / building services engineer)

- Inputs: U 2.6 -> 1.1 W/m2K; A 11.701 -> 13.153 m2; dT 20 K (assumed); room: B102 Living Room
- Method: `Q = U x A x dT`
- Result: 608 W -> 289 W  (dQ = -319 W) - update the room heat-load calculation and emitter sizing for B102 Living Room
- Flags: *previous U ASSUMED 2.6 (not in V1)*
- Status: **REVIEW REQUIRED**

**C23 - Window-to-wall ratio of the host wall (solar gain, daylight, overheating)**  (Facade / energy consultant)

- Inputs: window 11.701 -> 13.153 m2; host wall area 13.612 m2 (Basic Wall:Exterior - Brick on Block:138062)
- Method: `WWR = A_window / A_wall`
- Result: 86.0% -> 96.6% - very high glazing ratio: check overheating, energy compliance and facade structure
- Flags: *host wall area from its property set - confirm whether it is gross or net of openings*
- Status: **REVIEW REQUIRED**

**C24 - Lintel / header over the opening (span change)**  (Structural engineer)

- Inputs: clear span 4.835 m -> 5.435 m; host wall Basic Wall:Exterior - Brick on Block:138062 (load-bearing: False); storey Level 1
- Method: `M = w L^2 / 8 ; deflection = 5 w L^4 / (384 E I) -> ratios for the same load w`
- Result: span x1.124; bending moment x1.26 (+26%); deflection x1.60 (+60%) - lintel to be re-checked / re-sized
- Status: **CHECK (non load-bearing host - facade support only)**

### PMI_Fire_Rated_Door  ·  IfcDoor  ·  `1hOSvn6df7F8_7GcBWlRGQ`

Storey: **Level 1**  ·  Bounds: A101 Foyer  ·  Host: Basic Wall:Exterior - Brick on Block:138157 (2O2Fr$t4X7Zf8NOew3FNqI)  ·  Detected change: Name changed; Description changed; FireRating: 'Fire Rating' -> 'EI 60'

| Value | V1 | V2 |
|---|---|---|
| fire | not in model | EI 60 |

**C25 - Fire resistance and compartmentation**  (Fire safety engineer)

- Inputs: FireRating not in model -> EI 60; element bounds: A101 Foyer; storey Level 1
- Method: `rating of the opening <= rating of the wall it sits in; check the fire strategy / escape route`
- Result: new rating EI 60; host wall rating not in model - host wall rating must be confirmed
- Flags: *host wall fire rating NOT DEFINED in model*
- Status: **REVIEW REQUIRED**

### PMI_V3_Concrete_Floor_1  ·  IfcSlab  ·  `1hOSvn6df7F8_7GcBWlRqU`

Storey: **Level 2**  ·  Bounds: B105 Room, B201 Hallway, B202 Bedroom 1, B203 Bedroom 2, B204 Bathroom 2, B205 Utility  ·  Host: -  ·  Detected change: Name changed; Description changed; Thickness: 0.3050000000000001 -> 0.4; Volume: 18.06485036799987 -> 23.6916; geometry (shape / position) changed

**C26 - Self-weight / extra dead load on supports and foundations**  (Structural engineer)

- Inputs: V 18.065 m3 (wood, 5.0 kN/m3) -> 23.692 m3 (concrete, 25.0 kN/m3); storey Level 2
- Method: `G = V x unit weight`
- Result: 90 kN -> 592 kN (dG = +502 kN) to be carried by the supporting walls / beams and the foundations
- Flags: *unit weights ASSUMED from the element name*
- Status: **REVIEW REQUIRED**

**C27 - Load path / member check**  (Structural engineer)

- Inputs: modified (attribute, property, geometry); length not in model; area 59.229 m2; volume 23.692 m3; load-bearing True; storey Level 2
- Method: `verify supports, loads and connections for the revised member`
- Result: structural engineer to confirm the member and the load path
- Status: **REVIEW REQUIRED**

### PMI_V3_Concrete_Floor_2  ·  IfcSlab  ·  `1hOSvn6df7F8_7GcBWlRrM`

Storey: **Level 2**  ·  Bounds: A105 Stair, A201 Hallway, A202 Bedroom 1, A203 Bedroom 2, A204 Bathroom 2, A205 Utility  ·  Host: -  ·  Detected change: Name changed; Description changed; Thickness: 0.3050000000000001 -> 0.4; Volume: 18.09679301799989 -> 23.7335; geometry (shape / position) changed

**C28 - Self-weight / extra dead load on supports and foundations**  (Structural engineer)

- Inputs: V 18.097 m3 (wood, 5.0 kN/m3) -> 23.733 m3 (concrete, 25.0 kN/m3); storey Level 2
- Method: `G = V x unit weight`
- Result: 90 kN -> 593 kN (dG = +503 kN) to be carried by the supporting walls / beams and the foundations
- Flags: *unit weights ASSUMED from the element name*
- Status: **REVIEW REQUIRED**

**C29 - Load path / member check**  (Structural engineer)

- Inputs: modified (attribute, property, geometry); length not in model; area 59.334 m2; volume 23.733 m3; load-bearing True; storey Level 2
- Method: `verify supports, loads and connections for the revised member`
- Result: structural engineer to confirm the member and the load path
- Status: **REVIEW REQUIRED**

### PMI_External_Wall_Revised  ·  IfcWall  ·  `2O2Fr$t4X7Zf8NOew3FKau`

Storey: **Level 2**  ·  Bounds: A202 Bedroom 1, A203 Bedroom 2, B202 Bedroom 1, B203 Bedroom 2  ·  Host: -  ·  Detected change: Name changed; Description changed; ThermalTransmittance: not defined -> 0.18

| Value | V1 | V2 |
|---|---|---|
| U | not in model | 0.18 |

**C30 - Fabric heat loss of the element (heating load of the room)**  (MEP / building services engineer)

- Inputs: U 0.35 -> 0.18 W/m2K; A 38.406 -> 38.406 m2; dT 20 K (assumed); room: A202 Bedroom 1, A203 Bedroom 2, B202 Bedroom 1, B203 Bedroom 2
- Method: `Q = U x A x dT`
- Result: 269 W -> 138 W  (dQ = -131 W) - update the room heat-load calculation and emitter sizing for A202 Bedroom 1, A203 Bedroom 2, B202 Bedroom 1, B203 Bedroom 2
- Flags: *previous U ASSUMED 0.35 (not in V1)*
- Status: **REVIEW REQUIRED**

## 3. Sign-off

| Discipline | Checks | Name | Registration no. | Signature | Date |
|---|---|---|---|---|---|
| Structural engineer | C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C24, C26, C27, C28, C29 |  |  |  |  |
| MEP / building services engineer | C22, C30 |  |  |  |  |
| Facade / energy consultant | C23 |  |  |  |  |
| Fire safety engineer | C25 |  |  |  |  |

*Parameters: data/engineering_rules.json. Change detection: data/changes.json.*
