import matplotlib.pyplot as plt

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

def generate_trs_design_updated():
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8.5))

    # --- 1. Local Devil's Advocate ---
    ax1.set_xlim(0, 11)
    ax1.set_ylim(0, 3.5)
    ax1.axis('off')
    ax1.set_title("MAS-H3: Local Devil's Advocate (Paired with Each Stage)", loc='left', fontsize=11, weight='bold', color='#202124')
    
    draw_arrow(ax1, 1.4, 1.5, 1.6, 1.5)
    draw_arrow(ax1, 3.4, 1.5, 3.6, 1.5)
    draw_arrow(ax1, 5.4, 1.5, 6.1, 1.5, text="Refined Z")
    draw_arrow(ax1, 7.9, 1.5, 8.1, 1.5)
    draw_arrow(ax1, 9.9, 1.5, 10.1, 1.5, text="Refined ŷ")
    
    draw_box(ax1, "Inputs", 0.8, 1.5, width=1.0, height=0.8, facecolor='#F1F3F4', edgecolor='#5F6368')
    draw_box(ax1, "Agent 1\n(Extract)", 2.5, 1.5, width=1.6, height=0.8)
    draw_box(ax1, "Local DA 1\n(Critique Z)", 4.5, 1.5, width=1.6, height=0.8, facecolor='#FCE8E6', edgecolor='#EA4335')
    draw_box(ax1, "Agent 2\n(Score)", 7.0, 1.5, width=1.6, height=0.8)
    draw_box(ax1, "Local DA 2\n(Critique ŷ)", 9.0, 1.5, width=1.6, height=0.8, facecolor='#FCE8E6', edgecolor='#EA4335')
    draw_box(ax1, "Output", 10.5, 1.5, width=0.6, height=0.8, facecolor='#E6F4EA', edgecolor='#137333')

    ax1.annotate('Critique &\nRevise', xy=(2.5, 1.95), xytext=(4.5, 1.95),
                 arrowprops=dict(arrowstyle="->", color="#EA4335", connectionstyle="arc3,rad=.5", lw=1.5),
                 ha='center', va='bottom', fontsize=8, color='#EA4335')
    ax1.annotate('Critique &\nRevise', xy=(7.0, 1.95), xytext=(9.0, 1.95),
                 arrowprops=dict(arrowstyle="->", color="#EA4335", connectionstyle="arc3,rad=.5", lw=1.5),
                 ha='center', va='bottom', fontsize=8, color='#EA4335')

    # --- 2. Global Devil's Advocate (Updated Loop Routing) ---
    ax2.set_xlim(0, 11)
    ax2.set_ylim(0, 3.8)
    ax2.axis('off')
    ax2.set_title("MAS-H3: Global Devil's Advocate (Evaluates Final Output)", loc='left', fontsize=11, weight='bold', color='#202124')
    
    # Forward paths
    draw_arrow(ax2, 1.4, 2.2, 1.6, 2.2)
    draw_arrow(ax2, 3.6, 2.2, 4.2, 2.2, text="Z")
    draw_arrow(ax2, 6.2, 2.2, 7.1, 2.2, text="ŷ")
    draw_arrow(ax2, 9.3, 2.2, 9.9, 2.2, text="Endorse")
    
    # Draw Core Blocks
    draw_box(ax2, "Inputs", 0.8, 2.2, width=1.0, height=0.8, facecolor='#F1F3F4', edgecolor='#5F6368')
    draw_box(ax2, "Agent 1\n(Extract JSON Z)", 2.6, 2.2, width=1.8, height=0.8)
    draw_box(ax2, "Agent 2\n(Score ŷ)", 5.2, 2.2, width=1.8, height=0.8)
    draw_box(ax2, "Global DA\n(Critique Final)", 8.2, 2.2, width=2.0, height=0.8, facecolor='#FCE8E6', edgecolor='#EA4335')
    draw_box(ax2, "Final\nOutput", 10.4, 2.2, width=0.8, height=0.8, facecolor='#E6F4EA', edgecolor='#137333')

    # Top feedback loop: Global DA (top) to Agent 1 (top)
    ax2.annotate('Trigger Recomputation (Full Pipeline)', xy=(2.6, 2.65), xytext=(8.2, 2.65),
                 arrowprops=dict(arrowstyle="->", color="#EA4335", connectionstyle="arc3,rad=.35", lw=1.5),
                 ha='center', va='bottom', fontsize=8, color='#EA4335')

    # UPDATED Bottom feedback loop: Global DA (bottom) curves down completely below the chain to Agent 2 (bottom)
    ax2.annotate('Trigger Recomputation (Partial Score)', xy=(5.2, 1.75), xytext=(8.2, 1.75),
                 arrowprops=dict(arrowstyle="->", color="#EA4335", connectionstyle="arc3,rad=-0.45", lw=1.5),
                 ha='center', va='top', fontsize=8, color='#EA4335')

    # Stance Footnote Legend
    ax2.text(5.5, 0.3, "Stances: 1) Always-Critical (unconditional challenge)  |  2) Conditional (challenge only on logical flaw)",
             ha='center', va='center', fontsize=9, style='italic', bbox=dict(facecolor='#FFF', edgecolor='#5F6368', boxstyle='round,pad=0.5'))

    plt.tight_layout()
    plt.savefig('4_trs_design_updated.png', dpi=300)
    plt.close()
    print("Saved 4_trs_design_updated.png with the sub-level feedback loop routing clean!")

if __name__ == '__main__':
    generate_trs_design_updated()