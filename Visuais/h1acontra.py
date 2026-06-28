import matplotlib.pyplot as plt

# Set up style configurations globally
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.family'] = 'sans-serif'

# ==========================================
# CORE RENDERING ENGINE FUNCTIONS
# ==========================================
def draw_box(ax, text, x, y, width=2, height=1, facecolor='#E8F0FE', edgecolor='#1A73E8', lw=2):
    rect = plt.Rectangle((x - width/2, y - height/2), width, height, facecolor=facecolor, edgecolor=edgecolor, lw=lw, zorder=3)
    ax.add_patch(rect)
    ax.text(x, y, text, ha='center', va='center', fontsize=10, zorder=4, 
            weight='bold' if any(w in text for w in ['Agent', 'System', 'Profiles']) else 'normal')

def draw_arrow(ax, x1, y1, x2, y2, text="", text_offset_y=0.12):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color="#5F6368", lw=2, mutation_scale=15),
                zorder=1)
    if text:
        mid_x = (x1 + x2) / 2
        mid_y = ((y1 + y2) / 2) + text_offset_y
        ax.text(mid_x, mid_y, text, ha='center', va='bottom', fontsize=9, 
                color="#202124", weight='bold' if 'JSON' in text else 'normal', zorder=4)


# ==========================================
# 1. MAS-H1a: Profile-Aware Agents
# ==========================================
def generate_tms_h1a_original():
    fig, ax = plt.subplots(figsize=(11, 3.8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 3.2)
    ax.axis('off')
    ax.set_title("MAS-H1a: Profile-Aware Agents", loc='left', fontsize=11, weight='bold', color='#202124')
    
    # Arrows
    draw_arrow(ax, 2.1, 1.3, 2.6, 1.3)
    draw_arrow(ax, 5.0, 1.3, 5.8, 1.3, text="JSON Z")
    draw_arrow(ax, 8.2, 1.3, 8.5, 1.3)
    draw_arrow(ax, 3.8, 2.4, 3.8, 1.9)
    draw_arrow(ax, 7.0, 2.4, 7.0, 1.9)
    
    # Boxes
    draw_box(ax, "Inputs\n(Q, S, R, O)", 1.2, 1.3, width=1.6, height=1, facecolor='#F1F3F4', edgecolor='#5F6368')
    draw_box(ax, "Agent 1", 3.8, 1.3, width=2.2, height=1)
    draw_box(ax, "Agent 2", 7.0, 1.3, width=2.2, height=1)
    draw_box(ax, "Output (ŷ)", 9.2, 1.3, width=1.2, height=1, facecolor='#E6F4EA', edgecolor='#137333')
    draw_box(ax, "Own Profile", 3.8, 2.6, width=1.6, height=0.4, facecolor='#FEF7E0', edgecolor='#FBBC04')
    draw_box(ax, "Own Profile", 7.0, 2.6, width=1.6, height=0.4, facecolor='#FEF7E0', edgecolor='#FBBC04')

    plt.tight_layout()
    plt.savefig('tms_h1a_profile_aware.png', dpi=300)
    plt.close()

generate_tms_h1a_original()