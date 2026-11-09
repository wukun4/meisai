"""Rebuild the independent PDF calculation grid; sourced dimensions, assumed partition."""
from pathlib import Path
import json, os
ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "model" / ".mplconfig"))
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / "model" / ".cache"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

# Read the same geometry as the numerical model; no separate rounded input.
import sys
sys.path.insert(0, str(ROOT / "model"))
from geometry import shelter_zones
cfg = json.loads((ROOT / "model" / "scenario.json").read_text())
zones = shelter_zones(cfg)
g = cfg["geometry"]
L, W, H = g["length_m"], g["width_m"], g["height_m"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "pdf.fonttype": 42})
fig, ax = plt.subplots(figsize=(10, 4.5))
colors = ["#D8E9F1", "#E5E9E4", "#F0E3D1"]
# Grid only: no inferred bench/column sizes or net-standing-area claims.
for i, z in enumerate(zones):
    left, right = z["x_min_m"], z["x_max_m"]
    xc = z["center_x_m"]
    ax.add_patch(Rectangle((left, 0), right-left, W, facecolor=colors[i], edgecolor="#364B55", lw=1.3))
    ax.text(xc, W*.81, cfg["zone_names"][i], ha="center", va="center", fontsize=13, weight="bold")
    ax.plot(xc, W/2, "o", color="#364B55", ms=5)
    ax.text(xc, W*.30, f"x = {xc:.4f} m\nArea = {z['gross_area_m2']:.4f} m²", ha="center", va="center", linespacing=1.6)
ax.annotate("", (L, W+.23), (0, W+.23), arrowprops={"arrowstyle":"<->", "color":"#364B55", "lw":1})
ax.text(L/2, W+.29, f"L = {L:.4f} m  (14 ft)", ha="center", va="bottom")
ax.annotate("", (L+.25, W), (L+.25, 0), arrowprops={"arrowstyle":"<->", "color":"#364B55", "lw":1})
ax.text(L+.33, W/2, f"W = {W:.4f} m\n(5 ft)", ha="left", va="center", linespacing=1.5)
ax.annotate("", (L, -.22), (0, -.22), arrowprops={"arrowstyle":"->", "color":"#364B55", "lw":1})
ax.text(0, -.30, "x = 0: assumed delivery reference", ha="left", va="top", fontsize=10)
ax.text(L, -.30, "x", ha="right", va="top", fontsize=11, style="italic")
ax.set_title("NYC regular-size shelter: gross plan and calculation zones", loc="left", pad=18, weight="bold", fontsize=14)
fig.text(.10, .07, f"Height H = {H:.4f} m (8 ft 11 in)     |     Gross footprint = {L*W:.4f} m²", fontsize=11, color="#364B55")
ax.set(xlim=(-.1, L+1.0), ylim=(-.48, W+.55), aspect="equal")
ax.axis("off")
fig.subplots_adjust(left=.08, right=.99, top=.84, bottom=.17)
fig.savefig(ROOT / "figures" / "08_shelter_zoning.pdf", bbox_inches="tight", facecolor="white")
plt.close(fig)
