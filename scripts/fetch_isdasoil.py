"""Download the iSDAsoil layers for Kafue District (spec task H6).

iSDAsoil publishes each layer for all of Africa as one cloud-optimised
GeoTIFF (5 to 50 GB each). This script reads only the window around
Kafue District over HTTP and writes small local copies, so the map
service never needs the internet in the field (spec 2).

Values are written exactly as published (uint8, EPSG:3857, 30 m grid,
nodata 255). They are NOT converted to real units here; the
back-transformation for each layer is recorded in layers.json and must
be applied by the map service:

    pH, pH SD        x / 10
    OC, P, K         expm1(x / 10)   (log scale; their SD is also on the
                                      log scale and is not a simple +/-)
    texture class    integer code, see TEXTURE_CLASSES below

Usage (from the repo root):

    pip install -r scripts/requirements.txt
    python scripts/fetch_isdasoil.py --boundary "path/to/gadm41_ZMB.gpkg"
    python scripts/fetch_isdasoil.py            # fallback box, see below
    python scripts/fetch_isdasoil.py --check 28.18 -15.77

Output goes to data/isdasoil/ (the .tif files are ignored by git).
"""

import argparse
import datetime
import json
import math
import sys
from pathlib import Path

import rasterio
from rasterio.warp import transform, transform_bounds
from rasterio.windows import from_bounds

BASE_URL = "https://isdasoil.s3.amazonaws.com/soil_data"

# Layers the spec needs (2.4): pH mean and SD, organic carbon, P, K, texture.
LAYERS = {
    "ph": {
        "bands": ["mean_0_20", "mean_20_50", "stdev_0_20", "stdev_20_50"],
        "back_transformation": "x/10",
        "unit": "pH (water)",
    },
    "carbon_organic": {
        "bands": ["mean_0_20", "mean_20_50", "stdev_0_20", "stdev_20_50"],
        "back_transformation": "expm1(x/10)",
        "unit": "g/kg",
    },
    "phosphorous_extractable": {
        "bands": ["mean_0_20", "mean_20_50", "stdev_0_20", "stdev_20_50"],
        "back_transformation": "expm1(x/10)",
        "unit": "ppm",
    },
    "potassium_extractable": {
        "bands": ["mean_0_20", "mean_20_50", "stdev_0_20", "stdev_20_50"],
        "back_transformation": "expm1(x/10)",
        "unit": "ppm",
    },
    "texture_class": {
        "bands": ["mean_0_20", "mean_20_50"],
        "back_transformation": "class code",
        "unit": "USDA texture class",
    },
}

# From texture_class_attribute_table.csv in the iSDAsoil bucket.
TEXTURE_CLASSES = {
    1: "Clay", 2: "Silty Clay", 3: "Sandy Clay", 4: "Clay Loam",
    5: "Silty Clay Loam", 6: "Sandy Clay Loam", 7: "Loam", 8: "Silt Loam",
    9: "Sandy Loam", 10: "Silt", 11: "Loamy Sand", 12: "Sand",
}

NODATA = 255

# Approximate box around Kafue town and Shimabala (lon/lat, WGS84), used
# only when no boundary file is given. It is deliberately generous; prefer
# --boundary with the GADM file so the window follows the real district.
FALLBACK_BBOX = (27.6, -16.2, 28.8, -15.3)


def kafue_bbox_from_gadm(path):
    """Return (west, south, east, north) of Kafue District from a GADM file."""
    import geopandas as gpd  # only needed for this option

    try:
        districts = gpd.read_file(path, layer="ADM_ADM_2")
    except Exception:
        districts = gpd.read_file(path)
    if "NAME_2" not in districts.columns:
        sys.exit(f"{path} has no NAME_2 column; is it the GADM level-2 file?")
    kafue = districts[districts["NAME_2"].str.upper() == "KAFUE"]
    if kafue.empty:
        sys.exit(f"Kafue not found in {path}")
    return tuple(kafue.to_crs(epsg=4326).total_bounds)


def buffer_bbox(bbox, km):
    """Grow a lon/lat box by roughly `km` kilometres on every side."""
    west, south, east, north = bbox
    dlat = km / 111.0
    dlon = km / (111.0 * math.cos(math.radians((south + north) / 2)))
    return (west - dlon, south - dlat, east + dlon, north + dlat)


def fetch_layer(name, bbox, out_dir):
    url = f"/vsicurl/{BASE_URL}/{name}/{name}.tif"
    out_path = out_dir / f"{name}.tif"
    with rasterio.open(url) as src:
        window = from_bounds(*transform_bounds("EPSG:4326", src.crs, *bbox),
                             transform=src.transform)
        window = window.round_offsets().round_lengths()
        data = src.read(window=window)
        profile = src.profile.copy()
        profile.update(
            driver="GTiff",
            height=data.shape[1],
            width=data.shape[2],
            transform=src.window_transform(window),
            compress="deflate",
            tiled=True,
            blockxsize=256,
            blockysize=256,
        )
        profile.pop("photometric", None)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(data)
        for i, band in enumerate(LAYERS[name]["bands"], start=1):
            dst.set_band_description(i, band)
    valid = (data[0] != NODATA).mean() * 100
    size_mb = out_path.stat().st_size / 1e6
    print(f"  {name}: {data.shape[2]} x {data.shape[1]} px, "
          f"{valid:.0f}% with data, {size_mb:.1f} MB")
    return out_path


def back_transform(name, raw):
    if raw == NODATA:
        return None
    rule = LAYERS[name]["back_transformation"]
    if rule == "x/10":
        return round(raw / 10, 2)
    if rule == "expm1(x/10)":
        return round(math.expm1(raw / 10), 2)
    return TEXTURE_CLASSES.get(int(raw), f"unknown code {raw}")


def check_point(lon, lat, out_dir):
    """Print the 0-20 cm values at one location from the local copies."""
    print(f"\nValues at lon {lon}, lat {lat} (0-20 cm):")
    for name in LAYERS:
        path = out_dir / f"{name}.tif"
        if not path.exists():
            print(f"  {name}: not downloaded")
            continue
        with rasterio.open(path) as src:
            xs, ys = transform("EPSG:4326", src.crs, [lon], [lat])
            row, col = src.index(xs[0], ys[0])
            if not (0 <= row < src.height and 0 <= col < src.width):
                print(f"  {name}: point is outside the downloaded area")
                continue
            raw = list(src.sample([(xs[0], ys[0])]))[0]
        mean = back_transform(name, raw[0])
        line = f"  {name}: {mean}"
        if name == "ph":
            line += f" (SD {back_transform(name, raw[2])})"
        print(line)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--boundary", help="GADM Zambia file (gadm41_ZMB.gpkg)")
    parser.add_argument("--buffer-km", type=float, default=2.0,
                        help="extra margin around the district (default 2 km)")
    parser.add_argument("--out", default="data/isdasoil", help="output folder")
    parser.add_argument("--check", nargs=2, type=float, metavar=("LON", "LAT"),
                        help="only print values at this point from existing files")
    args = parser.parse_args()

    out_dir = Path(args.out)
    if args.check:
        check_point(args.check[0], args.check[1], out_dir)
        return

    if args.boundary:
        bbox = kafue_bbox_from_gadm(args.boundary)
        source = f"GADM Kafue District from {Path(args.boundary).name}"
    else:
        bbox = FALLBACK_BBOX
        source = "fallback box (approximate); rerun with --boundary for the real district"
        print("No --boundary given: using an approximate box around Kafue town and Shimabala.")
    bbox = buffer_bbox(bbox, args.buffer_km)
    print(f"Area (lon/lat): {tuple(round(v, 4) for v in bbox)}")

    out_dir.mkdir(parents=True, exist_ok=True)
    print("Downloading (this reads only the Kafue window, a few minutes per layer):")
    for name in LAYERS:
        fetch_layer(name, bbox, out_dir)

    manifest = {
        "source": "iSDAsoil v1 (https://isdasoil.s3.amazonaws.com/soil_data/)",
        "licence": "CC BY 4.0 (iSDA)",
        "fetched": datetime.date.today().isoformat(),
        "area_source": source,
        "bbox_lonlat": [round(v, 6) for v in bbox],
        "crs": "EPSG:3857",
        "resolution_m": 30,
        "nodata": NODATA,
        "layers": LAYERS,
        "texture_classes": TEXTURE_CLASSES,
        "notes": [
            "Values are stored raw; apply back_transformation before use.",
            "Spec 2.4 uses band mean_0_20 and stdev_0_20 of ph for the agreement rule.",
            "iSDAsoil pH is pH in water.",
        ],
    }
    (out_dir / "layers.json").write_text(json.dumps(manifest, indent=2))
    print(f"Wrote {out_dir / 'layers.json'}")


if __name__ == "__main__":
    main()
