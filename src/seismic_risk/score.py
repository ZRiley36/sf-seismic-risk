"""Step 6: the exposure and vulnerability index, plus the sensitivity check.

Weights and bins live in config/score.toml. Each component is 0-1 and the score is their
weighted average. The base score, every component, and each variant's score and rank are kept
in the output so any ranking can be traced back to its inputs.
"""
import copy

import geopandas as gpd
import numpy as np
import pandas as pd

from seismic_risk.config import DOCS, interim, score_config

COMPONENTS = ["shaking", "ground_failure", "vulnerability", "retrofit"]


def log(msg):
    print(f"  {msg}")


def binned(values, edges, scores):
    """Score for the bin each value falls in. Bins are [edge_i, edge_i+1). NaN stays NaN."""
    v = np.asarray(values, dtype=float)
    out = np.asarray(scores, dtype=float)[np.digitize(v, edges)]
    return np.where(np.isnan(v), np.nan, out)


def shaking_score(b, cfg, metric):
    bins = cfg["shaking"]["bins"][metric]
    return binned(b[metric], bins["edges"], bins["scores"])


def ground_failure_score(b, cfg):
    g = cfg["ground_failure"]
    prob = np.clip(b.liq_prob_mid.fillna(0) / g["liq_prob_full_score_pct"], 0, 1)
    zone = np.maximum(np.where(b.cgs_liquefaction, g["cgs_liquefaction_zone"], 0),
                      np.where(b.cgs_landslide, g["cgs_landslide_zone"], 0))
    return np.maximum(zone, prob)


def vulnerability_score(b, cfg, weights=None):
    v = cfg["vulnerability"]
    w = weights or v["weights"]
    tier = b.tier.astype(str).map(v["tier_scores"]).astype(float)
    age = pd.Series(binned(b.year_built, v["age_edges"], v["age_scores"]), index=b.index) \
        .fillna(v["unknown_age_score"])
    units = b.units.where(b.units > 0)
    unit_s = (np.log10(units.clip(lower=1)) / np.log10(v["units_full_score"])).clip(0, 1) \
        .fillna(v["unknown_units_score"])
    total = w["tier"] + w["age"] + w["units"]
    return (w["tier"] * tier + w["age"] * age + w["units"] * unit_s) / total


def retrofit_score(b, cfg):
    r = cfg["retrofit"]
    return np.where(b.retrofitted, r["retrofitted"], r["not_retrofitted"])


def components(b, cfg, shaking_metric=None, vulnerability_weights=None):
    return pd.DataFrame({
        "shaking": shaking_score(b, cfg, shaking_metric or cfg["shaking"]["metric"]),
        "ground_failure": ground_failure_score(b, cfg),
        "vulnerability": vulnerability_score(b, cfg, vulnerability_weights),
        "retrofit": retrofit_score(b, cfg),
    }, index=b.index)


def combine(comp, weights):
    w = pd.Series(weights)[COMPONENTS]
    return (comp[COMPONENTS] * w).sum(axis=1) / w.sum()


def variant_config(cfg, name):
    v = cfg["variants"][name]
    return {"weights": {**cfg["weights"], **v.get("weights", {})},
            "shaking_metric": v.get("shaking_metric"),
            "vulnerability_weights": v.get("vulnerability_weights")}


def rank(s):
    return s.rank(ascending=False, method="min").astype(int)


def sensitivity(b, cfg):
    base = b.score
    n_top = int(np.ceil(len(b) * (1 - cfg["high_score_quantile"])))
    top_base = set(base.nlargest(n_top).index)
    top50 = set(base.nlargest(50).index)
    rows = []
    for name in cfg["variants"]:
        vc = variant_config(cfg, name)
        comp = components(b, cfg, vc["shaking_metric"], vc["vulnerability_weights"])
        s = combine(comp, vc["weights"])
        b[f"score_{name}"] = s
        b[f"rank_{name}"] = rank(s)
        rows.append({
            "variant": name,
            # Spearman = Pearson on ranks, without pulling in scipy
            "spearman_vs_base": round(base.rank().corr(s.rank()), 3),
            f"top_{n_top}_overlap_pct": round(len(top_base & set(s.nlargest(n_top).index)) / n_top * 100, 1),
            "top_50_overlap": len(top50 & set(s.nlargest(50).index)),
            "median_rank_shift": int((b.rank_base - b[f"rank_{name}"]).abs().median()),
            "unretrofitted_in_top": int((~b.loc[list(s.nlargest(n_top).index), "retrofitted"]).sum()),
        })
    return pd.DataFrame(rows)


def main():
    cfg = score_config()
    b = gpd.read_parquet(interim("05_buildings_hazards"))
    comp = components(b, cfg)
    for c in COMPONENTS:
        b[f"c_{c}"] = comp[c]
    b["score"] = combine(comp, cfg["weights"])
    b["rank_base"] = rank(b.score)
    cut = b.score.quantile(cfg["high_score_quantile"])
    b["high_score"] = b.score >= cut
    log(f"score: min {b.score.min():.3f}, median {b.score.median():.3f}, max {b.score.max():.3f}. "
        f"High score is >= {cut:.3f} ({b.high_score.sum():,} buildings)")
    for c in COMPONENTS:
        log(f"  {c}: mean {comp[c].mean():.2f}, values {comp[c].round(2).value_counts().sort_index().head(8).to_dict()}")
    log(f"unretrofitted among high-score buildings: {(~b.loc[b.high_score, 'retrofitted']).sum()} "
        f"of {(~b.retrofitted).sum()} unretrofitted overall")

    sens = sensitivity(b, cfg)
    print(sens.to_string(index=False))
    sens.to_csv(DOCS / "score_sensitivity.csv", index=False)
    b.to_parquet(interim("06_buildings_scored"))


if __name__ == "__main__":
    main()
