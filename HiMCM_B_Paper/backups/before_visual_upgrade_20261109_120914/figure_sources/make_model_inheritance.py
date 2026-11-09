"""Draw the standalone model-inheritance PDF used by the revised paper.

The freezer establishes the evaluation framework, not an implemented SET model.
The bus and rail applications share the same human-response and local-delivery
modules; the rail application adds an evolving background and device allocation.
"""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("MPLCONFIGDIR", "/tmp/himcm-inheritance-mpl")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/himcm-inheritance-cache")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11,
    "pdf.fonttype": 42, "ps.fonttype": 42,
    "mathtext.fontset": "dejavusans",
})

INK = "#253D49"
LINE = "#657C86"
TEAL = "#277B80"
BLUE = "#345F8A"
fig, ax = plt.subplots(figsize=(10, 5.35))
fig.subplots_adjust(left=0.015, right=0.985, bottom=0.02, top=0.98)
ax.set(xlim=(0, 10), ylim=(0, 5.35))
ax.axis("off")

def box(x, y, width, height, title, body, face, accent=INK,
        title_size=11.5, body_size=10.8):
    ax.add_patch(FancyBboxPatch(
        (x, y), width, height, boxstyle="round,pad=0.015,rounding_size=0.09",
        linewidth=1.05, edgecolor=accent, facecolor=face, zorder=2))
    ax.text(x + width / 2, y + height - 0.18, title,
            ha="center", va="top", fontsize=title_size, weight="bold",
            color=accent, zorder=3)
    ax.text(x + width / 2, y + height / 2 - 0.13, body,
            ha="center", va="center", fontsize=body_size,
            linespacing=1.45, color=INK, zorder=3)

def arrow(start, end, color=LINE, dashed=False):
    ax.add_patch(FancyArrowPatch(
        start, end, arrowstyle="-|>", mutation_scale=13,
        linewidth=1.25, color=color, linestyle="--" if dashed else "-",
        shrinkA=1.5, shrinkB=1.5, zorder=1))

# Layer 1: the conceptual foundation is established by the freezer task.
box(0.14, 4.31, 9.72, 0.88, "FREEZER: establish the service framework",
    "Quantity × quality × time / energy; heat and moisture boundary; food-temperature compliance",
    "#EAF0F4", BLUE, title_size=12, body_size=10.8)
arrow((5, 4.30), (5, 3.88), BLUE)
ax.text(5.18, 4.08, "retain the evaluation logic", va="center",
        ha="left", fontsize=10.5, color=BLUE)

# Layer 2: a shared calculation interface; recipient modules are explicit.
chain_y, chain_h, chain_w = 2.71, 1.16, 2.22
chain_x = [0.14, 2.64, 5.14, 7.64]
nodes = [
    ("DEVICE / STRATEGY", "$h_s,\\,w_s$; airflow\npower and operating time"),
    ("DELIVERED CONDITIONS", "mix $h,\\,w$ → $T$, RH\nairspeed and radiation"),
    ("RECIPIENT RESPONSE", "food compliance\nor human SET"),
    ("SERVICE EFFICIENCY", "weighted service $U$\nelectricity $E$: $U/E$"),
]
for x, (title, body) in zip(chain_x, nodes):
    box(x, chain_y, chain_w, chain_h, title, body,
        "#F4F7F8", INK, title_size=10.3, body_size=11)
for x in chain_x[:-1]:
    arrow((x + chain_w, chain_y + chain_h / 2),
          (x + 2.50, chain_y + chain_h / 2))

# A common branch declares inheritance, not two independent scoring models.
ax.plot([5, 5], [2.71, 2.43], color=LINE, lw=1.1, zorder=1)
ax.plot([2.30, 7.70], [2.43, 2.43], color=LINE, lw=1.1, zorder=1)
arrow((2.30, 2.43), (2.30, 2.18))
arrow((7.70, 2.43), (7.70, 2.18))

# Layer 3: the two human-service applications differ in background dynamics.
box(0.14, 0.60, 4.25, 1.56, "BUS SHELTER: quasi-steady",
    "Fixed ambient background\nLocal mixing of supply and ambient air\nSET → person-time service / energy",
    "#E8F3F0", TEAL, title_size=11.8, body_size=11)
box(5.61, 0.60, 4.25, 1.56, "RAIL STATION: dynamic extension",
    "Retain device, local mixing, SET and service\nEvolve background $h_z$, $w_z$, $T_{m,z}$\nAdd exchange, crowds and device allocation",
    "#EAF0F7", BLUE, title_size=11.3, body_size=10.5)
arrow((4.42, 1.39), (5.58, 1.39), BLUE, dashed=True)
ax.text(5, 1.55, "add", ha="center", va="bottom", fontsize=10.5, color=BLUE)
ax.text(5, 1.22, "dynamics", ha="center", va="top", fontsize=10.5, color=BLUE)

ax.text(5, 0.20,
        "Food and human services use different response modules and units; their raw efficiencies are not directly comparable.",
        ha="center", va="center", fontsize=10, color=INK)

target = ROOT / "figures" / "19_model_inheritance.pdf"
target.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(target, facecolor="white", metadata={
    "Title": "Inheritance of the cooling-service model",
    "Subject": "Shared service framework, quasi-steady shelter, and dynamic rail-station extension",
    "Creator": "make_model_inheritance.py (Matplotlib)",
})
plt.close(fig)
print(target)
