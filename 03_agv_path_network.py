"""
03_agv_path_network.py
======================
Author: Emmanuel Oyekanlu — Principal Data Engineer

PURPOSE:
    Define the AGV guide path network as a GeoDataFrame of LineString segments.
    In a physical AGV installation, these paths correspond to:
    - Magnetic tape strips embedded in the floor
    - QR code / RFID waypoint markers
    - Virtual lanes programmed into the fleet management software

    This script also demonstrates spatial intersection queries:
    "Which zones does each path segment pass through?"

PATH NETWORK DESIGN:
    - 2 main north-south arterials (west lane, east lane)
    - 3 east-west cross-aisles (north, center, south)
    - 2 approach paths to loading docks (branching from south aisle)
    - 2 approach paths to charging stations (branching from main aisles)
    - One-way and bidirectional designations for collision avoidance

PRODUCTION CONTEXT:
    At Corning, the path network was maintained as a GeoJSON versioned in Git.
    The fleet management system (FMS) loaded this file at startup and used
    Dijkstra's algorithm on the resulting graph for route planning.
    Path segment IDs were the edge identifiers in the navigation graph.
"""

import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from shapely.geometry import LineString, Point
import os

# ---------------------------------------------------------------------------
# SECTION 1: Define Path Segments as LineStrings
# ---------------------------------------------------------------------------

paths = []

# --- Main North-South Arterials ---

# West arterial: runs from south staging area to north end
# One-way: NORTH-bound traffic only (southbound uses east arterial)
paths.append({
    "path_id": "P01",
    "path_name": "West_Arterial_NB",
    "direction": "one_way",
    "max_speed_mps": 2.0,
    "geometry": LineString([(50, 5), (50, 95)])
})

# East arterial: runs from south staging area to north end
# One-way: SOUTH-bound traffic only
paths.append({
    "path_id": "P02",
    "path_name": "East_Arterial_SB",
    "direction": "one_way",
    "max_speed_mps": 2.0,
    "geometry": LineString([(150, 95), (150, 5)])
})

# Center arterial: bidirectional, passes through center
paths.append({
    "path_id": "P03",
    "path_name": "Center_Arterial_BD",
    "direction": "bidirectional",
    "max_speed_mps": 1.5,
    "geometry": LineString([(100, 5), (100, 95)])
})

# --- East-West Cross Aisles ---

# North cross-aisle: connects west and east arterials near north wall
paths.append({
    "path_id": "P04",
    "path_name": "North_Cross_Aisle",
    "direction": "bidirectional",
    "max_speed_mps": 1.5,
    "geometry": LineString([(50, 80), (100, 80), (150, 80)])
})

# Center cross-aisle: main perpendicular connector
paths.append({
    "path_id": "P05",
    "path_name": "Center_Cross_Aisle",
    "direction": "bidirectional",
    "max_speed_mps": 1.0,  # Slower — passes through pedestrian crossing
    "geometry": LineString([(50, 50), (100, 50), (150, 50)])
})

# South cross-aisle: near dock approach area
paths.append({
    "path_id": "P06",
    "path_name": "South_Cross_Aisle",
    "direction": "bidirectional",
    "max_speed_mps": 1.5,
    "geometry": LineString([(50, 20), (100, 20), (150, 20)])
})

# --- Dock Approach Paths ---
# Branch from south cross-aisle down to dock zones
# One-way inbound (approach from east arteral side)
paths.append({
    "path_id": "P07",
    "path_name": "Dock1_Approach",
    "direction": "one_way",
    "max_speed_mps": 0.5,  # Slow — dock coordination zone
    "geometry": LineString([(63, 20), (63, 8), (63, 2)])
})

paths.append({
    "path_id": "P08",
    "path_name": "Dock2_Approach",
    "direction": "one_way",
    "max_speed_mps": 0.5,
    "geometry": LineString([(133, 20), (133, 8), (133, 2)])
})

# --- Charging Station Approach Paths ---
# Robots leave main arterials to reach chargers
paths.append({
    "path_id": "P09",
    "path_name": "Charger_West_Approach",
    "direction": "bidirectional",
    "max_speed_mps": 0.3,  # Very slow — charger approach
    "geometry": LineString([(50, 80), (22, 80), (22, 82)])
})

paths.append({
    "path_id": "P10",
    "path_name": "Charger_East_Approach",
    "direction": "bidirectional",
    "max_speed_mps": 0.3,
    "geometry": LineString([(150, 80), (177, 80), (177, 82)])
})

# --- Loop connector paths at staging areas ---
paths.append({
    "path_id": "P11",
    "path_name": "West_Staging_Loop",
    "direction": "one_way",
    "max_speed_mps": 0.5,
    "geometry": LineString([(50, 20), (40, 20), (25, 20), (25, 10), (50, 10), (50, 20)])
})

paths.append({
    "path_id": "P12",
    "path_name": "East_Staging_Loop",
    "direction": "one_way",
    "max_speed_mps": 0.5,
    "geometry": LineString([(150, 20), (165, 20), (175, 20), (175, 10), (150, 10), (150, 20)])
})

# ---------------------------------------------------------------------------
# SECTION 2: Build GeoDataFrame
# ---------------------------------------------------------------------------

gdf_paths = gpd.GeoDataFrame(
    [{k: v for k, v in p.items() if k != "geometry"} for p in paths],
    geometry=[p["geometry"] for p in paths],
    crs="EPSG:32617"
)

# Compute path lengths
gdf_paths["length_m"] = gdf_paths.geometry.length

print("=== AGV Path Network ===")
print(gdf_paths[["path_id", "path_name", "direction",
                  "max_speed_mps", "length_m"]].to_string())
print(f"\nTotal path segments: {len(gdf_paths)}")
print(f"Total path network length: {gdf_paths['length_m'].sum():.1f} m")
print(f"Bidirectional paths: {(gdf_paths['direction'] == 'bidirectional').sum()}")
print(f"One-way paths: {(gdf_paths['direction'] == 'one_way').sum()}")

# ---------------------------------------------------------------------------
# SECTION 3: Spatial Intersection — Paths vs Zones
# ---------------------------------------------------------------------------

# Load the zones GeoDataFrame
zones_path = "data/agv_zones.geojson"
if os.path.exists(zones_path):
    gdf_zones = gpd.read_file(zones_path).to_crs("EPSG:32617")

    print("\n=== Path-Zone Intersection Analysis ===")
    print("(Which zones does each path pass through?)\n")

    for _, path_row in gdf_paths.iterrows():
        path_geom = path_row.geometry
        # Find all zones that intersect this path segment
        intersecting = gdf_zones[gdf_zones.geometry.intersects(path_geom)]

        if len(intersecting) > 0:
            zone_names = intersecting["zone_name"].tolist()
            zone_types = intersecting["zone_type"].tolist()

            # Check if any path passes through a no_go_zone
            no_go = intersecting[intersecting["zone_type"] == "no_go_zone"]
            flag = " *** NO-GO VIOLATION ***" if len(no_go) > 0 else ""

            print(f"  {path_row['path_id']} ({path_row['path_name']}):{flag}")
            for zn, zt in zip(zone_names, zone_types):
                print(f"    -> {zt}: {zn}")
        else:
            print(f"  {path_row['path_id']} ({path_row['path_name']}): [no zone intersection]")
else:
    print(f"\nZones file not found at {zones_path}")
    print("Run 02_geofence_zone_definition.py first to generate zones.")

# ---------------------------------------------------------------------------
# SECTION 4: Export to GeoJSON
# ---------------------------------------------------------------------------

os.makedirs("data", exist_ok=True)
gdf_paths_wgs84 = gdf_paths.to_crs("EPSG:4326")
output_path = "data/path_network.geojson"
gdf_paths_wgs84.to_file(output_path, driver="GeoJSON")
print(f"\nExported: {output_path}")

# ---------------------------------------------------------------------------
# SECTION 5: Visualization
# ---------------------------------------------------------------------------

fig, ax = plt.subplots(1, 1, figsize=(18, 10))
ax.set_aspect("equal")
ax.set_facecolor("#1a1a2e")  # Dark background for contrast

# Draw warehouse outline
wh_x = [0, 200, 200, 0, 0]
wh_y = [0, 0, 100, 100, 0]
ax.fill(wh_x, wh_y, color="#16213e", zorder=0)
ax.plot(wh_x, wh_y, color="#e0e0e0", linewidth=2.5, zorder=1)

# Draw zones as subtle overlays (if available)
if os.path.exists(zones_path):
    gdf_zones_local = gpd.read_file(zones_path).to_crs("EPSG:32617")
    zone_alpha_map = {
        "no_go_zone": ("#ff4444", 0.3),
        "slow_zone":  ("#ffaa00", 0.2),
        "charging_station": ("#44ff44", 0.2),
        "parking_area": ("#4444ff", 0.15),
    }
    for _, zrow in gdf_zones_local.iterrows():
        color_alpha = zone_alpha_map.get(zrow["zone_type"], ("#888888", 0.1))
        zx, zy = zrow.geometry.exterior.xy
        ax.fill(zx, zy, color=color_alpha[0], alpha=color_alpha[1], zorder=1)

# Draw path segments
PATH_COLORS = {
    "one_way":       "#00d4ff",   # cyan for one-way
    "bidirectional": "#ffd700",   # gold for bidirectional
}

for _, row in gdf_paths.iterrows():
    geom = row.geometry
    coords = list(geom.coords)
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    color = PATH_COLORS[row["direction"]]
    ax.plot(xs, ys, color=color, linewidth=2.5, zorder=3, solid_capstyle="round")

    # Draw waypoint dots
    for x, y in coords:
        ax.plot(x, y, "o", color=color, markersize=3, zorder=4)

    # Label path ID at midpoint
    midpoint = geom.interpolate(0.5, normalized=True)
    ax.text(midpoint.x + 1, midpoint.y + 1, row["path_id"],
            color=color, fontsize=7, fontweight="bold", zorder=5)

# Arrows for one-way direction indication
for _, row in gdf_paths[gdf_paths["direction"] == "one_way"].iterrows():
    geom = row.geometry
    # Get direction at 60% of path
    p1 = geom.interpolate(0.5, normalized=True)
    p2 = geom.interpolate(0.6, normalized=True)
    ax.annotate(
        "", xy=(p2.x, p2.y), xytext=(p1.x, p1.y),
        arrowprops=dict(arrowstyle="-|>", color="#00d4ff",
                        lw=1.5, mutation_scale=15),
        zorder=6
    )

legend_elements = [
    plt.Line2D([0], [0], color="#00d4ff", lw=2.5, label="One-way path"),
    plt.Line2D([0], [0], color="#ffd700", lw=2.5, label="Bidirectional path"),
    mpatches.Patch(facecolor="#ff4444", alpha=0.3, label="No-Go Zone"),
    mpatches.Patch(facecolor="#ffaa00", alpha=0.2, label="Slow Zone"),
    mpatches.Patch(facecolor="#44ff44", alpha=0.2, label="Charging Station"),
]
ax.legend(handles=legend_elements, loc="upper left", fontsize=9,
          facecolor="#16213e", edgecolor="#888888", labelcolor="white")

ax.set_xlim(-5, 210)
ax.set_ylim(-5, 108)
ax.set_xlabel("X (meters East)", fontsize=11, color="#cccccc")
ax.set_ylabel("Y (meters North)", fontsize=11, color="#cccccc")
ax.tick_params(colors="#cccccc")
ax.set_title(
    "Corning Inc. Warehouse — AGV Guide Path Network\n"
    "Cyan = One-way | Gold = Bidirectional | Emmanuel Oyekanlu",
    fontsize=13, fontweight="bold", color="#ffffff"
)

plt.tight_layout()
plt.savefig("path_network_map.png", dpi=150, bbox_inches="tight",
            facecolor="#1a1a2e")
print("Plot saved: path_network_map.png")
plt.show()

print("\n=== Script 03 Complete ===")
print("Generated: data/path_network.geojson, path_network_map.png")
