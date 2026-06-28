import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.family'] = 'sans-serif'

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
# H1b-minimal: Degraded instructions, profile sharing RETAINED
# Same as H1b but agents receive minimal task instruction instead of full
# The "Agent 2 Profile" / "Agent 1 Profile" boxes are kept (sharing retained)
# but agent boxes are labelled to signal minimal instruction
# ==========================================
def generate_h1b_minimal(fig, ax):
    # fig, ax = plt.subplots(figsize=(11, 3.8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 3.2)
    ax.axis('off')
    ax.set_title("MAS-H1b-minimal: Degraded Instructions, Profile Sharing Retained", loc='left', fontsize=11, weight='bold', color='#202124')

    draw_arrow(ax, 2.1, 1.3, 2.6, 1.3)
    draw_arrow(ax, 5.0, 1.3, 5.8, 1.3, text="JSON Z")
    draw_arrow(ax, 8.2, 1.3, 8.5, 1.3)
    draw_arrow(ax, 3.8, 2.4, 3.8, 1.9)
    draw_arrow(ax, 7.0, 2.4, 7.0, 1.9)

    draw_box(ax, "Inputs\n(Q, S, R, O)", 1.2, 1.3, width=1.6, height=1, facecolor='#F1F3F4', edgecolor='#5F6368')
    # Agents labelled as minimal instruction
    draw_box(ax, "Agent 1\n[Minimal Instr.]", 3.8, 1.3, width=2.2, height=1)
    draw_box(ax, "Agent 2\n[Minimal Instr.]", 7.0, 1.3, width=2.2, height=1)
    draw_box(ax, "Output (ŷ)", 9.2, 1.3, width=1.2, height=1, facecolor='#E6F4EA', edgecolor='#137333')
    # Profile sharing retained — each agent sees the OTHER agent's profile (same as H1b)
    draw_box(ax, "Agent 2 Profile", 3.8, 2.6, width=1.6, height=0.4, facecolor='#FEF7E0', edgecolor='#FBBC04')
    draw_box(ax, "Agent 1 Profile", 7.0, 2.6, width=1.6, height=0.4, facecolor='#FEF7E0', edgecolor='#FBBC04')

    # plt.tight_layout()
    # plt.savefig('tms_h1b_minimal.png', dpi=300)
    # plt.close()
    # print(" -> Saved: tms_h1b_minimal.png")


# ==========================================
# H1b-minimal-noshare: Degraded instructions, profile sharing REMOVED
# Same degraded instruction as H1b-minimal but profile boxes are gone entirely
# ==========================================
def generate_h1b_minimal_noshare(fig, ax):
    # fig, ax = plt.subplots(figsize=(11, 3.8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 3.2)
    ax.axis('off')
    ax.set_title("MAS-H1b-minimal-noshare: Degraded Instructions, Profile Sharing Removed", loc='left', fontsize=11, weight='bold', color='#202124')

    draw_arrow(ax, 2.1, 1.3, 2.6, 1.3)
    draw_arrow(ax, 5.0, 1.3, 5.8, 1.3, text="JSON Z")
    draw_arrow(ax, 8.2, 1.3, 8.5, 1.3)

    draw_box(ax, "Inputs\n(Q, S, R, O)", 1.2, 1.3, width=1.6, height=1, facecolor='#F1F3F4', edgecolor='#5F6368')
    draw_box(ax, "Agent 1\n[Minimal Instr.]", 3.8, 1.3, width=2.2, height=1)
    draw_box(ax, "Agent 2\n[Minimal Instr.]", 7.0, 1.3, width=2.2, height=1)
    draw_box(ax, "Output (ŷ)", 9.2, 1.3, width=1.2, height=1, facecolor='#E6F4EA', edgecolor='#137333')
    # No profile boxes — sharing removed entirely

    # plt.tight_layout()
    # plt.savefig('tms_h1b_minimal_noshare.png', dpi=300)
    # plt.close()
    # print(" -> Saved: tms_h1b_minimal_noshare.png")


# ==========================================
# H1c-incorrect: Inverted context — wrong source material provided
# Same structure as H1c but the context box is labelled as incorrect/wrong task
# ==========================================
def generate_h1c_incorrect():
    fig, ax = plt.subplots(figsize=(11, 3.8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 3.2)
    ax.axis('off')
    ax.set_title("MAS-H1c-WrongContext", loc='left', fontsize=11, weight='bold', color='#202124')

    draw_arrow(ax, 2.1, 2.1, 2.6, 1.7)
    draw_arrow(ax, 2.1, 0.9, 2.6, 1.3)
    draw_arrow(ax, 5.0, 1.5, 5.8, 1.5, text="JSON Z")
    draw_arrow(ax, 8.2, 1.5, 8.5, 1.5)

    draw_box(ax, "Inputs\n(Q, S, R, O)", 1.2, 2.1, width=1.6, height=0.8, facecolor='#F1F3F4', edgecolor='#5F6368')
    # Wrong context box — red tint to signal inversion
    draw_box(ax, "Incorrect Context", 1.2, 0.9, width=1.6, height=0.8, facecolor='#FCE8E6', edgecolor='#D93025')
    draw_box(ax, "Agent 1\n(Extract JSON Z)", 3.8, 1.5, width=2.2, height=1)
    draw_box(ax, "Agent 2\n(Score ŷ)", 7.0, 1.5, width=2.2, height=1)
    draw_box(ax, "Output (ŷ)", 9.2, 1.5, width=1.2, height=1, facecolor='#E6F4EA', edgecolor='#137333')

    plt.tight_layout()
    plt.savefig('tms_h1c_incorrect.png', dpi=300)
    plt.close()
    print(" -> Saved: tms_h1c_incorrect.png")


if __name__ == '__main__':
    print("Generating ablation condition diagrams...")
    
    # Generate the first image with the first two diagrams
    fig, axs = plt.subplots(2, 1, figsize=(11, 8))
    generate_h1b_minimal(fig, axs[0])
    generate_h1b_minimal_noshare(fig, axs[1])
    plt.tight_layout()
    plt.savefig('tms_h1b_minimal_combined.png', dpi=300)
    plt.close()
    print(" -> Saved: tms_h1b_minimal_combined.png")

    # Generate the second image with the third diagram
    generate_h1c_incorrect()
    print("\nDone!")