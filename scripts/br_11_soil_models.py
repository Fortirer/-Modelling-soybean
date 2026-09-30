"""BR 11 - What does soil actually buy us for Mato Grosso? Analogue of US
script 16, adapted to what this branch actually has:

  Q1  Does soil explain the LEVEL of municipality yield? Same logic as the
      US version -- detrending removed exactly this signal from yield_anom,
      so it has never been examined.
  Q2  SKIPPED. The US version regresses soil against per-county climate-
      SENSITIVITY coefficients from script 09 (a county-level sensitivity-
      ranking script). No Brazil equivalent has been built yet -- this is
      a real gap, not a deliberate omission, flagged so it doesn't get
      mistaken for "soil doesn't affect sensitivity here."
  Q3  Does soil improve out-of-sample prediction of yield_anom, over
      climate + process features alone? Same expanding-window design as
      the US version (rolling origin, no random splits).

wrb_class (categorical) is turned into one dummy, is_ferralsol, standing in
for the US version's soil_mollisol_pct -- both are "does this municipality/
county sit on the dominant, well-behaved soil order" indicators, though a
WRB order and a USDA order are not the same taxonomy and the comparison
should be read loosely, not as like-for-like.
"""
import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import statsmodels.formula.api as smf
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.inspection import permutation_importance
from matplotlib.patches import Patch
from _brcfg import FINAL, PROC, RES, FIG, SEED, FOCAL_CODE, FOCAL_MUNICIPIO
from _viz import *

d = pd.read_csv(FINAL / "soja_mt_climate_1981_2024.csv", dtype={"fips5": str})
d = d[d.in_balanced_panel == 1].copy()

ph = pd.read_csv(PROC / "phenology_features.csv", dtype={"fips5": str})
d = d.merge(ph, on=["fips5", "year"], how="inner", suffixes=("", "_ph"))

s = pd.read_csv(PROC / "soil_features.csv", dtype={"fips5": str})
s["is_ferralsol"] = (s.wrb_class == "Ferralsols").astype(int)
SOIL = [c for c in s.columns if c not in ("fips5", "wrb_class")]

before = d.fips5.nunique()
d = d.merge(s, on="fips5", how="left", validate="many_to_one")
unmatched = int(d[SOIL[0]].isna().sum())
print(f"[br11] panel {len(d):,} rows, {before} municipalities, {len(SOIL)} soil features")
print(f"[br11] rows with no soil match : {unmatched}")
if unmatched:
    d = d[d[SOIL[0]].notna()].copy()
    print(f"[br11] dropped -- see br_09's soil coverage report")

CLIM = ["pcp_critical", "tmax_critical", "tmp_critical", "hot_days_critical",
        "dry_days_critical", "heat_x_dry", "climate_normal_pcp", "climate_normal_tmax"]
PROCESS = ["win_gdd", "win_edd", "win_hot_days", "win_vpd_mean", "win_vpd_max",
           "win_prcp_mm", "win_et0_mm", "win_water_deficit_mm", "season_gdd",
           "season_edd", "season_prcp_mm"]
TARGET = "yield_anom"


def metrics(a, p):
    e = p - a
    return dict(RMSE=float(np.sqrt((e ** 2).mean())), MAE=float(np.abs(e).mean()),
                R2=float(1 - (e ** 2).sum() / ((a - a.mean()) ** 2).sum()))


def fit_ols(df, y, X):
    return smf.ols(y + " ~ " + " + ".join(X), data=df).fit()


KEY = ["soil_clay_topsoil", "soil_sand_topsoil", "soil_om_topsoil", "soil_ph_topsoil",
       "soil_bd_topsoil", "soil_cec_topsoil", "soil_om_subsoil", "is_ferralsol"]

# ===== Q1: soil vs the LEVEL of municipality yield ============================
muni = (d.groupby(["fips5"])
         .agg(yield_mean=("yield_bu_ac", "mean"), trend_slope=("trend_slope", "first"),
              anom_sd=("yield_anom", "std")).reset_index()
         .merge(s, on="fips5", how="left"))

q1 = []
for y, lab in [("yield_mean", "municipality mean yield (bu/acre)"),
               ("trend_slope", "yield trend (bu/acre/yr)"),
               ("anom_sd", "yield volatility (sd of anomaly)")]:
    m = fit_ols(muni, y, KEY)
    p = m.pvalues.drop("Intercept")
    q1.append(dict(target=lab, n=int(m.nobs), r2=float(m.rsquared),
                   adj_r2=float(m.rsquared_adj), strongest_term=p.idxmin(),
                   p_value=float(p.min())))
Q1 = pd.DataFrame(q1)
print("\n[br11] Q1  SOIL vs THE LEVEL OF MUNICIPALITY YIELD  (OLS, 8 soil terms)")
print(Q1.round(4).to_string(index=False))

m_lvl = fit_ols(muni, "yield_mean", KEY)
print("\n[br11] municipality mean yield ~ soil, coefficients")
print(pd.DataFrame(dict(coef=m_lvl.params, se=m_lvl.bse, p=m_lvl.pvalues))
      .drop("Intercept").round(4).to_string())

print("\n[br11] Q2 SKIPPED: no Brazil equivalent of US script 09's county "
      "climate-sensitivity table exists yet -- a real gap, not a null result")

# ===== Q3: does soil improve out-of-sample prediction? ========================
SETS = {"climate only": CLIM, "climate + process": CLIM + PROCESS,
        "climate + process + soil": CLIM + PROCESS + SOIL, "soil only": SOIL}
ALL_FEATS = sorted(set(CLIM + PROCESS + SOIL))
na_mask = d[ALL_FEATS].isna().any(axis=1)
if na_mask.any():
    # br_09 reported 66 null cells scattered across a handful of soil
    # columns/municipalities (ISRIC pixels with no data at some depth) --
    # same "drop rather than silently propagate NaN into a model fit"
    # discipline used throughout the US pipeline for its own soil-coverage
    # gaps (SSURGO reservation-survey counties, script 16's note)
    print(f"[br11] dropping {int(na_mask.sum())} rows with a NaN feature "
          f"(soil coverage gaps, see br_09)")
    d = d[~na_mask].copy()
d = d.sort_values(["fips5", "year"]).reset_index(drop=True)
acc = []
preds = {k: [] for k in SETS}
preds["baseline: anomaly = 0"] = []
years = sorted(d.year.unique())
start = years[len(years) // 2]  # expanding window from the midpoint on
for t in years:
    if t < start:
        continue
    trn, tst = d[d.year < t], d[d.year == t]
    if len(tst) == 0 or len(trn) == 0:
        continue
    acc.append(tst[TARGET].values)
    preds["baseline: anomaly = 0"].append(np.zeros(len(tst)))
    for name, F in SETS.items():
        mdl = GradientBoostingRegressor(n_estimators=200, max_depth=3,
                                        learning_rate=.05, random_state=SEED)
        preds[name].append(mdl.fit(trn[F], trn[TARGET]).predict(tst[F]))
a = np.concatenate(acc)
Q3 = pd.DataFrame([dict(features=k, n_features=len(SETS.get(k, [])),
                        **metrics(a, np.concatenate(v))) for k, v in preds.items()])
base = Q3.loc[Q3.features.str.startswith("baseline"), "RMSE"].iloc[0]
Q3["skill_vs_baseline_pct"] = ((1 - Q3.RMSE / base) * 100).round(2)
clim = Q3.loc[Q3.features == "climate only", "RMSE"].iloc[0]
Q3["gain_vs_climate_pct"] = ((1 - Q3.RMSE / clim) * 100).round(2)
Q3 = Q3.sort_values("RMSE")
print(f"\n[br11] Q3  EXPANDING-WINDOW VALIDATION {start}-{years[-1]}  ({len(a):,} test observations)")
print(Q3.round(4).to_string(index=False))

tr2, te2 = d[d.year < years[-6]], d[d.year >= years[-6]]
F = CLIM + PROCESS + SOIL
mdl = GradientBoostingRegressor(n_estimators=200, max_depth=3, learning_rate=.05,
                                random_state=SEED).fit(tr2[F], tr2[TARGET])
pi = permutation_importance(mdl, te2[F], te2[TARGET], n_repeats=12,
                            random_state=SEED, n_jobs=-1)
imp = (pd.DataFrame(dict(feature=F, importance=pi.importances_mean, sd=pi.importances_std))
       .sort_values("importance", ascending=False).reset_index(drop=True))
imp["kind"] = np.where(imp.feature.isin(SOIL), "soil",
              np.where(imp.feature.isin(PROCESS), "process", "climate"))
imp.to_csv(RES / "br16_importance_with_soil.csv", index=False)
print(f"\n[br11] permutation importance, top 12 (all features, tested on {years[-6]}-{years[-1]})")
print(imp.head(12).round(4).to_string(index=False))
soil_ranks = imp.index[imp.kind == "soil"]
if len(soil_ranks):
    print(f"[br11] best soil feature : {imp.feature[soil_ranks[0]]} at rank "
          f"{int(soil_ranks[0]) + 1} of {len(F)}")

Q1.round(5).to_csv(RES / "br14_soil_explains_level.csv", index=False)
Q3.round(5).to_csv(RES / "br17_soil_prediction_gain.csv", index=False)

# ---------- Figure: soil vs municipality yield level ---------------------------
f, axes = plt.subplots(1, 3, figsize=(13, 4.8), dpi=200)
f.patch.set_facecolor(SURFACE)
pairs = [("soil_om_topsoil", "Topsoil organic matter (%)"),
         ("soil_clay_topsoil", "Topsoil clay (%)"),
         ("soil_ph_topsoil", "Topsoil pH")]
for ax_, (col, xl) in zip(axes, pairs):
    ax_.set_facecolor(SURFACE)
    ax_.scatter(muni[col], muni.yield_mean, s=26, color=S1, alpha=.75,
                edgecolor=SURFACE, linewidth=.6)
    fo = muni[muni.fips5 == FOCAL_CODE]
    if len(fo):
        ax_.scatter(fo[col], fo.yield_mean, s=70, color=FOCAL, zorder=3,
                    edgecolor=SURFACE, linewidth=1.1, label=FOCAL_MUNICIPIO.title())
    b = np.polyfit(muni[col].dropna(), muni.loc[muni[col].notna(), "yield_mean"], 1)
    xx = np.linspace(muni[col].min(), muni[col].max(), 50)
    ax_.plot(xx, np.polyval(b, xx), color=INK, lw=1.6, ls="--")
    r = np.corrcoef(muni[col].dropna(), muni.loc[muni[col].notna(), "yield_mean"])[0, 1]
    ax_.text(.03, .95, f"r = {r:+.2f}", transform=ax_.transAxes, fontsize=10,
             color=INK2, va="top")
    ax_.grid(color=GRID, lw=.7); ax_.set_axisbelow(True)
    for sp in ("top", "right"):
        ax_.spines[sp].set_visible(False)
    ax_.tick_params(colors=MUTED, labelsize=8.5)
    ax_.set_xlabel(xl, fontsize=9.5, color=INK2)
axes[0].set_ylabel("Municipality mean yield (bu/acre)", fontsize=9.5, color=INK2)
axes[0].legend(frameon=False, fontsize=9, labelcolor=INK2, loc="lower right")
f.suptitle("Figure BR-22. Soil and Mato Grosso soybean yield",
           fontsize=14.5, color=INK, x=.02, ha="left", y=1.06, fontweight="semibold")
f.text(.02, .975, "Municipality mean soybean yield 1981-2024 against three soil properties.",
       fontsize=9.6, color=INK2)
f.tight_layout(rect=[0, 0, 1, .91])
f.savefig(FIG / "fig_br22_soil_vs_yield_level.png", facecolor=SURFACE, bbox_inches="tight")
plt.close(f)
print("   figure -> fig_br22_soil_vs_yield_level.png")

json.dump(dict(
    soil_source="ISRIC SoilGrids v2.0", n_soil_features=len(SOIL), soil_features=SOIL,
    key_terms_used_in_ols=KEY,
    validation=f"expanding window, rolling origin {start}-{years[-1]}, no random splits",
    q2_status="SKIPPED -- no Brazil equivalent of US script 09 yet, real gap not a null result",
), open(RES / "br16_soil_config.json", "w"), indent=2)
print("\n[br11] wrote br14, br16, br17, fig_br22")
