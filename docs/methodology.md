# Methodology (Step 2)

This covers the pipeline from raw files to the scored building table and the neighborhood and tract summaries.
`make pipeline` (or `python -m seismic_risk`) reruns all of it in about a minute. Every number here comes from that
run's log. The data itself is described in `data_inventory.md`.

| Step | Module | Output | What it does |
|---|---|---|---|
| 0 | `shakemap_tif.py` | `data/interim/haywired_shakemap.tif` | grid.xml to a 6-band GeoTIFF |
| 1 | `ingest.py` | `01_*.parquet` | Reproject to EPSG:7131, repair geometry, clip to SF, normalize parcel IDs |
| 2 | `clean.py` | `02_*.parquet` | Status values, latest roll year per parcel, ACS sentinels, liquefaction classes, fault ages |
| 3 | `join.py` | `03_buildings` | Soft-story list + parcels + assessor + footprints + neighborhood + tract |
| 4 | `raster.py` | `04_buildings_shaking` | ShakeMap values at a point and over the footprint |
| 5 | `hazards.py` | `05_buildings_hazards` | CGS zones, liquefaction probability, fault distance |
| 6 | `score.py` | `06_buildings_scored`, `docs/score_sensitivity.csv` | Index and sensitivity check |
| 7 | `analyze.py` | `data/processed/*` | Building table and neighborhood and tract summaries |
| 8 | `outputs.py` | `data/processed/web/*` | ShakeMap cropped to SF as a COG, building points as GeoJSON |
| | `spotcheck.py` | log only | Re-derives a few buildings straight from the raw files |

## Decisions made after the inventory

**The ShakeMap is used as published.** The HayWired ShakeMap has no site amplification of its own (its rock and site
grids are identical over SF) and its cells are 1.5 to 1.85 km across. So shaking in this analysis doesn't separate
bay fill from bedrock, and the fill story is carried by the ground-failure layers instead. I could have added a
Vs30-based amplification, but then it wouldn't be the HayWired scenario anymore.

**MMI is the primary shaking metric.** It's what the scenario reports lead with and it's the easiest to explain.
PSA at 0.3 seconds is closer to how a short wood-frame building actually responds, so it runs as a sensitivity
variant.

**"Newly Added" counts as unretrofitted.** Nothing in the data says the work is done. That puts 240 buildings in
the unretrofitted group: 228 non-compliant and 12 newly added.

**Tier and ground failure are scored separately.** Tier 4 is partly defined by being in a liquefaction zone, so this
double-counts for some buildings. It's less overlap than I expected, though. 448 of the 777 soft-story buildings in
a CGS liquefaction zone are tier 4, and 578 of the 1,026 tier 4 buildings are outside the zones, presumably tier 4 for
ground-floor commercial instead. The `no_tier` variant shows what happens without tier, and it barely moves the ranking.

## Projection

Everything is in **EPSG:7131, NAD83(2011) / San Francisco CS13**, in meters. It's a low-distortion projection
designed for San Francisco, so distances and areas are as close to true as you can get here. Its area of use covers
the whole Bay Area, which matters because distance to the Hayward Fault is measured across the bay. CA State Plane
III (EPSG:2227) would have worked too, but it's in US survey feet and its distortion isn't tuned to SF.

The ShakeMap is the one exception. It stays in its native EPSG:4326 grid, and buildings are transformed to EPSG:4326
to sample it. Warping a 1.5 km grid into meters would resample the values and gain nothing.

Clipping uses the Census cartographic boundary for SF County, which is shoreline-clipped and includes Treasure
Island and the Farallones. Faults aren't clipped. Everything within 100 km is kept so distances are right.

## Building table

There's one row per soft-story building, meaning a row of the DataSF list. The one exact duplicate row
is dropped, which leaves **4,957 buildings**.

**Location.** 4,953 buildings use the DataSF point. Three without a point get the representative point of their
parcel polygon, once their unpadded parcel numbers are fixed. The fourth has no point and no current parcel
polygon, so it's placed by the footprint on its lot.

Parcel IDs come from `parcel_number` first and block + lot second. The two disagree on exactly one row,
and the point and the 2025 roll both back up `parcel_number`.

**Parcel groups.** A building's parcel group is its own lot plus every active lot sharing a `mapblklot` with it or
with the lot under its point. For a plain building that's one lot. For a condo conversion it's all the unit lots,
which is how a building whose original lot was retired finds its way back into the roll. 302 buildings have
multi-lot groups, with a median of 6 lots.

**Assessor attributes** come from the 2025 roll:

| Route | Buildings |
|---|---|
| The building's own lot | 4,664 (94.1%) |
| Condo group: units summed, earliest year built, most common class | 282 (5.7%) |
| One lot of the group, not the building's own | 10 (0.2%) |
| Own lot in an earlier roll (2022) | 1 |
| None | 0 |

The result looks like the building type it should be. 97% are wood frame (construction type D). The median year
built is 1922, the median is 8 units, and most are 3 stories. The footprints' median height of 11.9 m agrees with
that. 32 buildings show a year built of 1978 or later. The assessor's year built "can be blend of original and newer
construction", so those are probably remodel dates, and I left them alone.

Several soft-story rows can share a parcel. In one case, four buildings on four different streets
share a lot with 111 units. Neighborhood totals use `units_alloc`, the group's units divided evenly among its rows, so no unit is
counted twice. 97 buildings have 0 or missing units.

**Footprints.** The pipeline prefers a footprint on the building's own parcel group:

| Route | Buildings |
|---|---|
| Point is inside a footprint on its parcel | 4,549 (91.8%) |
| Largest footprint on its parcel (point is in a yard or between buildings) | 369 (7.4%) |
| Point is inside a footprint on another parcel | 33 (0.7%) |
| Nearest footprint within 35 m | 6 (0.1%) |

124 buildings share a footprint with another soft-story row, usually because several addresses sit on one lot.

All 4,957 buildings fall inside an analysis neighborhood and a census tract.

## Shaking

Each building gets the ShakeMap values for the cell containing its representative point. That's the footprint's
representative point, or the location point if there's no footprint. ShakeMap nodes are cell centers, so this is
the nearest node, with no interpolation. I also ran zonal stats over each footprint, counting every cell the
footprint touches. A 250 m² footprint almost never contains a cell center, so without that most footprints would
come back empty.

The two methods agree, which is what the cell size predicts. All 4,957 buildings fall in just **43 distinct cells**.
158 footprints straddle a cell edge. For those, the zonal mean differs from the point value by up to 0.36 MMI, with
a 99th percentile of 0.19. The point value is what the score uses, and the zonal columns stay in the output for
comparison.

Soft-story buildings see MMI 6.2 to 7.3, a median of 6.8. Within SF, shaking doesn't drop off with distance from the
Hayward Fault (r = −0.02 over 15 to 27 km). That's the coarse, site-flat ShakeMap again.

## Ground failure

A building counts as in a CGS zone if its footprint touches one. The footprint is the building, so any overlap
counts. This catches more buildings than the point alone:

| | By footprint | By point |
|---|---|---|
| CGS liquefaction zone | 777 (15.7%) | 693 |
| CGS landslide zone | 47 (0.9%) | 29 |

HayWired liquefaction probability is the highest class any part of the footprint touches, stored as the class's
low, high and midpoint percent. The two layers agree well. The median midpoint is 22.5% inside CGS liquefaction
zones and 2.5% outside. They don't agree everywhere, though. One Marina building is inside a CGS zone but
in HayWired's <5% class.

## Fault context

Each building gets its distance to the nearest Holocene-active fault trace (Qfaults `historic` or `latest
Quaternary`) and to the Hayward fault zone. For every soft-story building, the nearest is the Serra fault zone, 3 to
15 km away. The Hayward is 15.5 to 27 km away. **This is context only and isn't in the score.** The ShakeMap already
reflects distance to the rupture, and the nearest fault isn't the one in this scenario.

## The index

This is an **exposure and vulnerability index for ranking buildings, not an engineering damage estimate.** It says
which soft-story buildings combine more shaking, worse ground, more vulnerable characteristics and no retrofit. It
doesn't say how likely any building is to be damaged.

Four components, each 0 to 1. The score is their weighted average. Everything lives in `config/score.toml`.

| Component | Weight | How it's scored |
|---|---|---|
| Shaking | 0.30 | MMI binned: <6.0 → 0, 6.0–6.5 → 0.25, 6.5–7.0 → 0.5, 7.0–7.5 → 0.75, ≥7.5 → 1 |
| Ground failure | 0.25 | 1 in a CGS liquefaction or landslide zone. Otherwise liquefaction probability ÷ 25%, capped at 1 |
| Vulnerability | 0.20 | Tier (0.4), age (0.4) and units (0.2), averaged. See below |
| Retrofit | 0.25 | 1 if not retrofitted, 0 if retrofitted |

The vulnerability sub-scores work like this. Tier 1 scores 1.0, tiers 2 and 4 score 0.75, and tier 3 scores 0.5.
Age scores 1.0 before 1920, 0.75 for 1920 to 1949, 0.5 for 1950 to 1977 and 0.25 after that. Units are on a log
scale from 1 unit (0) to 50 or more (1), which stands in for how many people are affected. Unknown age or units
score 0.5.

Scores run from 0.17 to 0.90, with a median of 0.35. **High score** means the top 20% (score ≥ 0.501, 993 buildings
including ties). 205 of the 240 unretrofitted buildings are high score.

## Sensitivity

I reran the score five ways and compared each ranking with the base (`docs/score_sensitivity.csv`). The top group is
the 992 highest-scoring buildings.

| Variant | Change | Spearman vs base | Top group overlap | Top 50 overlap | Median rank shift |
|---|---|---|---|---|---|
| hazard_heavy | 0.40 / 0.35 / 0.15 / 0.10 | 0.972 | 91.8% | 21 | 120 |
| retrofit_heavy | 0.20 / 0.20 / 0.20 / 0.40 | 0.993 | 96.4% | 49 | 76 |
| equal | 0.25 each | 0.996 | 98.0% | 49 | 50 |
| psa03 | PSA 0.3 s instead of MMI | 0.774 | 88.0% | 46 | 546 |
| no_tier | tier sub-weight 0 | 0.989 | 97.5% | 48 | 134 |

Weights shown as shaking / ground failure / vulnerability / retrofit.

The weights barely matter for the overall ordering. **The choice of shaking metric matters most.** Swapping MMI for
PSA 0.3 s drops the rank correlation to 0.77, because the two metrics don't rank the 43 cells the same way. The other
thing worth knowing is what happens at the very top under hazard_heavy. With retrofit down to 0.10, retrofitted
buildings on bad ground move into the top 50, and only 21 of the base top 50 stay. Dropping tier changes very
little, so the tier 4 double-count isn't driving the results.

## Aggregates

`neighborhood_summary.csv` and `tract_summary.csv` have, for each area: soft-story buildings, unretrofitted,
high-score, high-score and unretrofitted, buildings in a CGS liquefaction zone, residential units, units in
high-score buildings, estimated residents, mean MMI, and mean and max score.

**Estimated residents** are units × the tract's average renter household size (ACS 2024 5-year, B25010). Soft-story
buildings are nearly all rentals, so the renter figure fits better than the all-households one. Every soft-story
building's tract had a renter figure, so the fallbacks (the tract's all-households size, then the citywide renter
average of 1.99) never kicked in. This assumes every unit is occupied, so it runs high.

Citywide, the 4,957 buildings hold 49,086 units and an estimated 93,000 residents. High-score buildings hold 10,167
units and about 19,000 residents. The Marina and the Mission lead on units in high-score buildings.

## Checks

`spotcheck.py` re-derives seven buildings straight from the raw files, without the pipeline's code: the nearest
grid.xml node, point-in-polygon against the raw CGS GeoJSON and liquefaction shapefile, and the raw roll CSV. All
seven agree on shaking, zones, units and year built. The sample includes a shared-parcel building, a non-compliant
building in a liquefaction zone, and a landslide-zone building on Twin Peaks.

`pytest` covers parcel-ID normalization, raster sampling (known pixels give known values, edge cases, and the
grid.xml cell-center conversion), and the score (each component by hand, a full score by hand, bounds and variant
overrides).
