"""Step 2: fix values. Writes data/interim/02_*.parquet.

Soft-story status is collapsed to three values, assessor rows are cut to each parcel's latest
roll year, sentinels become nulls, and liquefaction probability classes become numbers.
"""
import re

import geopandas as gpd
import numpy as np
import pandas as pd

from seismic_risk.config import interim

STATUS = {
    "work complete, cfc issued": "retrofitted",
    "non-compliant": "non_compliant",
    "newly added": "newly_added",
}
# Qfaults has no Holocene class. "latest Quaternary" is < 15 ka, which also takes in the
# latest Pleistocene, so this is a slightly generous reading of Holocene-active.
HOLOCENE_AGES = {"historic", "latest Quaternary"}


def log(msg):
    print(f"  {msg}")


def soft_story():
    g = gpd.read_parquet(interim("01_soft_story"))
    g["status_clean"] = g.status.str.strip().str.lower().map(STATUS)
    if g.status_clean.isna().any():
        raise ValueError(f"unexpected status values: {g.loc[g.status_clean.isna(), 'status'].unique()}")
    # "Newly Added" counts as not retrofitted: nothing says the work is done.
    g["retrofitted"] = g.status_clean == "retrofitted"
    g["tier"] = g.tier.astype(int)
    dup = g.drop(columns=["ss_id"]).duplicated()
    log(f"soft story: dropped {dup.sum()} exact duplicate row(s): "
        f"{g.loc[dup, 'property_address'].tolist()}")
    g = g[~dup].copy()
    g["parcel_rows"] = g.groupby("pn").pn.transform("size")
    log(f"soft story: {len(g):,} buildings, status {g.status_clean.value_counts().to_dict()}, "
        f"{(g.parcel_rows > 1).sum()} rows share a parcel")
    g.to_parquet(interim("02_soft_story"))


def assessor():
    a = pd.read_parquet(interim("01_assessor"))
    a["roll_year"] = a.closed_roll_year.astype(int)
    a["year_built"] = pd.to_numeric(a.year_property_built, errors="coerce")
    a.loc[(a.year_built <= 0) | (a.year_built > 2026), "year_built"] = np.nan
    for src, dst in [("number_of_units", "units"), ("number_of_stories", "stories")]:
        a[dst] = pd.to_numeric(a[src], errors="coerce")
    a = a.dropna(subset=["pn"]).sort_values("roll_year", ascending=False)
    latest = a.drop_duplicates("pn", keep="first")
    keep = ["pn", "roll_year", "property_location", "use_code", "use_definition", "property_class_code",
            "property_class_code_definition", "construction_type", "year_built", "units", "stories"]
    latest = latest[keep].reset_index(drop=True)
    log(f"assessor: {len(a):,} rows -> {len(latest):,} parcels at their latest roll year "
        f"({latest.roll_year.value_counts().sort_index().to_dict()})")
    latest.to_parquet(interim("02_assessor"))


def acs():
    acs = pd.read_parquet(interim("01_acs"))
    num = acs.select_dtypes("number").columns
    sentinel = acs[num] < 0
    log(f"ACS: {int(sentinel.sum().sum())} negative sentinel values -> null")
    acs[num] = acs[num].mask(sentinel)
    out = acs[["GEOID"]].assign(
        population=acs.B01003_E001, households=acs.B25003_E001, renter_households=acs.B25003_E003,
        avg_hh_size=acs.B25010_E001, avg_hh_size_renter=acs.B25010_E003)
    out.to_parquet(interim("02_acs"))


def parse_prob_class(c):
    """'20 - 25' -> (20, 25). '< 5' -> (0, 5). '>= 75' -> (75, 100). '0' -> (0, 0)."""
    c = c.strip()
    if c == "0":
        return 0.0, 0.0
    if m := re.fullmatch(r"<\s*(\d+)", c):
        return 0.0, float(m.group(1))
    if m := re.fullmatch(r">=\s*(\d+)", c):
        return float(m.group(1)), 100.0
    if m := re.fullmatch(r"(\d+)\s*-\s*(\d+)", c):
        return float(m.group(1)), float(m.group(2))
    raise ValueError(f"unknown liquefaction class {c!r}")


def liq_prob():
    g = gpd.read_parquet(interim("01_liq_prob"))
    lo_hi = g.Reclass.map(parse_prob_class)
    g["liq_prob_low"] = [x[0] for x in lo_hi]
    g["liq_prob_high"] = [x[1] for x in lo_hi]
    g["liq_prob_mid"] = (g.liq_prob_low + g.liq_prob_high) / 2
    g.to_parquet(interim("02_liq_prob"))
    log(f"liquefaction probability: {g.Reclass.nunique()} classes parsed")


def faults():
    q = gpd.read_parquet(interim("01_faults"))
    q["holocene"] = q.age.isin(HOLOCENE_AGES)
    q.to_parquet(interim("02_faults"))
    log(f"faults: {q.holocene.sum():,} of {len(q):,} segments Holocene-active (historic or latest Quaternary)")


def main():
    soft_story()
    assessor()
    acs()
    liq_prob()
    faults()


if __name__ == "__main__":
    main()
