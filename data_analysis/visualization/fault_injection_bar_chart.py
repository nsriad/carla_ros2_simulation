from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# global LaTeX config
plt.rcParams.update({
    "text.usetex": True,
    "font.family": "serif",
    "font.serif": ["Computer Modern Roman"],
    "axes.labelsize": 12,
    "font.size": 10,
    "legend.fontsize": 9,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
})

OUT_DIR = Path(__file__).parent
METRIC = "MAE"  # "MAE" or "RMSE"

conditions = ["Nominal", "Camera dropout", "LiDAR dropout",
              "Both dropout", "LiDAR noise", "Combined faults"]

# offline results in meters, columns: LiDAR, camera, fused
results = {
    "MAE": np.array([
        [0.108, 2.203, 0.094],
        [0.108, 7.526, 0.071],
        [6.194, 2.203, 1.015],
        [6.755, 7.526, 1.637],
        [0.311, 2.203, 0.424],
        [0.311, 8.505, 0.333],
    ]),
    "RMSE": np.array([
        [0.903, 3.681, 0.747],
        [0.903, 10.968, 0.583],
        [10.547, 3.681, 1.948],
        [11.150, 10.968, 3.206],
        [0.952, 3.681, 0.858],
        [0.952, 11.548, 0.714],
    ]),
}
data = results[METRIC]

series = ["LiDAR", "Camera", "Fused"]
colors = ["#17707A", "#C8651B", "#8E1B6B"]  # dark cyan, burnt orange, dark magenta

fig, ax = plt.subplots(figsize=(3.4, 3.4))

n_cond, n_ser = data.shape
bar_h = 0.30
y = np.arange(n_cond)
offsets = (np.arange(n_ser) - (n_ser - 1) / 2) * bar_h

bars = []
for j, (name, color) in enumerate(zip(series, colors)):
    b = ax.barh(y + offsets[j], data[:, j], height=bar_h * 0.92,
                color=color, label=name, zorder=3)
    bars.append(b)

ax.set_yticks(y)
ax.set_yticklabels(conditions)
ax.invert_yaxis()  # first condition on top
ax.set_xlim(0, data.max() * 1.12)
ax.set_xlabel(f"{METRIC} (m)")
ax.grid(axis="x", color="0.85", linewidth=0.6, zorder=0)
ax.tick_params(axis="y", length=0)
for side in ("top", "right"):
    ax.spines[side].set_visible(False)

ax.legend(loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=3,
          frameon=False, handlelength=1.2, columnspacing=1.2)

fig.tight_layout()
fig.canvas.draw()
renderer = fig.canvas.get_renderer()

# value labels: inside the bar if it fits, otherwise just right of it
pad_pt = 2
for b in bars:
    for rect in b:
        w = rect.get_width()
        ann = ax.annotate(f"{w:.3f}", xy=(w, rect.get_y() + rect.get_height() / 2),
                          xytext=(-pad_pt, 0), textcoords="offset points",
                          ha="right", va="center", color="white", fontsize=7)
        text_px = ann.get_window_extent(renderer).width
        bar_px = ax.transData.transform((w, 0))[0] - ax.transData.transform((0, 0))[0]
        if text_px + 4 * pad_pt * fig.dpi / 72 > bar_px:
            ann.set_ha("left")
            ann.set_color("0.15")
            ann.xyann = (pad_pt, 0)

fig.savefig(OUT_DIR / f"fault_injection_{METRIC.lower()}.pdf", bbox_inches="tight")
fig.savefig(OUT_DIR / f"fault_injection_{METRIC.lower()}.png", dpi=300, bbox_inches="tight")