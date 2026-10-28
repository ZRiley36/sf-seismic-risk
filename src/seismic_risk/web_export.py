"""Step 9: data files for the web map, written to web/data/ (committed, served by GitHub Pages).

buildings.geojson      soft-story points with every field the popup shows
footprints.geojson     the same buildings' outlines, with only id, score and retrofit status
                       (the map looks the rest up from buildings.geojson)
shaking.geojson        ShakeMap cells over SF as squares, so the map shows the real resolution
liquefaction.geojson   CGS liquefaction zones, simplified
landslide.geojson      CGS landslide zones, simplified
neighborhoods.geojson  analysis neighborhoods with the summary columns
faults.geojson         Holocene-active fault traces near SF
stats.json             headline numbers for the panel and the guide

Everything is EPSG:4326 with coordinates rounded to 6 decimals (about 10 cm).
"""
import json

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from shapely.geometry import box

from seismic_risk.config import GEOGRAPHIC, PROCESSED, ROOT, interim, score_config

OUT = ROOT / "web/data"
SIMPLIFY_M = 1.0
FAULT_BBOX = (-122.95, 37.45, -121.85, 38.05)  # SF plus the East Bay, so the Hayward fault is on the map
EPICENTER = (-122.1786, 37.8046)


def log(msg):
    print(f"  {msg}")


def round_coords(c):
    if isinstance(c[0], (int, float)):
        return [round(c[0], 6), round(c[1], 6)]
    return [round_coords(x) for x in c]


def write(gdf, name):
    gj = json.loads(gdf.to_crs(GEOGRAPHIC).to_json(na="null", drop_id=True))
    for f in gj["features"]:
        if f["geometry"]:
            f["geometry"]["coordinates"] = round_coords(f["geometry"]["coordinates"])
    path = OUT / name
    path.write_text(json.dumps(gj, separators=(",", ":")))
    log(f"{name}: {len(gdf):,} features, {path.stat().st_size / 1e6:.2f} MB")


def nullable_int(s):
    return s.round(0).astype("Int64")


def liq_label(low, high):
    if pd.isna(low):
        return None
    if high == 0:
        return "0%"
    if low == 0:
        return f"<{high:g}%"
    if high == 100:
        return f"≥{low:g}%"
    return f"{low:g}–{high:g}%"


def buildings(b):
    p = pd.DataFrame({
        "id": b.ss_id, "addr": b.property_address.str.strip().str.title(), "nhood": b.nhood,
        "tier": b.tier, "status": b.status_clean, "yr": nullable_int(b.year_built), "units": nullable_int(b.units),
        "stories": nullable_int(b.stories), "cls": b.property_class_code_definition, "lot_n": b.rows_on_group,
        "mmi": b.MMI.round(2), "pga": b.PGA.round(1), "pgv": b.PGV.round(1), "psa03": b.PSA03.round(1),
        "liq": b.cgs_liquefaction.astype(int), "ls": b.cgs_landslide.astype(int),
        "lp": [liq_label(lo, hi) for lo, hi in zip(b.liq_prob_low, b.liq_prob_high)],
        "score": b.score.round(3), "rank": b.rank_base, "hi": b.high_score.astype(int),
        "c_s": b.c_shaking.round(2), "c_g": b.c_ground_failure.round(2), "c_v": b.c_vulnerability.round(2),
        "c_r": b.c_retrofit.round(2), "res": b.est_residents.round(0).astype(int),
        "hay_km": b.hayward_fault_km.round(1), "fault": b.nearest_fault, "fault_km": b.nearest_fault_km.round(1),
    })
    pts = gpd.GeoDataFrame(p, geometry=gpd.GeoSeries(b.sample_point, crs=b.crs), crs=b.crs)
    write(pts.sort_values("score"), "buildings.geojson")  # high scores last, so they draw on top
    fp = gpd.GeoDataFrame({"id": b.ss_id, "score": b.score.round(3), "retro": b.retrofitted.astype(int)},
                          geometry=gpd.GeoSeries(b.footprint, crs=b.crs).simplify(SIMPLIFY_M / 4), crs=b.crs)
    write(fp[fp.geometry.notna()].drop_duplicates("id"), "footprints.geojson")


def shaking(sf):
    with rasterio.open(PROCESSED / "web/haywired_shakemap_sf.tif") as r:
        names = list(r.descriptions)
        arr = {n: r.read(i + 1, masked=True) for i, n in enumerate(names)}
        rows, cols = np.nonzero(~arr["MMI"].mask)
        cells = []
        for row, col in zip(rows, cols):
            x0, y0 = r.transform * (col, row)
            x1, y1 = r.transform * (col + 1, row + 1)
            cells.append({"geometry": box(x0, y1, x1, y0), "mmi": round(float(arr["MMI"][row, col]), 2),
                          "pga": round(float(arr["PGA"][row, col]), 1), "pgv": round(float(arr["PGV"][row, col]), 1),
                          "psa03": round(float(arr["PSA03"][row, col]), 1)})
    write(gpd.GeoDataFrame(cells, crs=GEOGRAPHIC), "shaking.geojson")


def zones():
    for src, name in [("01_cgs_liquefaction_zones", "liquefaction.geojson"),
                      ("01_cgs_landslide_zones", "landslide.geojson")]:
        g = gpd.read_parquet(interim(src))
        g["geometry"] = g.simplify(SIMPLIFY_M)
        write(g[["geometry"]], name)


def neighborhoods():
    nb = gpd.read_parquet(interim("01_neighborhoods"))
    s = pd.read_csv(PROCESSED / "neighborhood_summary.csv")
    nb = nb.merge(s, on="nhood", how="left")
    num = s.columns.drop("nhood")
    nb[num] = nb[num].fillna(0)
    nb["geometry"] = nb.simplify(SIMPLIFY_M * 2)
    write(nb[["nhood", *num, "geometry"]], "neighborhoods.geojson")


def faults():
    q = gpd.read_parquet(interim("02_faults"))
    q = q[q.holocene].to_crs(GEOGRAPHIC).clip(box(*FAULT_BBOX))
    q = q[~q.is_empty][["fault_name", "section_na", "age", "geometry"]]
    q["geometry"] = q.to_crs(q.estimate_utm_crs()).simplify(5).to_crs(GEOGRAPHIC)
    write(q, "faults.geojson")


def stats(b):
    cfg = score_config()
    hi7 = b.MMI >= 7.0
    unretro = ~b.retrofitted
    s = {
        "buildings": len(b), "retrofitted": int(b.retrofitted.sum()), "unretrofitted": int(unretro.sum()),
        "non_compliant": int((b.status_clean == "non_compliant").sum()),
        "newly_added": int((b.status_clean == "newly_added").sum()),
        "pct_retrofitted": round(b.retrofitted.mean() * 100, 1),
        "in_liquefaction": int(b.cgs_liquefaction.sum()), "in_landslide": int(b.cgs_landslide.sum()),
        "unretro_in_liquefaction": int((unretro & b.cgs_liquefaction).sum()),
        "units": int(round(b.units_alloc.sum())), "residents": int(round(b.est_residents.sum())),
        "unretro_units": int(round(b.loc[unretro, "units_alloc"].sum())),
        "unretro_residents": int(round(b.loc[unretro, "est_residents"].sum())),
        "high_cut": round(float(b.score.quantile(cfg["high_score_quantile"])), 3),
        "high_buildings": int(b.high_score.sum()), "high_units": int(round(b.loc[b.high_score, "units_alloc"].sum())),
        "high_residents": int(round(b.loc[b.high_score, "est_residents"].sum())),
        "high_unretrofitted": int((b.high_score & unretro).sum()),
        "mmi_min": round(float(b.MMI.min()), 2), "mmi_max": round(float(b.MMI.max()), 2),
        "mmi7_buildings": int(hi7.sum()), "cells": int(b.shakemap_cell.nunique()),
        "pct_unretro_mmi7": round(unretro[hi7].mean() * 100, 1), "pct_unretro_below7": round(unretro[~hi7].mean() * 100, 1),
        "pct_unretro_liq": round(unretro[b.cgs_liquefaction].mean() * 100, 1),
        "pct_unretro_not_liq": round(unretro[~b.cgs_liquefaction].mean() * 100, 1),
        "hayward_km_min": round(float(b.hayward_fault_km.min()), 1), "hayward_km_max": round(float(b.hayward_fault_km.max()), 1),
        "epicenter": EPICENTER, "weights": cfg["weights"],
    }
    (OUT / "stats.json").write_text(json.dumps(s, indent=1))
    log(f"stats.json: {len(s)} values")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    b = gpd.read_parquet(interim("06_buildings_scored"))
    b = b.merge(pd.read_parquet(PROCESSED / "buildings_seismic.parquet", columns=["ss_id", "est_residents"]), on="ss_id")
    b = gpd.GeoDataFrame(b, geometry="geometry", crs=b.crs)
    buildings(b)
    shaking(gpd.read_parquet(interim("01_sf_boundary")))
    zones()
    neighborhoods()
    faults()
    stats(b)


if __name__ == "__main__":
    main()
