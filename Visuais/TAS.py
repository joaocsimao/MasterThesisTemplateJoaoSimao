import numpy as np
import matplotlib.pyplot as plt

# Set up style configurations globally
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.family'] = 'sans-serif'

def draw_box(ax, text, x, y, width=2, height=1, facecolor='#E8F0FE', edgecolor='#1A73E8', lw=2):
    rect = plt.Rectangle((x - width/2, y - height/2), width, height, facecolor=facecolor, edgecolor=edgecolor, lw=lw, zorder=3)
    ax.add_patch(rect)
    ax.text(x, y, text, ha='center', va='center', fontsize=10, zorder=4, 
            weight='bold' if any(w in text for w in ['Agent', 'Role']) else 'normal')

def draw_arrow(ax, x1, y1, x2, y2, text="", text_offset_x=0.0, text_offset_y=0.12, rotate=False):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color="#5F6368", lw=2, mutation_scale=15),
                zorder=1)
    
    if text:
        mid_x = (x1 + x2) / 2 + text_offset_x
        mid_y = (y1 + y2) / 2 + text_offset_y
        
        if rotate:
            # Calculate angle based on line vector slope
            dy = y2 - y1
            dx = x2 - x1
            angle = np.degrees(np.arctan2(dy, dx))
            
            # FIX: If the arrow flows right-to-left, flip the angle by 180 degrees 
            # so the text is never rendered upside down!
            if angle > 90:
                angle -= 180
            elif angle < -90:
                angle += 180
                
            ax.text(mid_x, mid_y, text, ha='center', va='bottom', fontsize=9, 
                    color="#202124", rotation=angle, rotation_mode='anchor', zorder=4)
        else:
            ax.text(mid_x, mid_y, text, ha='center', va='bottom', fontsize=9, 
                    color="#202124", zorder=4)

# ==========================================
# 1. MAS-H2a: Role Reconfiguration (Fixed Rotation)
# ==========================================
def generate_tas_h2a_fixed():
    fig, ax = plt.subplots(figsize=(11, 3.8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 3.5)
    ax.axis('off')
    ax.set_title("MAS-H2a: Role Reconfiguration (Dynamic Allocation)", loc='left', fontsize=12, weight='bold', color='#202124')
    
    # Angled communication lanes
    draw_arrow(ax, 2.6, 2.2, 3.9, 2.8, text="Switches to", text_offset_y=0.08, rotate=True)
    draw_arrow(ax, 2.6, 2.2, 3.9, 1.6, text="Switches to", text_offset_y=0.08, rotate=True)
    
    draw_arrow(ax, 6.1, 2.8, 7.3, 2.4, text="Saves JSON", text_offset_y=0.08, rotate=True)
    
    # Right-to-Left arrow fixed! Text stays right-side up now.
    draw_arrow(ax, 7.3, 2.0, 6.1, 1.6, text="Fetches JSON", text_offset_y=0.08, rotate=True)
    
    # Structural Layout Blocks
    draw_box(ax, "Available Agent\n(Idle)", 1.5, 2.2, width=2.0, height=0.8, facecolor='#F1F3F4', edgecolor='#5F6368')
    draw_box(ax, "Role: Agent 1\n(Extract)", 5.0, 2.8, width=2.0, height=0.7, facecolor='#E8F0FE')
    draw_box(ax, "Role: Agent 2\n(Score)", 5.0, 1.6, width=2.0, height=0.7, facecolor='#E8F0FE')
    draw_box(ax, "Intermediate Storage\n(Queue / DB)", 8.5, 2.2, width=2.2, height=0.8, facecolor='#FCF8E3', edgecolor='#F0AD4E')

    plt.tight_layout()
    plt.savefig('tas_h2a_role_reconfiguration.png', dpi=300)
    plt.close()
    print("Saved tas_h2a_role_reconfiguration.png with right-side up text!")

if __name__ == '__main__':
    generate_tas_h2a_fixed()