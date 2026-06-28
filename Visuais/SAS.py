import matplotlib.pyplot as plt

# Let's set up some style configurations
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.family'] = 'sans-serif'

def draw_box(ax, text, x, y, width=2, height=1, facecolor='#E8F0FE', edgecolor='#1A73E8', lw=2):
    rect = plt.Rectangle((x - width/2, y - height/2), width, height, facecolor=facecolor, edgecolor=edgecolor, lw=lw, zorder=3)
    ax.add_patch(rect)
    ax.text(x, y, text, ha='center', va='center', fontsize=10, zorder=4, weight='bold' if 'Agent' in text or 'System' in text else 'normal')

def draw_arrow(ax, x1, y1, x2, y2, text=""):
    ax.annotate(text, xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color="#5F6368", lw=2, mutation_scale=15),
                ha='center', va='bottom', fontsize=9, zorder=2)

# Figure 1: SAS Only (Changed to a single plot layout)
fig, ax1 = plt.subplots(figsize=(10, 4))

# SAS Configuration
ax1.set_xlim(0, 10)
ax1.set_ylim(0, 3)
ax1.axis('off')
ax1.set_title("3.5.1 Single-Agent System (SAS)", loc='left', fontsize=12, weight='bold', color='#202124')

# Drawing Components
draw_box(ax1, "Inputs\n(Q, S, R, O)", 2, 1.5, width=2, height=1, facecolor='#F1F3F4', edgecolor='#5F6368')
draw_box(ax1, "Single Agent\nŷ = γ(Q, S, R, O)", 5, 1.5, width=2.5, height=1)
draw_box(ax1, "Output Score\n(ŷ)", 8.5, 1.5, width=1.5, height=1, facecolor='#E6F4EA', edgecolor='#137333')

# Drawing Arrows
draw_arrow(ax1, 3, 1.5, 3.75, 1.5)
draw_arrow(ax1, 6.25, 1.5, 7.75, 1.5)

plt.tight_layout()
plt.savefig('sas_baseline.png', dpi=300)
plt.close()
print("Saved sas_baseline.png")