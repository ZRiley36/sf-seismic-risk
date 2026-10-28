"""Step 1 of the pipeline: read raw files, keep needed columns, reproject to EPSG:7131,
repair geometry, clip to San Francisco, and normalize parcel IDs.

Writes data/interim/01_*.parquet. The ShakeMap raster is not touched here: it stays in its
native EPSG:4326 grid and buildings are sampled in that CRS (see raster.py).
"""
import warnings

import geopandas as gpd
import pandas as pd

from seismic_risk.config import (COUNTY_ZIP, CRS, LIQ_PROB, QFAULTS, RAW, SF_FIPS, TRACT_ZIP,
                                 interim)
from seismic_risk.parcels import normalize_block_lot, normalize_parcel

warnings.filterwarnings("ignore", message=".*geographic CRS.*")
FAULT_BUFFER_M = 100_000  # faults are context, so keep everything within 100 km instead of clipping


def log(msg):
    print(f"  {msg}")


def prep(g, name):
    """Reproject and repair. Returns the frame and logs what changed."""
    g = g.to_crs(CRS)
    bad = ~g.is_valid & g.geometry.notna()
    if bad.any():
        g.loc[bad, "geometry"] = g.loc[bad].make_valid()
        log(f"{name}: repaired {bad.sum()} invalid geometries")
    return g


def clip_to_sf(g, sf, name):
    before = len(g)
    out = g.clip(sf)
    out = out[~out.is_empty]
    log(f"{name}: {before:,} -> {len(out):,} after clipping to SF")
    return out


def sf_boundary():
    cty = gpd.read_file(COUNTY_ZIP)
    sf = prep(cty[cty.GEOID == SF_FIPS][["GEOID", "NAME", "geometry"]], "county")
    sf.to_parquet(interim("01_sf_boundary"))
    log(f"SF county: {sf.area.sum() / 1e6:.1f} km2 land")
    return sf


def soft_story():
    ss = pd.read_csv(RAW / "soft_story/soft_story_beah-shgi.csv", dtype=str)
    ss = ss[["block", "lot", "parcel_number", "property_address", "tier", "status", "point", "data_as_of"]]
    # parcel_number wins over block + lot: they disagree on one row, and the
    # parcel_number version is the one the point and the assessor roll agree with.
    pn = [normalize_parcel(p) or normalize_block_lot(b, l)
          for b, l, p in zip(ss.block, ss.lot, ss.parcel_number)]
    ss["pn"] = pn
    g = gpd.GeoDataFrame(ss.drop(columns="point"), geometry=gpd.GeoSeries.from_wkt(ss.point), crs=4326)
    g = prep(g, "soft story")
    g.insert(0, "ss_id", range(len(g)))
    g.to_parquet(interim("01_soft_story"))
    log(f"soft story: {len(g):,} rows, {g.geometry.isna().sum()} without a point, "
        f"{g.pn.isna().sum()} parcel IDs that don't normalize, "
        f"{(g.pn != g.parcel_number).sum()} changed by normalization")
    return g


def assessor():
    cols = ["closed_roll_year", "parcel_number", "block", "lot", "property_location", "use_code",
            "use_definition", "property_class_code", "property_class_code_definition",
            "year_property_built", "number_of_units", "number_of_stories", "construction_type"]
    path = next((RAW / "assessor_roll").glob("*.csv"))
    a = pd.read_csv(path, dtype=str, usecols=cols)
    a["pn"] = a.parcel_number.map(normalize_parcel)
    a.to_parquet(interim("01_assessor"))
    log(f"assessor: {len(a):,} rows over roll years {a.closed_roll_year.min()}-{a.closed_roll_year.max()}, "
        f"{a.pn.isna().sum()} IDs that don't normalize")


def parcels(sf):
    p = gpd.read_file(RAW / "parcels/parcels_acdm-wktn.geojson",
                      columns=["blklot", "mapblklot", "active", "in_asr_secured_roll", "date_rec_drop"],
                      engine="pyogrio")
    no_geom = p.geometry.isna().sum()
    p = p[p.geometry.notna()]
    p["pn"] = p.blklot.map(normalize_parcel)
    p["map_pn"] = p.mapblklot.map(normalize_parcel)
    p["active"] = p.active.astype(str).str.lower() == "true"
    p = prep(p, "parcels")
    p.to_parquet(interim("01_parcels"))
    log(f"parcels: {len(p):,} with geometry ({no_geom} without, dropped), {p.active.sum():,} active, "
        f"{p.pn.isna().sum()} non-lot IDs kept with pn = null")


def footprints(sf):
    fp = gpd.read_file(RAW / "building_footprints/building_footprints_ynuv-fyni.geojson",
                       columns=["sf16_bldgid", "mblr", "hgt_median_m", "gnd_min_m"], engine="pyogrio")
    fp["pn"] = fp.mblr.map(normalize_parcel)
    fp["hgt_median_m"] = pd.to_numeric(fp.hgt_median_m, errors="coerce")
    fp = prep(fp, "footprints")
    # Footprints straddling the county line are kept whole, assigned by representative point.
    inside = fp.representative_point().within(sf.union_all())
    log(f"footprints: {len(fp):,}, {(~inside).sum():,} outside SF dropped "
        f"({fp.loc[~inside, 'mblr'].str[:2].value_counts().to_dict()})")
    fp = fp[inside].copy()
    fp["area_m2"] = fp.area
    fp.to_parquet(interim("01_footprints"))


def areas(sf):
    nb = gpd.read_file(RAW / "analysis_neighborhoods/analysis_neighborhoods_j2bu-swwd.geojson")
    prep(nb, "neighborhoods").to_parquet(interim("01_neighborhoods"))
    tr = gpd.read_file(TRACT_ZIP)
    tr = prep(tr[tr.COUNTYFP == SF_FIPS[2:]][["GEOID", "NAME", "ALAND", "geometry"]], "tracts")
    tr.to_parquet(interim("01_tracts"))
    acs = pd.read_csv(RAW / "acs/acs5_2024_sf_tracts.csv", dtype={"GEO_ID": str})
    acs.insert(0, "GEOID", acs.GEO_ID.str[-11:])
    acs.to_parquet(interim("01_acs"))
    log(f"neighborhoods {len(nb)}, tracts {len(tr)}, ACS rows {len(acs)}")


def hazards(sf):
    for name in ["cgs_liquefaction_zones", "cgs_landslide_zones", "cgs_unevaluated_areas"]:
        g = gpd.read_file(RAW / name / f"{name}.geojson")
        g = g[["QUAD_NAME", "geometry"]]
        clip_to_sf(prep(g, name), sf, name).to_parquet(interim(f"01_{name}"))
    lp = gpd.read_file(LIQ_PROB)
    clip_to_sf(prep(lp, "liquefaction probability"), sf, "liquefaction probability") \
        .to_parquet(interim("01_liq_prob"))
    q = gpd.read_file(QFAULTS, columns=["fault_name", "section_na", "fault_id", "age", "slip_sense",
                                        "slip_rate", "certainty"],
                      bbox=(-124.0, 36.8, -121.0, 38.8))
    q = prep(q, "faults")
    q = q[q.distance(sf.union_all()) <= FAULT_BUFFER_M]
    q.to_parquet(interim("01_faults"))
    log(f"faults within {FAULT_BUFFER_M / 1000:.0f} km of SF: {len(q):,} segments")


def main():
    sf = sf_boundary()
    soft_story()
    assessor()
    parcels(sf)
    footprints(sf)
    areas(sf)
    hazards(sf)


if __name__ == "__main__":
    main()
