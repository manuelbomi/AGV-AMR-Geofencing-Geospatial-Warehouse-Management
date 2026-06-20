"""
generate_readme_images.py - Repo 07: AGV/AMR Geofencing & Geospatial Warehouse Management
Generates illustrative images using only matplotlib + numpy.
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Circle, Polygon
import numpy as np
import os

os.makedirs("images", exist_ok=True)

BG = "#f8f9fa"
DARK = "#212121"
rng = np.random.default_rng(7)


# =============================================================
# IMAGE 1: warehouse_geofence_layout.png
# Full warehouse layout with all zone types and AGV fleet
# =============================================================
fig, ax = plt.subplots(figsize=(14, 9))
ax.set_facecolor("#ECEFF1")
fig.patch.set_facecolor("#FAFAFA")

fig.suptitle("Warehouse AGV/AMR Geofence Layout — Zone-Based Navigation",
             fontsize=14, fontweight='bold', color=DARK, y=0.99)

# Warehouse boundary 200m x 100m
warehouse = FancyBboxPatch((0, 0), 200, 100, boxstyle="square,pad=0",
                            facecolor="#F5F5F5", edgecolor="#212121",
                            linewidth=3, zorder=1)
ax.add_patch(warehouse)

# Support columns
for cx, cy in [(15, 15), (15, 75), (185, 15), (185, 75),
               (100, 15), (100, 75)]:
    col = FancyBboxPatch((cx - 2, cy - 2), 4, 4, boxstyle="square,pad=0",
                          facecolor="#424242", edgecolor="#212121",
                          linewidth=1, zorder=5)
    ax.add_patch(col)

# Loading docks
for dx, dy, dw, dh, lbl in [(25, 0, 20, 8, "DOCK A"), (70, 0, 20, 8, "DOCK B")]:
    dock = FancyBboxPatch((dx, dy), dw, dh, boxstyle="square,pad=0",
                           facecolor="#1565C0", edgecolor="#0D47A1",
                           linewidth=1.5, alpha=0.85, zorder=4)
    ax.add_patch(dock)
    ax.text(dx + dw / 2, dy + dh / 2, lbl, ha='center', va='center',
            fontsize=7, color='white', fontweight='bold', zorder=6)

# No-go zones
for nx, ny, nw, nh, lbl in [(3, 58, 28, 38, "NO-GO\nZONE A"),
                              (169, 58, 28, 38, "NO-GO\nZONE B")]:
    nogo = FancyBboxPatch((nx, ny), nw, nh, boxstyle="square,pad=0",
                           facecolor="#FFCDD2", edgecolor="#B71C1C",
                           linewidth=2, hatch="///", alpha=0.85, zorder=3)
    ax.add_patch(nogo)
    ax.text(nx + nw / 2, ny + nh / 2, lbl, ha='center', va='center',
            fontsize=7.5, color='#B71C1C', fontweight='bold', zorder=6)

# Slow zones (pedestrian crossings)
for sx, sy, sw, sh in [(38, 0, 9, 58), (120, 30, 9, 70)]:
    slow = FancyBboxPatch((sx, sy), sw, sh, boxstyle="square,pad=0",
                           facecolor="#FFF176", edgecolor="#F9A825",
                           linewidth=1.5, hatch="---", alpha=0.85, zorder=3)
    ax.add_patch(slow)
    ax.text(sx + sw / 2, sy + sh / 2, "SLOW\nZONE", ha='center', va='center',
            fontsize=6.5, color='#F57F17', fontweight='bold',
            rotation=90, zorder=6)

# AGV operating zone
agv_zone = FancyBboxPatch((50, 5), 115, 52, boxstyle="square,pad=0",
                           facecolor="#C8E6C9", edgecolor="#2E7D32",
                           linewidth=2.5, alpha=0.55, zorder=2)
ax.add_patch(agv_zone)
ax.text(107, 31, "AGV OPERATING ZONE", ha='center', va='center',
        fontsize=9.5, color='#1B5E20', fontweight='bold', zorder=6)

# Charging stations
for chx, chy in [(65, 88), (107, 88), (149, 88)]:
    ch = Circle((chx, chy), 5, facecolor="#FF6F00", edgecolor="#E65100",
                linewidth=1.5, zorder=5, alpha=0.9)
    ax.add_patch(ch)
    ax.text(chx, chy, "E", ha='center', va='center',
            fontsize=10, color='white', fontweight='bold', zorder=7)

# Parking areas
for px, py, pw, ph in [(52, 63, 18, 11), (97, 63, 18, 11), (142, 63, 18, 11)]:
    park = FancyBboxPatch((px, py), pw, ph, boxstyle="square,pad=0",
                           facecolor="#CE93D8", edgecolor="#6A1B9A",
                           linewidth=1.5, alpha=0.75, zorder=3)
    ax.add_patch(park)
    ax.text(px + pw / 2, py + ph / 2, "PARK", ha='center', va='center',
            fontsize=6.5, color='#4A148C', fontweight='bold', zorder=6)

# Path network (dashed lines)
paths = [
    ([50, 165], [31, 31]),    # Main east-west aisle
    ([50, 165], [53, 53]),    # Upper east-west
    ([107, 107], [5, 63]),    # North-south main
    ([60, 60], [5, 57]),      # Western N-S
    ([150, 150], [5, 57]),    # Eastern N-S
]
for px, py in paths:
    ax.plot(px, py, color="#546E7A", linewidth=1.8, linestyle='--',
            alpha=0.7, zorder=4)

# AGV positions
agv_data = [
    (68,  22, "#F44336", "A-01"),
    (88,  40, "#2196F3", "A-02"),
    (112, 16, "#4CAF50", "A-03"),
    (133, 35, "#FF9800", "A-04"),
    (80,  25, "#9C27B0", "A-05"),
    (155, 18, "#00BCD4", "A-06"),
]
for agv_x, agv_y, ac, alabel in agv_data:
    ax.plot(agv_x, agv_y, marker="^", markersize=13, color=ac,
            markeredgecolor="white", markeredgewidth=1.2, zorder=8)
    ax.text(agv_x + 2, agv_y + 4, alabel, fontsize=6.5, color=ac,
            fontweight='bold', zorder=8)

# Legend
legend_elements = [
    mpatches.Patch(facecolor="#F5F5F5", edgecolor="#212121", lw=2,
                   label="Warehouse boundary"),
    mpatches.Patch(facecolor="#1565C0", label="Loading dock"),
    mpatches.Patch(facecolor="#FFCDD2", edgecolor="#B71C1C", hatch="///",
                   label="No-go zone"),
    mpatches.Patch(facecolor="#FFF176", edgecolor="#F9A825", hatch="---",
                   label="Slow / pedestrian zone"),
    mpatches.Patch(facecolor="#C8E6C9", edgecolor="#2E7D32",
                   label="AGV operating zone"),
    mpatches.Patch(facecolor="#FF6F00", label="Charging station"),
    mpatches.Patch(facecolor="#CE93D8", edgecolor="#6A1B9A",
                   label="Parking area"),
    mpatches.Patch(facecolor="#424242", label="Support column"),
    plt.Line2D([0], [0], marker="^", color="w", markerfacecolor="#2196F3",
               markersize=10, label="AGV position"),
    plt.Line2D([0], [0], color="#546E7A", lw=1.8, linestyle='--',
               label="Guide path network"),
]
ax.legend(handles=legend_elements, loc="lower right", fontsize=7.5,
          framealpha=0.95, ncol=2, title="Zone Legend", title_fontsize=9,
          edgecolor="#BDBDBD")

ax.set_xlim(-5, 205)
ax.set_ylim(-5, 108)
ax.set_xlabel("X — East (meters)", fontsize=10)
ax.set_ylabel("Y — North (meters)", fontsize=10)
ax.set_aspect("equal")
ax.grid(True, linestyle='--', linewidth=0.4, alpha=0.4, color="#90A4AE")
ax.tick_params(labelsize=9)

# North arrow
ax.annotate("", xy=(200, 105), xytext=(200, 96),
            arrowprops=dict(arrowstyle="-|>", color="black", lw=2.5))
ax.text(200, 106.5, "N", ha='center', va='bottom', fontsize=11,
        fontweight='bold', color='black')

fig.tight_layout()
fig.savefig("images/warehouse_geofence_layout.png", dpi=150, bbox_inches='tight')
plt.close(fig)
print("Saved: images/warehouse_geofence_layout.png")


# =============================================================
# IMAGE 2: path_deviation_analysis.png
# Planned vs actual AGV path + Hausdorff deviation
# =============================================================
fig, axes = plt.subplots(1, 2, figsize=(14, 7))
fig.patch.set_facecolor(BG)
fig.suptitle("AGV Path Deviation Analysis — Actual vs Planned Route",
             fontsize=14, fontweight='bold', color=DARK, y=0.98)

# Planned path (smooth)
t = np.linspace(0, 1, 200)
plan_x = t * 160 + 20
plan_y = 50 + 20 * np.sin(t * np.pi * 2)

# Actual path (with noise / deviation)
rng2 = np.random.default_rng(42)
noise_x = rng2.normal(0, 2.5, 200)
noise_y = rng2.normal(0, 3.5, 200)
actual_x = plan_x + noise_x + 5 * np.sin(t * np.pi * 6)
actual_y = plan_y + noise_y + 8 * np.sin(t * np.pi * 3.5) * (t > 0.4)

# LEFT: Path comparison
ax = axes[0]
ax.set_facecolor("#ECEFF1")
ax.set_title("Planned vs Actual Path\n(Hausdorff distance metric)",
             fontsize=11, fontweight='bold', color=DARK, pad=8)

# Warehouse outline
wh = FancyBboxPatch((5, 5), 190, 90, boxstyle="square,pad=0",
                     facecolor="#F5F5F5", edgecolor="#90A4AE",
                     linewidth=1.5, alpha=0.5, zorder=1)
ax.add_patch(wh)

ax.plot(plan_x, plan_y, color="#1565C0", linewidth=2.5, label="Planned path",
        zorder=4)
ax.plot(actual_x, actual_y, color="#D32F2F", linewidth=2, linestyle='-',
        alpha=0.85, label="Actual path", zorder=3)

# Show Hausdorff deviation arrows at worst points
worst_idx = np.argmax(np.sqrt((plan_x - actual_x) ** 2 + (plan_y - actual_y) ** 2))
ax.annotate("", xy=(actual_x[worst_idx], actual_y[worst_idx]),
            xytext=(plan_x[worst_idx], plan_y[worst_idx]),
            arrowprops=dict(arrowstyle="<->", color="#FF6F00", lw=2.5))
ax.text((plan_x[worst_idx] + actual_x[worst_idx]) / 2 + 3,
        (plan_y[worst_idx] + actual_y[worst_idx]) / 2,
        f"Max deviation\n{np.sqrt((plan_x[worst_idx]-actual_x[worst_idx])**2 + (plan_y[worst_idx]-actual_y[worst_idx])**2):.1f}m",
        fontsize=8, color='#E65100', fontweight='bold',
        bbox=dict(boxstyle='round', fc='white', ec='#FF6F00', alpha=0.9))

# Fill deviation band
ax.fill_between(plan_x, plan_y - 10, plan_y + 10, alpha=0.08,
                color="#1565C0", label="±10m tolerance")
ax.axhline(50, color='gray', linestyle=':', linewidth=1, alpha=0.5)

ax.set_xlim(0, 200)
ax.set_ylim(0, 105)
ax.set_xlabel("X — East (m)", fontsize=10)
ax.set_ylabel("Y — North (m)", fontsize=10)
ax.legend(fontsize=9, loc='upper right', framealpha=0.9)
ax.grid(True, linestyle='--', alpha=0.4)
ax.set_aspect('equal')
ax.tick_params(labelsize=8)

# RIGHT: Deviation distribution
ax = axes[1]
ax.set_facecolor(BG)
ax.set_title("Deviation Distribution Along Path\n(Safety alert threshold = 10m)",
             fontsize=11, fontweight='bold', color=DARK, pad=8)

deviations = np.sqrt((plan_x - actual_x) ** 2 + (plan_y - actual_y) ** 2)
time_pct = np.linspace(0, 100, 200)

ax.plot(time_pct, deviations, color="#1565C0", linewidth=2, label="Deviation (m)")
ax.fill_between(time_pct, deviations, alpha=0.15, color="#1565C0")
ax.axhline(10, color="#D32F2F", linewidth=2, linestyle='--',
           label="Safety threshold (10m)")
ax.axhline(5, color="#FF9800", linewidth=1.5, linestyle='--',
           label="Warning threshold (5m)")

# Highlight exceedances
exc_mask = deviations > 10
ax.fill_between(time_pct, deviations, 10, where=exc_mask,
                alpha=0.35, color="#D32F2F", label="Safety violation zone")

n_exc = exc_mask.sum()
ax.text(0.98, 0.95, f"Violations: {n_exc}/{len(deviations)} ({100*n_exc/len(deviations):.1f}%)",
        transform=ax.transAxes, ha='right', va='top', fontsize=9,
        color='#B71C1C', fontweight='bold',
        bbox=dict(boxstyle='round', fc='#FFCDD2', ec='#B71C1C', lw=1.5))

ax.set_xlabel("Path Progress (%)", fontsize=10)
ax.set_ylabel("Deviation from Planned Path (m)", fontsize=10)
ax.legend(fontsize=9, loc='upper left', framealpha=0.9)
ax.grid(True, linestyle='--', alpha=0.4)
ax.tick_params(labelsize=9)
ax.set_xlim(0, 100)
ax.set_ylim(0, max(deviations) * 1.15)

fig.tight_layout(pad=2)
fig.savefig("images/path_deviation_analysis.png", dpi=150, bbox_inches='tight')
plt.close(fig)
print("Saved: images/path_deviation_analysis.png")


# =============================================================
# IMAGE 3: zone_dwell_heatmap.png
# AGV dwell time heatmap + coverage analysis
# =============================================================
fig, axes = plt.subplots(1, 2, figsize=(14, 7))
fig.patch.set_facecolor(BG)
fig.suptitle("AGV Dwell Time Analytics & Coverage Heatmap",
             fontsize=14, fontweight='bold', color=DARK, y=0.98)

# Simulate telemetry positions
n_pts = 500
# Heavy traffic near loading docks & charging stations
pts_x = np.concatenate([
    rng.uniform(20, 50, 150),   # Loading dock area
    rng.uniform(55, 165, 200),  # Main operating zone
    rng.uniform(60, 155, 100),  # Charging area
    rng.uniform(5, 200, 50),    # Scattered
])
pts_y = np.concatenate([
    rng.uniform(5, 30, 150),
    rng.uniform(10, 60, 200),
    rng.uniform(78, 96, 100),
    rng.uniform(5, 95, 50),
])

# LEFT: 2D histogram heatmap
ax = axes[0]
ax.set_facecolor("#212121")
ax.set_title("AGV Position Heatmap\n(telemetry density = dwell time proxy)",
             fontsize=11, fontweight='bold', color=DARK, pad=8)

h, xe, ye = np.histogram2d(pts_x, pts_y, bins=[20, 12],
                             range=[[0, 200], [0, 100]])
im = ax.imshow(h.T, origin='lower', extent=[0, 200, 0, 100],
               cmap='hot', aspect='equal', interpolation='bilinear')

# Overlay zone outlines
# No-go
for nx, ny, nw, nh in [(3, 58, 28, 38), (169, 58, 28, 38)]:
    rect = FancyBboxPatch((nx, ny), nw, nh, boxstyle="square,pad=0",
                           facecolor='none', edgecolor='#EF5350',
                           linewidth=2.5, linestyle='--', zorder=4)
    ax.add_patch(rect)

# AGV zone
rect2 = FancyBboxPatch((50, 5), 115, 52, boxstyle="square,pad=0",
                        facecolor='none', edgecolor='#69F0AE',
                        linewidth=2, linestyle='-', alpha=0.7, zorder=4)
ax.add_patch(rect2)

ax.set_xlabel("X — East (m)", fontsize=10)
ax.set_ylabel("Y — North (m)", fontsize=10)
ax.tick_params(labelsize=8)
cbar = fig.colorbar(im, ax=ax, fraction=0.038, pad=0.02)
cbar.set_label("Telemetry density (dwell proxy)", fontsize=8.5)
cbar.ax.tick_params(labelsize=7.5)

ax.plot([], [], color='#EF5350', lw=2.5, ls='--', label='No-go zone boundary')
ax.plot([], [], color='#69F0AE', lw=2, label='AGV operating zone')
ax.legend(fontsize=8, loc='upper right', framealpha=0.8,
          facecolor='#333333', labelcolor='white', edgecolor='gray')

# RIGHT: Per-zone dwell time bar chart
ax = axes[1]
ax.set_facecolor(BG)
ax.set_title("Average Dwell Time per Zone\n(bottleneck identification)",
             fontsize=11, fontweight='bold', color=DARK, pad=8)

zone_names = ["Loading\nDock A", "Loading\nDock B", "AGV\nOperating",
              "Charging\nStation 1", "Charging\nStation 2",
              "Charging\nStation 3", "Parking\nArea 1", "Parking\nArea 2"]
dwell_times = [18.5, 15.2, 3.1, 22.7, 19.4, 8.3, 12.1, 10.8]  # minutes
bar_colors_dw = ["#D32F2F" if d > 18 else "#FF9800" if d > 10 else "#1B5E20"
                 for d in dwell_times]

x_pos = np.arange(len(zone_names))
bars = ax.bar(x_pos, dwell_times, color=bar_colors_dw, edgecolor='white',
              linewidth=1.5, width=0.65, zorder=3)
ax.axhline(15, color="#D32F2F", linestyle='--', linewidth=1.5,
           label="Bottleneck threshold (15 min)", alpha=0.8)

for bar, val in zip(bars, dwell_times):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
            f"{val:.1f}m", ha='center', fontsize=8.5, fontweight='bold',
            color=DARK, zorder=5)

ax.set_xticks(x_pos)
ax.set_xticklabels(zone_names, fontsize=8, rotation=0)
ax.set_ylabel("Average Dwell Time (minutes)", fontsize=10)
ax.grid(axis='y', linestyle='--', alpha=0.4)
ax.legend(fontsize=9, framealpha=0.9)
ax.tick_params(labelsize=8)

bottlenecks = [z for z, d in zip(zone_names, dwell_times) if d > 15]
ax.text(0.5, 0.04, f"Bottlenecks: {', '.join(b.replace(chr(10), ' ') for b in bottlenecks)}",
        transform=ax.transAxes, ha='center', fontsize=8.5, color='#B71C1C',
        fontweight='bold',
        bbox=dict(boxstyle='round', fc='#FFCDD2', ec='#B71C1C', lw=1.5))

legend_patches_dw = [
    mpatches.Patch(facecolor="#D32F2F", label="Bottleneck (>18 min)"),
    mpatches.Patch(facecolor="#FF9800", label="Warning (10-18 min)"),
    mpatches.Patch(facecolor="#1B5E20", label="Normal (<10 min)"),
]
ax.legend(handles=legend_patches_dw, loc='upper right', fontsize=8.5,
          framealpha=0.9)

fig.tight_layout(pad=2)
fig.savefig("images/zone_dwell_heatmap.png", dpi=150, bbox_inches='tight')
plt.close(fig)
print("Saved: images/zone_dwell_heatmap.png")

print("\nAll images generated in images/")
