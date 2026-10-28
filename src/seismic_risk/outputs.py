"""Step 8: web-ready outputs in data/processed/web/.

haywired_shakemap_sf.tif   Cloud-Optimized GeoTIFF of the ShakeMap cropped to SF County. It
                           keeps the native EPSG:4326 grid (no resampling), MMI is band 1, and
                           cells that don't touch the county are nodata.
soft_story_buildings.geojson
                           One point per building in EPSG:4326 (the representative point used
                           for sampling), with a short list of display fields, rounded.
"""
import json

import geopandas as gpd
import numpy as np
import rasterio
import rasterio.shutil
from rasterio.features import geometry_mask
from rasterio.io import MemoryFile
from rasterio.windows import Window, from_bounds

from seismic_risk.config import GEOGRAPHIC, PROCESSED, SHAKEMAP_TIF, interim

WEB = PROCESSED / "web"
BAND_ORDER = ["MMI", "PGA", "PGV", "PSA03", "PSA10", "PSA30"]
POINT_FIELDS = {
    "ss_id": None, "property_address": None, "nhood": None, "tract": None, "tier": None,
    "status_clean": None, "retrofitted": None, "year_built": 0, "units": 0, "stories": 0,
    "MMI": 2, "PGA": 1, "PGV": 1, "PSA03": 1, "cgs_liquefaction": None, "cgs_landslide": None,
    "liq_prob_mid": 1, "score": 3, "rank_base": None, "high_score": None, "est_residents": 0,
    "nearest_fault_km": 1, "hayward_fault_km": 1,
}


def log(msg):
    print(f"  {msg}")


def shaking_cog():
    sf = gpd.read_parquet(interim("01_sf_boundary")).to_crs(GEOGRAPHIC)
    with rasterio.open(SHAKEMAP_TIF) as src:
        w = from_bounds(*sf.total_bounds, transform=src.transform).round_offsets().round_lengths()
        w = Window(w.col_off - 1, w.row_off - 1, w.width + 2, w.height + 2)  # one cell of margin
        transform = src.window_transform(w)
        names = list(src.descriptions)
        data = {n: src.read(names.index(n) + 1, window=w) for n in BAND_ORDER}
        units = {n: src.tags(names.index(n) + 1).get("units") for n in BAND_ORDER}
        nodata = src.nodata
        tags = src.tags()
    shape = next(iter(data.values())).shape
    outside = geometry_mask(sf.geometry, out_shape=shape, transform=transform, all_touched=True)
    profile = dict(driver="GTiff", width=shape[1], height=shape[0], count=len(BAND_ORDER), dtype="float32",
                   crs=GEOGRAPHIC, transform=transform, nodata=nodata)
    WEB.mkdir(parents=True, exist_ok=True)
    out = WEB / "haywired_shakemap_sf.tif"
    with MemoryFile() as mem:
        with mem.open(**profile) as tmp:
            for i, n in enumerate(BAND_ORDER, start=1):
                tmp.write(np.where(outside, nodata, data[n]).astype("float32"), i)
                tmp.set_band_description(i, n)
                tmp.update_tags(i, units=units[n])
            tmp.update_tags(**tags, clipped_to="SF County (Census cb 2024), cells touching the county")
            rasterio.shutil.copy(tmp, out, driver="COG", compress="DEFLATE", blocksize=256,
                                 overview_resampling="nearest")
    with rasterio.open(out) as r:
        valid = r.read(1, masked=True)
        log(f"{out.name}: {r.width}x{r.height} cells, {valid.count()} inside SF, "
            f"MMI {valid.min():.2f}-{valid.max():.2f}, layout {r.tags(ns='IMAGE_STRUCTURE').get('LAYOUT')}")


def building_points():
    b = gpd.read_parquet(PROCESSED / "buildings_seismic.parquet")
    pts = gpd.GeoDataFrame(b[list(POINT_FIELDS)].copy(),
                           geometry=gpd.GeoSeries(b.sample_point, crs=b.crs), crs=b.crs).to_crs(GEOGRAPHIC)
    for col, digits in POINT_FIELDS.items():
        if digits is not None:
            pts[col] = pts[col].round(digits)
            if digits == 0:
                pts[col] = pts[col].astype("Int64")
    out = WEB / "soft_story_buildings.geojson"
    gj = json.loads(pts.to_json(na="null", drop_id=True))
    for f in gj["features"]:
        f["geometry"]["coordinates"] = [round(c, 6) for c in f["geometry"]["coordinates"]]
    out.write_text(json.dumps(gj, separators=(",", ":")))
    log(f"{out.name}: {len(pts):,} points, {len(POINT_FIELDS)} fields, {out.stat().st_size / 1e6:.2f} MB")


def main():
    shaking_cog()
    building_points()


if __name__ == "__main__":
    main()
