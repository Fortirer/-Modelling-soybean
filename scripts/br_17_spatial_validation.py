"""BR 17 - Municipality-level spatial-holdout validation. Analogue of US
script 26, scoped to what the Brazil branch actually has.

WHAT CANNOT BE DONE, STATED FIRST
  US script 26 part C rebuilds phenology stage windows with a retained
  north-south thermal-time gradient and asks whether yield can discriminate
  a county-relative vs a state-relative window assumption. That requires a
  calibrated phenology model (US scripts 23-25) which does not exist for
  Brazil -- br_10 deliberately reports window CONDITIONS only (Sep-Dec /
  Jan-Feb fixed calendar months), not modeled planting/pod-set/maturity
  dates, because no NASS-equivalent crop-progress series exists to
  calibrate against (see br_10's docstring). Part C is therefore not
  attempted here; there is no window-timing assumption to test.

WHAT CAN BE DONE
  A. SPATIAL HOLDOUT. Predict each mesorregiao's (IBGE's official grouping
     of municipios, the direct analogue of a US ag-district) yield anomaly
     from a model trained on the other mesorregioes and only earlier
     years -- same design as US script 26 part A.
  B. SPATIAL STRUCTURE OF THE ERRORS. Mean residual against centroid
     latitude, both under the expanding-window (script 19-equivalent,
     i.e. br_11) and mesorregiao-holdout predictions.
  D. HETEROGENEITY OF THE HEAT RESPONSE. Does the tmax_critical
     coefficient differ across latitude terciles? One pooled model,
     municipality fixed effects, errors clustered by municipio -- same
     design as US script 26 part D.
"""
import sys, json, gzip, urllib.request
import numpy as np, pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import linregress
from joblib import Parallel, delayed
from sklearn.ensemble import GradientBoostingRegressor
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _brcfg import RAW, PROC, FINAL, RES, FIG, SEED, IBGE_UF
from _viz import *

TARGET = "yield_anom"
YEARS = range(2001, 2025)


def gbm(trn, tst, F):
    m = GradientBoostingRegressor(n_estimators=200, max_depth=3, learning_rate=.05,
                                  random_state=SEED).fit(trn[F], trn[TARGET])
    return m.predict(tst[F])


def rmse(e):
    return float(np.sqrt(np.mean(np.square(e))))


def centroids():
    rows = []
    for line in (RAW / "mt_municipio_boundaries.txt").read_text().splitlines():
        if not line.strip():
            continue
        code, coords = line.split("|", 1)
        pts = np.array([[float(x) for x in p.split(",")] for p in coords.split()])
        if len(pts) > 1 and np.allclose(pts[0], pts[-1]):
            pts = pts[:-1]
        rows.append(dict(unit_id=code.strip(), lon=pts[:, 0].mean(), lat=pts[:, 1].mean()))
    return pd.DataFrame(rows)


def mesorregioes():
    url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{IBGE_UF}/municipios"
    req = urllib.request.Request(url, headers={"User-Agent": "research-script"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    js = json.loads(body.decode("utf-8"))
    rows = []
    for m in js:
        micro = m.get("microrregiao")
        if micro and micro.get("mesorregiao"):
            rows.append(dict(fips5=str(m["id"]), mesorregiao=micro["mesorregiao"]["nome"]))
    return pd.DataFrame(rows)


def main():
    # same CLIM/PROCESS feature lists as br_11 (that script's config file, br16_soil_config.json,
    # only stores the soil feature list -- CLIM/PROCESS are defined inline there, reproduced here)
    CAL = ["pcp_critical", "tmax_critical", "tmp_critical", "hot_days_critical",
           "dry_days_critical", "heat_x_dry", "climate_normal_pcp", "climate_normal_tmax"]
    PRC = ["win_gdd", "win_edd", "win_hot_days", "win_vpd_mean", "win_vpd_max",
           "win_prcp_mm", "win_et0_mm", "win_water_deficit_mm", "season_gdd",
           "season_edd", "season_prcp_mm"]
    SETS = {"climate": CAL, "process": PRC, "both": CAL + PRC}

    pan = pd.read_csv(FINAL / "soja_mt_climate_1981_2024.csv", dtype={"fips5": str})
    pan = pan[pan.in_balanced_panel == 1]
    ph = pd.read_csv(PROC / "phenology_features.csv", dtype={"fips5": str})
    d = pan.merge(ph, on=["fips5", "year"], how="inner", validate="one_to_one")

    ALL_F = CAL + PRC
    na_mask = d[ALL_F].isna().any(axis=1)
    if na_mask.any():
        print(f"[br17] dropping {int(na_mask.sum())} rows with a NaN feature "
              f"({d.loc[na_mask, 'fips5'].nunique()} municipios affected, see br_10/br_11 "
              f"soil/process coverage notes)")
        d = d[~na_mask].copy()

    lat = centroids().set_index("unit_id").lat.to_dict()
    meso = mesorregioes().set_index("fips5").mesorregiao.to_dict()
    d["lat"] = d.fips5.map(lat)
    d["mesorregiao"] = d.fips5.map(meso)
    d = d[d.mesorregiao.notna() & d.lat.notna()].copy()
    d["terc"] = pd.qcut(d.groupby("fips5").lat.transform("first"), 3,
                        labels=["south", "central", "north"]).astype(str)
    d = d.sort_values(["county", "year"]).reset_index(drop=True)
    print(f"[br17] {len(d):,} municipio-years | {d.fips5.nunique()} municipios | "
          f"{d.mesorregiao.nunique()} mesorregioes | lat {d.lat.min():.2f} to {d.lat.max():.2f}")

    # ================= A. spatial holdout ===================================
    tasks = []
    for t in YEARS:
        for nm in SETS:
            tasks.append(("ns", t, None, nm))
            for g in sorted(d.mesorregiao.unique()):
                tasks.append(("sp", t, g, nm))
    print(f"[br17] A. {len(tasks)} model fits (non-spatial and mesorregiao holdout) ...", flush=True)

    def run(kind, t, g, nm):
        F = SETS[nm]
        if kind == "ns":
            trn, tst = d[d.year < t], d[d.year == t]
        else:
            trn = d[(d.year < t) & (d.mesorregiao != g)]
            tst = d[(d.year == t) & (d.mesorregiao == g)]
        if not len(tst):
            return []
        p = gbm(trn, tst, F)
        return [(kind, nm, i, float(pp)) for i, pp in zip(tst.index, p)]

    out = Parallel(n_jobs=-1, verbose=0)(delayed(run)(*a) for a in tasks)
    R = pd.DataFrame([r for chunk in out for r in chunk], columns=["kind", "set", "idx", "pred"])
    rows = []
    for nm in SETS:
        for kind in ("ns", "sp"):
            x = R[(R.kind == kind) & (R.set == nm)].set_index("idx")
            e = (x.pred - d.loc[x.index, TARGET])
            base = rmse(d.loc[x.index, TARGET])
            rows.append(dict(features=nm, holdout="none (br_11)" if kind == "ns" else "mesorregiao",
                             n=len(x), rmse=rmse(e), baseline_rmse=base,
                             skill_pct=(1 - rmse(e) / base) * 100))
    TA = pd.DataFrame(rows)
    TA.round(4).to_csv(RES / "br20_spatial_holdout.csv", index=False)
    print("\n[br17] A. MESORREGIAO HOLDOUT vs EXPANDING WINDOW (2001-2024)")
    print(TA.round(3).to_string(index=False))

    best = TA[TA.holdout == "mesorregiao"].sort_values("rmse").iloc[0].features
    print(f"\n[br17] best feature set under mesorregiao holdout: {best}")
    ns = R[(R.kind == "ns") & (R.set == best)].set_index("idx")
    sp = R[(R.kind == "sp") & (R.set == best)].set_index("idx")
    dd = d.loc[ns.index, ["mesorregiao", "county", "fips5", "lat", "terc", TARGET]].copy()
    dd["res_ns"] = dd[TARGET] - ns.pred
    dd["res_sp"] = dd[TARGET] - sp.pred.reindex(dd.index)
    by_m = (dd.groupby("mesorregiao")
              .agg(n=("res_ns", "size"), lat=("lat", "mean"),
                   rmse_expanding=("res_ns", lambda e: rmse(e)),
                   rmse_mesorregiao_holdout=("res_sp", lambda e: rmse(e)),
                   mean_resid_holdout=("res_sp", "mean")).reset_index())
    by_m["transfer_loss_pct"] = (by_m.rmse_mesorregiao_holdout / by_m.rmse_expanding - 1) * 100
    by_m.round(3).to_csv(RES / "br21_mesorregiao_errors.csv", index=False)
    print("\n[br17] BY MESORREGIAO (best set)")
    print(by_m.round(2).to_string(index=False))

    # ================= B. structure of the errors ============================
    cm = dd.groupby("fips5").agg(lat=("lat", "first"), res=("res_ns", "mean"),
                                 res_sp=("res_sp", "mean")).reset_index()
    lr = linregress(cm.lat, cm.res)
    lr2 = linregress(cm.lat, cm.res_sp)
    print(f"\n[br17] B. MUNICIPIO-MEAN RESIDUAL AGAINST LATITUDE ({len(cm)} municipios)")
    print(f"     expanding window     : slope {lr.slope:+.3f} bu/acre per degree, "
          f"r {lr.rvalue:+.2f}, p {lr.pvalue:.2f}")
    print(f"     mesorregiao holdout  : slope {lr2.slope:+.3f} bu/acre per degree, "
          f"r {lr2.rvalue:+.2f}, p {lr2.pvalue:.2f}")

    # ================= D. heterogeneity of the heat response =================
    print("\n[br17] D. THE HEAT RESPONSE (tmax_critical) BY LATITUDE TERCILE  (one pooled "
          "model, municipio fixed effects, errors clustered by municipio)")
    dw = d.copy()
    for tc in ["south", "central", "north"]:
        dw["tmx_" + tc] = np.where(dw.terc == tc, dw.tmax_critical, 0.0)
    SRD = ("yield_anom ~ tmx_south + tmx_central + tmx_north + pcp_critical + "
           "I(pcp_critical**2) + C(fips5)")
    md = smf.ols(SRD, data=dw).fit(cov_type="cluster", cov_kwds={"groups": dw.fips5})
    rows_d = []
    for tc in ["south", "central", "north"]:
        s_ = d[d.terc == tc]
        sep = smf.ols("yield_anom ~ tmax_critical + pcp_critical + I(pcp_critical**2) + C(fips5)",
                      data=s_).fit(cov_type="cluster", cov_kwds={"groups": s_.fips5})
        rows_d.append(dict(tercile=tc, municipios=s_.fips5.nunique(), n=len(s_),
                           mean_tmax=s_.tmax_critical.mean(),
                           tmx=md.params["tmx_" + tc], se=md.bse["tmx_" + tc],
                           tmx_separate_fit=sep.params["tmax_critical"]))
    TD = pd.DataFrame(rows_d)
    wald = md.wald_test("tmx_south = tmx_central, tmx_central = tmx_north", scalar=True)
    TD.round(4).to_csv(RES / "br22_heat_response_by_latitude.csv", index=False)
    print(TD.round(4).to_string(index=False))
    print(f"     heat slopes equal across terciles (one model): Wald p = {float(wald.pvalue):.3f}")

    # ================= figure ==================================================
    f, axes = plt.subplots(1, 3, figsize=(13.5, 4.8), dpi=200)
    f.patch.set_facecolor(SURFACE)
    ax = axes[0]; ax.set_facecolor(SURFACE)
    order = by_m.sort_values("lat", ascending=False)
    xx = np.arange(len(order)); w = .38
    ax.bar(xx - w / 2, order.rmse_expanding, w, color=S1, label="expanding window")
    ax.bar(xx + w / 2, order.rmse_mesorregiao_holdout, w, color=S2, label="mesorregiao held out")
    ax.set_xticks(xx); ax.set_xticklabels(order.mesorregiao, fontsize=7.5, rotation=35, ha="right")
    ax.set_ylabel("RMSE, yield anomaly (bu/acre)", fontsize=9.5, color=INK2)
    ax.legend(frameon=False, fontsize=8.5, labelcolor=INK2)
    ax = axes[1]; ax.set_facecolor(SURFACE)
    ax.scatter(cm.lat, cm.res, s=24, color=S1, alpha=.8, edgecolor=SURFACE, lw=.5)
    xl = np.linspace(cm.lat.min(), cm.lat.max(), 20)
    ax.plot(xl, lr.intercept + lr.slope * xl, color=INK, lw=1.6, ls="--")
    ax.axhline(0, color=MUTED, lw=.8)
    ax.text(.04, .94, f"slope {lr.slope:+.2f}/deg, r = {lr.rvalue:+.2f}, p = {lr.pvalue:.2f}",
            transform=ax.transAxes, fontsize=9.5, color=INK2, va="top")
    ax.set_xlabel("Municipio centroid latitude", fontsize=9.5, color=INK2)
    ax.set_ylabel("Mean residual (bu/acre)", fontsize=9.5, color=INK2)
    ax = axes[2]; ax.set_facecolor(SURFACE)
    ax.errorbar(range(3), TD.tmx, yerr=1.96 * TD.se, fmt="o", color=S2, capsize=4, ms=7)
    ax.axhline(0, color=MUTED, lw=.8)
    ax.set_xticks(range(3)); ax.set_xticklabels(TD.tercile, fontsize=9)
    ax.set_ylabel("Yield per degC of Jan-Feb tmax (bu/acre)", fontsize=9.5, color=INK2)
    ax.text(.04, .06, f"slopes equal: Wald p = {float(wald.pvalue):.2f}",
            transform=ax.transAxes, fontsize=9.5, color=INK2)
    for a_ in axes:
        a_.grid(color=GRID, lw=.7); a_.set_axisbelow(True)
        for s_ in ("top", "right"):
            a_.spines[s_].set_visible(False)
        a_.tick_params(colors=MUTED, labelsize=8.5)
    f.suptitle("Figure BR-21. Municipio-level spatial-holdout validation", fontsize=14.5,
               color=INK, x=.02, ha="left", y=1.10, fontweight="semibold")
    f.text(.02, .945, "Left: predicting a mesorregiao the model has never seen. Middle: whether "
           "errors line up north to south. Right: whether the Jan-Feb heat response differs by "
           "latitude.\nNo phenology-window assumption to test here (br_10 uses fixed calendar "
           "windows, not modeled stage dates -- see docstring).", fontsize=9.6, color=INK2, va="bottom")
    f.tight_layout(rect=[0, 0, 1, .90])
    f.savefig(FIG / "fig_br21_spatial_validation.png", facecolor=SURFACE, bbox_inches="tight")
    plt.close(f)
    print("\n   figure -> fig_br21_spatial_validation.png")

    json.dump(dict(
        cannot_do="phenology-window discrimination test (US script 26 part C): no calibrated "
                 "phenology model exists for Brazil, see br_10's docstring",
        holdout="leave-one-mesorregiao-out, earlier years only, 2001-2024",
        best_set_under_holdout=best,
        heat_slopes_equal_wald_p=float(wald.pvalue),
        residual_vs_latitude=dict(
            expanding_window=dict(slope=float(lr.slope), r=float(lr.rvalue), p=float(lr.pvalue)),
            mesorregiao_holdout=dict(slope=float(lr2.slope), r=float(lr2.rvalue), p=float(lr2.pvalue)),
            municipios=int(len(cm)), latitude_span_deg=float(cm.lat.max() - cm.lat.min())),
        limits=["yield is a noisy indirect probe of spatial transfer",
                f"{d.mesorregiao.nunique()} mesorregioes, not independent of one another"]),
        open(RES / "br23_spatial_validation_config.json", "w"), indent=2)
    print("[br17] wrote br20, br21, br22, br23, fig_br21")


if __name__ == "__main__":
    main()
