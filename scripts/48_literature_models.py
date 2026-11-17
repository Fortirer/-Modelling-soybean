"""48 - The reviewed papers' models, fitted on the panels of script 47.

A worked example, not a finished analysis: one specification per paper, the
same code for the US and Brazil, so each can be re-run and then refined.

Fixed-effects regressions. Outcome: log yield (kg/ha). Every model has unit
(county / municipality) fixed effects and a quadratic time trend per state,
removed by partialling out (Frisch-Waugh-Lovell). Standard errors clustered by
state, as in Schlenker & Roberts. With only 12 (US) or 10 (Brazil) clusters
those errors are too small; read the p-values as indicative.

  schlenker_roberts_2009  GDD 10-30 C, degree days > 30 C, season rain, rain^2
  ortiz_bobea_2019        the same + root-zone soil moisture and its square
  lobell_2014             GDD + critical-window VPD + critical rain, rain^2
  silva_2023              season mean temperature + season rain, rain^2
  parisoto_2026           SPEI-3, warm-spell days and their product (compound)

Machine learning (Leng & Hall 2020; Benso et al. 2025): a random forest on the
full climate feature set against the Schlenker-Roberts regression, both
predicting the yield anomaly (log yield net of unit effects and state trends)
for YEARS HELD OUT of training (5 folds of whole years). Unit effects and
trends are estimated on the training years of each fold only. Permutation
importance comes from the first fold.

Outputs in results/_literature_models/:
  coefficients.csv     model, country, term, coefficient, se, p, n, units
  ml_comparison.csv    country, model, out-of-sample R2 and RMSE
  rf_importance.csv    permutation importance of the forest's features
  config.json

Usage:  python scripts/48_literature_models.py [US|BR]
"""
import json
import sys
import time

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import sparse
from scipy.sparse.linalg import lsqr
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold

from _gap import ROOT, log

TAG = "48"
OUT = ROOT / "results" / "_literature_models"
SEED = 42
MIN_YEARS_PER_UNIT = 20
N_FOLDS = 5
OUTCOME = "log_yield_kg_ha"

# name -> (panel column, divisor) so coefficients read per sensible unit
TERMS = {
    "gdd_100": ("gs_gdd_10_30", 100.0),       # per 100 degree days 10-30 C
    "edd30_10": ("gs_edd_30", 10.0),          # per 10 degree days above 30 C
    "rain_100mm": ("gs_prcp_mm", 100.0),      # per 100 mm season rain
    "rain_cw_100mm": ("cw_prcp_mm", 100.0),
    "vpd_cw_kpa": ("cw_vpd_mean_kpa", 1.0),
    "soilm_cw": ("gwetroot_critical", 0.1),   # per 0.1 of saturation
    "spei3_cw": ("spei3_critical", 1.0),
    "wsdi_cw_10d": ("cw_wsdi_days", 10.0),
}
SPECIFICATIONS = {
    "schlenker_roberts_2009": ["gdd_100", "edd30_10", "rain_100mm", "rain_100mm^2"],
    "ortiz_bobea_2019": ["gdd_100", "edd30_10", "rain_100mm", "rain_100mm^2",
                         "soilm_cw", "soilm_cw^2"],
    "lobell_2014": ["gdd_100", "vpd_cw_kpa", "rain_cw_100mm", "rain_cw_100mm^2"],
    "silva_2023": ["tmean_gs_c", "rain_100mm", "rain_100mm^2"],
    "parisoto_2026": ["spei3_cw", "wsdi_cw_10d", "spei3_cw*wsdi_cw_10d"],
}
FOREST_FEATURES = [
    "gs_gdd_10_30", "gs_edd_30", "gs_edd_34", "gs_hot_days_35", "gs_warm_nights_24",
    "gs_prcp_mm", "gs_cdd", "gs_rx5day", "gs_r20mm", "gs_vpd_mean_kpa",
    "cw_edd_30", "cw_hot_days_32", "cw_tmax_mean", "cw_tmin_mean", "cw_prcp_mm",
    "cw_dry_days", "cw_wsdi_days", "cw_vpd_mean_kpa",
    "spei3_critical", "spei6_season", "spei3_min_grow", "drought_months_grow",
    "gwetroot_grow", "gwetroot_critical", "gwetroot_min_month", "oni_season",
]


def load_panel(country: str) -> pd.DataFrame:
    path = ROOT / "data" / "final" / f"model_panel_{country.lower()}.csv.gz"
    if not path.exists():
        raise SystemExit(f"[{TAG}] {path.name} not found; run script 47 first")
    panel = pd.read_csv(path, dtype={"fips5": str}, low_memory=False)
    required = {"gs_gdd_10_30", "spei3_critical"} - set(panel.columns)
    if required:
        raise SystemExit(f"[{TAG}] {path.name} lacks {sorted(required)}; "
                         f"run scripts 41, 42 and 47")
    terms = {name: panel[column] / divisor for name, (column, divisor) in TERMS.items()}
    terms["tmean_gs_c"] = (panel.gs_tmax_mean + panel.gs_tmin_mean) / 2.0
    return panel.assign(**terms)


def design(frame: pd.DataFrame, names: list[str]) -> pd.DataFrame:
    """Columns for a specification; 'x^2' is a square, 'a*b' a product."""
    columns = {}
    for name in names:
        if name.endswith("^2"):
            columns[name] = frame[name[:-2]] ** 2
        elif "*" in name:
            left, right = name.split("*")
            columns[name] = frame[left] * frame[right]
        else:
            columns[name] = frame[name]
    return pd.DataFrame(columns, index=frame.index)


def absorb_matrix(frame: pd.DataFrame) -> sparse.csr_matrix:
    """Unit dummies plus a linear and a quadratic trend for every state."""
    n = len(frame)
    unit_codes = pd.factorize(frame.fips5)[0]
    state_codes = pd.factorize(frame.region)[0]
    rows = np.arange(n)
    units = sparse.csr_matrix((np.ones(n), (rows, unit_codes)))
    t = (frame.year - frame.year.mean()).to_numpy() / 10.0
    n_states = state_codes.max() + 1
    linear = sparse.csr_matrix((t, (rows, state_codes)), shape=(n, n_states))
    quadratic = sparse.csr_matrix((t ** 2, (rows, state_codes)), shape=(n, n_states))
    return sparse.hstack([units, linear, quadratic]).tocsr()


def partial_out(matrix: sparse.csr_matrix, values: np.ndarray,
                fit_rows: np.ndarray | None = None) -> np.ndarray:
    """Residual of `values` after least-squares projection on `matrix`.

    With `fit_rows`, the projection is estimated on those rows only and then
    applied to every row, so held-out rows do not inform their own unit
    effect or trend.
    """
    rows = slice(None) if fit_rows is None else fit_rows
    solution = lsqr(matrix[rows], values[rows], atol=1e-10, btol=1e-10,
                    iter_lim=5000)[0]
    return values - matrix @ solution


def usable(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Complete rows, restricted to units observed often enough."""
    sample = frame.dropna(subset=columns + [OUTCOME])
    counts = sample.groupby("fips5").year.transform("size")
    return sample[counts >= MIN_YEARS_PER_UNIT]


def fit_specification(panel: pd.DataFrame, name: str, country: str) -> list[dict]:
    names = SPECIFICATIONS[name]
    sample = panel.assign(**design(panel, names))
    sample = usable(sample, names)
    if sample.empty:
        return []
    absorbed = absorb_matrix(sample)
    y = partial_out(absorbed, sample[OUTCOME].to_numpy())
    x = np.column_stack([partial_out(absorbed, sample[c].to_numpy()) for c in names])
    # a single state cannot be clustered by state: cluster by unit instead
    cluster = sample.region if sample.region.nunique() > 1 else sample.fips5
    result = sm.OLS(y, x).fit(cov_type="cluster", use_t=True,
                              cov_kwds={"groups": pd.factorize(cluster)[0]})
    return [dict(model=name, country=country, term=term,
                 states=int(sample.region.nunique()),
                 coefficient=float(result.params[i]), se=float(result.bse[i]),
                 p_value=float(result.pvalues[i]),
                 pct_yield_per_unit=(float(np.expm1(result.params[i]) * 100)
                                     if "^" not in term and "*" not in term else np.nan),
                 within_r2=float(result.rsquared), n=len(sample),
                 units=int(sample.fips5.nunique()),
                 years=f"{sample.year.min()}-{sample.year.max()}")
            for i, term in enumerate(names)]


def compare_forest(panel: pd.DataFrame, country: str) -> tuple[list[dict], pd.DataFrame]:
    """Out-of-sample skill, whole years held out: regression vs random forest."""
    linear_names = SPECIFICATIONS["schlenker_roberts_2009"]
    features = [c for c in FOREST_FEATURES if c in panel.columns]
    sample = panel.assign(**design(panel, linear_names))
    sample = usable(sample, features + linear_names)
    absorbed = absorb_matrix(sample)
    outcome = sample[OUTCOME].to_numpy()
    raw = {c: sample[c].to_numpy() for c in linear_names}
    models = {
        "regression_schlenker_roberts": LinearRegression(fit_intercept=False),
        "random_forest": RandomForestRegressor(
            n_estimators=200, min_samples_leaf=5, max_features=0.5,
            n_jobs=-1, random_state=SEED),
    }
    observed = np.full(len(sample), np.nan)
    predictions = {name: np.full(len(sample), np.nan) for name in models}
    importance = None
    for train, test in GroupKFold(N_FOLDS).split(sample, groups=sample.year):
        # unit effects and state trends come from the training years only
        anomaly = partial_out(absorbed, outcome, train)
        within = np.column_stack([partial_out(absorbed, raw[c], train)
                                  for c in linear_names])
        inputs = {"regression_schlenker_roberts": within,
                  "random_forest": sample[features].to_numpy()}
        observed[test] = anomaly[test]
        for name, model in models.items():
            model.fit(inputs[name][train], anomaly[train])
            predictions[name][test] = model.predict(inputs[name][test])
        if importance is None:
            importance = permutation_importance(
                models["random_forest"], inputs["random_forest"][test],
                anomaly[test], n_repeats=5, random_state=SEED, n_jobs=-1)
    sizes = {"regression_schlenker_roberts": len(linear_names),
             "random_forest": len(features)}
    rows = [dict(country=country, model=name, target="yield anomaly (log points)",
                 r2_out_of_sample=float(r2_score(observed, predicted)),
                 rmse=float(np.sqrt(mean_squared_error(observed, predicted))),
                 n=len(sample), units=int(sample.fips5.nunique()),
                 features=sizes[name], folds=N_FOLDS)
            for name, predicted in predictions.items()]
    table = pd.DataFrame(dict(country=country, feature=features,
                              importance=importance.importances_mean,
                              sd=importance.importances_std))
    return rows, table.sort_values("importance", ascending=False)


def main() -> None:
    countries = [a.upper() for a in sys.argv[1:]] or ["US", "BR"]
    OUT.mkdir(parents=True, exist_ok=True)
    coefficients, skill, importances = [], [], []
    for country in countries:
        panel = load_panel(country)
        for name in SPECIFICATIONS:
            rows = fit_specification(panel, name, country)
            coefficients += rows
            if rows:
                log(TAG, f"{country} {name}: n={rows[0]['n']} units={rows[0]['units']} "
                         f"within R2={rows[0]['within_r2']:.3f}")
        rows, table = compare_forest(panel, country)
        skill += rows
        importances.append(table)
        for row in rows:
            log(TAG, f"{country} {row['model']}: held-out-year R2 "
                     f"{row['r2_out_of_sample']:.3f}, RMSE {row['rmse']:.3f}")
    pd.DataFrame(coefficients).to_csv(OUT / "coefficients.csv", index=False,
                                      float_format="%.5g")
    pd.DataFrame(skill).to_csv(OUT / "ml_comparison.csv", index=False,
                               float_format="%.4f")
    pd.concat(importances).to_csv(OUT / "rf_importance.csv", index=False,
                                  float_format="%.5f")
    (OUT / "config.json").write_text(json.dumps(dict(
        run=time.strftime("%Y-%m-%d"), outcome=OUTCOME, terms=TERMS,
        specifications=SPECIFICATIONS, forest_features=FOREST_FEATURES,
        min_years_per_unit=MIN_YEARS_PER_UNIT, folds=N_FOLDS, seed=SEED,
        fixed_effects="unit dummies + state-specific quadratic trend",
        standard_errors="clustered by state, t distribution with G-1 df (few clusters: indicative only)",
    ), indent=2))
    log(TAG, f"-> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
