"""13 - IPCC/CMIP6 scenario projections. Tables 11-13, Figures 19-21.

Applies the CMIP6 change factors from script 12 to the observed county record,
recomputes every derived climate feature exactly as script 04 does, and
re-predicts yield with the model selected in script 08.

Unlike script 09, the perturbations here are NOT arbitrary: each one is the
change a named GCM simulates between 1985-2014 and the stated horizon under a
named SSP pathway. The ensemble spread across models is reported, not hidden.

Still not a forecast. See the caveats printed at the end and in
results/12_provenance_cmip6.json.
"""
import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import statsmodels.formula.api as smf
from sklearn.ensemble import GradientBoostingRegressor
from _cfg import FINAL, PROC, RES, FIG, SEED, FOCAL_COUNTY, GROW_MONTHS, CRITICAL_MONTHS
from _viz import *

F2C = 1.8                       # degC -> degF  (a delta, so no 32 offset)
HOT_F, DRY_IN = 88, 2.5         # thresholds fixed in script 04

d = pd.read_csv(FINAL / "soybean_illinois_climate_1980_2025.csv",
                dtype={"county_ansi": str, "fips5": str})
d = d[d.in_balanced_panel == 1].copy().reset_index(drop=True)
cfg = json.load(open(RES / "08_ml_config.json"))
FEATS, TARGET = cfg["features"], cfg["target"]

dl = pd.read_csv(PROC / "cmip6_deltas.csv", dtype={"fips5": str})
MODELS = sorted(dl.model.unique())
print(f"[13] panel {len(d):,} rows, {d.county.nunique()} counties")
print(f"[13] CMIP6 ensemble: {len(MODELS)} models -> {', '.join(MODELS)}")


def recompute(x):
    """Rebuild every derived feature from the monthly columns, as script 04 does."""
    P = [f"pcp{m:02d}" for m in GROW_MONTHS]
    T = [f"tmp{m:02d}" for m in GROW_MONTHS]
    C = [f"pcp{m:02d}" for m in CRITICAL_MONTHS]
    x["pcp_grow"]      = x[P].sum(axis=1)
    x["pcp_critical"]  = x[C].sum(axis=1)
    x["pcp_summer"]    = x[["pcp06", "pcp07", "pcp08"]].sum(axis=1)
    x["tmp_grow"]      = x[T].mean(axis=1)
    x["tmp_critical"]  = x[["tmp07", "tmp08"]].mean(axis=1)
    x["tmp_summer"]    = x[["tmp06", "tmp07", "tmp08"]].mean(axis=1)
    x["tmax_critical"] = x[["tmax07", "tmax08"]].mean(axis=1)
    x["tmax_summer"]   = x["tmax_jja"]
    x["tmp_range_crit"] = x["tmax_critical"] - x[["tmin09", "tmin10"]].mean(axis=1)
    x["pcp_grow_cv"]   = x[P].std(axis=1) / x["pcp_grow"].replace(0, np.nan) * len(P)
    x["tmp_grow_sd"]   = x[T].std(axis=1)
    x["hot_month_count"] = (x[["tmax07", "tmax08"]] >= HOT_F).sum(axis=1)
    x["dry_month_count"] = (x[C] < DRY_IN).sum(axis=1)
    # Palmer indices are NOT perturbed (CMIP6 supplies no PDSI); observed values persist
    x["heat_x_dry"] = x.tmax_critical * (-x.zndx08)
    g = x.groupby("county")
    x["climate_normal_pcp"]  = g["pcp_critical"].transform("mean")
    x["climate_normal_tmax"] = g["tmax_critical"].transform("mean")
    return x


def apply_deltas(base, sub):
    """Apply one model/scenario/horizon's monthly county deltas to the panel."""
    x = base.copy()
    piv_t  = sub.pivot(index="fips5", columns="month", values="d_tas_C")
    piv_tx = sub.pivot(index="fips5", columns="month", values="d_tasmax_C")
    piv_p  = sub.pivot(index="fips5", columns="month", values="pr_ratio")
    f5 = x.fips5.values

    def col(piv, months):
        """Per-row value for the given month (or mean of months) by county."""
        v = piv.reindex(f5)
        return v[months].mean(axis=1).values if isinstance(months, list) else v[months].values

    # --- growing-season monthlies -------------------------------------------
    for m in GROW_MONTHS:
        x[f"pcp{m:02d}"] = x[f"pcp{m:02d}"] * col(piv_p, m)
        x[f"tmp{m:02d}"] = x[f"tmp{m:02d}"] + col(piv_t, m) * F2C
    # --- other monthlies the feature set depends on --------------------------
    x["tmax07"]  = x["tmax07"] + col(piv_tx, 7) * F2C
    x["tmax08"]  = x["tmax08"] + col(piv_tx, 8) * F2C
    x["tmax_jja"] = x["tmax_jja"] + col(piv_tx, [6, 7, 8]) * F2C
    # tasmin was not retrieved; tas is used as the proxy for tmin (see caveats)
    for m in (4, 5, 9, 10):
        c = f"tmin{m:02d}"
        if c in x:
            x[c] = x[c] + col(piv_t, m) * F2C
    x["pcp_win"]    = x["pcp_win"] * col(piv_p, [12, 1, 2])
    if "pcp_prevND" in x:
        x["pcp_prevND"] = x["pcp_prevND"] * col(piv_p, [11, 12])
    return recompute(x)


# ---------- two estimators, because one of them cannot extrapolate ------------
# Boosted trees fit the observed record best, but a tree predicts a CONSTANT
# beyond the range it was trained on. Under strong warming most county-years
# fall outside that range, the heat signal saturates, and the scenario ranking
# stops being monotonic. The quadratic panel specification of script 07 is
# parametric in temperature, so it keeps responding -- at the cost of assuming
# the fitted curve holds outside the observed range. Neither is right on its
# own; both are reported, with the share of out-of-range rows beside them.
mdl = GradientBoostingRegressor(n_estimators=200, max_depth=3, learning_rate=.05,
                                random_state=SEED).fit(d[FEATS], d[TARGET])
d["pred_baseline"] = mdl.predict(d[FEATS])

OBS_TMAX_MAX = float(d.tmax_critical.max())
OBS_TMAX_MIN = float(d.tmax_critical.min())


def prep_par(x):
    """Design columns for the quadratic panel specification (script 07, M3)."""
    x = x.copy()
    x["PCP"] = x.pcp_critical
    x["TMX"] = x.tmax_critical
    x["PCP2"] = x.PCP ** 2
    x["TMX2"] = x.TMX ** 2
    x["PT"] = x.PCP * x.TMX
    x["cty"] = x.county.astype("category")
    return x


d_par = prep_par(d)
par = smf.ols("yield_anom ~ PCP + PCP2 + TMX + TMX2 + PT + C(cty)",
              data=d_par).fit(cov_type="cluster", cov_kwds={"groups": d_par.county})
d["pred_par_baseline"] = par.predict(d_par).values

mean_yield = d.yield_bu_ac.mean()
print(f"[13] baseline mean yield  : {mean_yield:.2f} bu/acre")
print(f"[13] observed tmax_critical range : {OBS_TMAX_MIN:.1f} - {OBS_TMAX_MAX:.1f} F")
print(f"[13] quadratic panel R2   : {par.rsquared:.3f}  (n={int(par.nobs):,})")

# ---------- run every model x scenario x horizon ------------------------------
per_model, per_county = [], []
for scen in sorted(dl.scenario.unique()):
    for hz in sorted(dl.horizon.unique()):
        preds, preds_par, oor = {}, {}, {}
        for mod in MODELS:
            sub = dl[(dl.model == mod) & (dl.scenario == scen) & (dl.horizon == hz)]
            if sub.empty:
                continue
            x = apply_deltas(d, sub)
            preds[mod] = mdl.predict(x[FEATS]) - d.pred_baseline.values
            preds_par[mod] = (par.predict(prep_par(x)).values
                              - d.pred_par_baseline.values)
            oor[mod] = float((x.tmax_critical > OBS_TMAX_MAX).mean() * 100)
            per_model.append(dict(
                scenario=scen, horizon=hz, model=mod,
                mean_delta_bu=float(preds[mod].mean()),
                pct_of_mean_yield=float(preds[mod].mean() / mean_yield * 100),
                mean_delta_bu_parametric=float(preds_par[mod].mean()),
                pct_parametric=float(preds_par[mod].mean() / mean_yield * 100),
                out_of_range_pct=oor[mod],
                dTmax_JA_C=float(sub[sub.month.isin([7, 8])].d_tasmax_C.mean()),
                precip_JA_pct=float((sub[sub.month.isin([7, 8])].pr_ratio.mean() - 1) * 100)))
        if not preds:
            continue
        ens = np.median(np.vstack([preds[m] for m in preds]), axis=0)
        ens_par = np.median(np.vstack([preds_par[m] for m in preds_par]), axis=0)
        tmp = d[["county", "fips5", "ag_district", "yield_bu_ac"]].copy()
        tmp["delta_bu"] = ens
        tmp["delta_bu_parametric"] = ens_par
        agg = (tmp.groupby(["county", "fips5", "ag_district"])
                  .agg(baseline_yield=("yield_bu_ac", "mean"),
                       delta_bu=("delta_bu", "mean"),
                       delta_bu_parametric=("delta_bu_parametric", "mean")).reset_index())
        agg["pct"] = agg.delta_bu / agg.baseline_yield * 100
        agg["pct_parametric"] = agg.delta_bu_parametric / agg.baseline_yield * 100
        agg["scenario"], agg["horizon"] = scen, hz
        per_county.append(agg)

PM = pd.DataFrame(per_model)
PC = pd.concat(per_county, ignore_index=True)
PM.round(4).to_csv(RES / "table12_cmip6_model_spread.csv", index=False)
PC.round(4).to_csv(RES / "table13_cmip6_by_county.csv", index=False)

# ---------- Table 11: headline summary ----------------------------------------
rows = []
for (scen, hz), g in PM.groupby(["scenario", "horizon"]):
    cty = PC[(PC.scenario == scen) & (PC.horizon == hz)]
    rows.append(dict(
        scenario=scen, horizon=hz, n_models=len(g),
        dTmax_JA_C=g.dTmax_JA_C.mean(), precip_JA_pct=g.precip_JA_pct.mean(),
        out_of_range_pct=g.out_of_range_pct.mean(),
        ens_median_delta_bu=float(np.median(g.mean_delta_bu)),
        ens_median_pct=float(np.median(g.pct_of_mean_yield)),
        ens_median_parametric_bu=float(np.median(g.mean_delta_bu_parametric)),
        ens_median_parametric_pct=float(np.median(g.pct_parametric)),
        model_min_bu=g.mean_delta_bu.min(), model_max_bu=g.mean_delta_bu.max(),
        counties_worse=int((cty.delta_bu < 0).sum()),
        counties_worse_parametric=int((cty.delta_bu_parametric < 0).sum()),
        counties_total=len(cty)))
T11 = pd.DataFrame(rows).sort_values(["scenario", "horizon"])
T11.round(4).to_csv(RES / "table11_cmip6_scenario_summary.csv", index=False)

print("\n[13] CMIP6 SCENARIO SUMMARY (ensemble median across models)")
print("     trees  = boosted trees, saturate beyond the observed range")
print("     quad   = quadratic panel, extrapolates")
print("     oor    = share of county-years above the hottest Jul-Aug ever observed")
print(T11[["scenario", "horizon", "n_models", "dTmax_JA_C", "precip_JA_pct",
           "out_of_range_pct", "ens_median_delta_bu", "ens_median_parametric_bu",
           "counties_worse", "counties_worse_parametric"]]
      .rename(columns={"out_of_range_pct": "oor_%",
                       "ens_median_delta_bu": "trees_bu",
                       "ens_median_parametric_bu": "quad_bu",
                       "counties_worse": "worse_trees",
                       "counties_worse_parametric": "worse_quad"})
      .round(3).to_string(index=False))

for _, r in T11.iterrows():
    if r.out_of_range_pct > 10:
        print(f"[13] WARNING {r.scenario} {r.horizon}: {r.out_of_range_pct:.0f}% of "
              f"county-years exceed the hottest Jul-Aug on record. The boosted-tree "
              f"estimate is not usable here; read the quadratic column.")

print("\n[13] PER-MODEL SPREAD (state mean yield change, bu/acre)")
print("     -- boosted trees --")
print(PM.pivot_table(index="model", columns=["scenario", "horizon"],
                     values="mean_delta_bu").round(3).to_string())
print("     -- quadratic panel --")
print(PM.pivot_table(index="model", columns=["scenario", "horizon"],
                     values="mean_delta_bu_parametric").round(3).to_string())

foc = PC[PC.county == FOCAL_COUNTY]
print(f"\n[13] {FOCAL_COUNTY}  (trees vs quadratic panel)")
print(foc[["scenario", "horizon", "baseline_yield", "delta_bu", "pct",
           "delta_bu_parametric", "pct_parametric"]]
      .rename(columns={"delta_bu": "trees_bu", "pct": "trees_pct",
                       "delta_bu_parametric": "quad_bu", "pct_parametric": "quad_pct"})
      .round(3).to_string(index=False))

# ---------- comparison with the arbitrary perturbations of script 09 ----------
try:
    old = pd.read_csv(RES / "table8a_scenario_state_summary.csv")
    print("\n[13] For contrast, the arbitrary perturbations of script 09:")
    print(old[["scenario", "delta_T_C", "delta_P_pct", "mean_delta_bu",
               "pct_of_mean_yield"]].to_string(index=False))
except FileNotFoundError:
    pass

# ---------- Figure 19: the climate signal itself ------------------------------
f, ax = fig(10.5, 6)
lab = [f"{s.upper()}\n{h.replace('_',' ')}" for s, h in zip(T11.scenario, T11.horizon)]
xp = np.arange(len(T11))
ax.bar(xp, T11.dTmax_JA_C, color=S2, width=.55)
for i, v in enumerate(T11.dTmax_JA_C):
    ax.text(i, v + .05, f"+{v:.2f} °C", ha="center", fontsize=10, color=INK2)
ax.set_xticks(xp); ax.set_xticklabels(lab, fontsize=9.5)
style(ax, "Figure 19. CMIP6 July-August warming over Illinois",
      f"Ensemble mean of {PM.model.nunique()} models, change in daily maximum temperature "
      f"from the 1985-2014 baseline.", None, "Δ Tmax (°C)",
      src="Source: CMIP6 Amon, AWS Open Data s3://cmip6-pds")
save(f, FIG / "fig19_cmip6_warming.png")

# ---------- Figure 20: yield change across counties ---------------------------
combos = list(T11[["scenario", "horizon"]].itertuples(index=False, name=None))
f, axes = plt.subplots(2, 2, figsize=(11.5, 7.6), dpi=200)
f.patch.set_facecolor(SURFACE)
for ax_, (scen, hz) in zip(axes.ravel(), combos):
    v = PC[(PC.scenario == scen) & (PC.horizon == hz)].delta_bu
    ax_.set_facecolor(SURFACE)
    ax_.hist(v, bins=24, color=S2 if v.mean() < 0 else S1, edgecolor=SURFACE, lw=1.1)
    ax_.axvline(0, color=INK, lw=1.2)
    ax_.axvline(v.mean(), color=FOCAL, lw=2, ls="--")
    ax_.set_title(f"{scen.upper()}  ·  {hz.replace('_',' ')}   mean {v.mean():+.2f} bu/acre",
                  fontsize=11, color=INK, loc="left")
    ax_.grid(color=GRID, lw=.7); ax_.set_axisbelow(True)
    for s in ("top", "right"): ax_.spines[s].set_visible(False)
    ax_.tick_params(colors=MUTED, labelsize=8.5)
    ax_.set_xlabel("Change in predicted yield (bu/acre)", fontsize=9.5, color=INK2)
    ax_.set_ylabel("Counties", fontsize=9.5, color=INK2)
f.suptitle("Figure 20. Projected yield change by county under CMIP6 scenarios",
           fontsize=14.5, color=INK, x=.02, ha="left", y=1.0, fontweight="semibold")
f.text(.02, .962, "Ensemble median across models. Dashed line is the state mean. "
       "Palmer drought indices are held at observed values, so losses are conservative.",
       fontsize=9.6, color=INK2)
f.tight_layout(rect=[0, 0, 1, .952])
f.savefig(FIG / "fig20_cmip6_county_distribution.png", facecolor=SURFACE, bbox_inches="tight")
plt.close(f); print("   figure -> fig20_cmip6_county_distribution.png")

# ---------- Figure 21: the two estimators disagree, and why -------------------
f, axes = plt.subplots(1, 2, figsize=(12.5, 6.6), dpi=200, sharey=True)
f.patch.set_facecolor(SURFACE)
# explicit order: least to most warming, so the bars read as an escalation
ORDER = [("ssp245", "mid_century"), ("ssp245", "late_century"),
         ("ssp585", "mid_century"), ("ssp585", "late_century")]
LABEL = {"ssp245": "SSP2-4.5", "ssp585": "SSP5-8.5"}
cols = [S1, S3, S4, S2]
# one model order for both panels, taken from the estimator that extrapolates
rank = (PM.pivot_table(index="model", columns=["scenario", "horizon"],
                       values="mean_delta_bu_parametric").mean(axis=1)
          .sort_values().index)
w = .8 / len(ORDER)
for ax_, (val, ttl) in zip(axes, [
        ("mean_delta_bu", "Boosted trees — saturate out of range"),
        ("mean_delta_bu_parametric", "Quadratic panel — extrapolates")]):
    piv = PM.pivot_table(index="model", columns=["scenario", "horizon"],
                         values=val).reindex(rank)
    ax_.set_facecolor(SURFACE)
    for j, c in enumerate(ORDER):
        if c not in piv.columns:
            continue
        ax_.barh(np.arange(len(piv)) + j * w, piv[c], height=w,
                 color=cols[j % len(cols)],
                 label=f"{LABEL[c[0]]}  {c[1].replace('_century','')}-century")
    ax_.set_yticks(np.arange(len(piv)) + .4 - w / 2)
    ax_.set_yticklabels(piv.index, fontsize=9.5)
    ax_.axvline(0, color=INK, lw=1.1)
    ax_.grid(axis="x", color=GRID, lw=.7); ax_.set_axisbelow(True)
    for s in ("top", "right"): ax_.spines[s].set_visible(False)
    ax_.tick_params(colors=MUTED, labelsize=9)
    ax_.set_title(ttl, fontsize=11, color=INK, loc="left")
    ax_.set_xlabel("Change in predicted yield (bu/acre)", fontsize=9.5, color=INK2)
    ax_.margins(y=.02)
# legend below the panels, clear of every bar
axes[0].legend(frameon=False, fontsize=9, labelcolor=INK2, ncol=4,
               loc="upper left", bbox_to_anchor=(0, -.12))
f.suptitle("Figure 21. The estimator matters as much as the climate model",
           fontsize=14.5, color=INK, x=.02, ha="left", y=1.0, fontweight="semibold")
f.text(.02, .952, "Same deltas, same counties, two ways of turning climate into yield. "
       "Trees cannot predict past the hottest July-August on record, so they understate "
       "the hot scenarios.", fontsize=9.6, color=INK2)
f.tight_layout(rect=[0, .04, 1, .94])
f.savefig(FIG / "fig21_cmip6_model_spread.png", facecolor=SURFACE, bbox_inches="tight")
plt.close(f); print("   figure -> fig21_cmip6_model_spread.png")

json.dump(dict(
    method="CMIP6 delta change-factor applied to the observed county record",
    baseline="1985-2014", scenarios=sorted(dl.scenario.unique()),
    horizons=sorted(dl.horizon.unique()), models=MODELS, n_models=len(MODELS),
    predictor_model=cfg["best_model"], target=TARGET, seed=SEED,
    estimators=dict(
        trees=f"{cfg['best_model']} from script 08; best in-sample skill, but a tree "
              "predicts a constant beyond its training range, so warming past the "
              "hottest observed July-August produces no further loss",
        parametric="quadratic panel with county fixed effects (script 07, M3); "
                   "extrapolates, at the cost of assuming the fitted curve holds "
                   "outside the observed range"),
    observed_tmax_critical_range_F=[OBS_TMAX_MIN, OBS_TMAX_MAX],
    caveats=[
        "Projection of the statistical yield-climate relationship under a changed "
        "climate, not a forecast. No adaptation, cultivar change or CO2 fertilisation.",
        "EXTRAPOLATION: under SSP5-8.5 late-century a large share of county-years "
        "exceed the hottest July-August in the record. The boosted-tree estimate "
        "saturates there and must not be read as a yield projection; the quadratic "
        "panel column is the one to use, and it carries its own functional-form risk.",
        "Palmer drought indices held at observed values; CMIP6 supplies no PDSI, so "
        "drought-driven losses are understated.",
        "tas used as the proxy for the tmin delta; tasmin was not retrieved.",
        "Monthly means only, so no change in within-month extremes.",
        "One realisation per model; internal variability not sampled.",
        "The yield model was fitted on 1980-2025 and is extrapolated beyond the "
        "temperature range it observed.",
    ]), open(RES / "13_cmip6_config.json", "w"), indent=2)

print("\n[13] CAVEATS")
for c in json.load(open(RES / "13_cmip6_config.json"))["caveats"]:
    print(f"     - {c}")
print("\n[13] wrote table11, table12, table13, fig19, fig20, fig21")
