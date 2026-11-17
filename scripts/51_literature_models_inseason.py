"""51 - In-season models: Mourtzinis et al. (2015) and a Khaki-style weekly model.

Completes script 48 with the two reviewed papers that need within-season
resolution (features from script 50).

Mourtzinis et al. (2015): month-by-month effects
  log yield ~ mean temperature and precipitation of each of five season
  months, with unit fixed effects and a quadratic trend per state (the same
  partialling-out and state-clustered errors as script 48). Months are
  May-September in the US and October-February in Brazil. The coefficients
  show WHEN in the season heat and rain matter.

Khaki, Wang & Archontoulis (2020): weekly weather as the input
  Their model is a CNN-RNN on weekly weather, soil layers and planting
  progress. What is fitted here is NOT that architecture: it is a
  feed-forward neural network (two hidden layers) on 26 weeks of maximum and
  minimum temperature, precipitation and vapour pressure deficit, compared
  with a random forest on the same weekly inputs and with the Schlenker-
  Roberts regression. It answers the narrower question the weekly inputs
  allow here: does within-season timing add predictive skill over season
  totals? A faithful CNN-RNN needs a deep-learning library (PyTorch or
  TensorFlow), which this repository does not depend on.

  All three predict the yield anomaly for whole years held out of training
  (5 folds); unit effects and trends come from the training years only.

Outputs in results/_literature_models/:
  mourtzinis_monthly_coefficients.csv
  khaki_weekly_comparison.csv

Usage:  python scripts/51_literature_models_inseason.py [US|BR]
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from _gap import ROOT, all_regions, log

TAG = "51"
OUT = ROOT / "results" / "_literature_models"
SEED = 42
N_FOLDS = 5
MIN_YEARS_PER_UNIT = 20
OUTCOME = "log_yield_kg_ha"
N_MONTHS = 5
MONTH_LABELS = {"US": ("May", "Jun", "Jul", "Aug", "Sep"),
                "BR": ("Oct", "Nov", "Dec", "Jan", "Feb")}
RAIN_UNIT_MM = 100.0


def script48():
    """Script 48 as a module (its name starts with a digit, so no plain import)."""
    spec = importlib.util.spec_from_file_location(
        "literature48", Path(__file__).with_name("48_literature_models.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load(country: str, lit) -> pd.DataFrame:
    panel = lit.load_panel(country)
    monthly, weekly = [], []
    for region in all_regions():
        if region.country != country:
            continue
        for name, bucket in (("monthly", monthly), ("weekly", weekly)):
            path = region.proc / f"{name}_weather_features.csv"
            if not path.exists():
                raise SystemExit(f"[{TAG}] {path} not found; run script 50 first")
            bucket.append(pd.read_csv(path, dtype={"fips5": str}))
    keys = ["fips5", "year"]
    return (panel.merge(pd.concat(monthly), on=keys, how="left")
            .merge(pd.concat(weekly), on=keys, how="left"))


def usable(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    sample = frame.dropna(subset=columns + [OUTCOME])
    counts = sample.groupby("fips5").year.transform("size")
    return sample[counts >= MIN_YEARS_PER_UNIT]


def mourtzinis(panel: pd.DataFrame, country: str, lit) -> list[dict]:
    temperature = [f"m{m}_tmean" for m in range(1, N_MONTHS + 1)]
    rain = [f"m{m}_prcp" for m in range(1, N_MONTHS + 1)]
    sample = usable(panel, temperature + rain)
    absorbed = lit.absorb_matrix(sample)
    y = lit.partial_out(absorbed, sample[OUTCOME].to_numpy())
    raw = [sample[c].to_numpy() for c in temperature] \
        + [sample[c].to_numpy() / RAIN_UNIT_MM for c in rain]
    x = np.column_stack([lit.partial_out(absorbed, values) for values in raw])
    fit = sm.OLS(y, x).fit(cov_type="cluster", use_t=True,
                           cov_kwds={"groups": pd.factorize(sample.region)[0]})
    rows = []
    for i in range(2 * N_MONTHS):
        is_temperature = i < N_MONTHS
        rows.append(dict(
            country=country, month=MONTH_LABELS[country][i % N_MONTHS],
            variable="temperature (per deg C)" if is_temperature
            else f"precipitation (per {RAIN_UNIT_MM:.0f} mm)",
            coefficient=float(fit.params[i]), se=float(fit.bse[i]),
            p_value=float(fit.pvalues[i]),
            pct_yield_per_unit=float(np.expm1(fit.params[i]) * 100),
            within_r2=float(fit.rsquared), n=len(sample),
            units=int(sample.fips5.nunique())))
    return rows


def weekly_comparison(panel: pd.DataFrame, country: str, lit) -> list[dict]:
    weekly = sorted(c for c in panel.columns if c[0] == "w" and c[1:3].isdigit())
    linear_names = lit.SPECIFICATIONS["schlenker_roberts_2009"]
    sample = panel.assign(**lit.design(panel, linear_names))
    sample = usable(sample, weekly + linear_names)
    absorbed = lit.absorb_matrix(sample)
    outcome = sample[OUTCOME].to_numpy()
    models = {
        "regression_schlenker_roberts": LinearRegression(fit_intercept=False),
        "random_forest_weekly": RandomForestRegressor(
            n_estimators=200, min_samples_leaf=5, max_features=0.33,
            n_jobs=-1, random_state=SEED),
        "neural_network_weekly": make_pipeline(StandardScaler(), MLPRegressor(
            hidden_layer_sizes=(64, 32), alpha=1e-3, early_stopping=True,
            max_iter=300, random_state=SEED)),
    }
    weekly_values = sample[weekly].to_numpy()
    observed = np.full(len(sample), np.nan)
    predicted = {name: np.full(len(sample), np.nan) for name in models}
    for train, test in GroupKFold(N_FOLDS).split(sample, groups=sample.year):
        anomaly = lit.partial_out(absorbed, outcome, train)
        within = np.column_stack([lit.partial_out(absorbed, sample[c].to_numpy(), train)
                                  for c in linear_names])
        inputs = {"regression_schlenker_roberts": within,
                  "random_forest_weekly": weekly_values,
                  "neural_network_weekly": weekly_values}
        observed[test] = anomaly[test]
        for name, model in models.items():
            model.fit(inputs[name][train], anomaly[train])
            predicted[name][test] = model.predict(inputs[name][test])
    sizes = {"regression_schlenker_roberts": len(linear_names),
             "random_forest_weekly": len(weekly), "neural_network_weekly": len(weekly)}
    return [dict(country=country, model=name,
                 r2_out_of_sample=float(r2_score(observed, values)),
                 rmse=float(np.sqrt(mean_squared_error(observed, values))),
                 n=len(sample), units=int(sample.fips5.nunique()),
                 inputs=sizes[name], folds=N_FOLDS)
            for name, values in predicted.items()]


def main() -> None:
    countries = [a.upper() for a in sys.argv[1:]] or ["US", "BR"]
    lit = script48()
    OUT.mkdir(parents=True, exist_ok=True)
    monthly_rows, weekly_rows = [], []
    for country in countries:
        panel = load(country, lit)
        rows = mourtzinis(panel, country, lit)
        monthly_rows += rows
        log(TAG, f"{country} mourtzinis_2015: n={rows[0]['n']} "
                 f"within R2={rows[0]['within_r2']:.3f}")
        rows = weekly_comparison(panel, country, lit)
        weekly_rows += rows
        for row in rows:
            log(TAG, f"{country} {row['model']}: held-out-year R2 "
                     f"{row['r2_out_of_sample']:.3f}")
    pd.DataFrame(monthly_rows).to_csv(OUT / "mourtzinis_monthly_coefficients.csv",
                                      index=False, float_format="%.5g")
    pd.DataFrame(weekly_rows).to_csv(OUT / "khaki_weekly_comparison.csv",
                                     index=False, float_format="%.4f")
    log(TAG, f"-> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
