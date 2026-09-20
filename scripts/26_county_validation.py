"""26 - County-level validation, as far as the data allow. Tables 35-38, Figure 33.

WHAT CANNOT BE DONE, STATED FIRST
  County-level validation of the PHENOLOGY is not possible. NASS publishes Illinois
  soybean progress at state level only (script 23 inspected every row of the bulk
  file), and every finer source that could stand in for it needs an Earthdata login
  or tens of gigabytes. The county dimension of the phenology therefore rests on
  one assumption that nothing here can confirm: that every county's yield window
  sits on the same dates, with only year-to-year anomalies varying by county
  (scripts 25 and _pheno).

WHAT CAN BE DONE
  Counties DO have observed yields, so everything downstream of the phenology can
  be validated at county level, and the exposed assumption can be tested
  indirectly, through yield.

  A. SPATIAL HOLDOUT. Predict each crop-reporting district's yield anomaly from a
     model trained on the OTHER eight districts and only earlier years. This is
     strictly harder than the expanding-window test of script 19, where the
     county being predicted was in the training set in every earlier year, and it
     measures transfer to unseen places, which is what a move to Brazil needs.
     Leaving a district out while keeping the same years elsewhere would leak the
     year's shared weather shock, so the temporal restriction is kept.
  B. SPATIAL STRUCTURE OF THE ERRORS. If the uniform-window assumption were badly
     wrong, model errors should line up north to south.
  C. THE ASSUMPTION ITSELF. Rebuild the windows with the north-south gradient in
     thermal time RETAINED (state-relative anomalies instead of county-relative)
     and ask whether county-level yield prediction improves. It cannot tell us the
     right answer, only whether yield can discriminate between the two.
  D. HETEROGENEITY. Does the heat penalty differ north to south? The scenarios
     apply one pooled coefficient to every county.

LIMITS
  Yield is a noisy, indirect probe of window timing. A null in B or C means yield
  cannot discriminate, not that the assumption is right. Nine districts is a small
  number of spatial units, and districts are not independent of one another.
"""
import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import statsmodels.formula.api as smf
from scipy.stats import linregress
from joblib import Parallel, delayed
from sklearn.ensemble import GradientBoostingRegressor
from _cfg import RAW, PROC, FINAL, RES, FIG, SEED
from _viz import *
import _pheno as P

TARGET = "yield_anom"
YEARS = range(2001, 2025)


def gbm(trn, tst, F):
    m = GradientBoostingRegressor(n_estimators=200, max_depth=3, learning_rate=.05,
                                  random_state=SEED).fit(trn[F], trn[TARGET])
    return m.predict(tst[F])


def rmse(e):
    return float(np.sqrt(np.mean(np.square(e))))


def main():
    cfg08 = json.load(open(RES / "08_ml_config.json"))
    cfg19 = json.load(open(RES / "19_comparison_config.json"))
    CAL, PRC = cfg08["features"], cfg19["process_features"]
    SETS = {"calendar": CAL, "process": PRC, "both": CAL + PRC}

    pan = pd.read_csv(FINAL / "soybean_illinois_climate_1980_2025.csv",
                      dtype={"fips5": str, "ag_district_code": str})
    pan = pan[pan.in_balanced_panel == 1]
    ph = pd.read_csv(PROC / "phenology_features.csv", dtype={"fips5": str})
    d = pan.merge(ph, on=["fips5", "year"], how="inner", validate="one_to_one")
    lat = P.centroid_lat(RAW).set_index("unit_id").lat.to_dict()
    d = d.copy()
    d["lat"] = d.fips5.map(lat)
    d["terc"] = pd.qcut(d.groupby("fips5").lat.transform("first"), 3,
                        labels=["south", "central", "north"]).astype(str)
    d = d.sort_values(["county", "year"]).reset_index(drop=True)
    print(f"[26] {len(d):,} county-years | {d.fips5.nunique()} counties | "
          f"{d.ag_district_code.nunique()} districts | lat {d.lat.min():.2f}-{d.lat.max():.2f}")

    # ================= A. spatial holdout ======================================
    tasks = []
    for t in YEARS:
        for nm in SETS:
            tasks.append(("ns", t, None, nm))
            for g in sorted(d.ag_district_code.unique()):
                tasks.append(("sp", t, g, nm))
    print(f"[26] A. {len(tasks)} model fits (non-spatial and district holdout) ...", flush=True)

    def run(kind, t, g, nm):
        F = SETS[nm]
        if kind == "ns":
            trn, tst = d[d.year < t], d[d.year == t]
        else:
            trn = d[(d.year < t) & (d.ag_district_code != g)]
            tst = d[(d.year == t) & (d.ag_district_code == g)]
        if not len(tst):
            return []
        p = gbm(trn, tst, F)
        return [(kind, nm, i, float(pp)) for i, pp in zip(tst.index, p)]

    out = Parallel(n_jobs=-1, verbose=0)(delayed(run)(*a) for a in tasks)
    R = pd.DataFrame([r for chunk in out for r in chunk],
                     columns=["kind", "set", "idx", "pred"])
    rows = []
    for nm in SETS:
        base = None
        for kind in ("ns", "sp"):
            x = R[(R.kind == kind) & (R.set == nm)].set_index("idx")
            e = (x.pred - d.loc[x.index, TARGET])
            base = rmse(d.loc[x.index, TARGET])          # baseline: anomaly = 0
            rows.append(dict(features=nm, holdout="none (script 19)" if kind == "ns"
                             else "district", n=len(x), rmse=rmse(e),
                             baseline_rmse=base, skill_pct=(1 - rmse(e) / base) * 100))
    TA = pd.DataFrame(rows)
    TA.round(4).to_csv(RES / "table35_spatial_holdout.csv", index=False)
    print("\n[26] A. DISTRICT HOLDOUT vs THE EXPANDING WINDOW OF SCRIPT 19  (2001-2024)")
    print(TA.round(3).to_string(index=False))

    best = TA[TA.holdout == "district"].sort_values("rmse").iloc[0].features
    print(f"\n[26] best feature set under district holdout: {best}")
    ns = R[(R.kind == "ns") & (R.set == best)].set_index("idx")
    sp = R[(R.kind == "sp") & (R.set == best)].set_index("idx")
    dd = d.loc[ns.index, ["ag_district_code", "county", "fips5", "lat", "terc", TARGET]].copy()
    dd["res_ns"] = dd[TARGET] - ns.pred
    dd["res_sp"] = dd[TARGET] - sp.pred.reindex(dd.index)
    by_d = (dd.groupby("ag_district_code")
              .agg(n=("res_ns", "size"), lat=("lat", "mean"),
                   rmse_expanding=("res_ns", lambda e: rmse(e)),
                   rmse_district_holdout=("res_sp", lambda e: rmse(e)),
                   mean_resid_holdout=("res_sp", "mean")).reset_index())
    by_d["transfer_loss_pct"] = (by_d.rmse_district_holdout / by_d.rmse_expanding - 1) * 100
    by_d.round(3).to_csv(RES / "table36_district_errors.csv", index=False)
    print("\n[26] BY DISTRICT (best set)")
    print(by_d.round(2).to_string(index=False))

    # ================= B. structure of the errors ==============================
    cm = dd.groupby("fips5").agg(lat=("lat", "first"), res=("res_ns", "mean"),
                                 res_sp=("res_sp", "mean")).reset_index()
    lr = linregress(cm.lat, cm.res)
    lr2 = linregress(cm.lat, cm.res_sp)
    print(f"\n[26] B. COUNTY-MEAN RESIDUAL AGAINST LATITUDE  ({len(cm)} counties)")
    print(f"     expanding window : slope {lr.slope:+.3f} bu/acre per degree, "
          f"r {lr.rvalue:+.2f}, p {lr.pvalue:.2f}")
    print(f"     district holdout : slope {lr2.slope:+.3f} bu/acre per degree, "
          f"r {lr2.rvalue:+.2f}, p {lr2.pvalue:.2f}")
    print("     mean residual by latitude tercile (expanding window / district holdout):")
    tt = dd.groupby("terc", observed=True).agg(n=("res_ns", "size"), res=("res_ns", "mean"),
                                               res_sp=("res_sp", "mean")).round(3)
    print(tt.to_string())

    # ================= D. heterogeneity of the heat penalty ====================
    # An earlier version tested season_edd * C(terc), where C(terc) is collinear
    # with the county fixed effects, giving a rank-deficient design. It happened to
    # return the right p-value, but it also reported tercile-by-tercile regressions
    # whose heat slopes (-0.091, -0.119, -0.127) looked different, because each
    # tercile fitted its own water and precipitation coefficients. Estimated
    # TOGETHER with shared terms the slopes are nearly identical, so the separate
    # fits overstated heterogeneity. Slopes are now parametrised directly.
    print("\n[26] D. THE HEAT PENALTY BY LATITUDE TERCILE  (one pooled model, county "
          "fixed effects, errors clustered by county)")
    dw = d.copy()
    for tc in ["south", "central", "north"]:
        dw["edd_" + tc] = np.where(dw.terc == tc, dw.season_edd, 0.0)
    SRD = ("yield_anom ~ edd_south + edd_central + edd_north + season_gdd + "
           "wb_min_water_frac + win_prcp_mm + I(win_prcp_mm**2) + C(fips5)")
    md = smf.ols(SRD, data=dw).fit(cov_type="cluster", cov_kwds={"groups": dw.fips5})
    rows_d = []
    for tc in ["south", "central", "north"]:
        s_ = d[d.terc == tc]
        sep = smf.ols("yield_anom ~ season_gdd + season_edd + wb_min_water_frac + win_prcp_mm "
                      "+ I(win_prcp_mm**2) + C(fips5)", data=s_).fit(
            cov_type="cluster", cov_kwds={"groups": s_.fips5})
        rows_d.append(dict(tercile=tc, counties=s_.fips5.nunique(), n=len(s_),
                           mean_edd=s_.season_edd.mean(),
                           edd=md.params["edd_" + tc], se=md.bse["edd_" + tc],
                           edd_separate_fit=sep.params["season_edd"],
                           water_separate_fit=sep.params["wb_min_water_frac"],
                           water_separate_se=sep.bse["wb_min_water_frac"]))
    TD = pd.DataFrame(rows_d)
    wald = md.wald_test("edd_south = edd_central, edd_central = edd_north", scalar=True)
    TD.round(4).to_csv(RES / "table37_heat_penalty_by_latitude.csv", index=False)
    print(TD.round(4).to_string(index=False))
    print(f"     heat slopes equal across terciles (one model): Wald p = {float(wald.pvalue):.3f}")
    print("     the separate-fit columns are shown to expose the overstatement: their heat")
    print("     slopes differ, and their water coefficients differ far more")

    # ================= C. the uniform-window assumption ========================
    print("\n[26] C. UNIFORM WINDOW vs A RETAINED NORTH-SOUTH GRADIENT")
    print("     rebuilding windows with state-relative anomalies ...", flush=True)
    daily = pd.read_csv(RAW / "power_daily.csv.gz", dtype={"unit_id": str}, parse_dates=["date"])
    daily = daily[daily.unit_id.isin(set(d.fips5))].copy()
    daily["lat"] = daily.unit_id.map(lat)
    soil = pd.read_csv(PROC / "soil_features.csv", dtype={"fips5": str})
    taw = (soil.set_index("fips5").soil_aws_0_100cm * 10.0).to_dict()
    obs = P.add_daily_terms(daily, lat)
    bl = P.county_baseline(obs, P.END_DRIVER)
    state_mean = float(np.mean(list(bl.values())))
    bl_state = {u: state_mean for u in bl}
    f2, _ = P.build_features(obs, taw, driver=P.END_DRIVER, baseline=bl_state)
    d2 = pan.merge(f2, on=["fips5", "year"], how="inner", validate="one_to_one")
    d2["lat"] = d2.fips5.map(lat)
    d2["terc"] = d.groupby("fips5").terc.first().reindex(d2.fips5).values
    d2 = d2.sort_values(["county", "year"]).reset_index(drop=True)

    def yr_fit(data, F, t):
        return gbm(data[data.year < t], data[data.year == t], F)

    variants = [("county-relative (uniform window, default)", d, PRC),
                ("county-relative + latitude as a feature (control)", d, PRC + ["lat"]),
                ("state-relative (north-south gradient retained)", d2, PRC)]
    store, rows_c = {}, []
    for nm, dat, F in variants:
        preds = Parallel(n_jobs=-1)(delayed(yr_fit)(dat, F, t) for t in YEARS)
        yy = [dat[dat.year == t][TARGET].values for t in YEARS]
        store[nm] = [(np.asarray(a) - np.asarray(b)) for a, b in zip(yy, preds)]
        e = np.concatenate(store[nm]); y = np.concatenate(yy)
        grad = dat.groupby("terc")[["end_doy", "start_doy"]].mean()
        rows_c.append(dict(windows=nm, rmse=rmse(e), skill_pct=(1 - rmse(e) / rmse(y)) * 100,
                           end_gradient_days=grad.loc["north", "end_doy"] - grad.loc["south", "end_doy"],
                           start_gradient_days=grad.loc["north", "start_doy"] - grad.loc["south", "start_doy"]))
    TC = pd.DataFrame(rows_c)
    TC.round(4).to_csv(RES / "table38_window_gradient_test.csv", index=False)
    print(TC.round(3).to_string(index=False))

    # paired comparison across the 24 test years: is the gain consistent, or one year?
    a_nm, c_nm = variants[0][0], variants[2][0]
    se_a = np.array([np.mean(np.square(x)) for x in store[a_nm]])
    se_c = np.array([np.mean(np.square(x)) for x in store[c_nm]])
    wins = int((se_c < se_a).sum())
    rng = np.random.default_rng(SEED)
    boots = []
    for _ in range(5000):
        ix = rng.integers(0, len(se_a), len(se_a))
        boots.append(np.sqrt(se_c[ix].mean()) / np.sqrt(se_a[ix].mean()) - 1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    rel = np.sqrt(se_c.mean()) / np.sqrt(se_a.mean()) - 1
    pd.DataFrame([dict(comparison="state-relative vs county-relative", test_years=len(se_a),
                       years_state_relative_better=wins, rmse_change_pct=rel * 100,
                       ci_low_pct=lo * 100, ci_high_pct=hi * 100)]) \
      .round(4).to_csv(RES / "table38b_paired_window_test.csv", index=False)
    print(f"\n     PAIRED, year by year: state-relative is better in {wins} of {len(se_a)} test "
          f"years; RMSE {rel * 100:+.2f}% (bootstrap over years, 95% CI "
          f"{lo * 100:+.2f}% to {hi * 100:+.2f}%)")
    lat_only = TC.rmse.iloc[1] / TC.rmse.iloc[0] - 1
    print(f"     control: adding latitude to the uniform-window features changes RMSE by "
          f"{lat_only * 100:+.2f}%, against {rel * 100:+.2f}% for retaining the window gradient. "
          f"Latitude alone does not reproduce the difference, but the difference itself is "
          f"not established (see the interval above)")
    ci_excl = (hi < 0) or (lo > 0)
    print(f"     the interval {'excludes' if ci_excl else 'INCLUDES'} zero, so yield "
          f"{'does' if ci_excl else 'does NOT reliably'} discriminate between the two")

    # ================= figure ==================================================
    f, axes = plt.subplots(1, 3, figsize=(13.5, 4.8), dpi=200)
    f.patch.set_facecolor(SURFACE)
    ax = axes[0]; ax.set_facecolor(SURFACE)
    xx = np.arange(len(by_d)); w = .38
    ax.bar(xx - w / 2, by_d.rmse_expanding, w, color=S1, label="expanding window")
    ax.bar(xx + w / 2, by_d.rmse_district_holdout, w, color=S2, label="district held out")
    ax.set_xticks(xx); ax.set_xticklabels(by_d.ag_district_code, fontsize=8.5)
    ax.set_xlabel("Crop-reporting district (ordered north to south by code)", fontsize=9, color=INK2)
    ax.set_ylabel("RMSE, yield anomaly (bu/acre)", fontsize=9.5, color=INK2)
    ax.legend(frameon=False, fontsize=8.5, labelcolor=INK2)
    ax = axes[1]; ax.set_facecolor(SURFACE)
    ax.scatter(cm.lat, cm.res, s=24, color=S1, alpha=.8, edgecolor=SURFACE, lw=.5)
    xl = np.linspace(cm.lat.min(), cm.lat.max(), 20)
    ax.plot(xl, lr.intercept + lr.slope * xl, color=INK, lw=1.6, ls="--")
    ax.axhline(0, color=MUTED, lw=.8)
    ax.text(.04, .94, f"slope {lr.slope:+.2f}/deg, r = {lr.rvalue:+.2f}, p = {lr.pvalue:.2f}",
            transform=ax.transAxes, fontsize=9.5, color=INK2, va="top")
    ax.set_xlabel("County centroid latitude", fontsize=9.5, color=INK2)
    ax.set_ylabel("Mean residual (bu/acre)", fontsize=9.5, color=INK2)
    ax = axes[2]; ax.set_facecolor(SURFACE)
    ax.errorbar(range(3), TD.edd, yerr=1.96 * TD.se, fmt="o", color=S2, capsize=4, ms=7)
    ax.axhline(0, color=MUTED, lw=.8)
    ax.set_xticks(range(3)); ax.set_xticklabels(TD.tercile, fontsize=9)
    ax.set_ylabel("Yield per extreme degree-day (bu/acre)", fontsize=9.5, color=INK2)
    ax.text(.04, .06, f"slopes equal: Wald p = {float(wald.pvalue):.2f}",
            transform=ax.transAxes, fontsize=9.5, color=INK2)
    for a_ in axes:
        a_.grid(color=GRID, lw=.7); a_.set_axisbelow(True)
        for s_ in ("top", "right"):
            a_.spines[s_].set_visible(False)
        a_.tick_params(colors=MUTED, labelsize=8.5)
    f.suptitle("Figure 33. County-level validation of what counties can validate",
               fontsize=14.5, color=INK, x=.02, ha="left", y=1.10, fontweight="semibold")
    f.text(.02, .945, "Left: predicting a district the model has never seen. Middle: whether errors "
           "line up north to south. Right: whether the heat penalty differs by latitude.\n"
           "Phenology itself cannot be validated at county level: NASS publishes state-level "
           "progress only.", fontsize=9.6, color=INK2, va="bottom")
    f.tight_layout(rect=[0, 0, 1, .90])
    f.savefig(FIG / "fig33_county_validation.png", facecolor=SURFACE, bbox_inches="tight")
    plt.close(f)
    print("\n   figure -> fig33_county_validation.png")

    json.dump(dict(
        cannot_do="county-level phenology validation: NASS publishes state-level progress only",
        holdout="leave-one-district-out, earlier years only, 2001-2024",
        window_test="county-relative vs state-relative anomalies, GBM on process features",
        best_set_under_holdout=best,
        heat_slopes_equal_wald_p=float(wald.pvalue),
        residual_vs_latitude=dict(
            expanding_window=dict(slope=float(lr.slope), r=float(lr.rvalue), p=float(lr.pvalue)),
            district_holdout=dict(slope=float(lr2.slope), r=float(lr2.rvalue), p=float(lr2.pvalue)),
            counties=int(len(cm)), latitude_span_deg=float(cm.lat.max() - cm.lat.min())),
        residual_by_tercile={k: dict(expanding=float(v.res), district_holdout=float(v.res_sp))
                             for k, v in tt.iterrows()},
        limits=["yield is a noisy indirect probe of window timing",
                "nine districts, not independent of one another",
                "a null means yield cannot discriminate, not that the assumption is right"]),
        open(RES / "26_county_validation_config.json", "w"), indent=2)
    print("[26] wrote table35, table36, table37, table38, fig33")


if __name__ == "__main__":
    main()
