# Findings

Which San Francisco soft-story buildings face the most severe shaking and ground failure under the HayWired M7.05
Hayward Fault scenario, and how many still aren't retrofitted?

Numbers come from `data/processed/buildings_seismic.parquet` and `neighborhood_summary.csv`, built by
`python -m seismic_risk`. How each one was calculated is in `methodology.md`.

## Headline numbers

The city's soft-story list has **4,957 buildings**, and **4,717 of them (95.2%) have finished their retrofit**. The
other **240** haven't. 228 are listed as non-compliant and 12 were newly added to the list. Together the 240 hold
about 2,400 units and an estimated 4,800 residents.

Under the scenario, every soft-story building sees **MMI 6.2 to 7.3**, which is strong to very strong shaking.
2,023 of them (41%) are at MMI 7.0 or higher.

**777 buildings (15.7%) sit in a state-mapped liquefaction zone**, and 47 are in a landslide zone. 47 of the
unretrofitted buildings are in a liquefaction zone and 1 is in a landslide zone.

The top 20% of buildings by my index (993 buildings, score 0.50 or higher) hold **about 10,200 units and an
estimated 19,000 residents**. 205 of the 240 unretrofitted buildings are in that group, and those 205 alone hold
about 2,100 units and 4,200 residents.

One thing I didn't expect: **unretrofitted buildings aren't concentrated where the shaking is worst.** 4.1% of
buildings at MMI 7.0 or higher are unretrofitted, compared with 5.4% everywhere else. They are a little more common
inside liquefaction zones, at 6.1% compared with 4.6% outside. The program seems to have cleared the shaking
hotspots about as well as anywhere else, but not the bad ground.

## Top 10 neighborhoods

Ranked by residential units in high-score buildings. A high score doesn't require an unretrofitted building.
Retrofitted buildings on liquefiable ground in strong shaking still score high, which is why the Marina leads even
though only 17 of its buildings are unretrofitted.

| Neighborhood | Soft-story buildings | Unretrofitted | High score | High score, unretrofitted | Units in high score | Est. residents in high score | In liquefaction zone | Mean MMI |
|---|---|---|---|---|---|---|---|
| Marina | 407 | 17 | 218 | 17 | 2,654 | 4,581 | 206 | 6.66 |
| Mission | 622 | 40 | 244 | 23 | 2,295 | 4,562 | 247 | 6.68 |
| Castro/Upper Market | 260 | 13 | 103 | 13 | 848 | 1,434 | 58 | 7.04 |
| Russian Hill | 353 | 13 | 43 | 13 | 540 | 913 | 30 | 6.60 |
| Hayes Valley | 260 | 13 | 47 | 13 | 515 | 973 | 36 | 7.06 |
| Sunset/Parkside | 143 | 6 | 40 | 6 | 454 | 1,092 | 37 | 6.84 |
| South of Market | 63 | 9 | 63 | 9 | 420 | 746 | 63 | 7.03 |
| Haight Ashbury | 329 | 11 | 45 | 11 | 385 | 741 | 32 | 7.08 |
| North Beach | 161 | 11 | 45 | 11 | 373 | 798 | 31 | 6.98 |
| Chinatown | 58 | 4 | 31 | 4 | 281 | 534 | 26 | 6.67 |

The Marina and the Mission are in a class of their own, with about 4,600 estimated residents each in high-score
buildings. Both have a lot of soft-story buildings on old bay and lagoon fill. South of Market is small but extreme:
all 63 of its soft-story buildings are in a liquefaction zone, all 63 score high, and it has the highest
unretrofitted share of any neighborhood on this list, at 14%.

Counting unretrofitted buildings alone gives a different list. The Mission has 40, then the Marina 17, Noe Valley 14,
Nob Hill 14, and Castro/Upper Market, Russian Hill and Hayes Valley with 13 each.

## Retrofitted and unretrofitted buildings where the shaking is worst

"Highest shaking" here means MMI 7.0 or higher. That's 2,023 buildings in 17 ShakeMap cells, mostly through the
middle of the city: Haight Ashbury, Hayes Valley, Castro/Upper Market, Pacific Heights, Lone Mountain/USF, Nob Hill
and the Western Addition.

| At MMI ≥ 7.0 | Retrofitted | Unretrofitted |
|---|---|---|
| Buildings | 1,941 | 82 |
| In a CGS liquefaction zone | 8.1% | 8.5% |
| In a CGS landslide zone | 1.7% | 1.2% |
| Median year built | 1913 | 1912 |
| Built before 1920 | 57.0% | 53.7% |
| Median units | 8 | 7.5 |
| Units | 19,239 | 854 |
| Estimated residents | 34,765 | 1,596 |
| Tier 4 (ground-floor commercial or liquefaction zone) | 15.0% | 30.5% |
| Mean score | 0.40 | 0.66 |

In the hardest-shaking part of the city, the two groups look almost the same. They're the same age, the same size
and about equally likely to be on liquefiable ground. The one real difference is tier. Unretrofitted buildings are
twice as likely to be tier 4, which usually means a storefront on the ground floor. That fits with tier 4 being the last
tier to come due. Its completion deadline was September 15, 2021, after a one-year COVID extension
([SF Board of Supervisors](https://sfbos.org/sites/default/files/9-15-2020%20San%20Francisco%20seismic%20retrofit%20deadline%20extended%20by%20one%20year%20to%20support%20small%20businesses%20during%20COVID-19.pdf)). The gap in mean score is mostly the retrofit component itself.

The highest-shaking area also isn't where the liquefaction is. Only about 8% of its buildings are in a liquefaction
zone, compared with 15.7% citywide. The ShakeMap's strongest cells run through the central hills, while the
liquefiable fill is along the bay and in the old creek and lagoon beds. That's why the top neighborhoods by score
are a mix of high-shaking areas (Castro, Hayes Valley, Haight) and bad-ground areas (Marina, Mission, SoMa).

## Highest-scoring unretrofitted buildings

These ten combine the most hazard factors in this index. That isn't a prediction that any of them will fail.

| Rank | Neighborhood | Tier | Year built | Units | MMI | Liquefaction zone | Score |
|---|---|---|---|---|---|---|---|
| 1 | Hayes Valley | 4 | 1906 | 18 | 7.07 | yes | 0.895 |
| 2 | South of Market | 4 | 1908 | 15 | 7.13 | yes | 0.893 |
| 3 | South of Market | 4 | 1907 | 6 | 7.13 | yes | 0.883 |
| 4 | Castro/Upper Market | 4 | 1925 | 10 | 7.07 | yes | 0.869 |
| 5 | Hayes Valley | 3 | 1908 | 6 | 7.07 | yes | 0.863 |
| 6 | Haight Ashbury | 3 | 1900 | 5 | 7.07 | yes | 0.861 |
| 7 | Castro/Upper Market | 3 | 1922 | 5 | 7.07 | yes | 0.841 |
| 8 | Castro/Upper Market | 3 | 1908 | 6 | 7.07 | no | 0.838 |
| 9 | Castro/Upper Market | 3 | 1902 | 5 | 7.07 | no | 0.836 |
| 10 | Mission | 4 | 1907 | 78 | 6.93 | yes | 0.830 |

All ten are unretrofitted and the top ten overall, because the retrofit component puts every unretrofitted building
ahead of a retrofitted one with the same hazards. Ranks 8 and 9 aren't in a CGS zone, but HayWired puts
them in its 20 to 25% liquefaction class.

## How much the ranking depends on my choices

I reran the index five ways (`score_sensitivity.csv`). Changing the weights barely matters. Rank correlation with the
base ranking stays between 0.97 and 1.00, and about 92% or more of the top group stays the same. Dropping soft-story tier
entirely, which removes the overlap with liquefaction zones, gives 0.99.

**The shaking metric matters more than any weight.** Swapping MMI for 0.3-second spectral acceleration drops the
rank correlation to 0.77. The two measures don't rank the city's 43 relevant cells in the same order, and with
shaking this coarse, a building's cell decides most of its shaking score.

The weighting that most changes the very top is hazard_heavy, which cuts retrofit to 10%. Retrofitted buildings on
bad ground then move into the top 50, and only 21 of the base top 50 stay. That's the right ranking if the question
is where the worst ground and shaking are, and the wrong one if it's where the unfinished retrofits are.

## Limitations

**HayWired is one earthquake.** It's a plausible Hayward Fault rupture, not a forecast. A San Andreas earthquake
would hit the west side of the city much harder, and the San Andreas is closer to SF than the Hayward is.

**The ShakeMap is coarse and has no site amplification of its own.** Its rock and site grids are identical over SF
and its cells are about 1.5 by 1.85 km. All 4,957 buildings fall in 43 cells, so shaking differences between
buildings mostly come down to which cell they're in. Bay fill doesn't shake harder than bedrock in this product. It
shows up through liquefaction instead. A Vs30-based site adjustment would change the shaking component, but it
would also stop being the HayWired scenario.

**The soft-story list covers one building type.** It's wood-frame buildings with weak ground floors, mostly 5 or
more units built before 1978. Non-ductile concrete, unreinforced masonry and single-family homes are outside it, and
some of them are just as vulnerable.

**The score is an index.** It ranks buildings by how many hazard and vulnerability factors stack up. It isn't a
damage, collapse or casualty estimate, and a retrofitted building with a high score isn't necessarily at risk. The
weights are judgment calls, and the sensitivity check shows how much they matter.

**Status is a snapshot.** It's the city's list as of 2026-10-07. "Non-compliant" is a program status, not an inspection
of the building. I counted the 12 "newly added" buildings as unretrofitted
because nothing says the work is done.

**Assessor data is imperfect.** Year built can reflect remodels, units are 0 or missing for 97 buildings, and condo
buildings are rebuilt from their unit parcels.

**Resident counts are estimates.** They're units times the tract's average renter household size, and they assume
every unit is occupied.

**Liquefaction zones are regulatory maps.** CGS zones mark where an investigation is required, not where the ground
will fail. The HayWired probabilities are a regional model at that same broad scale.

## Citations

Detweiler, S.T., and Wein, A.M., eds., 2017, The HayWired earthquake scenario: Earthquake hazards. U.S. Geological
Survey Scientific Investigations Report 2017–5013–A–H, https://doi.org/10.3133/sir20175013v1.

U.S. Geological Survey, ShakeMap scenario `ushaywiredm7.05_se`, version 33,
https://earthquake.usgs.gov/scenarios/eventpage/ushaywiredm7.05_se.

Jones, J.L., 2019, Results of individual and collocated lifeline exposure to hazards (and associated hazard and
multi-hazard exposure surface data) resulting from the HayWired scenario earthquake sequence for counties and cities
in the San Francisco Bay area, California. U.S. Geological Survey data release, https://doi.org/10.5066/P94HDTD8.

Other sources are listed in the README.
