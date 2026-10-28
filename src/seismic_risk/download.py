"""Download every raw source into data/raw/<name>/ with a SOURCE.txt next to it.

Run once: python -m seismic_risk.download  (add --force to re-fetch)
Raw files are never edited after this. The only filtering done here is server-side
(assessor roll years, CGS zones near SF) or keeping SF rows out of national ACS files,
and each SOURCE.txt says so.
"""
import argparse
import csv
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

RAW = Path(__file__).resolve().parents[2] / "data" / "raw"
SODA = "https://data.sf.gov"
SHAKEMAP = ("https://earthquake.usgs.gov/product/shakemap-scenario/ushaywiredm7.05_se/us/"
            "1484100039013/download/")
CGS = "https://services2.arcgis.com/zr3KAIbsRSUyARHG/ArcGIS/rest/services/{}/FeatureServer/0/query"
# SF county plus the Farallon Islands, with margin. CGS zones are clipped to the city later.
SF_BBOX = (-123.20, 37.60, -122.30, 37.95)
ASSESSOR_FIRST_YEAR = 2020
ACS_YEAR = 2024
ACS_TABLES = ["b01003", "b25003", "b25010"]

session = requests.Session()
session.headers["User-Agent"] = "sf-seismic-risk portfolio project"


def write_source(folder, url, note, rows=None):
    lines = [f"url: {url}", f"fetched: {datetime.now(timezone.utc).isoformat(timespec='seconds')}"]
    if rows is not None:
        lines.append(f"rows: {rows}")
    lines.append(f"note: {note}")
    (folder / "SOURCE.txt").write_text("\n".join(lines) + "\n")


def fetch(url, dest, params=None):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with session.get(url, params=params, stream=True, timeout=600) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        tmp.rename(dest)
    print(f"  {dest.relative_to(RAW)}  {dest.stat().st_size / 1e6:.1f} MB")
    return dest


def soft_story(force):
    d = RAW / "soft_story"
    out = d / "soft_story_beah-shgi.csv"
    if out.exists() and not force:
        return
    url = f"{SODA}/api/views/beah-shgi/rows.csv?accessType=DOWNLOAD"
    fetch(url, out)
    rows = sum(1 for _ in open(out, encoding="utf-8")) - 1
    write_source(d, url, "DataSF Soft-Story Properties, full export. `point` is WKT lon/lat.", rows)


def socrata_geojson(dataset, name, note, force):
    d = RAW / name
    out = d / f"{name}_{dataset}.geojson"
    if out.exists() and not force:
        return
    url = f"{SODA}/api/geospatial/{dataset}?method=export&format=GeoJSON"
    fetch(url, out)
    rows = len(json.loads(out.read_text())["features"])
    write_source(d, url, note, rows)


def assessor(force):
    d = RAW / "assessor_roll"
    out = d / f"assessor_roll_wv5m-vpq2_{ASSESSOR_FIRST_YEAR}plus.csv"
    if out.exists() and not force:
        return
    d.mkdir(parents=True, exist_ok=True)
    url = f"{SODA}/resource/wv5m-vpq2.csv"
    where = f"closed_roll_year >= '{ASSESSOR_FIRST_YEAR}'"
    page, offset, total = 200_000, 0, 0
    tmp = out.with_suffix(".part")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        while True:
            r = session.get(url, params={"$where": where, "$order": ":id", "$limit": page,
                                         "$offset": offset}, timeout=600)
            r.raise_for_status()
            text = r.text
            body = text.split("\n", 1)
            if offset == 0:
                f.write(text)
            elif len(body) > 1:
                f.write(body[1])
            n = sum(1 for _ in csv.reader(io.StringIO(text))) - 1
            total += n
            print(f"  assessor rows {total:,}", file=sys.stderr)
            if n < page:
                break
            offset += page
    tmp.rename(out)
    write_source(d, f"{url}?$where={where}", "Assessor Historical Secured Property Tax Rolls, "
                 f"server-side filtered to closed_roll_year >= {ASSESSOR_FIRST_YEAR}. "
                 "All columns, every row for those years.", total)


def shakemap(force):
    d = RAW / "haywired_shakemap"
    files = ["grid.xml.zip", "raster.zip", "uncertainty.xml.zip", "info.json", "metadata.txt",
             "metadata.xml", "intensity.jpg", "fault.kmz", "event.txt"]
    if (d / "grid.xml.zip").exists() and not force:
        return
    for f in files:
        fetch(SHAKEMAP + f, d / f)
    write_source(d, SHAKEMAP, "USGS ShakeMap scenario ushaywiredm7.05_se, version 33 "
                 "(the preferred product in ComCat, preferredWeight 8). Event: "
                 "https://earthquake.usgs.gov/scenarios/eventpage/ushaywiredm7.05_se")


def liquefaction_probability(force):
    d = RAW / "haywired_liquefaction"
    out = d / "haywired_expanded_liquefaction_probability.zip"
    if out.exists() and not force:
        return
    url = "https://www.sciencebase.gov/catalog/file/get/5d2fb2b7e4b01d82ce82c674"
    fetch(url, out)
    write_source(d, url, "Expanded liquefaction probability, HayWired mainshock "
                 "(ScienceBase 5d2fb2b7e4b01d82ce82c674). All attached files, as zipped by "
                 "ScienceBase.")


def cgs_zones(force):
    layers = {"cgs_liquefaction_zones": "CGS_Liquefaction_Zones",
              "cgs_landslide_zones": "CGS_Landslide_Zones",
              "cgs_unevaluated_areas": "CGS_SHZ_Unevaluated_Areas"}
    for name, svc in layers.items():
        d = RAW / name
        out = d / f"{name}.geojson"
        if out.exists() and not force:
            continue
        url = CGS.format(svc)
        feats, offset = [], 0
        while True:
            params = {"where": "1=1", "outFields": "*", "f": "geojson",
                      "geometry": ",".join(map(str, SF_BBOX)), "geometryType": "esriGeometryEnvelope",
                      "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
                      "resultOffset": offset, "resultRecordCount": 1000, "orderByFields": "OBJECTID"}
            r = session.get(url, params=params, timeout=600)
            r.raise_for_status()
            page = r.json()
            if "error" in page:
                raise RuntimeError(page["error"])
            feats += page["features"]
            if not page.get("properties", {}).get("exceededTransferLimit") and \
                    not page.get("exceededTransferLimit"):
                break
            offset += len(page["features"])
        d.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
        print(f"  {out.relative_to(RAW)}  {len(feats)} features")
        write_source(d, url, f"California Dept. of Conservation, CGS Seismic Hazards Program. "
                     f"Features intersecting bbox {SF_BBOX} (EPSG:4326). GeoJSON output, so "
                     "coordinates are EPSG:4326 (service native is EPSG:3310).", len(feats))


def qfaults(force):
    d = RAW / "usgs_qfaults"
    out = d / "Qfaults_GIS.zip"
    if out.exists() and not force:
        return
    url = "https://earthquake.usgs.gov/static/lfs/nshm/qfaults/Qfaults_GIS.zip"
    fetch(url, out)
    write_source(d, url, "USGS Quaternary Fault and Fold Database, national GIS download.")


def census_boundaries(force):
    d = RAW / "census_boundaries"
    for f in [f"cb_{ACS_YEAR}_06_tract_500k.zip", f"cb_{ACS_YEAR}_us_county_500k.zip"]:
        if (d / f).exists() and not force:
            continue
        fetch(f"https://www2.census.gov/geo/tiger/GENZ{ACS_YEAR}/shp/{f}", d / f)
    write_source(d, f"https://www2.census.gov/geo/tiger/GENZ{ACS_YEAR}/shp/",
                 "Census cartographic boundary files (1:500k, shoreline-clipped). California "
                 "tracts and US counties, unmodified.")


def acs(force):
    d = RAW / "acs"
    out = d / f"acs5_{ACS_YEAR}_sf_tracts.csv"
    if out.exists() and not force:
        return
    base = f"https://www2.census.gov/programs-surveys/acs/summary_file/{ACS_YEAR}/table-based-SF/data/5YRData/"
    merged = {}
    for t in ACS_TABLES:
        r = session.get(f"{base}acsdt5y{ACS_YEAR}-{t}.dat", timeout=600)
        r.raise_for_status()
        rows = csv.DictReader(io.StringIO(r.text), delimiter="|")
        for row in rows:
            if row["GEO_ID"].startswith("1400000US06075"):
                merged.setdefault(row["GEO_ID"], {"GEO_ID": row["GEO_ID"]}).update(
                    {k: v for k, v in row.items() if k != "GEO_ID"})
        print(f"  ACS {t}: {len(merged)} SF tracts so far")
    d.mkdir(parents=True, exist_ok=True)
    cols = ["GEO_ID"] + sorted({k for r in merged.values() for k in r} - {"GEO_ID"})
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(merged.values())
    write_source(d, base, f"ACS {ACS_YEAR} 5-year table-based summary files {ACS_TABLES}. "
                 "Kept only rows whose GEO_ID starts with 1400000US06075 (SF census tracts). "
                 "Column names are ACS variable IDs (E = estimate, M = margin of error).",
                 len(merged))


STEPS = {
    "soft_story": soft_story,
    "neighborhoods": lambda force: socrata_geojson(
        "j2bu-swwd", "analysis_neighborhoods", "DataSF Analysis Neighborhoods.", force),
    "parcels": lambda force: socrata_geojson(
        "acdm-wktn", "parcels", "DataSF Parcels - Active and Retired, full export. mapblklot groups "
        "condominium lots that share one footprint; retired lots keep their geometry.", force),
    "footprints": lambda force: socrata_geojson(
        "ynuv-fyni", "building_footprints", "DataSF Building Footprints, full export.", force),
    "assessor": assessor,
    "shakemap": shakemap,
    "liquefaction_probability": liquefaction_probability,
    "cgs": cgs_zones,
    "qfaults": qfaults,
    "census_boundaries": census_boundaries,
    "acs": acs,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("only", nargs="*", help=f"steps to run (default: all): {', '.join(STEPS)}")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    unknown = set(args.only) - set(STEPS)
    if unknown:
        ap.error(f"unknown steps: {', '.join(sorted(unknown))}")
    for name in args.only or STEPS:
        print(name)
        STEPS[name](args.force)


if __name__ == "__main__":
    main()
