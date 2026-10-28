"""Step 4: sample HayWired shaking for every building.

The raster stays in its native EPSG:4326 grid. Buildings are transformed to EPSG:4326 for
sampling instead of warping the raster, because warping a 1.5-1.85 km grid into meters would
resample the values and gain nothing.

Two methods, compared in the log and kept side by side in the output:
  point  the cell containing the building's representative point (the footprint's
         representative point, or the location point if there's no footprint). ShakeMap
         nodes are cell centers, so this is the nearest node. No interpolation.
  zonal  mean and max over every cell the footprint touches (all_touched=True, because a
         ~250 m2 footprint almost never contains a cell center).
"""
import geopandas as gpd
import numpy as np
import rasterio
from rasterstats import zonal_stats

from seismic_risk.config import GEOGRAPHIC, SHAKEMAP_TIF, interim

BANDS = ["MMI", "PGA", "PGV", "PSA03", "PSA10", "PSA30"]
ZONAL_BANDS = ["MMI", "PGA", "PGV", "PSA03"]


def log(msg):
    print(f"  {msg}")


def sample_points(points_4326, path=SHAKEMAP_TIF):
    """Value of the cell containing each point, per band, plus the cell's row/col."""
    with rasterio.open(path) as r:
        if r.crs.to_string() != GEOGRAPHIC:
            raise ValueError(f"expected {GEOGRAPHIC} raster, got {r.crs}")
        xy = [(p.x, p.y) for p in points_4326]
        vals = np.array(list(r.sample(xy)), dtype="float64")
        rows, cols = rasterio.transform.rowcol(r.transform, [p[0] for p in xy], [p[1] for p in xy])
        names = list(r.descriptions)
        if r.nodata is not None:
            vals[vals == r.nodata] = np.nan
    out = {n: vals[:, i] for i, n in enumerate(names)}
    out["cell"] = [f"{a}_{b}" for a, b in zip(rows, cols)]
    return out


def zonal(footprints_4326, path=SHAKEMAP_TIF):
    out = {}
    with rasterio.open(path) as r:
        names = list(r.descriptions)
        for band in [b for b in ZONAL_BANDS if b in names]:
            stats = zonal_stats(footprints_4326, str(path), band=names.index(band) + 1,
                                stats=["mean", "max", "count"], all_touched=True, nodata=r.nodata)
            out[f"{band}_zonal_mean"] = [s["mean"] for s in stats]
            out[f"{band}_zonal_max"] = [s["max"] for s in stats]
            out["zonal_cells"] = [s["count"] for s in stats]
    return out


def main():
    b = gpd.read_parquet(interim("03_buildings"))
    has_fp = b.footprint.notna()
    rep = b.geometry.copy()
    rep[has_fp] = gpd.GeoSeries(b.loc[has_fp, "footprint"], crs=b.crs).representative_point()
    b["sample_source"] = np.where(has_fp, "footprint", "location_point")
    b["sample_point"] = rep
    pts = gpd.GeoSeries(rep, crs=b.crs).to_crs(GEOGRAPHIC)
    s = sample_points(pts)
    for band in BANDS:
        b[band] = s[band]
    b["shakemap_cell"] = s["cell"]
    log(f"point sampling: {b.MMI.notna().sum():,} of {len(b):,} buildings, "
        f"{b.shakemap_cell.nunique()} distinct cells")
    log(f"MMI over soft-story buildings: min {b.MMI.min():.2f}, median {b.MMI.median():.2f}, "
        f"max {b.MMI.max():.2f}")

    fps = gpd.GeoSeries(b.loc[has_fp, "footprint"], crs=b.crs).to_crs(GEOGRAPHIC)
    z = zonal(list(fps))
    for k, v in z.items():
        b[k] = np.nan
        b.loc[has_fp, k] = v
    multi = (b.zonal_cells > 1).sum()
    log(f"zonal: {has_fp.sum():,} footprints, {multi:,} touch more than one cell "
        f"(max {int(b.zonal_cells.max())})")
    for band in ZONAL_BANDS:
        d = (b[f"{band}_zonal_mean"] - b[band]).abs()
        dmax = (b[f"{band}_zonal_max"] - b[band])
        log(f"{band}: |zonal mean - point| median {d.median():.3f}, 99th pct {d.quantile(.99):.3f}, "
            f"max {d.max():.3f}. zonal max exceeds point for {(dmax > 1e-6).sum():,} buildings")
    b.to_parquet(interim("04_buildings_shaking"))


if __name__ == "__main__":
    main()
