"""Paths and constants shared by every pipeline step."""
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw"
INTERIM = ROOT / "data/interim"
PROCESSED = ROOT / "data/processed"
DOCS = ROOT / "docs"

# NAD83(2011) / San Francisco CS13, in meters. A low-distortion projection built for SF, and its
# area of use covers the whole Bay Area, so distances to the Hayward fault are still accurate.
CRS = "EPSG:7131"
GEOGRAPHIC = "EPSG:4326"

SHAKEMAP_TIF = INTERIM / "haywired_shakemap.tif"
LIQ_PROB = ("zip://" + str(RAW / "haywired_liquefaction/haywired_expanded_liquefaction_probability.zip")
            + "!haywired_expanded_liquefaction_probability/haywired_expanded_liquefaction_probability.shp")
QFAULTS = "zip://" + str(RAW / "usgs_qfaults/Qfaults_GIS.zip") + "!SHP/Qfaults_US_Database.shp"
COUNTY_ZIP = "zip://" + str(RAW / "census_boundaries/cb_2024_us_county_500k.zip")
TRACT_ZIP = "zip://" + str(RAW / "census_boundaries/cb_2024_06_tract_500k.zip")
SF_FIPS = "06075"


def interim(name):
    return INTERIM / f"{name}.parquet"


def score_config(path=ROOT / "config/score.toml"):
    with open(path, "rb") as f:
        return tomllib.load(f)
