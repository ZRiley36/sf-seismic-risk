# SF Seismic Risk: Which Buildings Fail First?

San Francisco has about 5,000 soft-story buildings. They're mostly wood-frame apartments with a weak ground floor of
garages or storefronts, the kind that collapsed in the Marina in 1989. The city has required them to be retrofitted
since 2013. I wanted to see where they sit under the USGS HayWired scenario, a M7.0 earthquake on the Hayward Fault,
and how many of the ones facing the hardest shaking and the worst ground still haven't been retrofitted.

The findings are in `docs/findings.md`. The data inventory is in `docs/data_inventory.md` and the pipeline and
scoring are in `docs/methodology.md`. A web map is next.

## What I've found so far

Of the 4,957 buildings on the list, 240 still aren't retrofitted. Under the HayWired scenario the soft-story
buildings see MMI 6.2 to 7.3, which is strong to very strong shaking. 777 of them sit in a state-mapped liquefaction
zone. The top 20% by my index hold about 10,000 apartments and an estimated 19,000 people, and the Marina and the
Mission have the most.

The surprise was the shaking map. I expected bay fill to shake harder than the hills, and in the HayWired ShakeMap
it doesn't. The site and rock versions of the grid are identical over SF, and the cells are about 1.5 km across, so
the shaking can't tell a block of fill from the bedrock ridge next to it. In this analysis the fill shows up through
liquefaction instead. It also means the choice of shaking metric moves the ranking more than any of the weights do.

## Method

I join the soft-story list to the assessor roll and building footprints through block/lot. Condo conversions retire
the building's original lot, so for those I go through DataSF's parcel layer, and that gets 99.98% of buildings
matched. Each building gets the ShakeMap values at its footprint, whether it touches a CGS liquefaction or landslide
zone, and HayWired's liquefaction probability. The score is a weighted average of shaking, ground failure,
vulnerability (tier, age, units) and retrofit status. The weights live in `config/score.toml`, and I rerun it five
other ways to see how much the ranking depends on them. Everything is in EPSG:7131, the San Francisco low-distortion
projection.

## Limitations

HayWired is one possible earthquake, not a forecast. A San Andreas event would shake the west side of the city much
harder.

The ShakeMap is coarse and has no site amplification of its own, so shaking differences between buildings are
mostly about which 1.5 km cell they're in.

The soft-story list covers one building type. Plenty of other buildings in SF are vulnerable and aren't in this
analysis.

The score is a ranking index. It isn't a damage or casualty estimate, and a high score doesn't mean a building will
fail.

Assessor year built can reflect remodels, and resident estimates assume every unit is occupied.

## Data

| Dataset | Source | Notes |
|---|---|---|
| Soft-Story Properties | [DataSF `beah-shgi`](https://data.sf.gov/d/beah-shgi) | Tier, compliance status, parcel, point |
| Assessor Historical Secured Property Tax Rolls | [DataSF `wv5m-vpq2`](https://data.sf.gov/d/wv5m-vpq2) | Roll years 2020 to 2025 downloaded |
| Building Footprints | [DataSF `ynuv-fyni`](https://data.sf.gov/d/ynuv-fyni) | Footprints keyed to block/lot |
| Parcels – Active and Retired | [DataSF `acdm-wktn`](https://data.sf.gov/d/acdm-wktn) | Condo lot groups (`mapblklot`) |
| Analysis Neighborhoods | [DataSF `j2bu-swwd`](https://data.sf.gov/d/j2bu-swwd) | 41 neighborhoods |
| HayWired M7.05 ShakeMap | [USGS ShakeMap `ushaywiredm7.05_se` v33](https://earthquake.usgs.gov/scenarios/eventpage/ushaywiredm7.05_se) | MMI, PGA, PGV, PSA 0.3/1.0/3.0 s |
| HayWired expanded liquefaction probability | [USGS data release, Jones 2019](https://doi.org/10.5066/P94HDTD8) | Probability classes, Bay Area wide |
| CGS Seismic Hazard Zones | [CA Dept. of Conservation](https://gis.data.ca.gov/) (liquefaction, landslide, unevaluated areas) | Regulatory zones |
| Quaternary Fault and Fold Database | [USGS](https://www.usgs.gov/programs/earthquake-hazards/faults) | Fault traces |
| Census tracts and county | [Census cartographic boundary files 2024](https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html) | Shoreline-clipped |
| ACS 2024 5-year | [Census table-based summary files](https://www.census.gov/programs-surveys/acs/data/summary-file.html) | B01003, B25003, B25010 for SF tracts |

`python -m seismic_risk.download` fetches all of it into `data/raw/`, with a `SOURCE.txt` in each folder.

### Citations

HayWired scenario: Detweiler, S.T., and Wein, A.M., eds., 2017, The HayWired earthquake scenario: Earthquake
hazards. U.S. Geological Survey Scientific Investigations Report 2017–5013–A–H, https://doi.org/10.3133/sir20175013v1.

HayWired ShakeMap: U.S. Geological Survey, ShakeMap scenario `ushaywiredm7.05_se` (Haywired M7.05 Scenario), version
33, processed 2017-01-11, https://earthquake.usgs.gov/scenarios/eventpage/ushaywiredm7.05_se.

Liquefaction probability: Jones, J.L., 2019, Results of individual and collocated lifeline exposure to hazards (and
associated hazard and multi-hazard exposure surface data) resulting from the HayWired scenario earthquake sequence for
counties and cities in the San Francisco Bay area, California. U.S. Geological Survey data release,
https://doi.org/10.5066/P94HDTD8.

Faults: U.S. Geological Survey and California Geological Survey, Quaternary fault and fold database for the United
States, https://www.usgs.gov/programs/earthquake-hazards/faults.

Seismic hazard zones: California Geological Survey, Seismic Hazards Program, liquefaction and landslide zones, under
the Seismic Hazards Mapping Act of 1990.

## Setup
```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/pip install -e .
source .venv/bin/activate
python -m seismic_risk.download                      # ~1.3 GB into data/raw/
python -m seismic_risk.inventory > docs/data_inventory.json   # after shakemap_tif
python -m seismic_risk                               # the whole pipeline, about a minute
python -m pytest
```

Or `make setup download pipeline test`. `python -m seismic_risk score analyze` reruns just those steps, which is
all you need after changing `config/score.toml`.

Outputs land in `data/processed/`: `buildings_seismic.parquet` (one row per soft-story building, with every input,
component and variant score), `neighborhood_summary.csv` and `tract_summary.csv`. For the web map, `data/processed/web/` has the ShakeMap cropped to
SF as a Cloud-Optimized GeoTIFF (native EPSG:4326 grid, MMI in band 1) and the buildings as a 2.6 MB GeoJSON of
points in EPSG:4326.
