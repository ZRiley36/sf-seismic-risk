"""Step 1 inventory: open every raw file and report what is actually in it.

python -m seismic_risk.inventory > docs/data_inventory.json
Run seismic_risk.shakemap_tif first (the ShakeMap is only usable after conversion).
"""
import json
import re
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask

from seismic_risk.parcels import normalize_parcel

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw"
EQ_AREA = 3310  # California Albers, only used here to measure areas

LIQ_PROB = ("zip://" + str(RAW / "haywired_liquefaction/haywired_expanded_liquefaction_probability.zip")
            + "!haywired_expanded_liquefaction_probability/haywired_expanded_liquefaction_probability.shp")
QFAULTS = "zip://" + str(RAW / "usgs_qfaults/Qfaults_GIS.zip") + "!SHP/Qfaults_US_Database.shp"
# Rough places for sanity checks: (lon, lat, expected character)
PLACES = {
    "Marina": (-122.437, 37.804, "bay fill, liquefaction"),
    "Mission Bay": (-122.392, 37.770, "bay fill, liquefaction"),
    "SoMa (4th & Folsom)": (-122.401, 37.781, "old bay margin fill"),
    "Treasure Island": (-122.371, 37.823, "artificial fill"),
    "Bayview/Hunters Point": (-122.375, 37.729, "mixed fill and bedrock"),
    "Pacific Heights": (-122.435, 37.792, "bedrock ridge"),
    "Twin Peaks": (-122.447, 37.752, "bedrock hill"),
    "Outer Sunset (30th & Judah)": (-122.489, 37.761, "dune sand"),
}


def vector_summary(g, key_cols=()):
    out = {
        "rows": int(len(g)),
        "crs": g.crs.to_string() if g.crs else None,
        "geometry_types": {k: int(v) for k, v in g.geom_type.value_counts().items()},
        "invalid": int((~g.is_valid).sum()),
        "empty": int(g.is_empty.sum()),
        "null_geometry": int(g.geometry.isna().sum()),
        "bounds": [round(float(x), 5) for x in g.total_bounds],
        "columns": [c for c in g.columns if c != "geometry"],
    }
    for c in key_cols:
        s = g[c]
        out.setdefault("key_fields", {})[c] = {
            "dtype": str(s.dtype), "nulls": int(s.isna().sum()), "unique": int(s.nunique()),
            "sample": [str(x) for x in s.dropna().sample(min(5, s.notna().sum()), random_state=0)],
        }
    return out


def sf_boundary():
    cty = gpd.read_file("zip://" + str(RAW / "census_boundaries/cb_2024_us_county_500k.zip"))
    return cty[cty.GEOID == "06075"]


def files():
    return [{"path": str(p.relative_to(RAW)), "mb": round(p.stat().st_size / 1e6, 2)}
            for p in sorted(RAW.rglob("*")) if p.is_file()]


def soft_story():
    ss = pd.read_csv(RAW / "soft_story/soft_story_beah-shgi.csv", dtype=str)
    pts = gpd.GeoSeries.from_wkt(ss["point"], crs=4326)
    g = gpd.GeoDataFrame(ss, geometry=pts)
    out = vector_summary(g.dropna(subset=["point"]), ["block", "lot", "parcel_number", "tier", "status"])
    out["rows"] = int(len(ss))
    out["no_coordinates"] = ss.loc[ss.point.isna(), "parcel_number"].tolist()
    out["tier"] = ss.tier.value_counts().to_dict()
    out["status"] = ss.status.value_counts(dropna=False).to_dict()
    out["status_by_tier"] = pd.crosstab(ss.tier, ss.status.str.lower()).to_dict()
    pn = ss.parcel_number
    out["parcel_number_lengths"] = {int(k): int(v) for k, v in pn.str.len().value_counts().items()}
    out["parcel_number_with_letters"] = int(pn.str.contains("[A-Z]").sum())
    out["parcel_number_equals_block_plus_lot"] = int((pn == ss.block + ss.lot).sum())
    out["unpadded_lots"] = ss.loc[ss.lot.str.len() < 3, ["block", "lot", "parcel_number"]].to_dict("records")
    out["rows_sharing_a_parcel"] = int(pn.duplicated(keep=False).sum())
    out["parcels_with_several_rows"] = int(pn[pn.duplicated()].nunique())
    out["exact_duplicate_rows"] = int(ss.drop(columns=["data_loaded_at"]).duplicated().sum())
    out["data_as_of"] = ss.data_as_of.unique().tolist()
    return out, ss


def assessor():
    path = next((RAW / "assessor_roll").glob("*.csv"))
    usecols = ["closed_roll_year", "parcel_number", "block", "lot", "property_location", "use_code",
               "use_definition", "property_class_code", "property_class_code_definition",
               "year_property_built", "number_of_units", "number_of_stories", "construction_type"]
    a = pd.read_csv(path, dtype=str, usecols=usecols)
    out = {"file": path.name, "rows": int(len(a)), "columns_kept_for_inventory": usecols}
    out["rows_by_year"] = a.closed_roll_year.value_counts().sort_index().to_dict()
    latest = a.closed_roll_year.max()
    out["latest_year"] = latest
    out["duplicate_parcel_within_year"] = {y: int(g.parcel_number.duplicated().sum())
                                          for y, g in a.groupby("closed_roll_year")}
    out["parcels_in_several_years"] = int(a.groupby("parcel_number").closed_roll_year.nunique().gt(1).sum())
    out["unique_parcels_all_years"] = int(a.parcel_number.nunique())
    L = a[a.closed_roll_year == latest]
    pn = L.parcel_number.dropna()
    out["latest_parcel_number"] = {
        "nulls": int(L.parcel_number.isna().sum()),
        "lengths": {int(k): int(v) for k, v in pn.str.len().value_counts().items()},
        "with_letters": int(pn.str.contains("[A-Z]").sum()),
        "sample": pn.sample(8, random_state=0).tolist(),
        "equals_block_plus_lot": int((L.parcel_number == L.block + L.lot).sum()),
    }
    yb = pd.to_numeric(L.year_property_built, errors="coerce")
    units = pd.to_numeric(L.number_of_units, errors="coerce")
    out["latest_year_built"] = {"nulls": int(yb.isna().sum()), "zeros": int((yb == 0).sum()),
                                "min_nonzero": float(yb[yb > 0].min()), "median": float(yb[yb > 0].median()),
                                "max": float(yb.max()), "before_1800": int(((yb > 0) & (yb < 1800)).sum()),
                                "after_2026": int((yb > 2026).sum())}
    out["latest_units"] = {"nulls": int(units.isna().sum()), "zeros": int((units == 0).sum()),
                           "median": float(units.median()), "max": float(units.max())}
    out["latest_use_definition"] = L.use_definition.value_counts().head(15).to_dict()
    out["latest_property_class_top"] = L.property_class_code_definition.value_counts().head(15).to_dict()
    out["latest_construction_type"] = L.construction_type.value_counts(dropna=False).head(10).to_dict()
    return out, a


def footprints():
    fp = gpd.read_file(RAW / "building_footprints/building_footprints_ynuv-fyni.geojson",
                       columns=["sf16_bldgid", "mblr", "globalid", "hgt_median_m", "gnd_min_m"],
                       engine="pyogrio")
    out = vector_summary(fp, ["sf16_bldgid", "mblr", "hgt_median_m"])
    m = fp.mblr
    out["mblr_prefix"] = m.str.extract(r"^([A-Z]+)")[0].value_counts().to_dict()
    out["mblr_lengths"] = {int(k): int(v) for k, v in m.str.len().value_counts().items()}
    out["mblr_shared_by_several_footprints"] = int(m.duplicated().sum())
    sf = sf_boundary().to_crs(4326).union_all()
    inside = fp.representative_point().within(sf)
    out["outside_sf_county"] = int((~inside).sum())
    out["outside_sf_by_prefix"] = fp.loc[~inside, "mblr"].str[:2].value_counts().to_dict()
    area = fp.to_crs(EQ_AREA).area
    out["area_m2"] = {k: round(float(v), 1) for k, v in area.describe().items()}
    out["hgt_median_m"] = {k: round(float(v), 2) for k, v in
                           pd.to_numeric(fp.hgt_median_m, errors="coerce").describe().items()}
    return out, fp


def parcels():
    p = gpd.read_file(RAW / "parcels/parcels_acdm-wktn.geojson",
                      columns=["blklot", "mapblklot", "active", "in_asr_secured_roll", "date_rec_drop"],
                      engine="pyogrio")
    out = vector_summary(p[p.geometry.notna()], ["blklot", "mapblklot"])
    out["rows"] = int(len(p))
    out["null_geometry"] = int(p.geometry.isna().sum())
    out["active"] = p.active.astype(str).value_counts().to_dict()
    out["in_asr_secured_roll"] = p.in_asr_secured_roll.astype(str).value_counts().to_dict()
    out["duplicate_blklot"] = int(p.blklot.duplicated().sum())
    out["condo_lots_blklot_ne_mapblklot"] = int((p.blklot != p.mapblklot).sum())
    bad = p.blklot[p.blklot.map(normalize_parcel).isna()]
    out["blklot_not_normalizable"] = {"count": int(len(bad)), "sample": bad.head(8).tolist()}
    return out, p


def parcel_joins(ss, a, fp, p):
    latest = a[a.closed_roll_year == a.closed_roll_year.max()]
    ss_pn = ss.parcel_number.map(normalize_parcel)
    a_pn = set(latest.parcel_number.dropna().map(normalize_parcel))
    a_any = set(a.parcel_number.dropna().map(normalize_parcel))
    fp_pn = fp.mblr.str.replace(r"^(SF|CN)", "", regex=True).map(normalize_parcel)
    fp_set = set(fp_pn.dropna())
    raw_match = ss.parcel_number.isin(set(latest.parcel_number.dropna()))
    out = {
        "soft_story_to_assessor_latest_raw": round(float(raw_match.mean()) * 100, 2),
        "soft_story_to_assessor_latest_normalized": round(float(ss_pn.isin(a_pn).mean()) * 100, 2),
        "soft_story_to_assessor_any_year_normalized": round(float(ss_pn.isin(a_any).mean()) * 100, 2),
        "soft_story_to_footprint_mblr_normalized": round(float(ss_pn.isin(fp_set).mean()) * 100, 2),
        "footprints_in_sf_to_assessor_latest": round(float(fp_pn[fp.mblr.str.startswith("SF")]
                                                           .isin(a_pn).mean()) * 100, 2),
        "soft_story_unmatched_assessor_latest_sample": ss.loc[~ss_pn.isin(a_pn), "parcel_number"]
        .head(15).tolist(),
        "soft_story_unmatched_assessor_latest_count": int((~ss_pn.isin(a_pn)).sum()),
        "soft_story_unmatched_footprint_count": int((~ss_pn.isin(fp_set)).sum()),
    }
    # Condo conversions retire the building's lot, so the unmatched rows are recovered through
    # the parcel polygon under the soft-story point and that polygon's mapblklot group.
    act = p[p.active.astype(str).str.lower() == "true"].dropna(subset=["geometry"])
    act = act.assign(mpn=act.mapblklot.map(normalize_parcel), pn=act.blklot.map(normalize_parcel))
    in_roll = act.groupby("mpn").pn.apply(lambda s: bool(set(s) & a_pn))
    pts = gpd.GeoDataFrame(ss.assign(pn=ss_pn).dropna(subset=["point"]),
                           geometry=gpd.GeoSeries.from_wkt(ss.point.dropna()), crs=4326)
    j = gpd.sjoin(pts, act[["mpn", "geometry"]], how="left", predicate="within")
    spatial = j.mpn.map(in_roll).fillna(False).astype(bool).groupby(level=0).any()
    direct = ss_pn.isin(a_pn)
    recovered = ~direct & spatial.reindex(ss.index, fill_value=False)
    out["soft_story_recovered_via_parcel_polygon"] = int(recovered.sum())
    out["soft_story_to_assessor_latest_any_route"] = round(float((direct | recovered).mean()) * 100, 2)
    out["soft_story_still_unmatched"] = ss.loc[~(direct | recovered), "parcel_number"].tolist()
    return out


def shakemap():
    tif = ROOT / "data/interim/haywired_shakemap.tif"
    sf = sf_boundary().to_crs(4326)
    with rasterio.open(tif) as r:
        out = {"file": str(tif.relative_to(ROOT)), "source": "grid.xml (converted)", "crs": r.crs.to_string(),
               "res_deg": [round(v, 6) for v in r.res], "size": [r.width, r.height],
               "bounds": [round(v, 4) for v in r.bounds], "nodata": r.nodata, "bands": {}}
        minx, miny, maxx, maxy = sf.total_bounds
        b = r.bounds
        out["covers_sf_bbox"] = bool(b.left <= minx and b.right >= maxx and b.bottom <= miny and b.top >= maxy)
        mask = geometry_mask(sf.geometry, out_shape=(r.height, r.width), transform=r.transform,
                             invert=True, all_touched=True)
        out["cells_touching_sf"] = int(mask.sum())
        for i, name in enumerate(r.descriptions, start=1):
            arr = r.read(i)
            v = arr[mask]
            out["bands"][name] = {"units": r.tags(i).get("units"),
                                  "grid_min": round(float(arr.min()), 3), "grid_max": round(float(arr.max()), 3),
                                  "sf_min": round(float(v.min()), 3), "sf_max": round(float(v.max()), 3),
                                  "sf_mean": round(float(v.mean()), 3)}
        rows, cols = np.nonzero(mask)
        xs, ys = rasterio.transform.xy(r.transform, rows, cols)
        mmi = r.read(3)[mask]
        df = pd.DataFrame({"lon": xs, "lat": ys, "mmi": mmi})
        land = df[df.lon > -122.53]  # drops the Farallon Islands cells
        out["sf_mmi_vs_longitude_corr"] = round(float(land[["lon", "mmi"]].corr().iloc[0, 1]), 3)
        out["sf_mmi_by_lon_band"] = land.groupby(pd.cut(land.lon, [-122.53, -122.47, -122.42, -122.30]),
                                                 observed=True).mmi.mean().round(2).astype(str).to_dict()
        out["sf_mmi_by_lon_band"] = {str(k): v for k, v in out["sf_mmi_by_lon_band"].items()}
        samples = list(r.sample([(x, y) for x, y, _ in PLACES.values()]))
        out["place_samples"] = {n: {d: round(float(v[i]), 2) for i, d in enumerate(r.descriptions)}
                                for n, v in zip(PLACES, samples)}
    return out


def hazard_layers():
    sf = sf_boundary().to_crs(EQ_AREA)
    out = {}
    for name in ["cgs_liquefaction_zones", "cgs_landslide_zones", "cgs_unevaluated_areas"]:
        g = gpd.read_file(RAW / name / f"{name}.geojson")
        s = vector_summary(g, ["QUAD_NAME"])
        gi = g.to_crs(EQ_AREA)
        gi["geometry"] = gi.make_valid()
        c = gi.clip(sf)
        s["features_in_sf"] = int(len(c))
        s["area_in_sf_km2"] = round(float(c.area.sum() / 1e6), 2)
        s["quads_in_sf"] = sorted(c.QUAD_NAME.unique().tolist())
        s["released_dates_in_sf"] = sorted({str(x)[:10] for x in c.RELEASED.dropna()}) if "RELEASED" in c else None
        out[name] = s
    lp = gpd.read_file(LIQ_PROB)
    s = vector_summary(lp, ["Reclass"])
    s["classes"] = lp.Reclass.value_counts().to_dict()
    li = lp.to_crs(EQ_AREA)
    li["geometry"] = li.make_valid()
    c = li.clip(sf)
    s["area_in_sf_km2_by_class"] = (c.assign(km2=c.area / 1e6).groupby("Reclass").km2.sum().round(2).to_dict())
    s["sf_land_km2"] = round(float(sf.area.sum() / 1e6), 1)
    out["haywired_liquefaction_probability"] = s
    pts = gpd.GeoDataFrame({"place": list(PLACES)},
                           geometry=gpd.points_from_xy([v[0] for v in PLACES.values()],
                                                       [v[1] for v in PLACES.values()]), crs=4326)
    liq = gpd.read_file(RAW / "cgs_liquefaction_zones/cgs_liquefaction_zones.geojson")
    ls = gpd.read_file(RAW / "cgs_landslide_zones/cgs_landslide_zones.geojson")
    lp4 = lp.to_crs(4326)
    lp4["geometry"] = lp4.make_valid()
    j = gpd.sjoin(pts, lp4, how="left", predicate="within").groupby(level=0).Reclass.first()
    out["place_checks"] = {p: {"expected": PLACES[p][2],
                               "cgs_liquefaction": bool(liq.intersects(g).any()),
                               "cgs_landslide": bool(ls.intersects(g).any()),
                               "haywired_liq_prob": None if pd.isna(j[i]) else j[i]}
                           for i, (p, g) in enumerate(zip(pts.place, pts.geometry))}
    return out


def faults():
    q = gpd.read_file(QFAULTS)
    s = vector_summary(q)
    sf = sf_boundary().to_crs(EQ_AREA)
    qi = q.to_crs(EQ_AREA)
    near = qi[qi.distance(sf.union_all()) < 50_000]
    s["within_50km_of_sf"] = int(len(near))
    s["age_within_50km"] = near.age.value_counts().to_dict()
    s["named_faults_within_50km"] = near.fault_name.value_counts().head(15).to_dict()
    s["intersecting_sf"] = near[near.intersects(sf.union_all())].fault_name.value_counts().to_dict()
    hol = near[near.age.isin(["historic", "latest Quaternary"])]
    d = hol.groupby("fault_name").geometry.apply(lambda g: g.distance(sf.union_all()).min() / 1000)
    s["nearest_holocene_faults_km_from_sf"] = d.sort_values().head(8).round(1).to_dict()
    return s


def census():
    tr = gpd.read_file("zip://" + str(RAW / "census_boundaries/cb_2024_06_tract_500k.zip"))
    tr = tr[tr.COUNTYFP == "075"]
    out = {"sf_county": vector_summary(sf_boundary()), "tracts": vector_summary(tr, ["GEOID"])}
    acs = pd.read_csv(RAW / "acs/acs5_2024_sf_tracts.csv", dtype={"GEO_ID": str})
    out["acs"] = {"rows": int(len(acs)), "columns": acs.columns.tolist(),
                  "not_in_tract_polygons": acs.loc[~acs.GEO_ID.str[-11:].isin(tr.GEOID), "GEO_ID"].tolist(),
                  "sentinel_negative_rows": acs.loc[(acs.select_dtypes("number") < 0).any(axis=1), "GEO_ID"].tolist(),
                  "total_population": int(acs.B01003_E001.sum()),
                  "occupied_units": int(acs.B25003_E001.sum()),
                  "renter_units": int(acs.B25003_E003.sum()),
                  "avg_hh_size_valid": {k: round(float(v), 2) for k, v in
                                        acs.loc[acs.B25010_E001 > 0, "B25010_E001"].describe().items()}}
    nb = gpd.read_file(RAW / "analysis_neighborhoods/analysis_neighborhoods_j2bu-swwd.geojson")
    out["analysis_neighborhoods"] = vector_summary(nb, ["nhood"])
    return out


def main():
    report = {"files": files()}
    print("soft story", file=sys.stderr)
    report["soft_story"], ss = soft_story()
    print("assessor", file=sys.stderr)
    report["assessor"], a = assessor()
    print("footprints", file=sys.stderr)
    report["footprints"], fp = footprints()
    print("parcels", file=sys.stderr)
    report["parcels"], p = parcels()
    report["parcel_joins"] = parcel_joins(ss, a, fp, p)
    print("rasters and hazards", file=sys.stderr)
    report["shakemap"] = shakemap()
    report["hazards"] = hazard_layers()
    report["faults"] = faults()
    report["census"] = census()
    json.dump(report, sys.stdout, indent=1, default=str)


if __name__ == "__main__":
    main()
