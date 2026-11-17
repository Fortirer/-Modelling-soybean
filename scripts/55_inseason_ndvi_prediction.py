"""55 - Does January-February NDVI improve within-season yield prediction?

The question of Schwalbert et al. (2020) and von Bloh et al. (2023), asked on
this panel: a random forest predicting the Brazilian yield anomaly from
weather and drought indices alone, against the same forest with the MODIS
NDVI of January-February added (script 53). Same design as script 48: whole
harvest years held out, unit effects and state trends estimated on the
training years only.

This is prediction DURING the season (NDVI of a season is known only once the
crop is in the field), not projection: NDVI has no future values, so it does
not enter any scenario.

Only municipalities with MODIS data (script 53) and harvest years 2001-2025
are used, and both models are fitted on exactly the same rows.

Output: results/_literature_models/inseason_ndvi_comparison.csv
Usage:  python scripts/55_inseason_ndvi_prediction.py
"""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold

from _gap import ROOT, all_regions, log

TAG = "55"
SEED = 42
N_FOLDS = 5
MIN_YEARS = 15
NDVI = ["ndvi_jf_max", "ndvi_jf_mean"]
OUT = ROOT / "results" / "_literature_models" / "inseason_ndvi_comparison.csv"


def script48():
    spec = importlib.util.spec_from_file_location(
        "literature48", Path(__file__).with_name("48_literature_models.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ndvi_table() -> pd.DataFrame:
    frames = [pd.read_csv(r.proc / "modis_ndvi_features.csv", dtype={"fips5": str})
              for r in all_regions()
              if r.country == "BR" and (r.proc / "modis_ndvi_features.csv").exists()]
    if not frames:
        raise SystemExit(f"[{TAG}] no modis_ndvi_features.csv; run script 53 first")
    return pd.concat(frames, ignore_index=True)[["fips5", "year"] + NDVI]


def compare(sample: pd.DataFrame, features: list[str], lit, label: str) -> list[dict]:
    absorbed = lit.absorb_matrix(sample)
    outcome = sample[lit.OUTCOME].to_numpy()
    sets = {"weather and drought": features, "weather, drought and NDVI": features + NDVI}
    observed = np.full(len(sample), np.nan)
    predicted = {name: np.full(len(sample), np.nan) for name in sets}
    for train, test in GroupKFold(N_FOLDS).split(sample, groups=sample.year):
        anomaly = lit.partial_out(absorbed, outcome, train)
        observed[test] = anomaly[test]
        for name, columns in sets.items():
            forest = RandomForestRegressor(n_estimators=300, min_samples_leaf=5,
                                           max_features=0.5, n_jobs=-1, random_state=SEED)
            forest.fit(sample.iloc[train][columns], anomaly[train])
            predicted[name][test] = forest.predict(sample.iloc[test][columns])
    return [dict(group=label, features=name, n=len(sample),
                 municipalities=int(sample.fips5.nunique()),
                 years=f"{sample.year.min()}-{sample.year.max()}",
                 r2_out_of_sample=float(r2_score(observed, values)),
                 rmse_log=float(np.sqrt(mean_squared_error(observed, values))))
            for name, values in predicted.items()]


def main() -> None:
    lit = script48()
    panel = lit.load_panel("BR").merge(ndvi_table(), on=["fips5", "year"], how="inner")
    features = [c for c in lit.FOREST_FEATURES if c in panel.columns]
    panel = panel.dropna(subset=features + NDVI + [lit.OUTCOME])
    panel = panel[panel.groupby("fips5").year.transform("size") >= MIN_YEARS]
    rows = []
    for state, group in panel.groupby("region"):
        if group.fips5.nunique() >= 10:
            rows += compare(group, features, lit, state)
    if panel.region.nunique() > 1:
        rows += compare(panel, features, lit, "all with NDVI")
    table = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT, index=False, float_format="%.4f")
    for row in rows:
        log(TAG, f"{row['group']} [{row['features']}]: R2 {row['r2_out_of_sample']:.3f} "
                 f"({row['municipalities']} municipalities)")


if __name__ == "__main__":
    main()
