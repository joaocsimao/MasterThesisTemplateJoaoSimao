import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Data ──────────────────────────────────────────────────────────────────────
models = ["GPT-4o", "GPT-4.1 Mini", "GPT-4o Mini"]
raters = ["Teacher", "Expert 1", "Expert 2"]

baseline = [
    [0.6597, 0.8225, 0.8104 ],
    [0.6417, 0.7873, 0.7311],   
    [0.6341, 0.7182, 0.714]

]
h1a = [
    [0.6577,0.8099,0.8317],
    [0.6651, 0.7901, 0.7812],
    [0.6704, 0.7894, 0.737],
]
h1acontra = [
    [0.652, 0.8177, 0.823],
    [0.6382, 0.785, 0.7649],
    [0.6483, 0.7811, 0.7159],

]

# ── Layout ────────────────────────────────────────────────────────────────────
bar_w     = 0.22
rater_gap = 0.08
group_gap = 0.35

colors = {
    "baseline":   "#333333",
    "h1a":        "#888888",
    "h1acontra":  "#CCCCCC",
}

fig, ax = plt.subplots(figsize=(13, 5.5))

# Build x positions
positions = []
x = 0.0
for m in range(len(models)):
    group = []
    for r in range(len(raters)):
        group.append(x)
        x += bar_w * 3 + rater_gap + 0.08
    positions.append(group)
    x += group_gap

for m, model in enumerate(models):
    for r, rater in enumerate(raters):
        xpos = positions[m][r]
        bval  = baseline[m][r]
        hval  = h1a[m][r]
        cval  = h1acontra[m][r]

        if bval is None:
            continue

        bars = [(xpos,             bval,  "baseline"),
                (xpos + bar_w,     hval,  "h1a"),
                (xpos + bar_w * 2, cval,  "h1acontra")]

        for xv, val, key in bars:
            if val is None:
                continue
            ax.bar(xv, val, bar_w, color=colors[key],
                   edgecolor="white", linewidth=0.5, zorder=3)
            ax.text(xv + bar_w / 2, val + 0.003, f"{val:.3f}",
                    ha="center", va="bottom", fontsize=7,
                    color="#333333")

# ── Ceiling lines ─────────────────────────────────────────────────────────────
x_min = positions[0][0] - 0.15
x_max = positions[-1][-1] + bar_w * 3 + 0.15

for yval, label in [(0.733, "Teacher × Expert ≈ 0.733"),
                    (0.905, "Expert × Expert = 0.905")]:
    ax.axhline(yval, color="#AAAAAA", linewidth=0.9,
               linestyle=(0, (5, 4)), zorder=2)
    ax.text(x_max + 0.08, yval, label,
            va="center", fontsize=8, color="#777777")

# ── Model group labels ────────────────────────────────────────────────────────
for m, model in enumerate(models):
    grp_xs  = positions[m]
    x_left  = grp_xs[0]
    x_right = grp_xs[-1] + bar_w * 3
    x_mid   = (x_left + x_right) / 2
    y_top   = ax.get_ylim()[1]
    ax.text(x_mid, 0.948, model, ha="center", va="bottom",
            fontsize=10, fontweight="bold", color="#222222",
            transform=ax.get_xaxis_transform())

    # vertical separator between model groups
    if m < len(models) - 1:
        x_sep = (x_right + positions[m + 1][0]) / 2
        ax.axvline(x_sep, color="#DDDDDD", linewidth=0.8,
                   linestyle="--", zorder=1)

# ── Rater x-tick labels ───────────────────────────────────────────────────────
tick_positions, tick_labels = [], []
for m in range(len(models)):
    for r, rater in enumerate(raters):
        if baseline[m][r] is not None:
            xpos = positions[m][r]
            tick_positions.append(xpos + bar_w * 1.5)
            tick_labels.append(rater)

ax.set_xticks(tick_positions)
ax.set_xticklabels(tick_labels, fontsize=9)

# ── Axes ──────────────────────────────────────────────────────────────────────
ax.set_ylim(0.55, 0.96)
ax.set_xlim(x_min, x_max + 2.2)
ax.set_ylabel("QWK", fontsize=10)
ax.yaxis.grid(True, color="#EEEEEE", linewidth=0.7, zorder=0)
ax.set_axisbelow(True)
ax.spines[["top", "right"]].set_visible(False)
ax.spines[["left", "bottom"]].set_color("#CCCCCC")
ax.tick_params(colors="#555555")

# ── Legend ────────────────────────────────────────────────────────────────────
legend_handles = [
    mpatches.Patch(facecolor=colors["baseline"],  edgecolor="white", label="MAS baseline"),
    mpatches.Patch(facecolor=colors["h1a"],       edgecolor="white", label="H1a"),
    mpatches.Patch(facecolor=colors["h1acontra"], edgecolor="#AAAAAA", label="H1a contra"),
]
ax.legend(handles=legend_handles, loc="lower right",
          frameon=False, fontsize=9)

plt.tight_layout()
plt.savefig("qwk_baseline_vs_h1a_v2.png", dpi=300, bbox_inches="tight")
plt.show()
print("Saved.")