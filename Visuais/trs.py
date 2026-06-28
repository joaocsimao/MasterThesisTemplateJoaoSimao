import numpy as np
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
            weight='bold' if any(w in text for w in ['Agent', 'System', 'Instance', 'DA']) else 'normal')

def draw_arrow(ax, x1, y1, x2, y2, text="", text_offset_x=0.0, text_offset_y=0.12, rotate=False):
    # Draw arrow path line
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color="#5F6368", lw=2, mutation_scale=15),
                zorder=1)
    
    if text:
        mid_x = (x1 + x2) / 2 + text_offset_x
        mid_y = (y1 + y2) / 2 + text_offset_y
        
        if rotate:
            # Rotate text dynamically to match the slope of diagonal lines
            dy = y2 - y1
            dx = x2 - x1
            angle = np.degrees(np.arctan2(dy, dx))
            ax.text(mid_x, mid_y, text, ha='center', va='bottom', fontsize=9, 
                    color="#202124", rotation=angle, rotation_mode='anchor', zorder=4)
        else:
            # Flat horizontal label placement
            ax.text(mid_x, mid_y, text, ha='center', va='bottom', fontsize=9, 
                    color="#202124", weight='bold' if 'JSON' in text else 'normal', zorder=4)


# ==========================================
# DIAGRAM 1: SAS & BASELINE MAS (Fixed Overlaps)
# ==========================================
def generate_sas_baseline():
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6.5))

    # --- 3.5.1 Single-Agent System (SAS) ---
    ax1.set_xlim(0, 10)
    ax1.set_ylim(0, 3)
    ax1.axis('off')
    ax1.set_title("3.5.1 Single-Agent System (SAS)", loc='left', fontsize=12, weight='bold', color='#202124')
    
    draw_arrow(ax1, 3.1, 1.5, 3.6, 1.5)
    draw_arrow(ax1, 6.3, 1.5, 7.6, 1.5)
    
    draw_box(ax1, "Inputs\n(Q, S, R, O)", 2, 1.5, width=2, height=1, facecolor='#F1F3F4', edgecolor='#5F6368')
    draw_box(ax1, "Single Agent\nŷ = γ(Q, S, R, O)", 5, 1.5, width=2.5, height=1)
    draw_box(ax1, "Output Score\n(ŷ)", 8.5, 1.5, width=1.5, height=1, facecolor='#E6F4EA', edgecolor='#137333')

    # --- 3.5.2 Baseline MAS ---
    ax2.set_xlim(0, 10)
    ax2.set_ylim(0, 3)
    ax2.axis('off')
    ax2.set_title("3.5.2 Baseline MAS", loc='left', fontsize=12, weight='bold', color='#202124')
    
    # Adjusted arrow boundaries so they never cross line ends or box headers
    draw_arrow(ax2, 2.1, 1.5, 2.6, 1.5)
    draw_arrow(ax2, 5.0, 1.5, 5.8, 1.5, text="JSON Z", text_offset_y=0.15)
    draw_arrow(ax2, 8.2, 1.5, 8.5, 1.5) # Increased gap space here so text doesn't hit final block
    
    draw_box(ax2, "Inputs\n(Q, S, R, O)", 1.2, 1.5, width=1.6, height=1, facecolor='#F1F3F4', edgecolor='#5F6368')
    draw_box(ax2, "Agent 1\n(Extract JSON Z)", 3.8, 1.5, width=2.2, height=1)
    draw_box(ax2, "Agent 2\n(Score ŷ)", 7.0, 1.5, width=2.2, height=1)
    draw_box(ax2, "Output Score\n(ŷ)", 9.2, 1.5, width=1.2, height=1, facecolor='#E6F4EA', edgecolor='#137333')

    plt.tight_layout()
    plt.savefig('1_sas_baseline_mas.png', dpi=300)
    plt.close()


# ==========================================
# DIAGRAM 2: TAS DESIGN (Fixed Diagonal Text labels)
# ==========================================
def generate_tas_design():
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6.8))

    # --- MAS-H2a: Role Reconfiguration ---
    ax1.set_xlim(0, 10)
    ax1.set_ylim(0, 3.5)
    ax1.axis('off')
    ax1.set_title("MAS-H2a: Role Reconfiguration (Dynamic Allocation)", loc='left', fontsize=11, weight='bold', color='#202124')
    
    # Rotates text elements so they run perfectly parallel right on top of the paths
    draw_arrow(ax1, 2.6, 2.2, 3.9, 2.8, text="Switches to", text_offset_y=0.1, rotate=True)
    draw_arrow(ax1, 2.6, 2.2, 3.9, 1.6, text="Switches to", text_offset_y=0.1, rotate=True)
    
    draw_arrow(ax1, 6.1, 2.8, 7.3, 2.4, text="Saves JSON", text_offset_y=0.1, rotate=True)
    draw_arrow(ax1, 7.3, 2.0, 6.1, 1.6, text="Fetches JSON", text_offset_y=0.1, rotate=True)
    
    draw_box(ax1, "Available Agent\n(Idle)", 1.5, 2.2, width=2.0, height=0.8, facecolor='#F1F3F4', edgecolor='#5F6368')
    draw_box(ax1, "Role: Agent 1\n(Extract)", 5.0, 2.8, width=2.0, height=0.7, facecolor='#E8F0FE')
    draw_box(ax1, "Role: Agent 2\n(Score)", 5.0, 1.6, width=2.0, height=0.7, facecolor='#E8F0FE')
    draw_box(ax1, "Intermediate Storage\n(Queue / DB)", 8.5, 2.2, width=2.2, height=0.8, facecolor='#FCF8E3', edgecolor='#F0AD4E')

    # --- MAS-H2b: Concurrency ---
    ax2.set_xlim(0, 10)
    ax2.set_ylim(0, 3.5)
    ax2.axis('off')
    ax2.set_title("MAS-H2b: Concurrency (Parallel Processing)", loc='left', fontsize=11, weight='bold', color='#202124')
    
    draw_arrow(ax2, 2.2, 1.75, 3.3, 2.8)
    draw_arrow(ax2, 2.2, 1.75, 3.3, 1.75)
    draw_arrow(ax2, 2.2, 1.75, 3.3, 0.7)
    draw_arrow(ax2, 5.7, 2.8, 7.1, 1.75)
    draw_arrow(ax2, 5.7, 1.75, 7.1, 1.75)
    draw_arrow(ax2, 5.7, 0.7, 7.1, 1.75)
    
    draw_box(ax2, "Task Queue\n(Essay 1, 2, 3, ...)", 1.2, 1.75, width=1.8, height=1.2, facecolor='#F1F3F4', edgecolor='#5F6368')
    draw_box(ax2, "Instance 1\n(Agent 1 -> 2)", 4.5, 2.8, width=2.2, height=0.7)
    draw_box(ax2, "Instance 2\n(Agent 1 -> 2)", 4.5, 1.75, width=2.2, height=0.7)
    draw_box(ax2, "Instance N\n(Agent 1 -> 2)", 4.5, 0.7, width=2.2, height=0.7)
    draw_box(ax2, "Parallel Output\n(Scores)", 8.2, 1.75, width=2.0, height=1.2, facecolor='#E6F4EA', edgecolor='#137333')

    plt.tight_layout()
    plt.savefig('2_tas_design.png', dpi=300)
    plt.close()


# ==========================================
# DIAGRAM 3: TRS DESIGN (Fixed Local Under Track)
# ==========================================
def generate_trs_design():
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8.5))

    # --- Local Devil's Advocate ---
    ax1.set_xlim(0, 11)
    ax1.set_ylim(0, 3.5)
    ax1.axis('off')
    ax1.set_title("MAS-H3: Local Devil's Advocate (Paired with Each Stage)", loc='left', fontsize=11, weight='bold', color='#202124')
    
    draw_arrow(ax1, 1.4, 2.2, 1.6, 2.2)
    draw_arrow(ax1, 3.4, 2.2, 5.1, 2.2, text="Refined Z")
    draw_arrow(ax1, 6.9, 2.2, 8.6, 2.2, text="Refined ŷ")
    
    draw_box(ax1, "Inputs", 0.8, 2.2, width=1.0, height=0.8, facecolor='#F1F3F4', edgecolor='#5F6368')
    draw_box(ax1, "Agent 1\n(Extract)", 2.5, 2.2, width=1.6, height=0.8)
    draw_box(ax1, "Agent 2\n(Score)", 6.0, 2.2, width=1.6, height=0.8)
    draw_box(ax1, "Output", 9.5, 2.2, width=1.0, height=0.8, facecolor='#E6F4EA', edgecolor='#137333')

    # Placed neatly underneath with no clipping overlaps
    draw_box(ax1, "Local DA 1\n(Critique Z)", 2.5, 0.8, width=1.6, height=0.8, facecolor='#FCE8E6', edgecolor='#EA4335')
    draw_box(ax1, "Local DA 2\n(Critique ŷ)", 6.0, 0.8, width=1.6, height=0.8, facecolor='#FCE8E6', edgecolor='#EA4335')

    draw_arrow(ax1, 2.3, 1.8, 2.3, 1.2) 
    draw_arrow(ax1, 2.7, 1.2, 2.7, 1.8) 
    draw_arrow(ax1, 5.8, 1.8, 5.8, 1.2) 
    draw_arrow(ax1, 6.2, 1.2, 6.2, 1.8) 

    # --- Global Devil's Advocate ---
    ax2.set_xlim(0, 11)
    ax2.set_ylim(0, 3.8)
    ax2.axis('off')
    ax2.set_title("MAS-H3: Global Devil's Advocate (Evaluates Final Output)", loc='left', fontsize=11, weight='bold', color='#202124')
    
    draw_arrow(ax2, 1.4, 2.2, 1.6, 2.2)
    draw_arrow(ax2, 3.6, 2.2, 4.2, 2.2, text="Z")
    draw_arrow(ax2, 6.2, 2.2, 7.1, 2.2, text="ŷ")
    draw_arrow(ax2, 9.3, 2.2, 9.9, 2.2, text="Endorse")
    
    draw_box(ax2, "Inputs", 0.8, 2.2, width=1.0, height=0.8, facecolor='#F1F3F4', edgecolor='#5F6368')
    draw_box(ax2, "Agent 1\n(Extract JSON Z)", 2.6, 2.2, width=1.8, height=0.8)
    draw_box(ax2, "Agent 2\n(Score ŷ)", 5.2, 2.2, width=1.8, height=0.8)
    draw_box(ax2, "Global DA\n(Critique Final)", 8.2, 2.2, width=2.0, height=0.8, facecolor='#FCE8E6', edgecolor='#EA4335')
    draw_box(ax2, "Final\nOutput", 10.4, 2.2, width=0.8, height=0.8, facecolor='#E6F4EA', edgecolor='#137333')

    ax2.annotate('Trigger Recomputation (Full Pipeline)', xy=(2.6, 2.65), xytext=(8.2, 2.65),
                 arrowprops=dict(arrowstyle="->", color="#EA4335", connectionstyle="arc3,rad=.35", lw=1.5),
                 ha='center', va='bottom', fontsize=8, color='#EA4335')

    ax2.annotate('Trigger Recomputation (Partial Score)', xy=(5.2, 1.75), xytext=(8.2, 1.75),
                 arrowprops=dict(arrowstyle="->", color="#EA4335", connectionstyle="arc3,rad=-0.45", lw=1.5),
                 ha='center', va='top', fontsize=8, color='#EA4335')

    ax2.text(5.5, 0.3, "Stances: 1) Always-Critical (unconditional challenge)  |  2) Conditional (challenge only on logical flaw)",
             ha='center', va='center', fontsize=9, style='italic', bbox=dict(facecolor='#FFF', edgecolor='#5F6368', boxstyle='round,pad=0.5'))

    plt.tight_layout()
    plt.savefig('3_trs_design.png', dpi=300)
    plt.close()


if __name__ == '__main__':
    print("Generating layouts with fixed label offsets and margins...")
    generate_sas_baseline()
    generate_tas_design()
    generate_trs_design()
    print("Everything updated smoothly with zero text intersection points!")