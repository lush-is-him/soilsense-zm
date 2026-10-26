"""Look up iSDAsoil values at a field (spec 2.1, 2.4).

Reads the local copies written by scripts/fetch_isdasoil.py. Values are
back-transformed using the rules recorded in layers.json.
"""

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEPTH_BAND = {"mean": "mean_0_20", "stdev": "stdev_0_20"}   # spec 2.4: 0-20 cm


@dataclass
class MapEstimate:
    ph_mean: float
    ph_sd: float
    oc_g_kg: Optional[float]
    p_ppm: Optional[float]
    k_ppm: Optional[float]
    texture: Optional[str]          # USDA class name
    depth_cm: str = "0-20"
    ph_method: str = "water"


def _back_transform(rule, raw):
    if rule == "x/10":
        return raw / 10
    if rule == "expm1(x/10)":
        return math.expm1(raw / 10)
    raise ValueError(f"unknown back-transformation {rule!r}")


class MapService:
    def __init__(self, data_dir="data/isdasoil"):
        import rasterio  # imported here so the rest of the engine runs without it

        self._rasterio = rasterio
        self.data_dir = Path(data_dir)
        manifest_path = self.data_dir / "layers.json"
        if not manifest_path.exists():
            raise FileNotFoundError(
                f"{manifest_path} not found; run scripts/fetch_isdasoil.py first")
        self.manifest = json.loads(manifest_path.read_text())
        self.nodata = self.manifest["nodata"]
        self.textures = {int(k): v for k, v in self.manifest["texture_classes"].items()}
        self._sources = {}

    def _sample(self, layer, band_name, lon, lat):
        """Raw value at a point, or None if outside the area or no data."""
        from rasterio.warp import transform

        if layer not in self._sources:
            path = self.data_dir / f"{layer}.tif"
            if not path.exists():
                return None
            self._sources[layer] = self._rasterio.open(path)
        src = self._sources[layer]
        band = self.manifest["layers"][layer]["bands"].index(band_name) + 1
        xs, ys = transform("EPSG:4326", src.crs, [lon], [lat])
        row, col = src.index(xs[0], ys[0])
        if not (0 <= row < src.height and 0 <= col < src.width):
            return None
        raw = next(src.sample([(xs[0], ys[0])], indexes=band))[0]
        return None if raw == self.nodata else int(raw)

    def _value(self, layer, band_name, lon, lat):
        raw = self._sample(layer, band_name, lon, lat)
        if raw is None:
            return None
        rule = self.manifest["layers"][layer]["back_transformation"]
        return round(_back_transform(rule, raw), 2)

    def lookup(self, lat, lon):
        """Return a MapEstimate, or None when the map has no pH value there."""
        ph_mean = self._value("ph", DEPTH_BAND["mean"], lon, lat)
        ph_sd = self._value("ph", DEPTH_BAND["stdev"], lon, lat)
        if ph_mean is None or ph_sd is None:
            return None
        texture_raw = self._sample("texture_class", DEPTH_BAND["mean"], lon, lat)
        return MapEstimate(
            ph_mean=ph_mean,
            ph_sd=ph_sd,
            oc_g_kg=self._value("carbon_organic", DEPTH_BAND["mean"], lon, lat),
            p_ppm=self._value("phosphorous_extractable", DEPTH_BAND["mean"], lon, lat),
            k_ppm=self._value("potassium_extractable", DEPTH_BAND["mean"], lon, lat),
            texture=self.textures.get(texture_raw) if texture_raw is not None else None,
        )

    def close(self):
        for src in self._sources.values():
            src.close()
        self._sources.clear()
