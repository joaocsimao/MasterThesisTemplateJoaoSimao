import matplotlib.pyplot as plt

# Set up style configurations
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.family'] = 'sans-serif'

def draw_box(ax, text, x, y, width=2, height=1, facecolor='#E8F0FE', edgecolor='#1A73E8', lw=2):
    # Boxes sit securely on Layer 3
    rect = plt.Rectangle((x - width/2, y - height/2), width, height, facecolor=facecolor, edgecolor=edgecolor, lw=lw, zorder=3)
    ax.add_patch(rect)
    # Box text sits on Layer 4
    ax.text(x, y, text, ha='center', va='center', fontsize=10, zorder=4, 
            weight='bold' if 'Agent' in text or 'System' in text else 'normal')

def draw_arrow(ax, x1, y1, x2, y2, text="", text_offset_y=0.12):
    # Draw arrow path on background Layer 1
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color="#5F6368", lw=2, mutation_scale=15),
                zorder=1)
    
    # Draw text cleanly on top of the path (Layer 4) with vertical padding
    if text:
        mid_x = (x1 + x2) / 2
        mid_y = ((y1 + y2) / 2) + text_offset_y
        ax.text(mid_x, mid_y, text, ha='center', va='bottom', fontsize=10, 
                color="#202124", weight='bold', zorder=4)

# Create a clean single-plot frame just for MAS
fig, ax2 = plt.subplots(figsize=(10, 3.5))

# Baseline MAS Setup
ax2.set_xlim(0, 10)
ax2.set_ylim(0, 3)
ax2.axis('off')
ax2.set_title("3.5.2 Baseline MAS", loc='left', fontsize=12, weight='bold', color='#202124')

# 1. Draw Arrows first (with trimmed horizontal spans to avoid box collision)
draw_arrow(ax2, 2.1, 1.5, 2.6, 1.5)
draw_arrow(ax2, 5.0, 1.5, 5.8, 1.5, text="JSON Z", text_offset_y=0.12)
draw_arrow(ax2, 8.2, 1.5, 8.5, 1.5)

# 2. Layer Boxes completely over the line tips
draw_box(ax2, "Inputs\n(Q, S, R, O)", 1.2, 1.5, width=1.6, height=1, facecolor='#F1F3F4', edgecolor='#5F6368')
draw_box(ax2, "Agent 1\n(Extract JSON Z)", 3.8, 1.5, width=2.2, height=1)
draw_box(ax2, "Agent 2\n(Score ŷ)", 7.0, 1.5, width=2.2, height=1)
draw_box(ax2, "Output Score\n(ŷ)", 9.2, 1.5, width=1.2, height=1, facecolor='#E6F4EA', edgecolor='#137333')

plt.tight_layout()
plt.savefig('baseline_mas.png', dpi=300)
plt.close()
print("Saved baseline_mas.png with perfectly clear text labels!")