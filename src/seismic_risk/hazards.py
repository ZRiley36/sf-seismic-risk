"""Step 5: ground failure and fault context for every building.

Ground failure
  CGS liquefaction / landslide zone: the footprint intersects a zone (the footprint is the
  building, so any overlap counts). Buildings without a footprint use their point. The
  point-only answer is kept too, for comparison.
  HayWired liquefaction probability: the highest class any part of the footprint touches,
  stored as the class's low, high and midpoint percent.

Fault context
  Distance from the representative point to the nearest Holocene-active fault trace (Qfaults
  age "historic" or "latest Quaternary"), and to the Hayward fault zone, which is the
  scenario's source. This is context only. Shaking already accounts for distance to the
  rupture, so fault distance is not part of the score.
"""
import geopandas as gpd
import numpy as np

from seismic_risk.config import interim


def log(msg):
    print(f"  {msg}")


def in_zone(shapes, zone):
    """True for each shape that intersects any zone polygon."""
    j = gpd.sjoin(gpd.GeoDataFrame(geometry=shapes), zone[["geometry"]], predicate="intersects")
    return shapes.index.isin(j.index)


def main():
    b = gpd.read_parquet(interim("04_buildings_shaking"))
    shape = gpd.GeoSeries(b.footprint, crs=b.crs).where(b.footprint.notna(), b.geometry)
    pt = gpd.GeoSeries(b.sample_point, crs=b.crs)

    for name, col in [("cgs_liquefaction_zones", "cgs_liquefaction"), ("cgs_landslide_zones", "cgs_landslide")]:
        z = gpd.read_parquet(interim(f"01_{name}"))
        b[col] = in_zone(shape, z)
        b[f"{col}_point"] = in_zone(pt, z)
        log(f"{col}: {b[col].sum():,} buildings ({b[col].mean():.1%}) by footprint, "
            f"{b[f'{col}_point'].sum():,} by point")

    lp = gpd.read_parquet(interim("02_liq_prob"))
    j = gpd.sjoin(gpd.GeoDataFrame(geometry=shape), lp[["liq_prob_low", "liq_prob_high", "liq_prob_mid", "geometry"]],
                  predicate="intersects")
    top = j.sort_values("liq_prob_mid").groupby(level=0).last()
    for c in ["liq_prob_low", "liq_prob_high", "liq_prob_mid"]:
        b[c] = top[c].reindex(b.index)
    log(f"liquefaction probability: {b.liq_prob_mid.notna().sum():,} buildings covered, "
        f"class midpoints {b.liq_prob_mid.value_counts().sort_index().to_dict()}")

    zone = b.cgs_liquefaction
    log(f"liquefaction probability midpoint, in CGS zone: median {b.loc[zone, 'liq_prob_mid'].median()}, "
        f"outside: median {b.loc[~zone, 'liq_prob_mid'].median()}")
    t4 = b.tier == 4
    log(f"tier 4 buildings in a CGS liquefaction zone: {(t4 & zone).sum():,} of {t4.sum():,}. "
        f"Liquefaction-zone buildings that are tier 4: {(t4 & zone).sum():,} of {zone.sum():,}")

    q = gpd.read_parquet(interim("02_faults"))
    hol = q[q.holocene]
    near = gpd.sjoin_nearest(gpd.GeoDataFrame(geometry=pt), hol[["fault_name", "geometry"]], distance_col="d")
    near = near[~near.index.duplicated()]
    b["nearest_fault"] = near.fault_name
    b["nearest_fault_km"] = near.d / 1000
    hay = q[q.fault_name.str.contains("Hayward", na=False) & q.holocene].union_all()
    b["hayward_fault_km"] = pt.distance(hay) / 1000
    log(f"nearest Holocene fault: {b.nearest_fault.value_counts().to_dict()}, "
        f"{b.nearest_fault_km.min():.1f}-{b.nearest_fault_km.max():.1f} km")
    log(f"Hayward fault distance: {b.hayward_fault_km.min():.1f}-{b.hayward_fault_km.max():.1f} km")
    r = np.corrcoef(b.hayward_fault_km, b.MMI)[0, 1]
    log(f"correlation of MMI with Hayward distance: {r:.2f}")
    b.to_parquet(interim("05_buildings_hazards"))


if __name__ == "__main__":
    main()
