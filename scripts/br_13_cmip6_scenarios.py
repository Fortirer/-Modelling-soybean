"""BR 13 - Apply CMIP6 change factors to the Mato Grosso panel and re-predict
yield. Analogue of US script 13, SCOPED DOWN in two ways the docstring below
states plainly rather than silently matching the US script's shape:

1. ONE estimator, not two. US script 13 compares a boosted-tree fit (best
   in-sample, but saturates beyond the observed temperature range) against a
   quadratic-panel OLS (extrapolates, at the cost of assuming the fitted
   curve holds outside the observed range). This script reports only the
   quadratic-panel estimator -- the one that answers "what does the fitted
   relationship say under this warming," which is the number CMIP6 deltas
   exist to produce. Adding the boosted-tree comparison later is possible
   but was not done here.
2. Only pcp_critical and tmax_critical (the two terms br_07's regression
   actually uses) are recomputed under warming, not the full climate-feature
   family US script 13's recompute() rebuilds. Reason: the US branch keeps
   per-month nClimDiv columns (pcp07, tmax08, ...) all the way into the
   final panel, so every derived feature can be recomputed from perturbed
   monthly values. This branch computes its features directly from DAILY
   POWER data (br_05) and does not retain a monthly table downstream, so
   perturbing daily-resolution features (heat_x_dry, hot/dry-day counts)
   from monthly CMIP6 deltas is not straightforward and was not attempted.
   A dedicated monthly baseline table is built HERE, specifically for this
   script, restricted to Jan and Feb (the critical window) -- see
   monthly_baseline() below.
"""
import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import statsmodels.formula.api as smf
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _brcfg import RAW, FINAL, PROC, RES, FIG, UF, FOCAL_CODE
from _viz import *

d = pd.read_csv(FINAL / "soja_mt_climate_1981_2024.csv", dtype={"fips5": str})
d = d[d.in_balanced_panel == 1].copy().reset_index(drop=True)

dl = pd.read_csv(PROC / "cmip6_deltas.csv", dtype={"fips5": str})
MODELS = sorted(dl.model.unique())
print(f"[br13] panel {len(d):,} rows, {d.fips5.nunique()} municipalities")
print(f"[br13] CMIP6 ensemble: {len(MODELS)} models -> {', '.join(MODELS)}")


def monthly_baseline():
    """Jan/Feb monthly pcp (mm) and tmax (degC) per (fips5, crop_year), built
    directly from the daily POWER file -- see docstring point 2."""
    daily = pd.read_csv(RAW / "power_daily.csv.gz", dtype={"unit_id": str})
    daily["date"] = pd.to_datetime(daily.date)
    daily["month"] = daily.date.dt.month
    jf = daily[daily.month.isin([1, 2])].copy()
    jf["crop_year"] = jf.year - 1   # Jan/Feb of calendar Y belongs to crop_year Y-1
    m = (jf.groupby(["unit_id", "crop_year", "month"])
           .agg(pcp=("prcp_mm", "sum"), tmax=("tmax_c", "mean"))
           .reset_index().rename(columns={"unit_id": "fips5", "crop_year": "year"}))
    return m.pivot_table(index=["fips5", "year"], columns="month", values=["pcp", "tmax"])


MB = monthly_baseline()
d = d.merge(MB["pcp"][1].rename("pcp_jan"), on=["fips5", "year"], how="left") \
     .merge(MB["pcp"][2].rename("pcp_feb"), on=["fips5", "year"], how="left") \
     .merge(MB["tmax"][1].rename("tmax_jan"), on=["fips5", "year"], how="left") \
     .merge(MB["tmax"][2].rename("tmax_feb"), on=["fips5", "year"], how="left")
before = len(d)
d = d.dropna(subset=["pcp_jan", "pcp_feb", "tmax_jan", "tmax_feb"]).reset_index(drop=True)
if len(d) < before:
    print(f"[br13] dropped {before - len(d)} rows with no Jan/Feb monthly baseline "
          f"(POWER coverage edge, see br_04)")


def apply_deltas(base, sub):
    x = base.copy()
    piv_tx = sub.pivot(index="fips5", columns="month", values="d_tasmax_C")
    piv_p = sub.pivot(index="fips5", columns="month", values="pr_ratio")
    f5 = x.fips5.values
    x["pcp_jan"] = x.pcp_jan * piv_p.reindex(f5)[1].values
    x["pcp_feb"] = x.pcp_feb * piv_p.reindex(f5)[2].values
    x["tmax_jan"] = x.tmax_jan + piv_tx.reindex(f5)[1].values
    x["tmax_feb"] = x.tmax_feb + piv_tx.reindex(f5)[2].values
    x["PCP"] = x.pcp_jan + x.pcp_feb
    x["TMX"] = (x.tmax_jan + x.tmax_feb) / 2.0
    x["PCP2"], x["TMX2"], x["PT"] = x.PCP ** 2, x.TMX ** 2, x.PCP * x.TMX
    return x


d["PCP"] = d.pcp_jan + d.pcp_feb
d["TMX"] = (d.tmax_jan + d.tmax_feb) / 2.0
d["PCP2"], d["TMX2"], d["PT"] = d.PCP ** 2, d.TMX ** 2, d.PCP * d.TMX
d["muni"] = d.fips5.astype("category")

par = smf.ols("yield_anom ~ PCP + PCP2 + TMX + TMX2 + PT + C(muni)", data=d).fit(
    cov_type="cluster", cov_kwds={"groups": d.fips5})
d["pred_baseline"] = par.predict(d).values

mean_yield = d.yield_bu_ac.mean()
OBS_TMAX_MIN, OBS_TMAX_MAX = float(d.TMX.min()), float(d.TMX.max())
print(f"[br13] baseline mean yield  : {mean_yield:.2f} bu/acre")
print(f"[br13] observed Jan-Feb tmax range : {OBS_TMAX_MIN:.1f} - {OBS_TMAX_MAX:.1f} degC")
print(f"[br13] quadratic panel R2  : {par.rsquared:.3f}  (n={int(par.nobs):,})")

per_model, per_muni = [], []
for scen in sorted(dl.scenario.unique()):
    for hz in sorted(dl.horizon.unique()):
        preds, oor = {}, {}
        for mod in MODELS:
            sub = dl[(dl.model == mod) & (dl.scenario == scen) & (dl.horizon == hz)]
            if sub.empty:
                continue
            x = apply_deltas(d, sub)
            preds[mod] = par.predict(x).values - d.pred_baseline.values
            oor[mod] = float((x.TMX > OBS_TMAX_MAX).mean() * 100)
            per_model.append(dict(
                scenario=scen, horizon=hz, model=mod,
                mean_delta_bu=float(preds[mod].mean()),
                pct_of_mean_yield=float(preds[mod].mean() / mean_yield * 100),
                out_of_range_pct=oor[mod],
                dTmax_JF_C=float(sub[sub.month.isin([1, 2])].d_tasmax_C.mean()),
                precip_JF_pct=float((sub[sub.month.isin([1, 2])].pr_ratio.mean() - 1) * 100)))
        if not preds:
            continue
        ens = np.median(np.vstack([preds[m] for m in preds]), axis=0)
        tmp = d[["fips5", "yield_bu_ac"]].copy()
        tmp["delta_bu"] = ens
        agg = tmp.groupby("fips5").agg(baseline_yield=("yield_bu_ac", "mean"),
                                       delta_bu=("delta_bu", "mean")).reset_index()
        agg["pct"] = agg.delta_bu / agg.baseline_yield * 100
        agg["scenario"], agg["horizon"] = scen, hz
        per_muni.append(agg)

PM = pd.DataFrame(per_model)
PC = pd.concat(per_muni, ignore_index=True)
PM.round(4).to_csv(RES / "br12_cmip6_model_spread.csv", index=False)
PC.round(4).to_csv(RES / "br13_cmip6_by_municipio.csv", index=False)

rows = []
for (scen, hz), g in PM.groupby(["scenario", "horizon"]):
    cty = PC[(PC.scenario == scen) & (PC.horizon == hz)]
    rows.append(dict(scenario=scen, horizon=hz, n_models=len(g),
                     dTmax_JF_C=g.dTmax_JF_C.mean(), precip_JF_pct=g.precip_JF_pct.mean(),
                     out_of_range_pct=g.out_of_range_pct.mean(),
                     ens_median_delta_bu=float(np.median(g.mean_delta_bu)),
                     ens_median_pct=float(np.median(g.pct_of_mean_yield)),
                     model_min_bu=g.mean_delta_bu.min(), model_max_bu=g.mean_delta_bu.max(),
                     municipios_worse=int((cty.delta_bu < 0).sum()),
                     municipios_total=len(cty)))
T11 = pd.DataFrame(rows).sort_values(["scenario", "horizon"])
T11.round(4).to_csv(RES / "br11_cmip6_scenario_summary.csv", index=False)

print("\n[br13] CMIP6 SCENARIO SUMMARY (ensemble median across models, quadratic panel only)")
print(T11[["scenario", "horizon", "n_models", "dTmax_JF_C", "precip_JF_pct",
           "out_of_range_pct", "ens_median_delta_bu", "municipios_worse",
           "municipios_total"]].round(3).to_string(index=False))
for _, r in T11.iterrows():
    if r.out_of_range_pct > 10:
        print(f"[br13] WARNING {r.scenario} {r.horizon}: {r.out_of_range_pct:.0f}% of "
              f"municipality-years exceed the hottest Jan-Feb on record.")

print("\n[br13] PER-MODEL SPREAD (state mean yield change, bu/acre)")
print(PM.pivot_table(index="model", columns=["scenario", "horizon"],
                     values="mean_delta_bu").round(3).to_string())

foc = PC[PC.fips5 == FOCAL_CODE]
print(f"\n[br13] Sorriso ({FOCAL_CODE})")
print(foc[["scenario", "horizon", "baseline_yield", "delta_bu", "pct"]]
      .round(3).to_string(index=False))

# ---------- Figure: warming by scenario ----------------------------------------
f, ax = fig(10.5, 6)
lab = [f"{s.upper()}\n{h.replace('_',' ')}" for s, h in zip(T11.scenario, T11.horizon)]
xp = np.arange(len(T11))
ax.bar(xp, T11.dTmax_JF_C, color=S2, width=.55)
for i, v in enumerate(T11.dTmax_JF_C):
    ax.text(i, v + .05, f"+{v:.2f} C", ha="center", fontsize=10, color=INK2)
ax.set_xticks(xp); ax.set_xticklabels(lab, fontsize=9.5)
style(ax, "Figure BR-19. CMIP6 January-February warming over Mato Grosso",
      f"Ensemble mean of {PM.model.nunique()} models, change in daily maximum temperature "
      f"from the 1985-2014 baseline.", None, "Delta Tmax (degC)",
      src="Source: CMIP6 Amon, AWS Open Data s3://cmip6-pds")
save(f, FIG / "fig_br19_cmip6_warming.png")

json.dump(dict(
    method="CMIP6 delta change-factor applied to the observed municipality record, "
          "quadratic-panel estimator only (see docstring for scope vs US script 13)",
    baseline="1985-2014", scenarios=sorted(dl.scenario.unique()),
    horizons=sorted(dl.horizon.unique()), models=MODELS, n_models=len(MODELS),
    critical_window="Jan-Feb", target="yield_anom",
    observed_tmax_range_C=[OBS_TMAX_MIN, OBS_TMAX_MAX],
    caveats=[
        "Only the quadratic-panel estimator is reported -- no boosted-tree comparison.",
        "Only pcp_critical/tmax_critical (Jan-Feb) are perturbed; the full monthly "
        "climate-feature family (heat_x_dry, hot/dry-day counts) is not recomputed "
        "under warming, since those are daily-resolution features not retained as "
        "monthly columns in this branch's final panel.",
        "No Palmer drought index equivalent to hold constant or perturb.",
        "No agronomic adaptation, cultivar change or planting-date shift is assumed.",
        "One realisation per model; internal variability not sampled.",
    ]), open(RES / "br13_cmip6_config.json", "w"), indent=2)
print(f"\n[br13] wrote br11, br12, br13, fig_br19")
