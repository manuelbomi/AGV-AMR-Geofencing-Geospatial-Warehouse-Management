"""
02_geofence_zone_definition.py
==============================
Author: Emmanuel Oyekanlu — Principal Data Engineer

PURPOSE:
    Define all operational geofence zones within the warehouse. Each zone is
    a Shapely Polygon with associated metadata: zone type, speed limit, and
    priority level. This GeoDataFrame becomes the lookup table for real-time
    zone checking (Script 04).

ZONE TAXONOMY (from Corning's AGV safety specification):
    - agv_operating_zone:  General AGV travel corridor (max 2.0 m/s)
    - charging_station:    Battery recharge areas (AGVs queue here at 0.3 m/s)
    - no_go_zone:          Hard exclusion — active machinery, hazardous equipment
    - slow_zone:           Pedestrian crossing areas (max 0.5 m/s)
    - parking_area:        Robot staging while waiting for tasks (0.0 m/s)
    - loading_dock_zone:   Coordination buffer at dock bays (0.5 m/s)

SPEED LIMITS (m/s):
    - no_go_zone:          0.0  (prohibited)
    - parking_area:        0.0  (stationary)
    - slow_zone:           0.5  (pedestrian safe)
    - loading_dock_zone:   0.5  (dock coordination)
    - charging_station:    0.3  (approach speed)
    - agv_operating_zone:  2.0  (normal operation)
"""

import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from shapely.geometry import Polygon
import os

# ---------------------------------------------------------------------------
# SECTION 1: Define Zone Polygons
# All coordinates in local warehouse space: (0,0) = SW corner
# Warehouse: 200m W-E × 100m S-N
# ---------------------------------------------------------------------------

zones = []

# --- 1. Main AGV Operating Zone ---
# The large central corridor. This is the primary travel space.
# Excludes walls (5m buffer), dock approach areas, and machinery zones.
zones.append({
    "zone_id": "Z01",
    "zone_type": "agv_operating_zone",
    "zone_name": "Main AGV Corridor",
    "speed_limit_mps": 2.0,
    "priority": 3,
    "geometry": Polygon([
        (10, 10),
        (190, 10),
        (190, 90),
        (10, 90),
        (10, 10)
    ])
})

# --- 2. Charging Station 1 (Northwest corner) ---
# AGVs with <20% battery route here autonomously.
# Slow approach speed enforced in this zone.
zones.append({
    "zone_id": "Z02",
    "zone_type": "charging_station",
    "zone_name": "Charging_Station_West",
    "speed_limit_mps": 0.3,
    "priority": 5,
    "geometry": Polygon([
        (10, 75),
        (35, 75),
        (35, 90),
        (10, 90),
        (10, 75)
    ])
})

# --- 3. Charging Station 2 (Northeast corner) ---
zones.append({
    "zone_id": "Z03",
    "zone_type": "charging_station",
    "zone_name": "Charging_Station_East",
    "speed_limit_mps": 0.3,
    "priority": 5,
    "geometry": Polygon([
        (165, 75),
        (190, 75),
        (190, 90),
        (165, 90),
        (165, 75)
    ])
})

# --- 4. No-Go Zone 1 (Heavy machinery — central-west area) ---
# CNC grinding equipment. Robot entry is a hard safety violation.
zones.append({
    "zone_id": "Z04",
    "zone_type": "no_go_zone",
    "zone_name": "Machinery_Zone_A",
    "speed_limit_mps": 0.0,
    "priority": 1,  # Highest priority — overrides all other zones
    "geometry": Polygon([
        (15, 40),
        (40, 40),
        (40, 65),
        (15, 65),
        (15, 40)
    ])
})

# --- 5. No-Go Zone 2 (High-voltage electrical cabinet — east wall) ---
zones.append({
    "zone_id": "Z05",
    "zone_type": "no_go_zone",
    "zone_name": "Electrical_Cabinet_Zone",
    "speed_limit_mps": 0.0,
    "priority": 1,
    "geometry": Polygon([
        (185, 15),
        (195, 15),
        (195, 35),
        (185, 35),
        (185, 15)
    ])
})

# --- 6. Slow Zone 1 (Pedestrian crossing — main north aisle) ---
zones.append({
    "zone_id": "Z06",
    "zone_type": "slow_zone",
    "zone_name": "Pedestrian_Crossing_N",
    "speed_limit_mps": 0.5,
    "priority": 2,
    "geometry": Polygon([
        (90, 82),
        (110, 82),
        (110, 92),
        (90, 92),
        (90, 82)
    ])
})

# --- 7. Slow Zone 2 (Pedestrian crossing — central east-west aisle) ---
zones.append({
    "zone_id": "Z07",
    "zone_type": "slow_zone",
    "zone_name": "Pedestrian_Crossing_Mid",
    "speed_limit_mps": 0.5,
    "priority": 2,
    "geometry": Polygon([
        (90, 45),
        (110, 45),
        (110, 55),
        (90, 55),
        (90, 45)
    ])
})

# --- 8. Slow Zone 3 (Pedestrian crossing — south entrance) ---
zones.append({
    "zone_id": "Z08",
    "zone_type": "slow_zone",
    "zone_name": "Pedestrian_Crossing_S",
    "speed_limit_mps": 0.5,
    "priority": 2,
    "geometry": Polygon([
        (90, 10),
        (110, 10),
        (110, 20),
        (90, 20),
        (90, 10)
    ])
})

# --- 9. Parking Area 1 (Robot staging — northwest) ---
# Robots wait here between task assignments.
zones.append({
    "zone_id": "Z09",
    "zone_type": "parking_area",
    "zone_name": "Staging_Area_West",
    "speed_limit_mps": 0.0,
    "priority": 4,
    "geometry": Polygon([
        (10, 10),
        (40, 10),
        (40, 35),
        (10, 35),
        (10, 10)
    ])
})

# --- 10. Parking Area 2 (Robot staging — northeast) ---
zones.append({
    "zone_id": "Z10",
    "zone_type": "parking_area",
    "zone_name": "Staging_Area_East",
    "speed_limit_mps": 0.0,
    "priority": 4,
    "geometry": Polygon([
        (160, 10),
        (190, 10),
        (190, 35),
        (160, 35),
        (160, 10)
    ])
})

# --- 11. Loading Dock Zone (both dock bays + approach corridor) ---
# Covers dock approach area. AGVs coordinate with dock scheduler here.
zones.append({
    "zone_id": "Z11",
    "zone_type": "loading_dock_zone",
    "zone_name": "Dock_Approach_Zone",
    "speed_limit_mps": 0.5,
    "priority": 2,
    "geometry": Polygon([
        (50, 0),
        (150, 0),
        (150, 15),
        (50, 15),
        (50, 0)
    ])
})

# ---------------------------------------------------------------------------
# SECTION 2: Build GeoDataFrame
# ---------------------------------------------------------------------------

gdf_zones = gpd.GeoDataFrame(
    [{k: v for k, v in z.items() if k != "geometry"} for z in zones],
    geometry=[z["geometry"] for z in zones],
    crs="EPSG:32617"
)

# Compute zone areas for reference
gdf_zones["area_m2"] = gdf_zones.geometry.area

print("=== AGV Geofence Zones ===")
print(gdf_zones[["zone_id", "zone_type", "zone_name",
                  "speed_limit_mps", "priority", "area_m2"]].to_string())
print(f"\nTotal zones defined: {len(gdf_zones)}")
print(f"Zone types: {gdf_zones['zone_type'].value_counts().to_dict()}")

# Verify all zones are within warehouse boundary
from shapely.geometry import box
warehouse_box = box(0, 0, 200, 100)
outside = gdf_zones[~gdf_zones.geometry.within(warehouse_box)]
if len(outside) > 0:
    print(f"\nWARNING: {len(outside)} zones extend outside warehouse boundary!")
    print(outside[["zone_id", "zone_name"]])
else:
    print("\nValidation: All zones are within warehouse boundary. ✓")

# ---------------------------------------------------------------------------
# SECTION 3: Export to GeoJSON
# ---------------------------------------------------------------------------

os.makedirs("data", exist_ok=True)
gdf_zones_wgs84 = gdf_zones.to_crs("EPSG:4326")
output_path = "data/agv_zones.geojson"
gdf_zones_wgs84.to_file(output_path, driver="GeoJSON")
print(f"\nExported: {output_path}")

# ---------------------------------------------------------------------------
# SECTION 4: Color-Coded Visualization
# ---------------------------------------------------------------------------

# Define colors for each zone type
ZONE_COLORS = {
    "agv_operating_zone":  "#d4edda",  # light green
    "charging_station":    "#fff3cd",  # light yellow
    "no_go_zone":          "#f8d7da",  # light red
    "slow_zone":           "#ffeeba",  # light orange
    "parking_area":        "#d1ecf1",  # light blue
    "loading_dock_zone":   "#e2d9f3",  # light purple
}

ZONE_EDGE_COLORS = {
    "agv_operating_zone":  "#28a745",
    "charging_station":    "#ffc107",
    "no_go_zone":          "#dc3545",
    "slow_zone":           "#fd7e14",
    "parking_area":        "#17a2b8",
    "loading_dock_zone":   "#6610f2",
}

fig, ax = plt.subplots(1, 1, figsize=(18, 10))
ax.set_aspect("equal")
ax.set_facecolor("#f8f8f8")

# Draw warehouse outline
from shapely.geometry import Polygon as ShapelyPolygon
wh_x, wh_y = [0, 200, 200, 0, 0], [0, 0, 100, 100, 0]
ax.fill(wh_x, wh_y, color="#eeeeee", zorder=0)
ax.plot(wh_x, wh_y, color="#222222", linewidth=3, zorder=1)

# Draw each zone
for _, row in gdf_zones.iterrows():
    geom = row.geometry
    x_coords, y_coords = geom.exterior.xy
    z_type = row["zone_type"]
    fill_color = ZONE_COLORS.get(z_type, "#dddddd")
    edge_color = ZONE_EDGE_COLORS.get(z_type, "#666666")

    ax.fill(x_coords, y_coords, color=fill_color, alpha=0.75,
            zorder=2, linewidth=0)
    ax.plot(x_coords, y_coords, color=edge_color, linewidth=2, zorder=3)

    # Label each zone
    cx = geom.centroid.x
    cy = geom.centroid.y
    ax.text(cx, cy + 0.5, row["zone_id"], ha="center", va="center",
            fontsize=7.5, fontweight="bold", color=edge_color, zorder=4)
    ax.text(cx, cy - 2.5, f"{row['speed_limit_mps']} m/s",
            ha="center", va="center", fontsize=6.5, color="#444444", zorder=4)

# Legend
legend_patches = [
    mpatches.Patch(facecolor=ZONE_COLORS[zt], edgecolor=ZONE_EDGE_COLORS[zt],
                   linewidth=1.5, label=zt.replace("_", " ").title())
    for zt in ZONE_COLORS
]
ax.legend(handles=legend_patches, loc="upper right", fontsize=9,
          title="Zone Types", title_fontsize=10)

# Grid
for gx in range(0, 201, 20):
    ax.axvline(x=gx, color="#cccccc", lw=0.5, ls="--", zorder=0)
for gy in range(0, 101, 20):
    ax.axhline(y=gy, color="#cccccc", lw=0.5, ls="--", zorder=0)

ax.set_xlim(-5, 210)
ax.set_ylim(-5, 108)
ax.set_xlabel("X (meters East)", fontsize=11)
ax.set_ylabel("Y (meters North)", fontsize=11)
ax.set_title(
    "Corning Inc. Warehouse — AGV/AMR Geofence Zone Map\n"
    "Color-coded by zone type | Speed limits shown | Emmanuel Oyekanlu",
    fontsize=13, fontweight="bold"
)

plt.tight_layout()
plt.savefig("agv_zones_map.png", dpi=150, bbox_inches="tight")
print("Plot saved: agv_zones_map.png")
plt.show()

print("\n=== Script 02 Complete ===")
print("Generated: data/agv_zones.geojson, agv_zones_map.png")
