"""
04_position_zone_checker.py
===========================
Author: Emmanuel Oyekanlu — Principal Data Engineer

PURPOSE:
    Core geofencing logic: for each incoming AGV position reading, determine
    which zone the vehicle is in and flag any safety violations.

    This is the HEART of the geofencing system. At Corning, this logic ran
    as a Python microservice consuming from a Kafka topic of robot telemetry.
    Each event looked like: {"agv_id": "AGV-003", "x": 145.2, "y": 62.1,
    "timestamp": "2024-03-15T14:23:01.552Z", "speed_mps": 1.8}

APPROACH:
    - Simulate 50 AGV position readings across 5 vehicles (10 readings each)
    - Use geopandas.sjoin() for efficient spatial join (point-in-polygon)
    - Flag positions in no_go_zones as violations
    - Generate a summary report per AGV

WHY SPATIAL JOIN vs MANUAL CHECKING:
    Naive approach: for each position, loop through all zones and call
    zone.contains(point). That's O(positions × zones) with Python loops.

    Spatial join with an R-tree index: GeoPandas builds a spatial index
    internally. Zone lookup is O(positions × log(zones)) — dramatically
    faster for large robot fleets and high-frequency telemetry.

SIMULATION:
    AGV positions are randomly sampled from the warehouse space.
    We intentionally place some points near no_go_zone boundaries
    to simulate realistic violation scenarios.
"""

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from shapely.geometry import Point
from datetime import datetime, timedelta
import os

np.random.seed(42)  # Reproducibility

# ---------------------------------------------------------------------------
# SECTION 1: Load Zone GeoDataFrame
# ---------------------------------------------------------------------------

zones_path = "data/agv_zones.geojson"
if not os.path.exists(zones_path):
    raise FileNotFoundError(
        "zones file not found — run 02_geofence_zone_definition.py first"
    )

gdf_zones = gpd.read_file(zones_path).to_crs("EPSG:32617")

print("=== Zone GeoDataFrame Loaded ===")
print(f"Zones loaded: {len(gdf_zones)}")
print(gdf_zones[["zone_id", "zone_type", "zone_name"]].to_string())

# ---------------------------------------------------------------------------
# SECTION 2: Simulate AGV Position Telemetry
# ---------------------------------------------------------------------------

AGV_IDS = ["AGV-001", "AGV-002", "AGV-003", "AGV-004", "AGV-005"]
N_READINGS_PER_AGV = 10
BASE_TIME = datetime(2024, 3, 15, 8, 0, 0)  # Shift start

records = []

# Predefined route positions for each AGV to ensure realistic movement
# and intentional boundary violations for AGV-004
AGV_ROUTES = {
    "AGV-001": [  # Traveling north on west arterial
        (50, 20), (50, 35), (50, 50), (50, 65), (50, 80),
        (22, 82), (22, 82), (50, 80), (50, 65), (50, 50),
    ],
    "AGV-002": [  # Cross-aisle traversal, south to north
        (100, 5), (100, 20), (100, 35), (100, 50), (90, 50),
        (100, 50), (100, 65), (100, 80), (100, 90), (100, 80),
    ],
    "AGV-003": [  # Dock approach and return
        (150, 50), (150, 35), (150, 20), (133, 20), (133, 8),
        (133, 2), (133, 8), (133, 20), (150, 20), (150, 35),
    ],
    "AGV-004": [  # This AGV has a sensor glitch and drifts into no_go_zone!
        (50, 50), (45, 50), (40, 50), (35, 50), (30, 52),
        (25, 55),   # <- VIOLATION: enters Machinery_Zone_A (no_go)
        (20, 58),   # <- VIOLATION: deep in no_go zone
        (30, 52),   # Recovering...
        (40, 50), (50, 50),
    ],
    "AGV-005": [  # Charging run
        (150, 80), (177, 80), (177, 82), (177, 82), (177, 82),
        (177, 82), (177, 82), (177, 80), (150, 80), (150, 65),
    ],
}

reading_id = 0
for agv_id in AGV_IDS:
    route = AGV_ROUTES[agv_id]
    for i, (x, y) in enumerate(route):
        # Add small jitter to simulate real GPS/LiDAR noise (±0.3m)
        x_jitter = x + np.random.uniform(-0.3, 0.3)
        y_jitter = y + np.random.uniform(-0.3, 0.3)

        timestamp = BASE_TIME + timedelta(seconds=reading_id * 5)
        speed = np.random.uniform(0.3, 2.0)

        records.append({
            "reading_id": reading_id,
            "agv_id": agv_id,
            "timestamp": timestamp,
            "x": round(x_jitter, 3),
            "y": round(y_jitter, 3),
            "speed_mps": round(speed, 2),
        })
        reading_id += 1

df_positions = pd.DataFrame(records)
print(f"\n=== Simulated AGV Telemetry: {len(df_positions)} readings ===")
print(df_positions.head(10).to_string())

# ---------------------------------------------------------------------------
# SECTION 3: Convert to GeoDataFrame (Points)
# ---------------------------------------------------------------------------

gdf_positions = gpd.GeoDataFrame(
    df_positions,
    geometry=gpd.points_from_xy(df_positions["x"], df_positions["y"]),
    crs="EPSG:32617"
)

# ---------------------------------------------------------------------------
# SECTION 4: Spatial Join — Determine Zone for Each Position
# ---------------------------------------------------------------------------

# sjoin: "inner" keeps only points that fall within a zone polygon.
# "left" keeps all points (those outside any zone get NaN zone columns).
# We use "left" to also capture positions in unzoned areas.

gdf_joined = gpd.sjoin(
    gdf_positions,
    gdf_zones[["zone_id", "zone_type", "zone_name",
               "speed_limit_mps", "priority", "geometry"]],
    how="left",
    predicate="within"
)

# If a point falls in multiple overlapping zones, sjoin returns multiple rows.
# Take the highest-priority zone (lowest priority number = most critical).
# Priority 1 = no_go (highest enforcement), Priority 5 = charging (informational)
gdf_joined_dedup = (
    gdf_joined
    .sort_values("priority", ascending=True)  # Priority 1 first
    .drop_duplicates(subset=["reading_id"], keep="first")  # Keep highest priority
    .reset_index(drop=True)
)

# Rename joined columns for clarity
gdf_joined_dedup = gdf_joined_dedup.rename(columns={
    "zone_id": "current_zone_id",
    "zone_type": "current_zone_type",
    "zone_name": "current_zone_name",
    "speed_limit_mps": "zone_speed_limit",
})

# Fill unzoned positions
gdf_joined_dedup["current_zone_type"] = (
    gdf_joined_dedup["current_zone_type"].fillna("unzoned")
)
gdf_joined_dedup["current_zone_name"] = (
    gdf_joined_dedup["current_zone_name"].fillna("outside_any_zone")
)
gdf_joined_dedup["zone_speed_limit"] = (
    gdf_joined_dedup["zone_speed_limit"].fillna(0.0)
)

# ---------------------------------------------------------------------------
# SECTION 5: Flag Violations
# ---------------------------------------------------------------------------

# Violation Type 1: AGV entered a no_go_zone
gdf_joined_dedup["is_no_go_violation"] = (
    gdf_joined_dedup["current_zone_type"] == "no_go_zone"
)

# Violation Type 2: AGV exceeding zone speed limit
gdf_joined_dedup["is_speed_violation"] = (
    (gdf_joined_dedup["speed_mps"] > gdf_joined_dedup["zone_speed_limit"])
    & (gdf_joined_dedup["zone_speed_limit"] > 0)
    & (gdf_joined_dedup["current_zone_type"] != "unzoned")
)

# Any violation
gdf_joined_dedup["has_violation"] = (
    gdf_joined_dedup["is_no_go_violation"] | gdf_joined_dedup["is_speed_violation"]
)

print("\n=== Zone Assignment Results (first 15 rows) ===")
display_cols = ["reading_id", "agv_id", "x", "y",
                "current_zone_type", "current_zone_name",
                "is_no_go_violation", "is_speed_violation"]
print(gdf_joined_dedup[display_cols].head(15).to_string())

# ---------------------------------------------------------------------------
# SECTION 6: Violation Report
# ---------------------------------------------------------------------------

print("\n" + "="*60)
print("    AGV ZONE VIOLATION REPORT")
print("    Corning Inc. Warehouse — Shift 2024-03-15 08:00")
print("="*60)

# No-go violations
no_go_violations = gdf_joined_dedup[gdf_joined_dedup["is_no_go_violation"]]
if len(no_go_violations) > 0:
    print(f"\n[CRITICAL] NO-GO ZONE VIOLATIONS: {len(no_go_violations)}")
    print("-" * 50)
    for _, vrow in no_go_violations.iterrows():
        print(f"  AGV: {vrow['agv_id']}  |  "
              f"Time: {vrow['timestamp'].strftime('%H:%M:%S')}  |  "
              f"Position: ({vrow['x']:.1f}, {vrow['y']:.1f})  |  "
              f"Zone: {vrow['current_zone_name']}")
else:
    print("\n[OK] No no-go zone violations detected.")

# Speed violations
speed_violations = gdf_joined_dedup[gdf_joined_dedup["is_speed_violation"]]
if len(speed_violations) > 0:
    print(f"\n[WARNING] SPEED LIMIT VIOLATIONS: {len(speed_violations)}")
    print("-" * 50)
    for _, vrow in speed_violations.iterrows():
        print(f"  AGV: {vrow['agv_id']}  |  "
              f"Speed: {vrow['speed_mps']:.2f} m/s  |  "
              f"Limit: {vrow['zone_speed_limit']:.1f} m/s  |  "
              f"Zone: {vrow['current_zone_name']}")

# Summary table per AGV
print("\n=== Per-AGV Summary ===")
summary = (
    gdf_joined_dedup
    .groupby("agv_id")
    .agg(
        total_readings=("reading_id", "count"),
        no_go_violations=("is_no_go_violation", "sum"),
        speed_violations=("is_speed_violation", "sum"),
        zones_visited=("current_zone_type", lambda x: x.nunique()),
        avg_speed_mps=("speed_mps", "mean"),
    )
    .reset_index()
)
summary["violation_rate_pct"] = (
    (summary["no_go_violations"] + summary["speed_violations"])
    / summary["total_readings"] * 100
).round(1)

print(summary.to_string(index=False))

# ---------------------------------------------------------------------------
# SECTION 7: Visualization
# ---------------------------------------------------------------------------

fig, ax = plt.subplots(1, 1, figsize=(18, 10))
ax.set_aspect("equal")
ax.set_facecolor("#f8f8f8")

# Draw warehouse
wh_x = [0, 200, 200, 0, 0]
wh_y = [0, 0, 100, 100, 0]
ax.fill(wh_x, wh_y, color="#eeeeee", zorder=0)
ax.plot(wh_x, wh_y, color="#333333", linewidth=2, zorder=1)

# Draw no_go zones in red
for _, zrow in gdf_zones[gdf_zones["zone_type"] == "no_go_zone"].iterrows():
    zx, zy = zrow.geometry.exterior.xy
    ax.fill(zx, zy, color="#ffcccc", alpha=0.7, zorder=1)
    ax.plot(zx, zy, color="#cc0000", linewidth=2, zorder=2)

# Draw positions color-coded by AGV
AGV_COLORS = {
    "AGV-001": "#2196F3",
    "AGV-002": "#4CAF50",
    "AGV-003": "#FF9800",
    "AGV-004": "#9C27B0",
    "AGV-005": "#00BCD4",
}

for agv_id, agv_group in gdf_joined_dedup.groupby("agv_id"):
    color = AGV_COLORS[agv_id]
    ax.scatter(agv_group["x"], agv_group["y"],
               c=color, s=40, zorder=4, alpha=0.7, label=agv_id)

    # Connect positions with a line showing the route
    xs = agv_group["x"].tolist()
    ys = agv_group["y"].tolist()
    ax.plot(xs, ys, color=color, linewidth=1, alpha=0.4, zorder=3)

# Highlight violations with red X markers
if len(no_go_violations) > 0:
    ax.scatter(no_go_violations["x"], no_go_violations["y"],
               c="red", s=150, marker="X", zorder=6,
               label="No-Go Violation", edgecolors="darkred", linewidth=1.5)

ax.set_xlim(-5, 210)
ax.set_ylim(-5, 108)
ax.set_xlabel("X (meters East)", fontsize=11)
ax.set_ylabel("Y (meters North)", fontsize=11)
ax.set_title(
    "Corning Inc. Warehouse — AGV Position Tracking & Zone Violations\n"
    f"50 readings | {len(no_go_violations)} no-go violations (red X) | Emmanuel Oyekanlu",
    fontsize=12, fontweight="bold"
)
ax.legend(fontsize=9, loc="upper right")

plt.tight_layout()
plt.savefig("position_zone_check.png", dpi=150, bbox_inches="tight")
print("\nPlot saved: position_zone_check.png")
plt.show()

print("\n=== Script 04 Complete ===")
