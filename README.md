# SF Seismic Risk: Which Buildings Fail First?

San Francisco has about 5,000 soft-story buildings. They're mostly wood-frame apartments with a weak ground floor of
garages or storefronts, the kind that collapsed in the Marina in 1989. The city has required them to be retrofitted
since 2013. I wanted to see where they sit under the USGS HayWired scenario, a M7.0 earthquake on the Hayward Fault,
and how many of the ones facing the hardest shaking and the worst ground still haven't been retrofitted.

This is a work in progress. Step 1, the data inventory, is in `docs/data_inventory.md`.

## Data

| Dataset | Source | Notes |
|---|---|---|
| Soft-Story Properties | [DataSF `beah-shgi`](https://data.sf.gov/d/beah-shgi) | Tier, compliance status, parcel, point |
| Assessor Historical Secured Property Tax Rolls | [DataSF `wv5m-vpq2`](https://data.sf.gov/d/wv5m-vpq2) | Roll years 2020 to 2025 downloaded |
| Building Footprints | [DataSF `ynuv-fyni`](https://data.sf.gov/d/ynuv-fyni) | Footprints keyed to block/lot |
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
python -m seismic_risk.shakemap_tif                  # grid.xml -> data/interim/haywired_shakemap.tif
python -m seismic_risk.inventory > docs/data_inventory.json
python -m pytest
```
