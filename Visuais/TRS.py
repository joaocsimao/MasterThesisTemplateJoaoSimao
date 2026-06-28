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
            weight='bold' if any(w in text for w in ['Agent', 'DA']) else 'normal')

def draw_arrow(ax, x1, y1, x2, y2, text="", text_offset_x=0.0, text_offset_y=0.12):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color="#5F6368", lw=2, mutation_scale=15),
                zorder=1)
    if text:
        mid_x = (x1 + x2) / 2 + text_offset_x
        mid_y = (y1 + y2) / 2 + text_offset_y
        ax.text(mid_x, mid_y, text, ha='center', va='bottom', fontsize=9, color="#202124", zorder=4)

def draw_stances_legend(ax):
    """Helper to draw the exact same stances footnote uniformly across both figures."""
    ax.text(5.5, 0.3, "Stances: 1) Always-Critical (unconditional challenge)  |  2) Conditional (challenge only on logical flaw)",
             ha='center', va='center', fontsize=9, style='italic', 
             bbox=dict(facecolor='#FFF', edgecolor='#5F6368', boxstyle='round,pad=0.5'))


# ==========================================
# PLOT POPULATION LOGIC (MERGED IN ONE ENGINE)
# ==========================================
def populate_local_da_axes(ax):
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 3.8)
    ax.axis('off')
    ax.set_title("MAS-H3: Local Devil's Advocate (Paired with Each Stage)", loc='left', fontsize=11, weight='bold', color='#202124')
    
    # Horizontal Main Lane Flow
    draw_arrow(ax, 1.4, 2.4, 1.6, 2.4)
    draw_arrow(ax, 3.4, 2.4, 5.1, 2.4, text="Refined Z")
    draw_arrow(ax, 6.9, 2.4, 8.6, 2.4, text="Refined ŷ")
    
    # Main Lane Blocks (Shifted upward slightly to Y = 2.4)
    draw_box(ax, "Inputs", 0.8, 2.4, width=1.0, height=0.8, facecolor='#F1F3F4', edgecolor='#5F6368')
    draw_box(ax, "Agent 1\n(Extract)", 2.5, 2.4, width=1.6, height=0.8)
    draw_box(ax, "Agent 2\n(Score)", 6.0, 2.4, width=1.6, height=0.8)
    draw_box(ax, "Output", 9.5, 2.4, width=1.0, height=0.8, facecolor='#E6F4EA', edgecolor='#137333')

    # Local DA Vertical Feedback Loops (Y = 1.1)
    draw_box(ax, "Local DA 1\n(Critique Z)", 2.5, 1.1, width=1.6, height=0.8, facecolor='#FCE8E6', edgecolor='#EA4335')
    draw_box(ax, "Local DA 2\n(Critique ŷ)", 6.0, 1.1, width=1.6, height=0.8, facecolor='#FCE8E6', edgecolor='#EA4335')

    # Communication paths per pair
    draw_arrow(ax, 2.3, 2.0, 2.3, 1.5) 
    draw_arrow(ax, 2.7, 1.5, 2.7, 2.0) 
    
    draw_arrow(ax, 5.8, 2.0, 5.8, 1.5) 
    draw_arrow(ax, 6.2, 1.5, 6.2, 2.0) 

    # Footnote Legend
    draw_stances_legend(ax)

def populate_global_da_axes(ax):
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 3.8)
    ax.axis('off')
    ax.set_title("MAS-H3: Global Devil's Advocate (Evaluates Final Output)", loc='left', fontsize=11, weight='bold', color='#202124')
    
    # Main Lane Flow
    draw_arrow(ax, 1.4, 2.2, 1.6, 2.2)
    draw_arrow(ax, 3.6, 2.2, 4.2, 2.2, text="Z")
    draw_arrow(ax, 6.2, 2.2, 7.1, 2.2, text="ŷ")
    draw_arrow(ax, 9.3, 2.2, 9.9, 2.2, text="Endorse")
    
    # Core Processing Blocks
    draw_box(ax, "Inputs", 0.8, 2.2, width=1.0, height=0.8, facecolor='#F1F3F4', edgecolor='#5F6368')
    draw_box(ax, "Agent 1\n(Extract JSON Z)", 2.6, 2.2, width=1.8, height=0.8)
    draw_box(ax, "Agent 2\n(Score ŷ)", 5.2, 2.2, width=1.8, height=0.8)
    draw_box(ax, "Global DA\n(Critique Final)", 8.2, 2.2, width=2.0, height=0.8, facecolor='#FCE8E6', edgecolor='#EA4335')
    draw_box(ax, "Final\nOutput", 10.4, 2.2, width=0.8, height=0.8, facecolor='#E6F4EA', edgecolor='#137333')

    # Top feedback loop: Global DA to Agent 1
    ax.annotate('Trigger Recomputation (Full Pipeline)', xy=(2.6, 2.65), xytext=(8.2, 2.65),
                 arrowprops=dict(arrowstyle="->", color="#EA4335", connectionstyle="arc3,rad=.35", lw=1.5),
                 ha='center', va='bottom', fontsize=8, color='#EA4335')

    # Bottom feedback loop: Global DA curves down safely below to Agent 2
    ax.annotate('Trigger Recomputation (Partial Score)', xy=(5.2, 1.75), xytext=(8.2, 1.75),
                 arrowprops=dict(arrowstyle="->", color="#EA4335", connectionstyle="arc3,rad=-0.45", lw=1.5),
                 ha='center', va='top', fontsize=8, color='#EA4335')

    # Footnote Legend
    draw_stances_legend(ax)

def generate_combined_trs():
    # Combined multi-plot setup (11 inches wide, 9 inches tall total to fit both 4.5 inch tall panes)
    fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(11, 9))
    
    # Render into each separate subplot axis
    populate_local_da_axes(axes[0])
    populate_global_da_axes(axes[1])
    
    plt.tight_layout()
    plt.savefig('trs_h3_combined_da.png', dpi=300)
    plt.close()


# ==========================================
# MAIN EXECUTION RUNNER
# ==========================================
if __name__ == '__main__':
    print("Regenerating and merging TRS diagrams into a single image asset...")
    
    generate_combined_trs()
    print(" -> Saved: trs_h3_combined_da.png")
    
    print("\nComplete! Unified canvas contains both diagrams with preserved stance footnotes.")