"""Step 7: neighborhood and tract summaries, and the final building table.

Estimated residents = units x the tract's average renter household size (ACS 2024 5-year
B25010). Soft-story buildings are overwhelmingly rentals, so the renter figure fits better than
the all-households one. Tracts without a renter figure fall back to the all-households average,
then to the citywide renter average. This assumes every unit is occupied, so it's an upper-end
estimate. Units are split evenly among soft-story rows that share a parcel (`units_alloc`), so
no unit is counted twice.

Writes data/processed/buildings_seismic.parquet, neighborhood_summary.csv, tract_summary.csv.
"""
import geopandas as gpd
import numpy as np
import pandas as pd

from seismic_risk.config import PROCESSED, interim


def log(msg):
    print(f"  {msg}")


def household_size(b):
    acs = pd.read_parquet(interim("02_acs")).set_index("GEOID")
    city = (acs.avg_hh_size_renter * acs.renter_households).sum() / acs.loc[
        acs.avg_hh_size_renter.notna(), "renter_households"].sum()
    hh = b.tract.map(acs.avg_hh_size_renter)
    src = np.where(hh.notna(), "tract_renter", None)
    fb = b.tract.map(acs.avg_hh_size)
    src = np.where(hh.isna() & fb.notna(), "tract_all", src)
    hh = hh.fillna(fb)
    src = np.where(hh.isna(), "citywide_renter", src)
    hh = hh.fillna(city)
    log(f"household size: citywide renter average {city:.2f}, sources {pd.Series(src).value_counts().to_dict()}")
    return hh, src


def summarize(b, key):
    unretro = ~b.retrofitted
    hi = b.high_score
    g = b.assign(
        unretrofitted=unretro,
        high_unretrofitted=hi & unretro,
        units_high=b.units_alloc.where(hi, 0),
        residents_high=b.est_residents.where(hi, 0),
        residents_unretrofitted=b.est_residents.where(unretro, 0),
        in_liq_zone=b.cgs_liquefaction,
    ).groupby(key)
    out = pd.DataFrame({
        "soft_story_buildings": g.size(),
        "unretrofitted": g.unretrofitted.sum(),
        "high_score_buildings": g.high_score.sum(),
        "high_score_unretrofitted": g.high_unretrofitted.sum(),
        "in_cgs_liquefaction_zone": g.in_liq_zone.sum(),
        "residential_units": g.units_alloc.sum().round(0),
        "units_in_high_score": g.units_high.sum().round(0),
        "est_residents_in_high_score": g.residents_high.sum().round(0),
        "est_residents_unretrofitted": g.residents_unretrofitted.sum().round(0),
        "mean_mmi": g.MMI.mean().round(2),
        "mean_score": g.score.mean().round(3),
        "max_score": g.score.max().round(3),
    })
    out["pct_unretrofitted"] = (out.unretrofitted / out.soft_story_buildings * 100).round(1)
    return out.sort_values(["units_in_high_score", "high_score_buildings"], ascending=False)


def main():
    b = gpd.read_parquet(interim("06_buildings_scored"))
    b["avg_hh_size"], b["hh_size_source"] = household_size(b)
    b["est_residents"] = b.units_alloc.fillna(0) * b.avg_hh_size
    log(f"units: {b.units_alloc.sum():,.0f} across {len(b):,} buildings, "
        f"est. residents {b.est_residents.sum():,.0f}")

    nb = summarize(b, "nhood")
    tr = summarize(b, "tract")
    PROCESSED.mkdir(parents=True, exist_ok=True)
    nb.to_csv(PROCESSED / "neighborhood_summary.csv")
    tr.to_csv(PROCESSED / "tract_summary.csv")
    for name, t in [("neighborhoods", nb), ("tracts", tr)]:
        log(f"{name}: {len(t)} with soft-story buildings. Totals: {int(t.soft_story_buildings.sum()):,} buildings, "
            f"{int(t.unretrofitted.sum())} unretrofitted, {int(t.units_in_high_score.sum()):,} units in high-score "
            f"buildings, {int(t.est_residents_in_high_score.sum()):,} est. residents")

    drop = ["parcel_lots"]
    out = b.drop(columns=drop)
    out["parcel_lots"] = b.parcel_lots.map(lambda x: ";".join(x))
    out.to_parquet(PROCESSED / "buildings_seismic.parquet")
    log(f"wrote buildings_seismic.parquet ({len(out):,} rows, {len(out.columns)} columns)")
    pd.set_option("display.width", 220)
    print(nb.head(10)[["soft_story_buildings", "unretrofitted", "high_score_buildings", "high_score_unretrofitted",
                       "units_in_high_score", "est_residents_in_high_score", "in_cgs_liquefaction_zone",
                       "mean_mmi"]].to_string())


if __name__ == "__main__":
    main()
