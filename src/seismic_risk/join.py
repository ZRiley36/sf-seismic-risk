"""Step 3: build the soft-story building table.

One row per soft-story building (a row of the DataSF list), with:
  location     the DataSF point, or the parcel polygon's representative point if it has none
  parcel group the building's lot plus any condo lots that share its footprint (mapblklot)
  assessor     year built, units, stories and use, from the 2025 roll where possible
  footprint    the building outline, preferring footprints on the building's own parcel
  area         analysis neighborhood and census tract

Every join records how it matched in a *_match column. Unmatched rows are kept and flagged.
Writes data/interim/03_buildings.parquet with two geometry columns: `geometry` (the
representative point used for sampling) and `footprint`.
"""
import geopandas as gpd
import numpy as np
import pandas as pd

from seismic_risk.config import CRS, interim

NEAREST_FOOTPRINT_MAX_M = 35  # the farthest soft-story point from any footprint in the inventory was 31 m
LATEST_ROLL = 2025


def log(msg):
    print(f"  {msg}")


def rate(s, label, total):
    for k, v in s.value_counts(dropna=False).items():
        log(f"{label} {k}: {v:,} ({v / total:.2%})")


def locate(b, parcels):
    """Fill missing points from the parcel polygon (active lot first, then retired)."""
    b["loc_match"] = np.where(b.geometry.notna(), "datasf_point", None)
    missing = b.geometry.isna()
    poly = (parcels.sort_values("active", ascending=False).drop_duplicates("pn")
            .set_index("pn").geometry.representative_point())
    fill = b.loc[missing, "pn"].map(poly)
    b.loc[missing & fill.notna(), "geometry"] = fill[fill.notna()]
    b.loc[missing & fill.notna(), "loc_match"] = "parcel_polygon"
    b["loc_match"] = b.loc_match.fillna("none")
    return b


def parcel_groups(b, parcels):
    """The set of lots that make up each building's parcel.

    Starts from the building's own lot and the active lot(s) under its point, then expands to every
    active lot with the same mapblklot. A plain lot is a group of one. A condo building becomes all
    of its unit lots, which is how a retired pre-conversion lot finds its way back into the roll.
    """
    active = parcels[parcels.active]
    map_of = parcels.drop_duplicates("pn").set_index("pn").map_pn
    lots_of = active.dropna(subset=["map_pn"]).groupby("map_pn").pn.apply(set)
    hits = gpd.sjoin(b[["geometry"]].dropna(), active[["map_pn", "geometry"]], predicate="within")
    under_point = hits.groupby(level=0).map_pn.apply(lambda s: set(s.dropna()))
    groups = []
    for i, pn in b.pn.items():
        keys = set(under_point.get(i, set()))
        own = map_of.get(pn)
        if isinstance(own, str):
            keys.add(own)
        lots = {pn} | set().union(*(lots_of.get(k, set()) for k in keys))
        groups.append(frozenset(lots))
    b["parcel_lots"] = groups
    b["group_key"] = [min(g) for g in groups]
    return b


def attach_assessor(b, assessor):
    """Assessor attributes for each building's parcel group.

    One 2025 lot: use it. Several 2025 lots (condo units): units and stories are summed and maxed,
    year built is the earliest on record, and use/class come from the most common lot. No 2025
    lot: fall back to the building's own lot in its latest earlier roll year.
    """
    a = assessor.set_index("pn")
    cur = a[a.roll_year == LATEST_ROLL]
    rows = []
    for pn, lots in zip(b.pn, b.parcel_lots):
        hit = cur.loc[cur.index.intersection(list(lots))]
        if len(hit) == 1:
            r = hit.iloc[0].to_dict()
            r["assessor_match"] = "direct" if hit.index[0] == pn else "parcel_group_single"
            r["assessor_lots"] = 1
        elif len(hit) > 1:
            mode = hit.property_class_code_definition.mode()
            top = hit[hit.property_class_code_definition == mode.iloc[0]].iloc[0] if len(mode) else hit.iloc[0]
            r = top.to_dict()
            r.update(units=hit.units.sum(min_count=1), stories=hit.stories.max(),
                     year_built=hit.year_built.min(), assessor_match="condo_group",
                     assessor_lots=len(hit))
        elif pn in a.index:
            r = a.loc[pn].to_dict()
            r["assessor_match"] = "earlier_roll"
            r["assessor_lots"] = 1
        else:
            r = {"assessor_match": "none", "assessor_lots": 0}
        rows.append(r)
    cols = ["roll_year", "use_definition", "property_class_code", "property_class_code_definition",
            "construction_type", "year_built", "units", "stories", "assessor_match", "assessor_lots"]
    return pd.concat([b.reset_index(drop=True), pd.DataFrame(rows).reindex(columns=cols)], axis=1)


def attach_footprint(b, fp):
    fp = fp.reset_index(drop=True)
    by_pn = fp.dropna(subset=["pn"]).groupby("pn").groups
    contains = gpd.sjoin(b[["geometry"]].dropna(), fp[["geometry"]], predicate="within")
    in_fp = contains.groupby(level=0).index_right.apply(list)
    chosen, how = [], []
    for i, lots in zip(b.index, b.parcel_lots):
        cands = [j for lot in lots for j in by_pn.get(lot, [])]
        under = in_fp.get(i, [])
        both = [j for j in under if j in set(cands)]
        if both:
            chosen.append(both[0]); how.append("point_in_parcel_footprint")
        elif cands:
            chosen.append(max(cands, key=lambda j: fp.at[j, "area_m2"])); how.append("largest_on_parcel")
        elif under:
            chosen.append(under[0]); how.append("point_in_other_footprint")
        else:
            chosen.append(None); how.append(None)
    b["fp_idx"] = chosen
    b["footprint_match"] = how
    todo = b.fp_idx.isna() & b.geometry.notna()
    if todo.any():
        near = gpd.sjoin_nearest(b.loc[todo, ["geometry"]], fp[["geometry"]],
                                 max_distance=NEAREST_FOOTPRINT_MAX_M, distance_col="d")
        near = near[~near.index.duplicated()]
        b.loc[near.index, "fp_idx"] = near.index_right
        b.loc[near.index, "footprint_match"] = "nearest"
    b["footprint_match"] = b.footprint_match.fillna("none")
    sel = b.fp_idx.dropna().astype(int)
    b["sf16_bldgid"] = None
    b.loc[sel.index, "sf16_bldgid"] = fp.loc[sel.values, "sf16_bldgid"].values
    b["footprint"] = gpd.GeoSeries([None] * len(b), crs=CRS)
    b.loc[sel.index, "footprint"] = fp.loc[sel.values, "geometry"].values
    b["footprint_area_m2"] = np.nan
    b.loc[sel.index, "footprint_area_m2"] = fp.loc[sel.values, "area_m2"].values
    b["height_m"] = np.nan
    b.loc[sel.index, "height_m"] = fp.loc[sel.values, "hgt_median_m"].values
    b["footprints_shared"] = b.groupby("fp_idx").fp_idx.transform("size")
    return b.drop(columns="fp_idx")


def attach_areas(b):
    nb = gpd.read_parquet(interim("01_neighborhoods"))
    tr = gpd.read_parquet(interim("01_tracts"))
    pts = b[["geometry"]].dropna()
    j = gpd.sjoin(pts, nb[["nhood", "geometry"]], predicate="within")
    b["nhood"] = j[~j.index.duplicated()].nhood
    j = gpd.sjoin(pts, tr[["GEOID", "geometry"]], predicate="within")
    b["tract"] = j[~j.index.duplicated()].GEOID
    return b


def main():
    b = gpd.read_parquet(interim("02_soft_story"))
    parcels = gpd.read_parquet(interim("01_parcels"))
    n = len(b)
    log(f"soft-story buildings: {n:,}")

    b = locate(b, parcels)
    rate(b.loc_match, "location", n)

    b = parcel_groups(b, parcels)
    sizes = b.parcel_lots.map(len)
    log(f"parcel groups: {(sizes == 1).sum():,} single lots, {(sizes > 1).sum():,} multi-lot "
        f"(median {sizes[sizes > 1].median():.0f} lots)")

    b = gpd.GeoDataFrame(attach_assessor(b, pd.read_parquet(interim("02_assessor"))), geometry="geometry",
                         crs=CRS)
    rate(b.assessor_match, "assessor", n)
    # Several soft-story rows can sit on one parcel group. Split the group's units among them so
    # neighborhood totals don't count the same units twice.
    b["rows_on_group"] = b.groupby("group_key").group_key.transform("size")
    b["units_alloc"] = b.units / b.rows_on_group

    b = attach_footprint(b, gpd.read_parquet(interim("01_footprints")))
    rate(b.footprint_match, "footprint", n)
    # A building with no point and no parcel polygon can still be placed by its parcel's footprint.
    fill = b.geometry.isna() & b.footprint.notna()
    b.loc[fill, "geometry"] = b.loc[fill, "footprint"].representative_point()
    b.loc[fill, "loc_match"] = "footprint"
    if fill.any():
        log(f"location filled from footprint: {fill.sum()}")

    b = attach_areas(b)
    log(f"neighborhood assigned: {b.nhood.notna().sum():,}, tract assigned: {b.tract.notna().sum():,}")

    b["parcel_lots"] = b.parcel_lots.map(lambda s: sorted(s))
    b.to_parquet(interim("03_buildings"))
    log(f"wrote {interim('03_buildings').name}")


if __name__ == "__main__":
    main()
