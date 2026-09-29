"""BR 14 - Municipality climate sensitivity and perturbation scenarios.
Analogue of US script 09, adapted for what Brazil actually has: no Palmer
Z-index exists here (see br_05's docstring), so "moisture sensitivity" is
built directly from pcp_critical (Jan-Feb precipitation) rather than a
drought index. Uniform perturbations of observed climate, NOT CMIP6/IPCC
projections -- see br_12/13 for those. Retained as a robustness check that
isolates temperature and precipitation response separately, the same role
it plays in the US pipeline.
"""
import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from sklearn.ensemble import GradientBoostingRegressor
from _brcfg import FINAL, RES, FIG, SEED, FOCAL_CODE
from _viz import *

d = pd.read_csv(FINAL / "soja_mt_climate_1981_2024.csv", dtype={"fips5": str})
d = d[d.in_balanced_panel == 1].copy()
TARGET = "yield_anom"

# ---------- Table BR-7: municipality climate sensitivity ----------------------
rows = []
for f5, g in d.groupby("fips5"):
    if len(g) < 15:
        continue
    def r(v):
        k = g[v].notna() & g[TARGET].notna()
        return float(np.corrcoef(g.loc[k, v], g.loc[k, TARGET])[0, 1])
    X = np.column_stack([np.ones(len(g)),
                         (g.pcp_critical - g.pcp_critical.mean()) / g.pcp_critical.std(),
                         (g.tmax_critical - g.tmax_critical.mean()) / g.tmax_critical.std()])
    b, *_ = np.linalg.lstsq(X, g[TARGET].values, rcond=None)
    rows.append(dict(fips5=f5, county=g.county.iloc[0], n=len(g),
                     r_moisture=r("pcp_critical"), r_heat=r("tmax_critical"),
                     beta_moisture_bu_per_sd=float(b[1]), beta_heat_bu_per_sd=float(b[2]),
                     yield_recent=float(g[g.year >= g.year.max() - 9].yield_bu_ac.mean()),
                     trend=float(g.trend_slope.iloc[0]), volatility=float(g[TARGET].std()),
                     normal_pcp=float(g.pcp_critical.mean()), normal_tmax=float(g.tmax_critical.mean())))
t7 = pd.DataFrame(rows)
t7["sensitivity_index"] = ((t7.r_moisture.rank(pct=True) + (-t7.r_heat).rank(pct=True)) / 2).round(4)
t7 = t7.sort_values("sensitivity_index", ascending=False).round(4)
t7.to_csv(RES / "br07_municipio_climate_sensitivity.csv", index=False)
print(f"[br14] Table BR-7: {len(t7)} municipalities ranked")
print(t7.head(6)[["county", "r_moisture", "r_heat", "beta_moisture_bu_per_sd",
                  "sensitivity_index"]].to_string(index=False))
print("...")
print(t7.tail(4)[["county", "r_moisture", "r_heat", "beta_moisture_bu_per_sd",
                  "sensitivity_index"]].to_string(index=False))
if FOCAL_CODE in t7.fips5.values:
    rank = list(t7.fips5).index(FOCAL_CODE) + 1
    foc = t7[t7.fips5 == FOCAL_CODE].iloc[0]
    print(f"\n[br14] Sorriso: rank {rank} of {len(t7)} | r_moisture {foc.r_moisture:.3f} "
          f"| beta_moisture {foc.beta_moisture_bu_per_sd:+.3f} bu/SD")

# ---------- Scenarios -----------------------------------------------------------
CLIM_SIMPLE = ["pcp_critical", "tmax_critical", "tmp_critical",
               "climate_normal_pcp", "climate_normal_tmax"]
mdl = GradientBoostingRegressor(n_estimators=200, max_depth=3, learning_rate=.05,
                                random_state=SEED).fit(d[CLIM_SIMPLE], d[TARGET])
d["pred_baseline"] = mdl.predict(d[CLIM_SIMPLE])

TEMP_C = ["tmax_critical", "tmp_critical", "climate_normal_tmax"]
PREC = ["pcp_critical", "climate_normal_pcp"]


def perturb(df, dT_C=0.0, dP_pct=0.0):
    x = df.copy()
    for c in TEMP_C:
        x[c] = x[c] + dT_C
    for c in PREC:
        x[c] = x[c] * (1 + dP_pct / 100)
    return x


SCEN = {"S1 Baseline": (0, 0), "S2 +1C": (1, 0), "S3 -10% precip": (0, -10),
        "S4 +1C and -10% precip": (1, -10), "S5 +2C": (2, 0), "S6 +2C and -20% precip": (2, -20)}
out = []
for name, (dT, dP) in SCEN.items():
    d[f"pred_{name}"] = mdl.predict(perturb(d, dT, dP)[CLIM_SIMPLE])
    dl = d[f"pred_{name}"] - d.pred_baseline
    out.append(dict(scenario=name, delta_T_C=dT, delta_P_pct=dP,
                    mean_delta_bu=float(dl.mean()),
                    pct_of_mean_yield=float(dl.mean() / d.yield_bu_ac.mean() * 100),
                    p10=float(dl.quantile(.1)), p90=float(dl.quantile(.9)),
                    municipios_worse=int((d.groupby("fips5")[f"pred_{name}"].mean()
                                         - d.groupby("fips5").pred_baseline.mean() < 0).sum())))
S = pd.DataFrame(out).round(4)
S.to_csv(RES / "br08a_scenario_state_summary.csv", index=False)
print("\n[br14] SCENARIO SUMMARY (sensitivity experiments, NOT climate projections)")
print(S.to_string(index=False))

bymuni = d.groupby(["fips5", "county"]).agg(
    baseline_yield=("yield_bu_ac", "mean"),
    **{f"d_{k}": (f"pred_{k}", "mean") for k in SCEN}).reset_index()
for k in SCEN:
    bymuni[f"d_{k}"] = bymuni[f"d_{k}"] - bymuni["d_S1 Baseline"]
bymuni["pct_S4"] = bymuni["d_S4 +1C and -10% precip"] / bymuni.baseline_yield * 100
bymuni = bymuni.round(4)
bymuni.to_csv(RES / "br08b_scenario_by_municipio.csv", index=False)
print(f"\n[br14] worst municipalities under S4 (+1C, -10% precip):")
print(bymuni.nsmallest(6, "d_S4 +1C and -10% precip")[
    ["county", "baseline_yield", "d_S4 +1C and -10% precip", "pct_S4"]].to_string(index=False))
print(f"[br14] least affected:")
print(bymuni.nlargest(4, "d_S4 +1C and -10% precip")[
    ["county", "baseline_yield", "d_S4 +1C and -10% precip", "pct_S4"]].to_string(index=False))
if FOCAL_CODE in bymuni.fips5.values:
    fc = bymuni[bymuni.fips5 == FOCAL_CODE].iloc[0]
    print(f"\n[br14] Sorriso under S4: {fc['d_S4 +1C and -10% precip']:+.2f} bu/acre "
          f"({fc.pct_S4:+.2f}%)")

# ---------- Figure: sensitivity ranking -----------------------------------------
f, ax = fig(11, 7.6)
k = t7.sort_values("beta_moisture_bu_per_sd")
cols = [FOCAL if f5 == FOCAL_CODE else S1 for f5 in k.fips5]
ax.barh(range(len(k)), k.beta_moisture_bu_per_sd, color=cols, height=.86)
ax.set_yticks([])
ax.set_ylabel(f"{len(k)} municipalities, ordered", fontsize=10, color=INK2)
if FOCAL_CODE in list(k.fips5):
    i = list(k.fips5).index(FOCAL_CODE)
    ax.annotate("Sorriso", xy=(k.beta_moisture_bu_per_sd.iloc[i], i), xytext=(1.2, i - 9),
               fontsize=10, color=FOCAL, arrowprops=dict(arrowstyle="->", color=FOCAL, lw=1.3))
ax.grid(axis="y", lw=0)
ax.grid(axis="x", color=GRID, lw=.7)
style(ax, "Figure BR-13. Municipality climate sensitivity to Jan-Feb precipitation",
      "Yield response to a one-standard-deviation precipitation anomaly, municipality-by-municipality regression",
      "bu/acre per SD of Jan-Feb precipitation", None,
      src="Source: IBGE PAM; NASA POWER")
save(f, FIG / "fig_br13_municipio_climate_sensitivity.png")

for n, (key, ttl) in enumerate([
        ("S2 +1C", "Figure BR-14. Baseline versus +1 C"),
        ("S3 -10% precip", "Figure BR-15. Baseline versus -10% precipitation"),
        ("S4 +1C and -10% precip", "Figure BR-16. Baseline versus +1 C and -10% precipitation")], 14):
    f, ax = fig(10.5, 6)
    v = bymuni[f"d_{key}"]
    ax.hist(v, bins=26, color=S2 if v.mean() < 0 else S1, edgecolor=SURFACE, lw=1.1)
    ax.axvline(0, color=INK, lw=1.2)
    ax.axvline(v.mean(), color=FOCAL, lw=2, ls="--", label=f"mean {v.mean():+.2f} bu/acre")
    if FOCAL_CODE in bymuni.fips5.values:
        ax.axvline(bymuni.loc[bymuni.fips5 == FOCAL_CODE, f"d_{key}"].iloc[0], color=S4, lw=2,
                   label=f"Sorriso {bymuni.loc[bymuni.fips5 == FOCAL_CODE, f'd_{key}'].iloc[0]:+.2f}")
    style(ax, ttl, "Sensitivity experiment, not a climate projection. "
          f"Distribution across {len(bymuni)} municipalities.",
          "Change in predicted yield (bu/acre)", "Municipalities", legend=True,
          src="Source: IBGE PAM; NASA POWER")
    save(f, FIG / f"fig_br{n}_scenario_{key.split()[0].lower()}.png")

json.dump({"scenarios": {k: dict(delta_T_C=v[0], delta_P_pct=v[1]) for k, v in SCEN.items()},
          "note": "no Palmer Z-index for Brazil -- moisture sensitivity built from "
                  "pcp_critical directly, not a drought index (see br_05)",
          "disclaimer": "Sensitivity experiments. Uniform perturbations of observed "
                        "climate. Not CMIP6/IPCC projections and carry no probability "
                        "information."},
          open(RES / "br09_scenario_config.json", "w"), indent=2)
print("\n[br14] wrote br07 (sensitivity), br08a/b (scenarios), fig_br13-16")
