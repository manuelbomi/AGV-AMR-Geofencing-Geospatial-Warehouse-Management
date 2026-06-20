"""
06_dwell_time_and_coverage.py
=============================
Author: Emmanuel Oyekanlu — Principal Data Engineer

PURPOSE:
    Analyze AGV operational patterns from position telemetry:
    1. DWELL TIME: How much time does each AGV spend in each zone?
       Identifies bottleneck zones where robots wait excessively.
    2. COVERAGE HEAT MAP: Which areas of the warehouse are most frequently
       visited? Reveals traffic hotspots and dead zones.
    3. BOTTLENECK IDENTIFICATION: Zones with highest total dwell time
       indicate scheduling inefficiency or physical congestion.

BUSINESS VALUE:
    At Corning, this analysis directly informed:
    - Charging station placement (robots were spending too long traveling to chargers)
    - Dock coordination improvements (3 robots queuing at same dock = bottleneck)
    - Path network redesign (adding a dedicated return lane cut transit time 18%)

SIMULATION DESIGN:
    200 position readings across 5 AGVs over an 8-hour shift.
    Readings are 30 seconds apart (realistic telemetry frequency).
    Positions follow realistic patterns: traveling, queuing, docking.
"""

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from shapely.geometry import Point, box
import os

np.random.seed(99)

# ---------------------------------------------------------------------------
# SECTION 1: Generate Extended Position Log
# ---------------------------------------------------------------------------

from datetime import datetime, timedelta

AGV_IDS = ["AGV-001", "AGV-002", "AGV-003", "AGV-004", "AGV-005"]
SHIFT_START = datetime(2024, 3, 15, 6, 0, 0)
TELEMETRY_INTERVAL_SEC = 30  # One reading every 30 seconds
SHIFT_DURATION_HOURS = 8
READINGS_PER_AGV = int(SHIFT_DURATION_HOURS * 3600 / TELEMETRY_INTERVAL_SEC)  # = 960

# Simplified waypoint sequences representing robot behaviors over the shift
def generate_agv_trajectory(agv_id, n_readings, seed_offset=0):
    """
    Generate a realistic trajectory for one AGV over a shift.
    The robot cycles between: travel -> work zone -> dock approach -> staging
    """
    rng = np.random.default_rng(42 + seed_offset)

    # Define behavioral states and approximate warehouse locations
    states = {
        "traveling_N":    {"x_range": (45, 55), "y_range": (10, 90)},
        "traveling_E":    {"x_range": (50, 150), "y_range": (48, 52)},
        "at_dock":        {"x_range": (60, 140), "y_range": (0, 12)},
        "at_charger_W":   {"x_range": (10, 35), "y_range": (75, 92)},
        "at_charger_E":   {"x_range": (165, 190), "y_range": (75, 92)},
        "at_staging_W":   {"x_range": (10, 40), "y_range": (10, 35)},
        "at_staging_E":   {"x_range": (160, 190), "y_range": (10, 35)},
        "in_slow_zone":   {"x_range": (88, 112), "y_range": (44, 57)},
    }

    # Each AGV has a different typical behavioral mix
    state_probs = {
        "AGV-001": [0.30, 0.15, 0.10, 0.25, 0.00, 0.15, 0.00, 0.05],
        "AGV-002": [0.20, 0.20, 0.15, 0.00, 0.20, 0.00, 0.20, 0.05],
        "AGV-003": [0.25, 0.15, 0.25, 0.00, 0.10, 0.00, 0.15, 0.10],
        "AGV-004": [0.30, 0.20, 0.10, 0.15, 0.00, 0.20, 0.00, 0.05],
        "AGV-005": [0.15, 0.25, 0.20, 0.10, 0.00, 0.00, 0.20, 0.10],
    }

    state_names = list(states.keys())
    probs = state_probs.get(agv_id, [1/len(states)] * len(states))

    records = []
    current_state = rng.choice(state_names, p=probs)
    state_remaining = rng.integers(10, 40)  # Readings in current state

    for i in range(n_readings):
        if state_remaining <= 0:
            current_state = rng.choice(state_names, p=probs)
            state_remaining = rng.integers(10, 40)

        s = states[current_state]
        x = rng.uniform(s["x_range"][0], s["x_range"][1])
        y = rng.uniform(s["y_range"][0], s["y_range"][1])

        # Add positional noise (sensor jitter)
        x += rng.normal(0, 0.15)
        y += rng.normal(0, 0.15)

        # Clamp to warehouse bounds
        x = np.clip(x, 0, 200)
        y = np.clip(y, 0, 100)

        timestamp = SHIFT_START + timedelta(seconds=i * TELEMETRY_INTERVAL_SEC)
        records.append({
            "agv_id": agv_id,
            "timestamp": timestamp,
            "x": round(float(x), 3),
            "y": round(float(y), 3),
            "behavior_state": current_state,
            "reading_seq": i,
        })
        state_remaining -= 1

    return records

all_records = []
for offset, agv_id in enumerate(AGV_IDS):
    traj = generate_agv_trajectory(agv_id, READINGS_PER_AGV, seed_offset=offset * 100)
    all_records.extend(traj)

df_log = pd.DataFrame(all_records)
df_log = df_log.sort_values(["agv_id", "timestamp"]).reset_index(drop=True)

print(f"=== Position Log Generated ===")
print(f"Total readings: {len(df_log):,}")
print(f"AGVs: {df_log['agv_id'].nunique()}")
print(f"Time range: {df_log['timestamp'].min()} → {df_log['timestamp'].max()}")
print(f"Readings per AGV: {df_log.groupby('agv_id').size().to_dict()}")

# ---------------------------------------------------------------------------
# SECTION 2: Load Zones and Perform Spatial Join
# ---------------------------------------------------------------------------

zones_path = "data/agv_zones.geojson"
if not os.path.exists(zones_path):
    raise FileNotFoundError("Run 02_geofence_zone_definition.py first")

gdf_zones = gpd.read_file(zones_path).to_crs("EPSG:32617")

gdf_log = gpd.GeoDataFrame(
    df_log,
    geometry=gpd.points_from_xy(df_log["x"], df_log["y"]),
    crs="EPSG:32617"
)

# Spatial join: assign zone to each position
gdf_joined = gpd.sjoin(
    gdf_log,
    gdf_zones[["zone_id", "zone_type", "zone_name", "geometry"]],
    how="left",
    predicate="within"
)

# Deduplicate: if in overlapping zones, keep highest-priority (lowest priority int)
# For simplicity here, just keep first match
gdf_joined = (
    gdf_joined
    .sort_values("zone_id")
    .drop_duplicates(subset=["agv_id", "timestamp"], keep="first")
)

gdf_joined["zone_name"] = gdf_joined["zone_name"].fillna("transit_corridor")
gdf_joined["zone_type"] = gdf_joined["zone_type"].fillna("unzoned")

# ---------------------------------------------------------------------------
# SECTION 3: Dwell Time Analysis
# ---------------------------------------------------------------------------

# Each reading represents TELEMETRY_INTERVAL_SEC seconds of dwell time
INTERVAL_SEC = TELEMETRY_INTERVAL_SEC

dwell_by_agv_zone = (
    gdf_joined
    .groupby(["agv_id", "zone_name"])
    .size()
    .reset_index(name="reading_count")
)
dwell_by_agv_zone["dwell_seconds"] = dwell_by_agv_zone["reading_count"] * INTERVAL_SEC
dwell_by_agv_zone["dwell_minutes"] = dwell_by_agv_zone["dwell_seconds"] / 60

print("\n=== Dwell Time by AGV and Zone (minutes) ===")
pivot_dwell = dwell_by_agv_zone.pivot_table(
    index="zone_name", columns="agv_id",
    values="dwell_minutes", aggfunc="sum", fill_value=0
)
# Add total column
pivot_dwell["TOTAL"] = pivot_dwell.sum(axis=1)
pivot_dwell = pivot_dwell.sort_values("TOTAL", ascending=False)
print(pivot_dwell.round(1).to_string())

# Bottleneck zones: highest total dwell time
print("\n=== TOP 5 BOTTLENECK ZONES (Total dwell time, all AGVs) ===")
zone_totals = dwell_by_agv_zone.groupby("zone_name")["dwell_minutes"].sum()
zone_totals = zone_totals.sort_values(ascending=False)
for rank, (zone, minutes) in enumerate(zone_totals.head(5).items(), 1):
    hours = minutes // 60
    mins = minutes % 60
    print(f"  #{rank}: {zone:<35} {hours:.0f}h {mins:.0f}m total")

# ---------------------------------------------------------------------------
# SECTION 4: Coverage Heat Map
# ---------------------------------------------------------------------------

# Divide warehouse into 2m × 2m grid cells
CELL_SIZE = 2.0  # meters
X_CELLS = int(200 / CELL_SIZE)  # = 100 columns
Y_CELLS = int(100 / CELL_SIZE)  # = 50 rows

# Count readings per grid cell
x_bins = np.arange(0, 200 + CELL_SIZE, CELL_SIZE)
y_bins = np.arange(0, 100 + CELL_SIZE, CELL_SIZE)

heat_map, xedges, yedges = np.histogram2d(
    gdf_log["x"], gdf_log["y"],
    bins=[x_bins, y_bins]
)

# heat_map shape: (100, 50) — X cells × Y cells
# For matplotlib imshow we need shape (Y, X) and transpose
heat_map_display = heat_map.T  # Now shape (50, 100) for correct orientation

print(f"\n=== Coverage Heat Map ===")
print(f"Grid: {X_CELLS} × {Y_CELLS} cells at {CELL_SIZE}m resolution")
total_cells = X_CELLS * Y_CELLS
visited_cells = (heat_map > 0).sum()
coverage_pct = visited_cells / total_cells * 100
print(f"Total cells: {total_cells:,}")
print(f"Cells visited: {visited_cells:,} ({coverage_pct:.1f}% coverage)")
print(f"Max readings in any cell: {heat_map.max():.0f}")
print(f"Mean readings in visited cells: {heat_map[heat_map > 0].mean():.1f}")

# ---------------------------------------------------------------------------
# SECTION 5: Visualization — Combined Figure
# ---------------------------------------------------------------------------

fig = plt.figure(figsize=(22, 14))

# --- Plot 1: Coverage Heat Map ---
ax1 = fig.add_subplot(2, 2, (1, 2))  # Spans top row
im = ax1.imshow(
    heat_map_display,
    extent=[0, 200, 0, 100],
    origin="lower",
    cmap="hot",
    aspect="auto",
    interpolation="bilinear"
)
plt.colorbar(im, ax=ax1, label="Position readings per 2m² cell", shrink=0.8)
ax1.set_xlabel("X (meters East)", fontsize=11)
ax1.set_ylabel("Y (meters North)", fontsize=11)
ax1.set_title(
    f"Warehouse Coverage Heat Map — 8h Shift | 5 AGVs | "
    f"{coverage_pct:.1f}% floor coverage\n"
    "Emmanuel Oyekanlu — Corning Inc. AGV Analytics",
    fontsize=12, fontweight="bold"
)

# Draw warehouse boundary overlay
wh_x = [0, 200, 200, 0, 0]
wh_y = [0, 0, 100, 100, 0]
ax1.plot(wh_x, wh_y, "white", linewidth=2.5, zorder=5)

# --- Plot 2: Dwell Time by Zone (Bar Chart) ---
ax2 = fig.add_subplot(2, 2, 3)
zone_totals_plot = zone_totals.head(8)
colors_bar = plt.cm.RdYlGn_r(np.linspace(0.1, 0.9, len(zone_totals_plot)))
bars = ax2.barh(
    range(len(zone_totals_plot)),
    zone_totals_plot.values,
    color=colors_bar, edgecolor="white", linewidth=0.5
)
ax2.set_yticks(range(len(zone_totals_plot)))
ax2.set_yticklabels([z.replace("_", " ") for z in zone_totals_plot.index],
                     fontsize=9)
ax2.set_xlabel("Total Dwell Time (minutes)", fontsize=10)
ax2.set_title("Top Zones by Total Dwell Time\n(All AGVs, 8h Shift)",
              fontsize=11, fontweight="bold")

# Add value labels on bars
for i, bar in enumerate(bars):
    width = bar.get_width()
    ax2.text(width + 2, bar.get_y() + bar.get_height() / 2,
             f"{width:.0f} min", va="center", fontsize=8)
ax2.grid(axis="x", alpha=0.3)

# --- Plot 3: Dwell Time Breakdown per AGV ---
ax3 = fig.add_subplot(2, 2, 4)

# Stacked bar chart: dwell time by zone for each AGV
top_zones = zone_totals.head(6).index.tolist()
agv_zone_matrix = (
    dwell_by_agv_zone[dwell_by_agv_zone["zone_name"].isin(top_zones)]
    .pivot_table(index="agv_id", columns="zone_name",
                 values="dwell_minutes", fill_value=0)
)

agv_zone_matrix.plot(
    kind="bar", stacked=True, ax=ax3,
    colormap="tab10", edgecolor="white", linewidth=0.5
)
ax3.set_xlabel("AGV", fontsize=10)
ax3.set_ylabel("Dwell Time (minutes)", fontsize=10)
ax3.set_xticklabels(agv_zone_matrix.index, rotation=0, fontsize=9)
ax3.set_title("Dwell Time Distribution per AGV\n(Top 6 zones)",
              fontsize=11, fontweight="bold")
ax3.legend(fontsize=7, loc="upper right",
           title="Zone", title_fontsize=8)
ax3.grid(axis="y", alpha=0.3)

plt.tight_layout(pad=2.0)
plt.savefig("dwell_time_analysis.png", dpi=150, bbox_inches="tight")
print("\nPlot saved: dwell_time_analysis.png")
plt.show()

# ---------------------------------------------------------------------------
# SECTION 6: Export Summary Report
# ---------------------------------------------------------------------------

print("\n=== SHIFT SUMMARY REPORT ===")
print(f"Date: 2024-03-15 | Shift: 06:00 – 14:00")
print(f"Fleet size: {len(AGV_IDS)} AGVs")
print(f"Total telemetry readings: {len(df_log):,}")
print(f"Warehouse coverage: {coverage_pct:.1f}%")
print(f"\nPRIMARY BOTTLENECK: {zone_totals.index[0]}")
print(f"  -> Recommendation: Review scheduling assignments for this zone")
print(f"  -> Consider adding buffer capacity or rebalancing robot workloads")

print("\n=== Script 06 Complete ===")
