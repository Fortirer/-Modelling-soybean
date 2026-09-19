"""16 - What does soil actually buy us? Tables 14-17, Figures 22-23.

Three separate questions, because they have different answers and collapsing
them into one headline would overstate the result.

  Q1  Does soil explain the LEVEL of county yield?
      Expected yes. Detrending removed exactly this signal from the modelling
      target, so it has never been examined in this repo.

  Q2  Does soil explain each county's SENSITIVITY to climate?
      The interaction story: a sandy, shallow soil has less water to buffer a
      dry August than a deep silt loam. Tested against the county sensitivity
      coefficients estimated in script 09.

  Q3  Does soil improve out-of-sample prediction of yield_anom?
      Expected small. yield_anom is the residual of a county-specific trend, so
      its county mean is zero BY CONSTRUCTION and a static county attribute has
      almost no main effect left to explain. Any gain must arrive through
      interaction with climate. Judged under the same expanding-window
      validation as script 08 -- no random splits.
"""
import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import statsmodels.formula.api as smf
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.inspection import permutation_importance
from matplotlib.patches import Patch
from _cfg import FINAL, PROC, RES, FIG, SEED, FOCAL_COUNTY
from _viz import *

d = pd.read_csv(FINAL / "soybean_illinois_climate_1980_2025.csv",
                dtype={"county_ansi": str, "fips5": str})
d = d[d.in_balanced_panel == 1].copy()
s = pd.read_csv(PROC / "soil_features.csv", dtype={"fips5": str})
SOIL = [c for c in s.columns if c != "fips5"]

before = d.fips5.nunique()
d = d.merge(s, on="fips5", how="left", validate="many_to_one")
unmatched = int(d[SOIL[0]].isna().sum())
print(f"[16] panel {len(d):,} rows, {before} counties, {len(SOIL)} soil features")
print(f"[16] rows with no soil match : {unmatched}")
assert unmatched == 0, "soil join incomplete"

cfg = json.load(open(RES / "08_ml_config.json"))
CLIM, TARGET = cfg["features"], cfg["target"]


def metrics(a, p):
    e = p - a
    return dict(RMSE=float(np.sqrt((e ** 2).mean())), MAE=float(np.abs(e).mean()),
                R2=float(1 - (e ** 2).sum() / ((a - a.mean()) ** 2).sum()))


def fit_ols(df, y, X):
    return smf.ols(y + " ~ " + " + ".join(X), data=df).fit()


KEY = ["soil_aws_0_100cm", "soil_om_topsoil", "soil_clay_topsoil", "soil_sand_topsoil",
       "soil_ksat_subsoil", "soil_slope", "soil_drain_poorly_pct", "soil_mollisol_pct"]

# ===== Q1: soil vs the LEVEL of county yield =================================
cty = (d.groupby(["county", "fips5"])
         .agg(yield_mean=("yield_bu_ac", "mean"),
              trend_slope=("trend_slope", "first"),
              anom_sd=("yield_anom", "std")).reset_index()
         .merge(s, on="fips5", how="left"))

q1 = []
for y, lab in [("yield_mean", "county mean yield (bu/acre)"),
               ("trend_slope", "yield trend (bu/acre/yr)"),
               ("anom_sd", "yield volatility (sd of anomaly)")]:
    m = fit_ols(cty, y, KEY)
    p = m.pvalues.drop("Intercept")
    q1.append(dict(target=lab, n=int(m.nobs), r2=float(m.rsquared),
                   adj_r2=float(m.rsquared_adj),
                   strongest_term=p.idxmin(), p_value=float(p.min())))
Q1 = pd.DataFrame(q1)
print("\n[16] Q1  SOIL vs THE LEVEL OF COUNTY YIELD  (OLS, 8 soil terms)")
print(Q1.round(4).to_string(index=False))

m_lvl = fit_ols(cty, "yield_mean", KEY)
print("\n[16] county mean yield ~ soil, coefficients")
print(pd.DataFrame(dict(coef=m_lvl.params, se=m_lvl.bse, p=m_lvl.pvalues))
      .drop("Intercept").round(4).to_string())

# ===== Q2: soil vs climate SENSITIVITY =======================================
try:
    t7 = pd.read_csv(RES / "table7_county_climate_sensitivity.csv", dtype={"fips5": str})
    sens = t7.merge(s, on="fips5", how="inner")
    q2 = []
    for y, lab in [("beta_moisture_bu_per_sd", "yield response to moisture (bu/SD)"),
                   ("beta_heat_bu_per_sd", "yield response to heat (bu/SD)"),
                   ("sensitivity_index", "composite sensitivity index")]:
        m = fit_ols(sens, y, KEY)
        p = m.pvalues.drop("Intercept")
        q2.append(dict(target=lab, n=int(m.nobs), r2=float(m.rsquared),
                       adj_r2=float(m.rsquared_adj),
                       strongest_term=p.idxmin(), p_value=float(p.min())))
    Q2 = pd.DataFrame(q2)
    print("\n[16] Q2  SOIL vs CLIMATE SENSITIVITY  (OLS, 8 soil terms)")
    print(Q2.round(4).to_string(index=False))
except FileNotFoundError:
    Q2 = pd.DataFrame()
    print("\n[16] Q2 skipped: table7 not found (run script 09 first)")

# ===== Q3: does soil improve out-of-sample prediction? =======================
SETS = {"climate only": CLIM, "soil only": SOIL, "climate + soil": CLIM + SOIL}
d = d.sort_values(["county", "year"]).reset_index(drop=True)
acc = []
preds = {k: [] for k in SETS}
preds["baseline: anomaly = 0"] = []
for t in range(2001, 2026):
    trn, tst = d[d.year < t], d[d.year == t]
    if len(tst) == 0:
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
print(f"\n[16] Q3  EXPANDING-WINDOW VALIDATION 2001-2025  ({len(a):,} test observations)")
print(Q3.round(4).to_string(index=False))

# permutation importance with soil in the mix, on held-out years
tr2, te2 = d[d.year < 2019], d[d.year >= 2019]
F = CLIM + SOIL
mdl = GradientBoostingRegressor(n_estimators=200, max_depth=3, learning_rate=.05,
                                random_state=SEED).fit(tr2[F], tr2[TARGET])
pi = permutation_importance(mdl, te2[F], te2[TARGET], n_repeats=12,
                            random_state=SEED, n_jobs=-1)
imp = (pd.DataFrame(dict(feature=F, importance=pi.importances_mean, sd=pi.importances_std))
       .sort_values("importance", ascending=False).reset_index(drop=True))
imp["kind"] = np.where(imp.feature.isin(SOIL), "soil", "climate")
imp.to_csv(RES / "table16_importance_with_soil.csv", index=False)
print("\n[16] permutation importance, top 12 (climate + soil, tested on 2019-2025)")
print(imp.head(12).round(4).to_string(index=False))
soil_ranks = imp.index[imp.kind == "soil"]
if len(soil_ranks):
    print(f"[16] best soil feature : {imp.feature[soil_ranks[0]]} at rank "
          f"{int(soil_ranks[0]) + 1} of {len(F)}")

Q1.round(5).to_csv(RES / "table14_soil_explains_level.csv", index=False)
if not Q2.empty:
    Q2.round(5).to_csv(RES / "table15_soil_explains_sensitivity.csv", index=False)
Q3.round(5).to_csv(RES / "table17_soil_prediction_gain.csv", index=False)

# ---------- Figure 22: soil vs county yield level -----------------------------
f, axes = plt.subplots(1, 3, figsize=(13, 4.8), dpi=200)
f.patch.set_facecolor(SURFACE)
pairs = [("soil_mollisol_pct", "Mollisol share of county (%)"),
         ("soil_aws_0_100cm", "Available water, top metre (cm)"),
         ("soil_slope", "Mean slope (%)")]
for ax_, (col, xl) in zip(axes, pairs):
    ax_.set_facecolor(SURFACE)
    ax_.scatter(cty[col], cty.yield_mean, s=26, color=S1, alpha=.75,
                edgecolor=SURFACE, linewidth=.6)
    fo = cty[cty.county == FOCAL_COUNTY]
    if len(fo):
        ax_.scatter(fo[col], fo.yield_mean, s=70, color=FOCAL, zorder=3,
                    edgecolor=SURFACE, linewidth=1.1, label=FOCAL_COUNTY.title())
    b = np.polyfit(cty[col], cty.yield_mean, 1)
    xx = np.linspace(cty[col].min(), cty[col].max(), 50)
    ax_.plot(xx, np.polyval(b, xx), color=INK, lw=1.6, ls="--")
    r = np.corrcoef(cty[col], cty.yield_mean)[0, 1]
    ax_.text(.03, .95, f"r = {r:+.2f}", transform=ax_.transAxes, fontsize=10,
             color=INK2, va="top")
    ax_.grid(color=GRID, lw=.7); ax_.set_axisbelow(True)
    for sp in ("top", "right"):
        ax_.spines[sp].set_visible(False)
    ax_.tick_params(colors=MUTED, labelsize=8.5)
    ax_.set_xlabel(xl, fontsize=9.5, color=INK2)
axes[0].set_ylabel("County mean yield (bu/acre)", fontsize=9.5, color=INK2)
axes[0].legend(frameon=False, fontsize=9, labelcolor=INK2, loc="lower right")
f.suptitle("Figure 22. Soil explains where the good ground is",
           fontsize=14.5, color=INK, x=.02, ha="left", y=1.06, fontweight="semibold")
f.text(.02, .975, "County mean soybean yield 1980-2025 against three soil properties. "
       "Detrending removed this signal from the modelling target, so it went unexamined "
       "until now.", fontsize=9.6, color=INK2)
f.tight_layout(rect=[0, 0, 1, .91])
f.savefig(FIG / "fig22_soil_vs_yield_level.png", facecolor=SURFACE, bbox_inches="tight")
plt.close(f)
print("   figure -> fig22_soil_vs_yield_level.png")

# ---------- Figure 23: importance, soil vs climate ----------------------------
f, ax = fig(10.5, 7)
k = imp.head(16).iloc[::-1]
ax.barh(range(len(k)), k.importance, xerr=k.sd, height=.68,
        color=[S4 if v == "soil" else S1 for v in k.kind],
        error_kw=dict(ecolor=MUTED, lw=.9, capsize=2.5))
ax.set_yticks(range(len(k)))
ax.set_yticklabels(k.feature, fontsize=9)
ax.grid(axis="y", lw=0); ax.grid(axis="x", color=GRID, lw=.7)
ax.legend(handles=[Patch(color=S1, label="climate"), Patch(color=S4, label="soil")],
          frameon=False, fontsize=9.5, labelcolor=INK2, loc="lower right")
style(ax, "Figure 23. Soil barely moves the detrended target",
      "Permutation importance on held-out years 2019-2025. The target is yield with each "
      "county's own trend removed, so a static county attribute has little left to explain.",
      "Increase in MSE when permuted", None,
      src="Source: USDA NASS; NOAA NCEI nClimDiv; USDA-NRCS SSURGO")
save(f, FIG / "fig23_importance_with_soil.png")

json.dump(dict(
    soil_source="USDA-NRCS SSURGO via Soil Data Access",
    n_soil_features=len(SOIL), soil_features=SOIL, key_terms_used_in_ols=KEY,
    validation="expanding window, rolling origin 2001-2025, no random splits",
    q1_note="soil explains the level of county yield, which detrending removed from the target",
    q2_note="soil vs county climate-sensitivity coefficients from script 09",
    q3_note="static county attributes cannot shift a target whose county mean is zero "
            "by construction; any gain arrives through interaction with climate",
), open(RES / "16_soil_config.json", "w"), indent=2)
print("\n[16] wrote table14, table15, table16, table17, fig22, fig23")
