# PMI - RIBA stage risk report

*Rule-based forecast (documented rules in data/riba_rules.json + CPM, no machine learning).*

Model V1 quantities: 57 walls, 14 doors, 24 windows, 21 slabs, 7 footings, 8 beams/columns, 13 coverings

V1 handover: 23 Apr 2027 (day 195). Contract handover = V1 + 25 working days buffer. Construction-only analysis (schedule_engine.py): +33 days.

| Issue scenario | V2 handover | Slip | Verdict | Stages HIGH |
|---|---|---|---|---|
| V2 issued at end of Stage 4 | 09 Jul 2027 | +55 d | **HANDOVER AT RISK - misses the contract date by 30 working days** | Stage 4, Stage 5, Stage 6 |
| V2 issued late, after wall construction | 10 Aug 2027 | +77 d | **HANDOVER AT RISK - misses the contract date by 52 working days** | Stage 4, Stage 5, Stage 6 |

## V2 issued at end of Stage 4

**Critical path:** S0 -> S1 -> S2 -> S3 -> S4 -> R4 -> A1 -> A2 -> A3 -> A4 -> A6 -> A7 -> H6

**Newly critical:** none

**New activities (work already done when V2 arrived):** none

| Stage | Risk | Score | Role | Slip (d) | Min float V1 -> V2 | Changes | Why |
|---|---|---|---|---|---|---|---|
| Stage 0 Strategic Definition | **NONE** | 0 | - | 0 | 0 -> 0 | - | - |
| Stage 1 Preparation and Briefing | **NONE** | 0 | - | 0 | 0 -> 0 | - | - |
| Stage 2 Concept Design | **NONE** | 0 | - | 0 | 0 -> 0 | - | - |
| Stage 3 Spatial Coordination | **NONE** | 0 | - | 0 | 0 -> 0 | - | - |
| Stage 4 Technical Design | **HIGH** | 54 | origin | 22 | 0 -> 0 | Door, Footing, Slab, Wall, Window | Footing x7 (revised together): geometry+property change -> Stage 4 information re-issued (+6 d) | Window: geometry+property change -> Stage 4 information re-issued (+6 d) | Door: property change -> Stage 4 information re-issued (+2 d) | Slab x2 (revised together): geometry+property change -> Stage 4 information re-issued (+6 d) | Wall: property change -> Stage 4 information re-issued (+2 d) |
| Stage 5 Manufacturing and Construction | **HIGH** | 100 | origin | 55 | 0 -> 0 | Door, Footing, Slab, Wall, Window | Window: new spec/size -> longer lead time (+15 d) | Door: new spec -> longer lead time (+5 d) | Footing: review (+2 d on A1) | Footing: review (+2 d on A1) | Footing: review (+2 d on A1) | Footing: review (+2 d on A1) | Footing: review (+2 d on A1) | Footing: review (+2 d on A1) | Footing: review (+2 d on A1) | Window: new unit, longer lead time and opening enlargement (+3 d on A4) | Door: certified product, procurement and inspection (+2 d on A4) | Slab: structural rework (+5 d on A2) | Slab: structural rework (+5 d on A2) | Wall: partial rework of the wall build-up (+4 d on A3) |
| Stage 6 Handover | **HIGH** | 85 | knock-on | 55 | 0 -> 0 | - | finish moves with upstream delay |

## V2 issued late, after wall construction

**Critical path:** S0 -> S1 -> S2 -> S3 -> S4 -> A1 -> A2 -> A3 -> R4 -> P2 -> A4 -> A6 -> A7 -> H6

**Newly critical:** none

**New activities (work already done when V2 arrived):** RW_A1 Rework of built foundations: NEW 28 d (work already done when V2 arrived); RW_A2 Rework of built structural works: NEW 20 d (work already done when V2 arrived); RW_A3 Rework of built wall construction: NEW 8 d (work already done when V2 arrived); P2 Re-order changed doors / windows: NEW 50 d (work already done when V2 arrived)

| Stage | Risk | Score | Role | Slip (d) | Min float V1 -> V2 | Changes | Why |
|---|---|---|---|---|---|---|---|
| Stage 0 Strategic Definition | **NONE** | 0 | - | 0 | 0 -> 0 | - | - |
| Stage 1 Preparation and Briefing | **NONE** | 0 | - | 0 | 0 -> 0 | - | - |
| Stage 2 Concept Design | **NONE** | 0 | - | 0 | 0 -> 0 | - | - |
| Stage 3 Spatial Coordination | **NONE** | 0 | - | 0 | 0 -> 0 | - | - |
| Stage 4 Technical Design | **HIGH** | 80 | origin | 64 | 0 -> 0 | Door, Footing, Slab, Wall, Window | Footing x7 (revised together): geometry+property change -> Stage 4 information re-issued (+6 d) | Window: geometry+property change -> Stage 4 information re-issued (+6 d) | Door: property change -> Stage 4 information re-issued (+2 d) | Slab x2 (revised together): geometry+property change -> Stage 4 information re-issued (+6 d) | Wall: property change -> Stage 4 information re-issued (+2 d) |
| Stage 5 Manufacturing and Construction | **HIGH** | 100 | origin | 77 | 0 -> 0 | Door, Footing, Slab, Wall, Window | Window: new spec/size -> longer lead time (+15 d) | Door: new spec -> longer lead time (+5 d) | Footing: review (+2 d on A1) | Footing: review (+2 d on A1) | Footing: review (+2 d on A1) | Footing: review (+2 d on A1) | Footing: review (+2 d on A1) | Footing: review (+2 d on A1) | Footing: review (+2 d on A1) | Window: new unit, longer lead time and opening enlargement (+3 d on A4) | Door: certified product, procurement and inspection (+2 d on A4) | Slab: structural rework (+5 d on A2) | Slab: structural rework (+5 d on A2) | Wall: partial rework of the wall build-up (+4 d on A3) |
| Stage 6 Handover | **HIGH** | 85 | knock-on | 77 | 0 -> 0 | - | finish moves with upstream delay |

## Issues (extra work per change)

- Window: new spec/size -> longer lead time (+15 d)
- Door: new spec -> longer lead time (+5 d)
- Footing x7 (revised together): geometry+property change -> Stage 4 information re-issued (+6 d)
- Window: geometry+property change -> Stage 4 information re-issued (+6 d)
- Door: property change -> Stage 4 information re-issued (+2 d)
- Slab x2 (revised together): geometry+property change -> Stage 4 information re-issued (+6 d)
- Wall: property change -> Stage 4 information re-issued (+2 d)
- Footing: review (+2 d on A1)
- Footing: review (+2 d on A1)
- Footing: review (+2 d on A1)
- Footing: review (+2 d on A1)
- Footing: review (+2 d on A1)
- Footing: review (+2 d on A1)
- Footing: review (+2 d on A1)
- Window: new unit, longer lead time and opening enlargement (+3 d on A4)
- Door: certified product, procurement and inspection (+2 d on A4)
- Slab: structural rework (+5 d on A2)
- Slab: structural rework (+5 d on A2)
- Wall: partial rework of the wall build-up (+4 d on A3)

## Risk levels

- **HIGH**: the stage finishes later AND it is on the critical path after the change
- **MEDIUM**: the stage receives extra work or loses at least half of its float, but its finish does not drive the project
- **LOW**: the stage receives extra work that is fully absorbed by float
- **NONE**: no change touches the stage and its dates do not move
- **HANDOVER**: AT RISK when the V2 handover is later than the contract date (V1 handover + contract_handover_buffer_days); TIGHT when it uses more than half of the buffer
