import matplotlib.pyplot as plt

def draw_box(ax, text, x, y, width=2, height=1, facecolor='#E8F0FE', edgecolor='#1A73E8', lw=2):
    rect = plt.Rectangle((x - width/2, y - height/2), width, height, facecolor=facecolor, edgecolor=edgecolor, lw=lw, zorder=3)
    ax.add_patch(rect)
    ax.text(x, y, text, ha='center', va='center', fontsize=10, zorder=4, 
            weight='bold' if 'Agent' in text or 'System' in text else 'normal')

def draw_arrow(ax, x1, y1, x2, y2, text="", text_offset_x=0, text_offset_y=0):
    # Draw the arrow path
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color="#5F6368", lw=2, mutation_scale=15),
                zorder=1)
    
    # Position text with custom offsets to avoid the diagonal lines entirely
    if text:
        mid_x = (x1 + x2) / 2 + text_offset_x
        mid_y = (y1 + y2) / 2 + text_offset_y
        ax.text(mid_x, mid_y, text, ha='center', va='center', fontsize=9, color="#202124", zorder=2)

# ==========================================
# Sub-diagram functions (Perfected Alignment)
# ==========================================

def draw_diagram_h2a(ax1):
    ax1.set_xlim(0, 10)
    ax1.set_ylim(0, 3.5)
    ax1.axis('off')
    ax1.set_title("MAS-H2a: Role Reconfiguration (Dynamic Allocation)", loc='left', fontsize=11, weight='bold', color='#202124')

    # LEFT ARROWS: From X=2.5 (right edge of Left Box) to X=3.9 (left edge of Middle Boxes)
    draw_arrow(ax1, 2.5, 2.2, 3.9, 2.8, text="Switches to", text_offset_x=-0.1, text_offset_y=0.25)
    draw_arrow(ax1, 2.5, 2.2, 3.9, 1.6, text="Switches to", text_offset_x=-0.1, text_offset_y=-0.25)

    # RIGHT ARROWS: Between Middle Boxes (right edge X=6.1) and Right Box (left edge X=7.4)
    draw_arrow(ax1, 6.1, 2.8, 7.4, 2.4, text="Saves JSON", text_offset_x=0.1, text_offset_y=0.22)
    draw_arrow(ax1, 7.4, 2.0, 6.1, 1.6, text="Fetches JSON", text_offset_x=0.1, text_offset_y=-0.22)

    # Draw the boxes (Standardized Positions)
    draw_box(ax1, "Available Agent\n(Idle)", 1.5, 2.2, width=2.0, height=0.8, facecolor='#F1F3F4', edgecolor='#5F6368')
    draw_box(ax1, "Role: Agent 1\n(Extract)", 5.0, 2.8, width=2.2, height=0.7, facecolor='#E8F0FE')
    draw_box(ax1, "Role: Agent 2\n(Score)", 5.0, 1.6, width=2.2, height=0.7, facecolor='#E8F0FE')
    draw_box(ax1, "Intermediate Storage\n(Queue / DB)", 8.5, 2.2, width=2.2, height=0.8, facecolor='#FCF8E3', edgecolor='#F0AD4E')


def draw_diagram_h2b(ax2):
    ax2.set_xlim(0, 10)
    ax2.set_ylim(0, 3.5)
    ax2.axis('off')
    ax2.set_title("MAS-H2b: Parallel Execution (Concurrency)", loc='left', fontsize=11, weight='bold', color='#202124')

    # LEFT ARROWS: From X=2.5 (right edge of Left Box) to X=3.9 (left edge of Middle Boxes)
    draw_arrow(ax2, 2.5, 1.75, 3.9, 2.8)
    draw_arrow(ax2, 2.5, 1.75, 3.9, 1.75)
    draw_arrow(ax2, 2.5, 1.75, 3.9, 0.7)

    # RIGHT ARROWS: From X=6.1 (right edge of Middle Boxes) to X=7.4 (left edge of Right Box)
    draw_arrow(ax2, 6.1, 2.8, 7.4, 1.75)
    draw_arrow(ax2, 6.1, 1.75, 7.4, 1.75)
    draw_arrow(ax2, 6.1, 0.7, 7.4, 1.75)

    # Draw the boxes (Identical X-coordinates and widths to h2a)
    draw_box(ax2, "Task Queue\n(Essay 1, 2, 3, ...)", 1.5, 1.75, width=2.0, height=1.2, facecolor='#F1F3F4', edgecolor='#5F6368')
    draw_box(ax2, "Instance 1\n(Agent 1 -> 2)", 5.0, 2.8, width=2.2, height=0.7)
    draw_box(ax2, "Instance 2\n(Agent 1 -> 2)", 5.0, 1.75, width=2.2, height=0.7)
    draw_box(ax2, "Instance N\n(Agent 1 -> 2)", 5.0, 0.7, width=2.2, height=0.7)
    draw_box(ax2, "Parallel Output\n(Scores)", 8.5, 1.75, width=2.2, height=1.2, facecolor='#E6F4EA', edgecolor='#137333')

# ==========================================
# Main Execution: Master Layout Generator
# ==========================================
def generate_combined_image():
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8.0))
    
    draw_diagram_h2a(ax1)
    draw_diagram_h2b(ax2)
    
    plt.tight_layout()
    plt.savefig('combined_mas_diagrams.png', dpi=300)
    plt.close()
    print("Saved perfectly aligned combined_mas_diagrams.png successfully!")

if __name__ == '__main__':
    generate_combined_image()