import numpy as np
import pandas as pd
import pytest

from seismic_risk.clean import parse_prob_class
from seismic_risk.config import score_config
from seismic_risk.score import (binned, combine, components, ground_failure_score, retrofit_score,
                                variant_config, vulnerability_score)


@pytest.fixture
def cfg():
    return score_config()


def building(**kw):
    base = dict(MMI=6.8, PSA03=60.0, cgs_liquefaction=False, cgs_landslide=False, liq_prob_mid=0.0,
                tier=3, year_built=1925.0, units=8.0, retrofitted=True)
    base.update(kw)
    return pd.DataFrame([base])


def test_binned_edges_are_left_closed():
    assert binned([5.9, 6.0, 6.49, 6.5, 7.5, np.nan], [6.0, 6.5, 7.0, 7.5], [0, .25, .5, .75, 1]).tolist()[:5] \
        == [0, .25, .25, .5, 1]
    assert np.isnan(binned([np.nan], [1], [0, 1])[0])


def test_ground_failure_zone_beats_probability(cfg):
    assert ground_failure_score(building(cgs_liquefaction=True, liq_prob_mid=2.5), cfg)[0] == 1.0
    assert ground_failure_score(building(cgs_landslide=True), cfg)[0] == 1.0
    assert ground_failure_score(building(liq_prob_mid=12.5), cfg)[0] == pytest.approx(0.5)
    assert ground_failure_score(building(liq_prob_mid=87.5), cfg)[0] == 1.0
    assert ground_failure_score(building(liq_prob_mid=np.nan), cfg)[0] == 0.0


def test_vulnerability_by_hand(cfg):
    # tier 3 -> 0.5, 1925 -> 0.75, 50 units -> 1.0. (0.4*0.5 + 0.4*0.75 + 0.2*1.0) / 1.0 = 0.7
    assert vulnerability_score(building(units=50.0), cfg)[0] == pytest.approx(0.7)
    # unknown year and units fall back to 0.5 each: (0.4*0.5 + 0.4*0.5 + 0.2*0.5) = 0.5
    assert vulnerability_score(building(year_built=np.nan, units=0.0), cfg)[0] == pytest.approx(0.5)


def test_retrofit(cfg):
    assert list(retrofit_score(pd.concat([building(), building(retrofitted=False)]), cfg)) == [0.0, 1.0]


def test_full_score_by_hand(cfg):
    b = building(MMI=7.2, cgs_liquefaction=True, tier=4, year_built=1910.0, units=10.0, retrofitted=False)
    c = components(b, cfg).iloc[0]
    units = np.log10(10) / np.log10(50)
    vuln = 0.4 * 0.75 + 0.4 * 1.0 + 0.2 * units
    assert c.tolist() == pytest.approx([0.75, 1.0, vuln, 1.0])
    expected = 0.30 * 0.75 + 0.25 * 1.0 + 0.20 * vuln + 0.25 * 1.0
    assert combine(components(b, cfg), cfg["weights"]).iloc[0] == pytest.approx(expected)


def test_score_is_bounded(cfg):
    worst = building(MMI=9, cgs_liquefaction=True, tier=1, year_built=1900.0, units=500.0, retrofitted=False)
    best = building(MMI=5, tier=3, year_built=2000.0, units=1.0)
    s = combine(components(pd.concat([worst, best]), cfg), cfg["weights"])
    assert s.iloc[0] == pytest.approx(1.0) and s.iloc[1] == pytest.approx(0.0 + 0.2 * (0.4 * 0.5 + 0.4 * 0.25))


def test_variants_override_only_what_they_name(cfg):
    v = variant_config(cfg, "psa03")
    assert v["weights"] == cfg["weights"] and v["shaking_metric"] == "PSA03"
    assert variant_config(cfg, "no_tier")["vulnerability_weights"]["tier"] == 0.0


@pytest.mark.parametrize("cls, expected", [("0", (0, 0)), ("< 5", (0, 5)), ("20 - 25", (20, 25)),
                                           (">= 75", (75, 100))])
def test_liquefaction_classes(cls, expected):
    assert parse_prob_class(cls) == expected
