"""Spec 2.4: map lookup with back-transformation, on a small synthetic raster."""

import json

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin  # noqa: E402
from rasterio.warp import transform  # noqa: E402

from engine.map_service import MapService  # noqa: E402

LON, LAT = 28.18, -15.77
LAYERS = {
    "ph": (["mean_0_20", "mean_20_50", "stdev_0_20", "stdev_20_50"], "x/10", [64, 60, 3, 4]),
    "carbon_organic": (["mean_0_20", "mean_20_50", "stdev_0_20", "stdev_20_50"], "expm1(x/10)", [21, 16, 1, 1]),
    "phosphorous_extractable": (["mean_0_20", "mean_20_50", "stdev_0_20", "stdev_20_50"], "expm1(x/10)", [21, 20, 1, 1]),
    "potassium_extractable": (["mean_0_20", "mean_20_50", "stdev_0_20", "stdev_20_50"], "expm1(x/10)", [51, 50, 1, 1]),
    "texture_class": (["mean_0_20", "mean_20_50"], "class code", [6, 6]),
}


@pytest.fixture
def map_dir(tmp_path):
    xs, ys = transform("EPSG:4326", "EPSG:3857", [LON], [LAT])
    origin = from_origin(xs[0] - 45, ys[0] + 45, 30, 30)        # 3 x 3 cells around the point
    for name, (bands, _, values) in LAYERS.items():
        data = np.array([np.full((3, 3), v, dtype="uint8") for v in values])
        data[:, 0, 0] = 255                                        # one nodata corner
        with rasterio.open(tmp_path / f"{name}.tif", "w", driver="GTiff", height=3, width=3,
                           count=len(bands), dtype="uint8", crs="EPSG:3857",
                           transform=origin, nodata=255) as dst:
            dst.write(data)
    manifest = {
        "nodata": 255,
        "layers": {n: {"bands": b, "back_transformation": t} for n, (b, t, _) in LAYERS.items()},
        "texture_classes": {"6": "Sandy Clay Loam"},
    }
    (tmp_path / "layers.json").write_text(json.dumps(manifest))
    return tmp_path


def test_lookup_back_transforms_values(map_dir):
    estimate = MapService(map_dir).lookup(LAT, LON)
    assert estimate.ph_mean == 6.4 and estimate.ph_sd == 0.3
    assert estimate.oc_g_kg == 7.17 and estimate.p_ppm == 7.17 and estimate.k_ppm == 163.02
    assert estimate.texture == "Sandy Clay Loam" and estimate.ph_method == "water"


def test_outside_area_returns_none(map_dir):
    assert MapService(map_dir).lookup(-15.0, 30.0) is None


def test_nodata_cell_returns_none(map_dir):
    xs, ys = transform("EPSG:4326", "EPSG:3857", [LON], [LAT])
    lon, lat = transform("EPSG:3857", "EPSG:4326", [xs[0] - 30], [ys[0] + 30])
    assert MapService(map_dir).lookup(lat[0], lon[0]) is None


def test_missing_manifest_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        MapService(tmp_path)
