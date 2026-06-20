"""
05_path_vs_planned_analysis.py
==============================
Author: Emmanuel Oyekanlu — Principal Data Engineer

PURPOSE:
    Compare an AGV's actual traveled path against its planned reference path.
    This is a key quality metric in AGV fleet management — excessive deviation
    indicates sensor drift, floor obstruction, calibration issues, or
    unexpected manual intervention.

METRICS COMPUTED:
    1. Hausdorff Distance: The maximum of the minimum distances between
       two geometry sets. Intuitively: the worst-case deviation anywhere
       along the route. Used as the primary "path deviation" KPI.

    2. Buffer Tolerance Check: Create a ±tolerance buffer around the
       planned path. Count what % of actual positions fall inside.
       Corning's spec: 95% of positions must be within 0.75m of plan.

    3. Path Length Comparison: Actual vs planned distance traveled.
       Excess distance = inefficient routing.

    4. Maximum Point Deviation: For each actual position, find the
       nearest point on the planned path. Report distribution of deviations.

PRODUCTION CONTEXT:
    This analysis ran nightly as an Airflow task. Results were written to
    a Delta Lake table. Robots consistently exceeding the Hausdorff threshold
    were flagged for physical maintenance (wheel alignment, sensor recal).
"""

import numpy as np
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from shapely.geometry import LineString, Point, MultiPoint
from shapely.ops import nearest_points
import os

np.random.seed(7)

# ---------------------------------------------------------------------------
# SECTION 1: Define Planned Path (Reference Route)
# ---------------------------------------------------------------------------

# Planned route for AGV-003:
# Start at east arterial south end -> cross-aisle -> dock approach -> return
PLANNED_WAYPOINTS = [
    (150, 50),   # Start: east arterial center
    (150, 35),   # Move south on east arterial
    (150, 20),   # South cross-aisle junction
    (133, 20),   # Turn west on south cross-aisle
    (133, 8),    # Dock approach begins
    (133, 2),    # Dock face — stop point
]

planned_path = LineString(PLANNED_WAYPOINTS)
print(f"Planned path length: {planned_path.length:.2f} m")
print(f"Planned waypoints: {len(PLANNED_WAYPOINTS)}")

# ---------------------------------------------------------------------------
# SECTION 2: Simulate Actual Traveled Path
# ---------------------------------------------------------------------------

# The actual path has realistic deviations:
# - Small navigation errors (±0.3m typical)
# - A larger deviation in the middle (AGV avoided a misplaced pallet)
# - Slight undershoot at dock face

def interpolate_path(waypoints, n_points_per_segment=15):
    """
    Densify a path by interpolating n_points_per_segment between each waypoint pair.
    This gives us a realistic position log with frequent telemetry readings.
    """
    all_points = []
    for i in range(len(waypoints) - 1):
        p1 = np.array(waypoints[i])
        p2 = np.array(waypoints[i + 1])
        t_vals = np.linspace(0, 1, n_points_per_segment, endpoint=(i == len(waypoints) - 2))
        segment_points = [p1 + t * (p2 - p1) for t in t_vals]
        all_points.extend(segment_points)
    return all_points

# Generate densified planned path points
planned_points_dense = interpolate_path(PLANNED_WAYPOINTS, n_points_per_segment=12)

# Create actual path by adding realistic noise + a detour
actual_points = []
for i, pt in enumerate(planned_points_dense):
    base_noise = np.random.normal(0, 0.25, 2)  # 0.25m std normal noise

    # Simulate larger detour between waypoints 2-3 (south cross-aisle)
    # The AGV swung wide to avoid a parked forklift
    progress = i / len(planned_points_dense)
    if 0.35 < progress < 0.55:
        # Additional 2m deviation southward (y decreasing)
        detour_offset = np.array([0, -2.5 * np.sin(np.pi * (progress - 0.35) / 0.20)])
    else:
        detour_offset = np.array([0, 0])

    actual_x = pt[0] + base_noise[0] + detour_offset[0]
    actual_y = pt[1] + base_noise[1] + detour_offset[1]
    actual_points.append((actual_x, actual_y))

# The AGV undershot the dock face by 0.8m (typical of dock approach slowdown)
actual_points[-1] = (133, 2.8)  # Stopped 0.8m short of dock face

actual_path = LineString(actual_points)
print(f"\nActual path length: {actual_path.length:.2f} m")
print(f"Actual position readings: {len(actual_points)}")

# ---------------------------------------------------------------------------
# SECTION 3: Compute Path Deviation Metrics
# ---------------------------------------------------------------------------

# --- Metric 1: Hausdorff Distance ---
# shapely's hausdorff_distance gives the directed version.
# True Hausdorff = max(directed_hausdorff(A,B), directed_hausdorff(B,A))
hausdorff_forward = planned_path.hausdorff_distance(actual_path)
hausdorff_reverse = actual_path.hausdorff_distance(planned_path)
hausdorff_dist = max(hausdorff_forward, hausdorff_reverse)

print(f"\n=== Path Deviation Metrics ===")
print(f"Hausdorff Distance: {hausdorff_dist:.3f} m")

# --- Metric 2: Buffer Tolerance Check ---
TOLERANCE_M = 0.75  # 75cm tolerance buffer (Corning spec)

planned_buffer = planned_path.buffer(TOLERANCE_M)
actual_gdf = gpd.GeoDataFrame(
    {"pt_id": range(len(actual_points))},
    geometry=[Point(p) for p in actual_points],
    crs="EPSG:32617"
)

within_buffer = actual_gdf.geometry.within(planned_buffer)
pct_within = within_buffer.mean() * 100
n_outside = (~within_buffer).sum()

print(f"Tolerance buffer: ±{TOLERANCE_M} m")
print(f"Points within buffer: {within_buffer.sum()} / {len(actual_points)} "
      f"({pct_within:.1f}%)")
print(f"Points OUTSIDE buffer: {n_outside}")

# --- Metric 3: Per-Point Deviation Distance ---
deviations = []
for pt_geom in actual_gdf.geometry:
    # nearest_points returns (point_on_planned, point_on_actual)
    nearest_on_plan, _ = nearest_points(planned_path, pt_geom)
    dist = pt_geom.distance(nearest_on_plan)
    deviations.append(dist)

deviations = np.array(deviations)
print(f"\nDeviation statistics (distance from actual to planned path):")
print(f"  Mean:   {deviations.mean():.3f} m")
print(f"  Median: {np.median(deviations):.3f} m")
print(f"  Std:    {deviations.std():.3f} m")
print(f"  Max:    {deviations.max():.3f} m  (same as Hausdorff ≈)")
print(f"  95th pct: {np.percentile(deviations, 95):.3f} m")

# --- Metric 4: Path Length Comparison ---
length_diff = actual_path.length - planned_path.length
length_pct = (length_diff / planned_path.length) * 100
print(f"\nPath Length Comparison:")
print(f"  Planned: {planned_path.length:.2f} m")
print(f"  Actual:  {actual_path.length:.2f} m")
print(f"  Difference: {length_diff:+.2f} m ({length_pct:+.1f}%)")

# ---------------------------------------------------------------------------
# SECTION 4: Analysis Report
# ---------------------------------------------------------------------------

HAUSDORFF_THRESHOLD = 1.0  # Alert if max deviation > 1.0m
BUFFER_THRESHOLD = 95.0    # Alert if <95% within buffer

print("\n" + "="*60)
print("    PATH DEVIATION ANALYSIS REPORT")
print("    AGV-003 | 2024-03-15 Shift | Route: Dock_2_Approach")
print("="*60)

if hausdorff_dist > HAUSDORFF_THRESHOLD:
    print(f"\n[ALERT] Hausdorff distance {hausdorff_dist:.2f}m exceeds "
          f"threshold {HAUSDORFF_THRESHOLD}m")
    print("  -> Possible cause: obstacle avoidance, calibration drift, floor damage")
else:
    print(f"\n[OK] Hausdorff distance {hausdorff_dist:.2f}m within threshold")

if pct_within < BUFFER_THRESHOLD:
    print(f"[ALERT] Only {pct_within:.1f}% of positions within ±{TOLERANCE_M}m buffer "
          f"(threshold: {BUFFER_THRESHOLD}%)")
else:
    print(f"[OK] {pct_within:.1f}% of positions within ±{TOLERANCE_M}m buffer")

print(f"\nRecommendation: {'Schedule maintenance inspection' if hausdorff_dist > HAUSDORFF_THRESHOLD else 'No action required'}")

# ---------------------------------------------------------------------------
# SECTION 5: Visualization
# ---------------------------------------------------------------------------

fig, axes = plt.subplots(1, 2, figsize=(20, 8))

# --- Left plot: Path comparison ---
ax = axes[0]
ax.set_aspect("equal")
ax.set_facecolor("#f5f5f5")

# Draw planned path and buffer
plan_x, plan_y = planned_path.xy
buf_x, buf_y = planned_buffer.exterior.xy
ax.fill(buf_x, buf_y, color="#90EE90", alpha=0.3, zorder=1,
        label=f"Tolerance buffer (±{TOLERANCE_M}m)")
ax.plot(plan_x, plan_y, "b-", linewidth=3, zorder=3,
        label=f"Planned path ({planned_path.length:.1f}m)")
ax.plot(*[c for c in zip(*PLANNED_WAYPOINTS)],
        "b^", markersize=10, zorder=4)

# Draw actual path
act_x = [p[0] for p in actual_points]
act_y = [p[1] for p in actual_points]
ax.plot(act_x, act_y, "r-", linewidth=2, zorder=3, alpha=0.8,
        label=f"Actual path ({actual_path.length:.1f}m)")
ax.plot(act_x, act_y, "r.", markersize=4, zorder=4, alpha=0.5)

# Highlight points outside buffer
outside_pts = actual_gdf[~within_buffer]
if len(outside_pts) > 0:
    ax.scatter(outside_pts.geometry.x, outside_pts.geometry.y,
               c="orange", s=60, zorder=5, label=f"Outside buffer ({n_outside} pts)",
               edgecolors="darkorange", linewidth=1)

# Annotate Hausdorff point (approximate)
max_dev_idx = np.argmax(deviations)
max_pt = actual_points[max_dev_idx]
ax.annotate(f"Max deviation\n{deviations.max():.2f}m",
            xy=max_pt, xytext=(max_pt[0] - 5, max_pt[1] - 4),
            arrowprops=dict(arrowstyle="->", color="red"),
            fontsize=9, color="red", fontweight="bold")

ax.set_xlabel("X (meters)", fontsize=11)
ax.set_ylabel("Y (meters)", fontsize=11)
ax.set_title("Planned vs Actual AGV Path\n"
             f"Hausdorff = {hausdorff_dist:.2f}m | {pct_within:.1f}% within buffer",
             fontsize=11, fontweight="bold")
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)

# --- Right plot: Deviation distribution histogram ---
ax2 = axes[1]
ax2.hist(deviations, bins=20, color="#4a90d9", edgecolor="white",
         alpha=0.8, label="Deviation distribution")
ax2.axvline(TOLERANCE_M, color="green", linewidth=2, linestyle="--",
            label=f"Tolerance: {TOLERANCE_M}m")
ax2.axvline(deviations.mean(), color="orange", linewidth=2, linestyle="-",
            label=f"Mean: {deviations.mean():.2f}m")
ax2.axvline(hausdorff_dist, color="red", linewidth=2, linestyle="-.",
            label=f"Hausdorff: {hausdorff_dist:.2f}m")

ax2.set_xlabel("Deviation from Planned Path (meters)", fontsize=11)
ax2.set_ylabel("Number of Position Readings", fontsize=11)
ax2.set_title("Path Deviation Distribution\nAGV-003 | 2024-03-15",
              fontsize=11, fontweight="bold")
ax2.legend(fontsize=9)
ax2.grid(True, alpha=0.3)

plt.suptitle("AGV-003 Path Deviation Analysis — Emmanuel Oyekanlu",
             fontsize=13, fontweight="bold", y=1.01)
plt.tight_layout()
plt.savefig("path_deviation_analysis.png", dpi=150, bbox_inches="tight")
print("\nPlot saved: path_deviation_analysis.png")
plt.show()

print("\n=== Script 05 Complete ===")
