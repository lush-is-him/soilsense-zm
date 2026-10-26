# ============================================================
# SoilSense ZM — Phase 1
# extract_kafue.py
#
# What this script does:
#   1. Loads the Zambia district map (gadm41_ZMB.gpkg)
#   2. Extracts Kafue District boundary
#   3. Opens all 7 SoilGrids GeoTIFF files
#   4. Samples 500 points inside Kafue District
#   5. Extracts soil values at each point
#   6. Saves results as kafue_soil_data.csv
#   7. Produces a pH map of Kafue District
#
# Author: Lushomo Sibalwa — 202301072 — ZCAS University
# ============================================================

import os
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.mask import mask
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from shapely.geometry import Point
import warnings
warnings.filterwarnings('ignore')

# ── PATHS ────────────────────────────────────────────────────
TIFF_FOLDER = r"C:\Users\USER\SoilSense ZM\tiff files"
OUTPUT_FOLDER = r"C:\Users\USER\SoilSense ZM"

CSV_OUTPUT = os.path.join(OUTPUT_FOLDER, "kafue_soil_data.csv")
MAP_OUTPUT = os.path.join(OUTPUT_FOLDER, "kafue_pH_map.png")

# ── TIFF FILES ────────────────────────────────────────────────
TIFF_FILES = {
    "pH":   {"file": "phh2o_0-5cm_mean_1000.tif", "scale": 0.1},
    "Clay": {"file": "clay_0-5cm_mean_1000.tif",  "scale": 0.1},
    "Sand": {"file": "sand_0-5cm_mean_1000.tif",  "scale": 0.1},
    "Silt": {"file": "silt_0-5cm_mean_1000.tif",  "scale": 0.1},
    "SOC":  {"file": "soc_0-5cm_mean_1000.tif",   "scale": 0.1},
    "CEC":  {"file": "cec_0-5cm_mean_1000.tif",   "scale": 0.1},
    "BDOD": {"file": "bdod_0-5cm_mean_1000.tif",  "scale": 0.01},
}

SHAPEFILE = os.path.join(TIFF_FOLDER, "gadm41_ZMB.gpkg")
N_SAMPLES = 500

# ── STEP 1: LOAD KAFUE DISTRICT BOUNDARY ─────────────────────
print("=" * 55)
print("  SoilSense ZM — extract_kafue.py")
print("=" * 55)
print("\n[1/5] Loading Kafue District boundary...")

try:
    zambia = gpd.read_file(SHAPEFILE, layer="ADM_ADM_2")
    name_col = "NAME_2"
except Exception:
    try:
        zambia = gpd.read_file(SHAPEFILE)
        name_col = None
        for col in zambia.columns:
            if zambia[col].dtype == object:
                vals = zambia[col].str.upper().tolist()
                if any("KAFUE" in str(v) for v in vals):
                    name_col = col
                    break
        if name_col is None:
            print("   Could not find Kafue. Available columns:", list(zambia.columns))
            print("   Sample values:", zambia.iloc[0].to_dict())
            raise ValueError("Cannot find Kafue District in shapefile")
    except Exception as e:
        print(f"\n❌ Error loading shapefile: {e}")
        print("\nTrying alternative approach — loading all layers...")
        import fiona
        layers = fiona.listlayers(SHAPEFILE)
        print(f"   Available layers: {layers}")
        raise

kafue = zambia[zambia[name_col].str.upper() == "KAFUE"]

if kafue.empty:
    kafue = zambia[zambia[name_col].str.upper().str.contains("KAFUE")]

if kafue.empty:
    print(f"\n❌ Kafue not found. Available districts:")
    print(zambia[name_col].unique())
    raise ValueError("Kafue District not found in shapefile")

print(f"   ✅ Found Kafue District — {len(kafue)} polygon(s)")
print(f"   Bounds: {kafue.total_bounds.round(3)}")

kafue = kafue.to_crs(epsg=4326)
kafue_geom = kafue.geometry.values[0]

# ── STEP 2: GENERATE SAMPLE POINTS ───────────────────────────
print(f"\n[2/5] Generating {N_SAMPLES} sample points within Kafue District...")

minx, miny, maxx, maxy = kafue.total_bounds
points = []
attempts = 0
max_attempts = N_SAMPLES * 20

while len(points) < N_SAMPLES and attempts < max_attempts:
    x = np.random.uniform(minx, maxx)
    y = np.random.uniform(miny, maxy)
    pt = Point(x, y)
    if kafue_geom.contains(pt):
        points.append({"longitude": round(x, 6), "latitude": round(y, 6)})
    attempts += 1

print(f"   ✅ Generated {len(points)} valid points inside Kafue District")

# ── STEP 3: EXTRACT SOIL VALUES AT EACH POINT ────────────────
print(f"\n[3/5] Extracting soil values from {len(TIFF_FILES)} GeoTIFF files...")

df = pd.DataFrame(points)

for var_name, info in TIFF_FILES.items():
    filepath = os.path.join(TIFF_FOLDER, info["file"])

    if not os.path.exists(filepath):
        print(f"   ⚠️  File not found: {info['file']} — skipping")
        df[var_name] = np.nan
        continue

    print(f"   Reading {var_name} from {info['file']}...", end=" ")

    values = []
    with rasterio.open(filepath) as src:
        from pyproj import Transformer
        transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        
        for _, row in df.iterrows():
            try:
                x_proj, y_proj = transformer.transform(row["longitude"], row["latitude"])
                val = list(src.sample([(x_proj, y_proj)]))[0][0]
                nodata = src.nodata
                if nodata is not None and val == nodata:
                    values.append(np.nan)
                elif val < 0 or val > 32767:
                    values.append(np.nan)
                else:
                    values.append(round(val * info["scale"], 3))
            except Exception:
                values.append(np.nan)

    df[var_name] = values
    valid = df[var_name].notna().sum()
    print(f"✅ {valid}/{len(df)} valid values")

# ── STEP 4: CLEAN AND SAVE CSV ────────────────────────────────
print(f"\n[4/5] Cleaning data and saving CSV...")

df_clean = df.dropna()
print(f"   Rows before cleaning: {len(df)}")
print(f"   Rows after cleaning:  {len(df_clean)}")

df_clean.to_csv(CSV_OUTPUT, index=False)
print(f"   ✅ Saved: kafue_soil_data.csv ({len(df_clean)} rows)")

# ── STEP 5: PRINT SUMMARY STATISTICS ─────────────────────────
print(f"\n{'=' * 55}")
print("  KAFUE DISTRICT SOIL STATISTICS")
print(f"{'=' * 55}")

stats = df_clean[["pH", "Clay", "Sand", "Silt", "SOC", "CEC", "BDOD"]].describe()
print(stats.round(2).to_string())

ph_vals = df_clean["pH"]
below_45 = (ph_vals < 4.5).sum()
below_55 = (ph_vals < 5.5).sum()
below_65 = (ph_vals < 6.5).sum()
total = len(ph_vals)

print(f"\n  pH BREAKDOWN (n={total} sample points):")
print(f"  Below 4.5 (Severely acidic):   {below_45} points = {below_45/total*100:.1f}%")
print(f"  Below 5.5 (Moderately acidic): {below_55} points = {below_55/total*100:.1f}%")
print(f"  Below 6.5 (Slightly acidic):   {below_65} points = {below_65/total*100:.1f}%")
print(f"  Mean pH: {ph_vals.mean():.2f}  |  Min: {ph_vals.min():.2f}  |  Max: {ph_vals.max():.2f}")

print(f"\n  📝 DISSERTATION NOTE:")
print(f"  'Analysis of SoilGrids data for Kafue District")
print(f"   (n={total} sample points, 0-5cm depth) reveals that")
print(f"   {below_55/total*100:.1f}% of soils fall below pH 5.5,")
print(f"   confirming significant soil acidification in the study area.'")

# ── STEP 6: PRODUCE pH MAP ────────────────────────────────────
print(f"\n[5/5] Producing pH map of Kafue District...")

fig, axes = plt.subplots(1, 2, figsize=(14, 6))
fig.suptitle("SoilSense ZM — Kafue District Soil Analysis\n(SoilGrids 2.0, 0–5cm depth)",
             fontsize=13, fontweight='bold', y=1.02)

ax1 = axes[0]
kafue.plot(ax=ax1, color='#f0faf4', edgecolor='#2D6A4F', linewidth=1.5)

scatter = ax1.scatter(
    df_clean["longitude"], df_clean["latitude"],
    c=df_clean["pH"],
    cmap="RdYlGn",
    vmin=4.0, vmax=7.5,
    s=20, alpha=0.8, zorder=5
)
plt.colorbar(scatter, ax=ax1, label="Soil pH", shrink=0.8)
ax1.set_title("Soil pH Distribution — Kafue District", fontsize=11)
ax1.set_xlabel("Longitude")
ax1.set_ylabel("Latitude")

ax1.annotate("pH < 5.5\n= acidic for maize",
             xy=(0.05, 0.05), xycoords='axes fraction',
             fontsize=8, color='#C1121F',
             bbox=dict(boxstyle='round,pad=0.3', facecolor='#fdecea', alpha=0.8))

ax2 = axes[1]
kafue.plot(ax=ax2, color='#f0faf4', edgecolor='#2D6A4F', linewidth=1.5)

colors = []
labels_map = {0: "Severely Degraded (<4.5)", 1: "Moderately Degraded (4.5–5.5)",
              2: "Slightly Degraded (5.5–6.5)", 3: "Optimal (6.5–7.5)"}
palette = {0: "#C1121F", 1: "#E9C46A", 2: "#90BE6D", 3: "#2D6A4F"}

for ph in df_clean["pH"]:
    if ph < 4.5:
        colors.append(palette[0])
    elif ph < 5.5:
        colors.append(palette[1])
    elif ph < 6.5:
        colors.append(palette[2])
    else:
        colors.append(palette[3])

ax2.scatter(df_clean["longitude"], df_clean["latitude"],
            c=colors, s=20, alpha=0.8, zorder=5)

from matplotlib.patches import Patch
legend_elements = [Patch(facecolor=palette[k], label=labels_map[k]) for k in sorted(palette)]
ax2.legend(handles=legend_elements, loc='upper right', fontsize=7, title="Soil Health")
ax2.set_title("Soil Health Categories — Kafue District", fontsize=11)
ax2.set_xlabel("Longitude")
ax2.set_ylabel("Latitude")

plt.tight_layout()
plt.savefig(MAP_OUTPUT, dpi=150, bbox_inches='tight')
# plt.show()  # Commented out to prevent blocking in headless environments

print(f"   ✅ Map saved: kafue_pH_map.png")
print(f"\n{'=' * 55}")
print("  ✅ PHASE 1 COMPLETE")
print(f"{'=' * 55}")
print(f"\n  Files created:")
print(f"  📄 kafue_soil_data.csv  — your ML training dataset")
print(f"  🗺️  kafue_pH_map.png    — Figure 1 for your dissertation")
print(f"\n  Next step: run train_model.py (Phase 2)")
print(f"{'=' * 55}\n")
