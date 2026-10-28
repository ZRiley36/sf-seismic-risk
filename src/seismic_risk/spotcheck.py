"""Hand checks: re-derive a few buildings' values straight from the raw files, without any of
the pipeline's code paths, and compare with what the pipeline produced.

  shaking     nearest grid.xml node to the building's lon/lat (brute force over the raw XML)
  CGS zones   point-in-polygon against the raw GeoJSON in EPSG:4326 with shapely
  liq. prob.  point-in-polygon against the raw shapefile
  assessor    the raw roll CSV, filtered by the building's lots

python -m seismic_risk.spotcheck
"""
import json
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point, shape

from seismic_risk.config import GEOGRAPHIC, LIQ_PROB, RAW, interim

ADDRESSES = ["2258 MASON ST", "1360 TAYLOR ST", "1625 EDDY ST"]
SEED = 7


def raw_grid():
    z = zipfile.ZipFile(RAW / "haywired_shakemap/grid.xml.zip")
    xml = z.read("grid.xml").decode()
    body = xml.split("<grid_data>")[1].split("</grid_data>")[0]
    return np.array(body.split(), dtype=float).reshape(-1, 8)  # LON LAT PGA PGV MMI PSA03 PSA10 PSA30


def main():
    b = gpd.read_parquet(interim("05_buildings_hazards"))
    picks = pd.concat([
        b[b.property_address.isin(ADDRESSES)],
        b[b.cgs_liquefaction].sample(2, random_state=SEED),
        b[b.cgs_landslide].sample(1, random_state=SEED),
        b[~b.retrofitted].sample(2, random_state=SEED),
    ]).drop_duplicates("ss_id")
    grid = raw_grid()
    liq = [shape(f["geometry"]) for f in json.load(open(RAW / "cgs_liquefaction_zones/cgs_liquefaction_zones.geojson"))["features"]]
    ls = [shape(f["geometry"]) for f in json.load(open(RAW / "cgs_landslide_zones/cgs_landslide_zones.geojson"))["features"]]
    lp = gpd.read_file(LIQ_PROB).to_crs(GEOGRAPHIC)
    a = pd.read_csv(next((RAW / "assessor_roll").glob("*.csv")), dtype=str,
                    usecols=["closed_roll_year", "parcel_number", "number_of_units", "year_property_built"])
    a = a[a.closed_roll_year == "2025"]
    rows = []
    for _, r in picks.iterrows():
        p = gpd.GeoSeries([r.sample_point], crs=b.crs).to_crs(GEOGRAPHIC).iloc[0]
        node = grid[np.argmin((grid[:, 0] - p.x) ** 2 + (grid[:, 1] - p.y) ** 2)]
        pt = Point(p.x, p.y)
        lots = a[a.parcel_number.isin(r.parcel_lots)]
        lp_hit = lp[lp.contains(pt)].Reclass.tolist()
        rows.append({
            "address": r.property_address, "tier": r.tier, "status": r.status_clean, "lon": round(p.x, 5),
            "lat": round(p.y, 5),
            "MMI pipeline": round(r.MMI, 2), "MMI raw node": node[4],
            "PGA pipeline": round(r.PGA, 2), "PGA raw node": node[2],
            "liq zone pipeline (point)": bool(r.cgs_liquefaction_point), "liq zone raw": any(g.contains(pt) for g in liq),
            "landslide pipeline (point)": bool(r.cgs_landslide_point), "landslide raw": any(g.contains(pt) for g in ls),
            "liq prob pipeline (footprint max)": r.liq_prob_mid, "liq prob raw (point)": lp_hit,
            "units pipeline": r.units, "units raw": pd.to_numeric(lots.number_of_units).sum(),
            "year pipeline": r.year_built, "year raw": pd.to_numeric(lots.year_property_built).min(),
        })
    out = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(out.T.to_string())
    agree = ((out["MMI pipeline"] == out["MMI raw node"]) & (out["PGA pipeline"] == out["PGA raw node"])
             & (out["liq zone pipeline (point)"] == out["liq zone raw"])
             & (out["landslide pipeline (point)"] == out["landslide raw"])
             & (out["units pipeline"] == out["units raw"]))
    print(f"\n{agree.sum()} of {len(out)} buildings agree on shaking, zones and units")


if __name__ == "__main__":
    main()
