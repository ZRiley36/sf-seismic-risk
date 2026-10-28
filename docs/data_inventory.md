# Data Inventory (Step 1)

I generated this on 2026-10-28 with `src/seismic_risk/inventory.py`. The machine-readable output is
`docs/data_inventory.json`. Every number here was read out of the files, not copied from portal documentation.
`python -m seismic_risk.download` fetched everything, and each folder in `data/raw/` has a `SOURCE.txt` with the
URL, fetch time and row count.

Two things to know up front. DataSF moved from `data.sfgov.org` to `data.sf.gov`, and the old host now only
redirects. The Census API now requires a key, so the ACS numbers come from the Census table-based summary files,
which don't.

## Files on disk

```
data/raw/
  soft_story/soft_story_beah-shgi.csv                         1.0 MB
  assessor_roll/assessor_roll_wv5m-vpq2_2020plus.csv         591 MB  (roll years 2020-2025)
  building_footprints/building_footprints_ynuv-fyni.geojson   321 MB
  parcels/parcels_acdm-wktn.geojson                           346 MB  (added, see section 4)
  analysis_neighborhoods/analysis_neighborhoods_j2bu-swwd.geojson
  haywired_shakemap/   grid.xml.zip, rock_grid.xml.zip, raster.zip, uncertainty.xml.zip,
                       info.json, metadata.{txt,xml}, intensity.jpg, fault.kmz, event.txt
  haywired_liquefaction/haywired_expanded_liquefaction_probability.zip   (shapefile)
  cgs_liquefaction_zones/, cgs_landslide_zones/, cgs_unevaluated_areas/   (GeoJSON)
  usgs_qfaults/Qfaults_GIS.zip                                 32 MB  (national)
  census_boundaries/cb_2024_06_tract_500k.zip, cb_2024_us_county_500k.zip
  acs/acs5_2024_sf_tracts.csv                                  (SF rows of the national files)
```

The only derived file so far is `data/interim/haywired_shakemap.tif`, the GeoTIFF conversion of the ShakeMap
(section 5).

---

## 1. Soft-Story Properties (`beah-shgi`)

| | |
|---|---|
| Rows | 4,958, data as of 2026-10-07 |
| Geometry | `point` column, WKT lon/lat (EPSG:4326). 4,954 points, **4 rows with no point** |
| Fields | `block, lot, parcel_number, property_address, address, tier, status, bos_district, point, data_as_of, data_loaded_at`, plus 5 portal-computed region columns |

**Tiers.** Tier 3 has 3,408 rows, tier 4 has 1,026, tier 2 has 516 and tier 1 has 8. Per the dataset description,
tier 1 is buildings with assembly, school or residential care occupancies, tier 2 is 15 or more units, tier 4 is
ground-floor commercial *or buildings in a mapped liquefaction zone*, and tier 3 is everything else. That tier 4
definition matters later. Liquefaction is already baked into the tier, so scoring both tier and liquefaction counts
liquefaction twice for some buildings.

**Status** has only three real values:

| Status | Rows |
|---|---|
| Work Complete, CFC Issued | 4,718 (3 of them spelled "work Complete") |
| Non-Compliant | 228 |
| Newly Added | 12 |

So 95.2% of the list is retrofitted. The unretrofitted group is 240 buildings, and 12 of those are "Newly Added",
which could mean anything from just identified to mid-retrofit. Non-compliant buildings are tier 3 (136), tier 4
(77) and tier 2 (15).

**Parcel IDs.** `block` is 4 characters, or 5 with a letter suffix (`0463A`). `lot` is 3 characters, or 4 with a
suffix (`018A`). `parcel_number` is block plus lot for 4,957 of 4,958 rows. Three rows have unpadded lots, so their
parcel numbers are 6 digits (`1702` + `43` = `170243` instead of `1702043`). Those three are also three of the four
rows with no point, which is probably why the portal couldn't geocode them.

**Rows aren't parcels.** 84 rows share 27 parcels, usually because one lot has several addresses (four Eddy, Turk
and Pierce addresses all sit on `0751001`). Rows on the same parcel share one point, so the points are parcel
locations and not building locations. One row is an exact duplicate (735 Mason St).

## 2. Assessor Historical Secured Property Tax Rolls (`wv5m-vpq2`)

The full dataset is 3.9M rows covering roll years 2007 to 2025. I pulled 2020 to 2025 (1,268,350 rows, which
matches the server's per-year counts exactly). The analysis uses 2025, and the earlier years are there to catch
parcels that dropped out of the latest roll.

| Roll year | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|
| Rows | 209,695 | 210,698 | 211,551 | 212,206 | 212,653 | 211,547 |

**Duplicates.** There are no duplicate parcels within a year. Across years, 213,297 of 213,869 parcels appear more
than once, which is the expected one-row-per-year pattern. The pipeline keeps each parcel's latest year.

**Parcel IDs** in 2025 are 7 characters (176,031), 8 (32,003) or 9 (3,513). The 9-character ones have letters in
both block and lot, like `0452T035C`. `parcel_number` always equals `block` + `lot` here, and all 1.27M values
normalize cleanly.

**Year built** (2025) runs from 1808 to 2025 with a median of 1938. 10,683 are null and none are zero. The
dataset notes it "can be blend of original and newer construction," so a remodel can make an old building look
newer.

**Units** have no nulls but 50,431 zeros (vacant lots, garages, commercial), a median of 1, and a max of 3,146.

**Use and class.** The top use definitions are Single Family Residential (155,111), Multi-Family Residential
(36,278) and Mixed-Use (5,487). Property class is more specific, with Dwelling 95,049, Condominium 52,307, Flats &
Duplex 17,902 and the apartment classes split at 4, 5 to 14, and 15 or more units. `construction_type` is mostly D
(151,588, wood frame) and null for 47,305.

## 3. Building Footprints (`ynuv-fyni`)

| | |
|---|---|
| Rows | 177,023 MultiPolygons, EPSG:4326 |
| Invalid | **20** (need `make_valid`), 0 empty |
| Key | `sf16_bldgid` is unique. `globalid` is unique |
| Parcel field | `mblr`, the block/lot with a 2-letter prefix |
| Height | `hgt_median_m` median 6.6 m, min -0.07, max 218 m. Stored as text |

`mblr` is `SF` plus the parcel for 172,695 footprints. 3,207 start with `SM` and are San Mateo County parcels along
the southern border. 1,118 start with `CN`, and 64% of those match a 2025 parcel, mostly public, government and
vacant-lot classes. I couldn't find documentation for what `CN` means, so I treat it as an SF parcel. Three
footprints have placeholder values (`SFVACSTART1`, `SFPARKHOLL`).

**3,401 footprints fall outside SF County**, 3,140 of them `SM`. These get clipped. 27,309 footprints share a lot
with another footprint, so lot attributes from the assessor will repeat across buildings on the same lot.

Footprints are small. The median is 125 m², while a ShakeMap cell is about 2.7 km² (section 5).

## 4. Parcels – Active and Retired (`acdm-wktn`), added

This wasn't on the original list. I added it because of what the parcel joins showed (section 9). Condo conversions
retire a building's original lot and replace it with one lot per unit, so a soft-story parcel number can vanish
from the current roll. This layer has the geometry for every lot, active or retired, and a `mapblklot` field that
groups condo lots sharing one footprint.

| | |
|---|---|
| Rows | 236,575 (227,971 active, 8,604 retired). 212,255 flagged as in the secured roll |
| Geometry | MultiPolygon, EPSG:4326. **272 rows have no geometry** |
| Keys | `blklot` is unique. 73,287 lots have `blklot` ≠ `mapblklot` (condo units) |
| Odd IDs | 159 `blklot` values don't parse as block/lot (`7331CMAA`, `7517COM`, `3833ROWA`). These look like common areas and rights of way |

## 5. HayWired M7.05 ShakeMap

ComCat lists two ShakeMap versions for the HayWired mainshock. I used `ushaywiredm7.05_se` version 33 (processed
2017-01-11), which is the preferred product (preferredWeight 8, compared with 3 for the legacy
`gllegacyhaywiredm7p05_se` v2). The event is M7.05 at 37.8046, -122.1786, 8 km deep, on 2018-04-18 23:18 UTC.

The ShakeMap comes in three forms. `grid.xml` is the canonical one, an XML table of grid nodes. `raster.zip` has
headerless `.fit` binaries with ESRI-style `.hdr` files. `shape.zip` has contour polygons. No GeoTIFF is published,
so I convert `grid.xml` in a documented step (`python -m seismic_risk.shakemap_tif`).

| | |
|---|---|
| Output | `data/interim/haywired_shakemap.tif`, 6 bands, float32, deflate |
| CRS | EPSG:4326 (grid.xml is in geographic degrees, with no datum stated) |
| Grid | 253 × 206 nodes, 0.016667° × 0.016659° (1 arc-minute, about 1.47 km E-W by 1.85 km N-S here) |
| Extent | -124.208 to -119.992, 35.777 to 39.208 (cell edges) |
| Nodata | none in the source. -9999 is declared for the GeoTIFF but never used |
| Covers SF | yes, completely, with 76 cells touching the county (including the Farallones) |

| Band | Units | Max anywhere | Over SF: min / mean / max |
|---|---|---|---|
| PGA | %g | 245 | 7.4 / 23.1 / 43.7 |
| PGV | cm/s | 527 | 5.4 / 18.7 / 36.5 |
| MMI | intensity | 10.0 | 4.2 / 6.8 / 8.4 |
| PSA 0.3 s | %g | 290 | 14.0 / 59.4 / 103.0 |
| PSA 1.0 s | %g | 660 | 4.7 / 21.0 / 40.0 |
| PSA 3.0 s | %g | 122 | 0.8 / 5.5 / 18.7 |

The SF minimums come from the Farallon Islands cells. On the mainland, MMI ranges from about 6.0 to 8.5.

**Georeferencing check.** grid.xml nodes are cell centers, so the GeoTIFF's corner is half a cell up and left of the
first node. The `.fit` rasters hold exactly the same values (max difference 0.0), but their `.hdr` puts the first
node at the cell *corner*. Using them as-is would shift everything half a cell, about 0.7 to 0.9 km. I use the
grid.xml conversion.

**Resolution is the big constraint.** Mainland SF spans about 10 × 8 cells. Every building in a cell gets the
same value, so point sampling and footprint zonal stats will be nearly identical. A footprint is about 1/20,000 of a
cell. Zonal stats are still worth running as a check, but they won't add information.

**The shaking pattern doesn't follow geology.** I expected the bay fill on the east side to shake harder than the
bedrock hills. It doesn't, at least not in this product:

| Place | Ground | MMI | PGA %g | PGV cm/s |
|---|---|---|---|---|
| Marina | bay fill | 6.62 | 24.6 | 19.9 |
| Mission Bay | bay fill | 6.91 | 24.5 | 22.8 |
| SoMa (4th & Folsom) | old bay margin | 6.99 | 25.3 | 19.6 |
| Treasure Island | artificial fill | 7.18 | 43.7 | 35.8 |
| Bayview/Hunters Point | mixed | 7.03 | 27.0 | 23.9 |
| Pacific Heights | bedrock ridge | 7.09 | 26.9 | 20.8 |
| Twin Peaks | bedrock hill | 7.28 | 29.8 | 19.5 |
| Outer Sunset | dune sand | 6.71 | 17.7 | 16.3 |

Across mainland SF, MMI barely correlates with longitude (r = 0.10). The west, middle and east thirds average 6.85,
6.77 and 6.88. The hottest cells are in the southwest corner near Lake Merced (MMI 8.4 to 8.5), which is far from
the Hayward Fault.

The reason seems to be in the files themselves. `rock_grid.xml` (ground motion on uniform rock) is **identical** to
`grid.xml` for PGA and PGV everywhere on the grid, and for MMI everywhere over SF. ShakeMap didn't apply its own
site amplification. `info.json` lists the ground-motion source as "external estimates", meaning the values were
passed through from the HayWired simulation. Whatever site response the simulation included is all there is, and at
1.5 to 1.85 km it can't separate a block of fill from the hill next to it. Treasure Island is the one place where
fill clearly shows up, probably because its cell is mostly fill.

This is a decision for you (see the questions at the end).

## 6. HayWired expanded liquefaction probability

From Jones (2019), https://doi.org/10.5066/P94HDTD8. The older Jones and Knudsen (2017) raster only covers Alameda
and Santa Clara counties, so it doesn't help in SF.

| | |
|---|---|
| Rows | 11,001 Polygons, EPSG:4269 (NAD83), **95 invalid** |
| Field | one, `Reclass`, a text probability class in percent: `0`, `< 5`, `5 - 10`, ... `70 - 75`, `>= 75` |
| SF coverage | 118.0 km² of the 122.4 km² county land area |

| Class (%) in SF | 0 | < 5 | 5–10 | 10–15 | 15–20 | 20–25 | 45–50 | 50–55 |
|---|---|---|---|---|---|---|---|---|
| km² | 58.1 | 37.7 | 0.3 | 2.6 | 0.9 | 18.6 | 0.05 | 0.02 |

Almost all of SF's liquefiable ground lands in one class, 20 to 25%. These are probabilities that a given spot
liquefies under the scenario shaking, not severities, so a value of 20 to 25% over fill is high, not low.

## 7. CGS Seismic Hazard Zones

From the Department of Conservation's ArcGIS Online services (`services2.arcgis.com/zr3KAIbsRSUyARHG`, updated
November 2025). The `gis.conservation.ca.gov` services require a token. I requested features intersecting
(-123.20, 37.60, -122.30, 37.95) as GeoJSON, so coordinates are EPSG:4326 (the services are natively EPSG:3310).

None of the layers has a zone-type field. The layer *is* the type. Fields are quad name, release and revision
dates, and links to the official PDFs.

| Layer | Features | Invalid | In SF | Area in SF |
|---|---|---|---|---|
| Liquefaction zones | 132 | 0 | 53 | 22.8 km² (19% of land) |
| Landslide zones | 916 | **1** | 320 | 3.8 km² |
| Unevaluated areas | 8 | 0 | 1 (Farallon Islands) | 0.9 km² |

SF is covered by the San Francisco North, San Francisco South, Hunters Point and Oakland West quads, released
2000-11-17 and 2003-02-14, with a 2021-08-17 revision. All of mainland SF has been evaluated.

**Spot checks pass.** The Marina, Mission Bay, SoMa and Treasure Island are all inside CGS liquefaction zones and
in the HayWired 20 to 25% class. Twin Peaks is in a landslide zone. Pacific Heights, the Outer Sunset and my
Bayview point are in neither.

## 8. USGS Quaternary Fault and Fold Database

| | |
|---|---|
| Rows | 112,809 (national), EPSG:4326, 0 invalid |
| Fields | `fault_name, section_na, age, slip_sense, slip_rate, class, certainty, ...` |
| Within 50 km of SF | 1,692 segments |

No mapped Quaternary fault crosses SF County. The database has no "Holocene" age class, so I'll treat `historic`
plus `latest Quaternary` (younger than 15,000 years) as Holocene-active. That slightly overreaches, since 15 ka
reaches into the latest Pleistocene. The nearest such faults are the Serra fault zone (2.2 km), the San Andreas
(4.0 km), the Hayward (11.1 km) and the San Gregorio (19.0 km).

That ordering is a good reminder of why distance to fault is only context here. The scenario is on the Hayward,
which is the third-closest fault, and the San Andreas is much closer to SF.

## 9. Parcel IDs and expected join rates

All sources use the same block/lot scheme once normalized: a 4-digit block with an optional letter, then a 3-digit
lot with an optional letter, uppercase with no separators (`0463A017`). `src/seismic_risk/parcels.py` does this and
is tested in `tests/test_parcels.py`. The differences between sources are small:

| Source | Field | Format quirks |
|---|---|---|
| Soft-story | `parcel_number` (also `block`, `lot`) | 3 unpadded lots |
| Assessor | `parcel_number` | none |
| Footprints | `mblr` | `SF` / `CN` / `SM` prefix |
| Parcels | `blklot`, `mapblklot` | 159 non-lot IDs |

| Join | Match rate |
|---|---|
| Soft-story → 2025 roll, raw strings | 98.99% |
| Soft-story → 2025 roll, normalized | 99.05% (47 unmatched) |
| Soft-story → any roll year 2020–2025 | 99.44% |
| Soft-story → footprint `mblr` | 98.49% (75 unmatched) |
| SF footprints → 2025 roll | 97.65% |
| **Soft-story → 2025 roll, adding the parcel-polygon route** | **99.98% (1 unmatched)** |

The 47 soft-story parcels missing from the 2025 roll are mostly condo conversions. For 34 of them, the same block
has 2025 parcels at the same street number classed as condominiums. Going through the parcel layer (soft-story
point → active parcel polygon → its `mapblklot` group → 2025 roll) recovers 46 of the 47. The only one left is
668 Page St, which has no point but appears in the 2022 roll.

For condo buildings, the pipeline will need to sum units across the condo group and take year built from the group,
since no single condo parcel describes the whole building.

Footprint linking should be spatial too. 92.5% of soft-story points fall inside a footprint, and 98.6% of those
footprints carry the same parcel. The 372 that miss are a median 0.9 m from the nearest footprint (max 31 m).

## 10. Census and neighborhoods

| | |
|---|---|
| SF County (cb 2024, 1:500k) | 1 MultiPolygon (6 parts incl. Farallones), EPSG:4269, 122.4 km² land |
| Tracts (cb 2024) | 242, EPSG:4269, 0 invalid |
| ACS 2024 5-year | 244 SF tracts. Tables B01003 (population), B25003 (tenure), B25010 (avg household size) |
| Analysis Neighborhoods | 41 MultiPolygons, EPSG:4326, field `nhood` |

ACS totals for SF are 830,235 people in 363,970 occupied units, 224,913 of them renter-occupied (62%). Two ACS
tracts (`990100`, `990200`) are water with no polygon and no people. Average household size uses `-666666666` for
tracts with no households: 4 tracts for the total and renter columns, 13 for owners. Valid tract averages range
from 1.26 to 4.11, with a median of 2.12.

The analysis neighborhoods stop at the shoreline and don't include the Farallones (bounds -122.515 to -122.357).

---

## Problems flagged

| # | Issue | Severity | Proposed handling |
|---|---|---|---|
| 1 | ShakeMap has no site amplification and 1.5 to 1.85 km cells | **High** | Your call, see question 1 |
| 2 | `.fit` raster headers are off by half a cell | Medium | Use the grid.xml → GeoTIFF conversion |
| 3 | Tier 4 already includes "in a mapped liquefaction zone" | Medium | Avoid double-counting in the score, see question 3 |
| 4 | 47 soft-story parcels missing from the 2025 roll (condo conversions) | Medium | Recover through parcel polygons and `mapblklot` (99.98%) |
| 5 | 4 soft-story rows with no point, 3 with unpadded lots | Low | Normalize, then place from the parcel polygon |
| 6 | 84 soft-story rows share 27 parcels. 1 exact duplicate | Low | Keep every row as a building, drop the exact duplicate |
| 7 | 12 "Newly Added" soft-story rows, 3 lowercase status values | Low | Normalize case. "Newly Added" handling is question 2 |
| 8 | Assessor repeats parcels across roll years | Low | Keep each parcel's latest year |
| 9 | Year built null for 10,683 parcels, units 0 for 50,431 | Low | Treat as unknown, fall back to earlier roll years |
| 10 | Invalid geometries: 20 footprints, 1 CGS landslide, 95 liquefaction probability | Low | `make_valid` |
| 11 | 3,401 footprints outside SF (mostly San Mateo `SM` lots) | Low | Clip to the county |
| 12 | 272 parcels with no geometry, 159 non-lot parcel IDs | Low | Skip both for spatial joins |
| 13 | ACS `-666666666` sentinels | Low | Treat as null, fall back to the citywide average household size |
| 14 | No "Holocene" class in Qfaults | Low | Use `historic` + `latest Quaternary`, documented |
| 15 | DataSF host moved, Census API needs a key | n/a | Already handled in `download.py` |
