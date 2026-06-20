"""
01_warehouse_map_creation.py
============================
Author: Emmanuel Oyekanlu — Principal Data Engineer

PURPOSE:
    Build a digital twin of a Corning-style warehouse facility using Shapely
    Polygon geometry and GeoPandas GeoDataFrames. This is the foundational
    spatial layer upon which all AGV/AMR geofencing logic is built.

WAREHOUSE SPECS:
    - Footprint: 200m (east-west) × 100m (north-south)
    - Local coordinate origin: southwest corner at (0, 0)
    - Units: meters (using a metric CRS — EPSG:32617 UTM Zone 17N)
    - Structural features:
        * 4 interior support columns (circular obstacles for robot nav)
        * 2 loading docks on the south wall
        * 1 fire exit zone on the east wall

PRODUCTION CONTEXT:
    At Corning Inc., this warehouse map was stored as a versioned GeoJSON
    in S3. Robot navigation software consumed this file to define the
    "universe" of navigable space. Any structural change (new column,
    equipment relocation) triggered a map update workflow in Airflow.
"""

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from shapely.geometry import Polygon, Point, MultiPolygon
from shapely.affinity import translate
import json
import os

# ---------------------------------------------------------------------------
# SECTION 1: Warehouse Boundary
# ---------------------------------------------------------------------------

# The warehouse footprint is a simple rectangle.
# Origin (0,0) is the southwest (bottom-left) corner.
# X-axis runs east; Y-axis runs north.
WAREHOUSE_WIDTH = 200.0   # meters (east-west)
WAREHOUSE_HEIGHT = 100.0  # meters (north-south)

warehouse_boundary = Polygon([
    (0, 0),                              # SW corner
    (WAREHOUSE_WIDTH, 0),                # SE corner
    (WAREHOUSE_WIDTH, WAREHOUSE_HEIGHT), # NE corner
    (0, WAREHOUSE_HEIGHT),               # NW corner
    (0, 0)                               # close ring
])

print(f"Warehouse area: {warehouse_boundary.area:.0f} m²  "
      f"({warehouse_boundary.area / 1000:.1f} km²)")
print(f"Warehouse perimeter: {warehouse_boundary.length:.0f} m")

# ---------------------------------------------------------------------------
# SECTION 2: Structural Features
# ---------------------------------------------------------------------------

# --- Support Columns ---
# Four square columns, 1.5m × 1.5m, placed at structural load points.
# In robot navigation, columns are "hard obstacles" — no-entry zones.
# Positions are their southwest corners.
column_positions = [
    (45, 35),    # Column A — SW quadrant
    (45, 65),    # Column B — NW quadrant
    (155, 35),   # Column C — SE quadrant
    (155, 65),   # Column D — NE quadrant
]
COLUMN_SIZE = 1.5  # meters

def make_column(x, y, size=COLUMN_SIZE):
    """Create a square column polygon with SW corner at (x, y)."""
    return Polygon([
        (x, y),
        (x + size, y),
        (x + size, y + size),
        (x, y + size),
        (x, y)
    ])

columns = [make_column(cx, cy) for cx, cy in column_positions]
column_labels = ["Column_A", "Column_B", "Column_C", "Column_D"]

# --- Loading Docks ---
# Two recessed bays on the south wall (y=0).
# Each dock is 6m wide × 4m deep (protruding inward from south wall).
# In practice, trucks dock on the exterior; the interior polygon is the
# buffer zone where AGVs queue to pick up/drop off pallets.
dock_positions = [
    (60, 0),    # Loading Dock 1 — western bay
    (130, 0),   # Loading Dock 2 — eastern bay
]
DOCK_WIDTH = 6.0   # meters
DOCK_DEPTH = 4.0   # meters (extends inward from south wall)

def make_loading_dock(x, y, width=DOCK_WIDTH, depth=DOCK_DEPTH):
    """Create a loading dock rectangle along the south wall."""
    return Polygon([
        (x, y),
        (x + width, y),
        (x + width, y + depth),
        (x, y + depth),
        (x, y)
    ])

docks = [make_loading_dock(dx, dy) for dx, dy in dock_positions]
dock_labels = ["Loading_Dock_1", "Loading_Dock_2"]

# --- Fire Exit Zone ---
# Emergency egress area on the east wall. AGVs must not block this zone.
# Defined as a 10m × 8m buffer zone adjacent to the east wall.
fire_exit = Polygon([
    (190, 40),
    (200, 40),
    (200, 60),
    (190, 60),
    (190, 40)
])

# ---------------------------------------------------------------------------
# SECTION 3: Assemble GeoDataFrame
# ---------------------------------------------------------------------------

# Build lists for GeoDataFrame construction
all_geometries = [warehouse_boundary] + columns + docks + [fire_exit]
all_feature_ids = (
    ["warehouse_boundary"]
    + column_labels
    + dock_labels
    + ["fire_exit_zone"]
)
all_feature_types = (
    ["warehouse_boundary"]
    + ["support_column"] * 4
    + ["loading_dock"] * 2
    + ["fire_exit_zone"]
)
all_descriptions = (
    ["Main warehouse footprint 200m x 100m"]
    + [f"Structural load-bearing column {lbl[-1]}" for lbl in column_labels]
    + ["Loading dock bay for pallet truck access"] * 2
    + ["Emergency fire exit — AGV exclusion zone"]
)

warehouse_gdf = gpd.GeoDataFrame(
    {
        "feature_id":   all_feature_ids,
        "feature_type": all_feature_types,
        "description":  all_descriptions,
    },
    geometry=all_geometries,
    # EPSG:32617 = WGS 84 / UTM Zone 17N
    # This is the appropriate projected CRS for Corning, NY (western NY state).
    # Using a projected CRS gives us true metric distances and areas.
    crs="EPSG:32617"
)

print("\n--- Warehouse GeoDataFrame ---")
print(warehouse_gdf[["feature_id", "feature_type"]].to_string())
print(f"\nCRS: {warehouse_gdf.crs}")
print(f"Total features: {len(warehouse_gdf)}")

# Compute area for each feature (in m²)
warehouse_gdf["area_m2"] = warehouse_gdf.geometry.area
print("\nFeature areas:")
print(warehouse_gdf[["feature_id", "area_m2"]].to_string())

# ---------------------------------------------------------------------------
# SECTION 4: Export to GeoJSON
# ---------------------------------------------------------------------------

os.makedirs("data", exist_ok=True)

# GeoJSON spec (RFC 7946) requires WGS84 (EPSG:4326).
# We reproject for export, then keep the metric GDF for local operations.
warehouse_gdf_wgs84 = warehouse_gdf.to_crs("EPSG:4326")
output_path = "data/warehouse_layout.geojson"
warehouse_gdf_wgs84.to_file(output_path, driver="GeoJSON")
print(f"\nExported: {output_path}")
print(f"File size: {os.path.getsize(output_path):,} bytes")

# ---------------------------------------------------------------------------
# SECTION 5: Visualization
# ---------------------------------------------------------------------------

fig, ax = plt.subplots(1, 1, figsize=(16, 9))
ax.set_aspect("equal")
ax.set_facecolor("#f5f5f0")  # light cream — mimics floor plan look

# Draw warehouse boundary
x_bnd, y_bnd = warehouse_boundary.exterior.xy
ax.fill(x_bnd, y_bnd, color="#e8e8d8", zorder=1, label="Warehouse floor")
ax.plot(x_bnd, y_bnd, color="#333333", linewidth=2.5, zorder=2)

# Draw support columns
for col_geom, col_label in zip(columns, column_labels):
    xc, yc = col_geom.exterior.xy
    ax.fill(xc, yc, color="#555555", zorder=3)
    cx, cy = col_geom.centroid.x, col_geom.centroid.y
    ax.text(cx, cy, col_label[-1], ha="center", va="center",
            color="white", fontsize=7, fontweight="bold", zorder=4)

# Draw loading docks
for dock_geom, dock_label in zip(docks, dock_labels):
    xd, yd = dock_geom.exterior.xy
    ax.fill(xd, yd, color="#4a90d9", alpha=0.7, zorder=3)
    ax.plot(xd, yd, color="#2255aa", linewidth=1.5, zorder=4)
    dcx, dcy = dock_geom.centroid.x, dock_geom.centroid.y
    ax.text(dcx, dcy + 0.5, dock_label.replace("_", "\n"),
            ha="center", va="bottom", fontsize=7, color="#1a3366",
            fontweight="bold", zorder=5)

# Draw fire exit zone
xf, yf = fire_exit.exterior.xy
ax.fill(xf, yf, color="#ff4444", alpha=0.6, zorder=3, label="Fire exit zone")
ax.plot(xf, yf, color="#cc0000", linewidth=2, zorder=4)
ax.text(195, 50, "FIRE\nEXIT", ha="center", va="center",
        color="#cc0000", fontsize=8, fontweight="bold", zorder=5)

# Annotations
ax.annotate("N", xy=(5, 92), fontsize=18, fontweight="bold", color="#333")
ax.annotate("", xy=(5, 98), xytext=(5, 90),
            arrowprops=dict(arrowstyle="->", lw=2, color="#333"))

# Dimension arrows
ax.annotate("", xy=(200, -8), xytext=(0, -8),
            arrowprops=dict(arrowstyle="<->", lw=1.5, color="#666"))
ax.text(100, -10, "200 m", ha="center", va="top", fontsize=10, color="#666")

ax.annotate("", xy=(-8, 100), xytext=(-8, 0),
            arrowprops=dict(arrowstyle="<->", lw=1.5, color="#666"))
ax.text(-12, 50, "100 m", ha="right", va="center", fontsize=10,
        color="#666", rotation=90)

# Grid lines (every 20m)
for x in range(0, 201, 20):
    ax.axvline(x=x, color="#cccccc", linewidth=0.5, linestyle="--", zorder=0)
for y in range(0, 101, 20):
    ax.axhline(y=y, color="#cccccc", linewidth=0.5, linestyle="--", zorder=0)

ax.set_xlim(-15, 215)
ax.set_ylim(-15, 110)
ax.set_xlabel("X (meters East)", fontsize=11)
ax.set_ylabel("Y (meters North)", fontsize=11)
ax.set_title(
    "Corning Inc. Warehouse — Structural Layout\n"
    "AGV/AMR Geofencing Foundation Map | Emmanuel Oyekanlu",
    fontsize=13, fontweight="bold"
)

legend_elements = [
    mpatches.Patch(facecolor="#e8e8d8", edgecolor="#333", label="Warehouse floor"),
    mpatches.Patch(facecolor="#555555", label="Support columns"),
    mpatches.Patch(facecolor="#4a90d9", alpha=0.7, label="Loading docks"),
    mpatches.Patch(facecolor="#ff4444", alpha=0.6, label="Fire exit zone"),
]
ax.legend(handles=legend_elements, loc="upper left", fontsize=9)

plt.tight_layout()
plt.savefig("warehouse_layout.png", dpi=150, bbox_inches="tight")
print("\nPlot saved: warehouse_layout.png")
plt.show()

print("\n=== Script 01 Complete ===")
print("Generated: data/warehouse_layout.geojson, warehouse_layout.png")
