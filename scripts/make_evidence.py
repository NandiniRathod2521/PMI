"""
PMI - STEP 5: EVIDENCE IMAGES (static PNGs for the slides, backup if the live demo fails)
========================================================================================
Creates in evidence/:
    gantt_before.png          baseline schedule
    gantt_after.png           baseline vs revised, delay highlighted
    scenario_comparison.png   duration / extra cost / extra CO2 per scenario
    change_table.png          the detected changes table
    model_3d_original.png     3D model, everything neutral grey   (from grasshopper/pmi_geometry.json)
    model_3d_changes.png      3D model, changed wall / door / window highlighted

Run: python scripts/make_evidence.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import schedule_engine as se  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"
BLUE, LIGHT, RED, GREY, INK = "#1F4E9E", "#A9C1E8", "#D64545", "#9AA3AF", "#1B2430"
plt.rcParams.update({"font.family": ["Poppins", "DejaVu Sans"], "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False})


def gantt(ax, s, color, offset=0.0, height=0.35, label=None, highlight=True):
    for i, r in enumerate(s.itertuples()):
        y = len(s) - 1 - i + offset
        c = color
        ax.barh(y, r.duration, left=r.ES, height=height, color=c, label=label if i == 0 else None)
        if highlight and r.added_days:
            ax.barh(y, r.added_days, left=r.EF - r.added_days, height=height, color=RED,
                    label="Added by design change" if r.Index == s[s.added_days > 0].index[0] else None)
    ax.set_yticks(range(len(s)))
    ax.set_yticklabels(list(s["activity"])[::-1])
    ax.set_xlabel("Working days from project start")


CAT = {"wall": "#D64545", "door": "#F08C2E", "window": "#2F80ED", "other": "#7A5AC9"}
GEOMETRY = ROOT / "grasshopper" / "pmi_geometry.json"


def render_3d(geometry: Path = GEOMETRY, out_dir: Path = EV, suffix: str = ""):
    """Two 3D views of the IfcOpenShell meshes: all grey (V1 look) and changes highlighted."""
    if not geometry.is_file():
        print("No grasshopper/pmi_geometry.json - run export_geometry.py first (3D images skipped)")
        return
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    els = json.loads(geometry.read_text(encoding="utf-8"))["elements"]
    for highlight, name in ((False, "model_3d_original"), (True, "model_3d_changes")):
        fig = plt.figure(figsize=(12, 7.5))
        ax = fig.add_subplot(projection="3d")
        lo, hi = [1e9] * 3, [-1e9] * 3
        labels = []
        for e in sorted(els, key=lambda e: e["status"] != "UNCHANGED"):   # changed drawn last
            v = e["vertices"]
            tris = [[v[a], v[b], v[c]] for a, b, c in e["faces"]]
            changed = e["status"] != "UNCHANGED"
            if changed and highlight:
                pc = Poly3DCollection(tris, facecolor=CAT.get(e["category"], CAT["other"]),
                                      edgecolor="#1B2430", linewidths=0.15, alpha=1.0)
                xs, ys, zs = zip(*v)
                labels.append((max(xs), sum(ys) / len(ys), max(zs) + 0.5, e["name"], CAT.get(e["category"])))
            else:
                pc = Poly3DCollection(tris, facecolor="#C8CBD0", edgecolor="#9AA3AF",
                                      linewidths=0.08, alpha=0.35 if highlight else 0.85)
            ax.add_collection3d(pc)
            for x, y, z in v:
                lo = [min(lo[0], x), min(lo[1], y), min(lo[2], z)]
                hi = [max(hi[0], x), max(hi[1], y), max(hi[2], z)]
        ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
        ax.set_box_aspect([hi[i] - lo[i] for i in range(3)], zoom=1.45)
        ax.view_init(elev=24, azim=-38)
        ax.set_axis_off()
        title = "Model V2 - changed elements highlighted" if highlight else "Model V1 - original"
        fig.suptitle("PMI - " + title, x=0.02, ha="left", fontweight="bold", color=INK)
        if highlight:
            from matplotlib.patches import Patch
            present = []
            for e in els:
                if e["status"] != "UNCHANGED" and e["category"] not in present:
                    present.append(e["category"])
            names = {}
            for _, _, _, txt, col in labels:
                names.setdefault(col, []).append(txt)
            def lab(k):
                n = names.get(CAT.get(k, CAT["other"]), [])
                return n[0] if len(n) == 1 else f"Changed {k} ({len(n)})"
            fig.legend(handles=[Patch(color=CAT.get(k, CAT["other"]), label=lab(k)) for k in present]
                       + [Patch(color="#C8CBD0", label="Unchanged")], loc="lower center", ncol=min(5, len(present) + 1),
                       frameon=False)
        fig.subplots_adjust(0, 0.03, 1, 0.97)
        fig.savefig(out_dir / f"{name}{suffix}.png", dpi=170, bbox_inches="tight", pad_inches=0.15)
        plt.close(fig)


def main():
    EV.mkdir(exist_ok=True)
    render_3d()
    r = se.run_all()
    base, rev = r["schedules"]["baseline"], r["schedules"]["revised"]
    bd, rd = se.project_duration(base), se.project_duration(rev)

    fig, ax = plt.subplots(figsize=(11, 4.2))
    gantt(ax, base, BLUE, highlight=False)
    ax.axvline(bd, color=INK, ls="--", lw=1)
    ax.set_xlim(0, bd + 12)
    ax.text(bd + 0.7, -0.4, f"Finish: day {bd}\n{base.finish_date.max():%d %b %Y}", fontsize=9)
    ax.set_title("PMI - Baseline schedule (Model V1)", loc="left", fontweight="bold", color=INK)
    fig.tight_layout(); fig.savefig(EV / "gantt_before.png", dpi=200); plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 5.2))
    gantt(ax, base, LIGHT, offset=0.2, height=0.35, label="Baseline", highlight=False)
    gantt(ax, rev, BLUE, offset=-0.2, height=0.35, label="Revised (Model V2)")
    ax.axvline(bd, color=GREY, ls="--", lw=1); ax.axvline(rd, color=RED, ls="--", lw=1)
    ax.set_xlim(0, rd + 12)
    ax.text(rd + 0.7, -0.4, f"+{rd - bd} days\nfinish {rev.finish_date.max():%d %b %Y}", color=RED, fontsize=9)
    ax.text(bd + 0.7, len(base) - 0.8, f"baseline\nday {bd}", color=GREY, fontsize=9)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=3, frameon=False)
    ax.set_title("PMI - Schedule impact of detected IFC changes", loc="left", fontweight="bold", color=INK)
    fig.tight_layout(); fig.savefig(EV / "gantt_after.png", dpi=200); plt.close(fig)

    comp = r["comparison"]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
    names = [s.replace(" (accelerated)", "\n(accelerated)").replace(" - ", "\n") for s in comp["scenario"]]
    cols = [GREY, RED, BLUE, "#2E8B57", "#7A5AC9"]
    for ax, col, title in zip(axes, ["duration_days", "extra_cost_eur", "extra_tco2e"],
                              ["Duration (working days)", "Extra cost vs baseline (EUR)", "Extra emissions (tCO2e)"]):
        ax.barh(names[::-1], comp[col][::-1], color=cols[::-1])
        ax.set_title(title, loc="left", fontweight="bold", color=INK, fontsize=10)
        for y, v in enumerate(comp[col][::-1]):
            ax.text(v, y, f" {v:,.0f}" if col != "extra_tco2e" else f" {v:.2f}", va="center", fontsize=8)
    fig.suptitle("PMI - Mitigation scenarios (illustrative assumptions)", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout(); fig.savefig(EV / "scenario_comparison.png", dpi=200); plt.close(fig)

    imp = r["impacts"]
    if not imp.empty:
        t = imp[["ifc_type", "global_id", "element", "change_types", "activity_id", "extra_days"]]
        fig, ax = plt.subplots(figsize=(12, 0.6 + 0.45 * len(t)))
        ax.axis("off")
        tab = ax.table(cellText=t.values, colLabels=["IFC type", "GlobalId", "Element (V2)", "Change channel",
                                                     "Activity", "Assumed +days"], loc="center", cellLoc="left")
        tab.auto_set_font_size(False); tab.set_fontsize(9); tab.scale(1, 1.5)
        for (row, _), cell in tab.get_celld().items():
            if row == 0:
                cell.set_facecolor(BLUE); cell.get_text().set_color("white")
        fig.tight_layout(); fig.savefig(EV / "change_table.png", dpi=200); plt.close(fig)

    print(f"Evidence saved in {EV}")


if __name__ == "__main__":
    main()
