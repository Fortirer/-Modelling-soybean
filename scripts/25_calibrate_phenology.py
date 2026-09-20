"""25 - Calibrate the planting anchor and the yield-window end from observation.
Tables 32-33.

Script 24 found three problems with the phenology when checked against the real
NASS series: modelled planting ran 15 days early, thermal-time thresholds for R1
and R3 were slightly off, and thermal time predicted late-season timing worse
than the average date. This script makes the choices that fix them, on evidence,
and records why, so the constants in _pheno.py are reproducible rather than
asserted.

  A. PLANTING. Tune the temperature threshold of the planting rule so the
     modelled state mean meets the observed one, and report what that costs in
     year-to-year skill.

  B. WINDOW END. Predict observed leaf drop (roughly R7) by leave-one-out over 44
     years, from drivers that are defined for EVERY county-year:
        0  climatology            the mean date every year
        D1 thermal R7 anomaly     with unreached years imputed at the last day
        D2 thermal R3 anomaly     the stage validated against NASS   (default)
        D3 GDD planting -> day 250
        D4 GDD 1 May -> 15 Sep    independent of the planting rule    (sensitivity)
     Each is an anomaly from that COUNTY's own mean, so the north-south gradient
     in thermal time is not read as a maturity difference.

  WHY NOT SIMPLY THERMAL R7. The first version used it. Under the corrected,
  later planting, 15% of county-years never accumulate the 1504 GDD it needs,
  chiefly in cool northern counties, and dropping them was not random: it skewed
  the surviving planting mean four days early and would have biased everything
  downstream. Drivers that are always defined avoid the problem.

  The last block checks that the constants in _pheno.py agree with what this
  script recomputes, so drift between the two is caught rather than silent.

LIMITS
  State level only: NASS publishes nothing finer, so every comparison is between
  a state mean of county model output and a state observation. Leave-one-out over
  44 years is a small sample, and every driver's edge over the plain average date
  is modest, about 10%. The four drivers are indistinguishable historically but
  will extrapolate differently under large warming, and the slopes are weather-
  driven interannual estimates at today's level of adaptation. Script 20 reports
  the default and the alternative driver for that reason.
"""
import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _cfg import RAW, FINAL, RES
import _pheno as P

GRID = [12, 14, 15, 16, 17, 18, 19, 20, 21, 22]


def main():
    nass = pd.read_csv(RES / "table28_nass_observed_dates.csv")
    obs = nass[(nass.year >= 1981) & (nass.year <= 2024)].set_index("year")
    thr = pd.read_csv(RES / "table30_observed_thermal_requirement.csv").set_index("stage").median_gdd
    R1_GDD, R3_GDD, END_GDD = float(thr["blooming"]), float(thr["pods"]), float(thr["leaves"])
    print(f"[25] observed thermal requirement from observed planting: "
          f"R1 {R1_GDD:.0f}  R3 {R3_GDD:.0f}  R7 {END_GDD:.0f} GDD")
    print(f"[25] observed mean 50% dates: planted {obs.planted.mean():.1f}  "
          f"pods {obs.pods.mean():.1f}  leaves {obs.leaves.mean():.1f} "
          f"(sd {obs.leaves.std():.1f})")

    pan = pd.read_csv(FINAL / "soybean_illinois_climate_1980_2025.csv", dtype={"fips5": str})
    keep = set(pan[pan.in_balanced_panel == 1].fips5)
    d = pd.read_csv(RAW / "power_daily.csv.gz", dtype={"unit_id": str}, parse_dates=["date"])
    d = d[d.unit_id.isin(keep)].copy()
    d["gdd"] = (P.dd_single_sine(d.tmin_c, d.tmax_c, P.T_BASE)
                - P.dd_single_sine(d.tmin_c, d.tmax_c, P.T_CAP))
    d = d.sort_values(["unit_id", "date"])
    print(f"[25] {d.unit_id.nunique()} counties, {d.year.nunique()} years\n")

    lo, hi = P.GDD_WINDOW_DOY
    rows = []
    for (uid, yr), g in d.groupby(["unit_id", "year"], sort=False):
        if len(g) < 300:
            continue
        g = g.reset_index(drop=True)
        run = g.tmean_c.rolling(7, min_periods=7).mean().values
        doy, gdd = g.doy.values, g.gdd.values
        win = np.where((doy >= P.EARLIEST_DOY) & (doy <= P.LATEST_DOY))[0]
        i_lo, i_hi = int(np.searchsorted(doy, lo)), int(np.searchsorted(doy, hi))
        i250 = int(np.searchsorted(doy, 250))
        for T in GRID:
            hit = win[run[win] >= T]
            pi = int(hit[0]) if len(hit) else int(win[len(win) // 2])
            cum = np.cumsum(gdd[pi:])
            k1, k3, k7 = (int(np.searchsorted(cum, t)) for t in (R1_GDD, R3_GDD, END_GDD))
            rows.append(dict(
                T=T, unit=uid, year=int(yr), plant=float(doy[pi]),
                r1=float(doy[pi + k1]) if k1 < len(cum) else np.nan,
                r3=float(doy[pi + k3]) if k3 < len(cum) else np.nan,
                r7=float(doy[pi + k7]) if k7 < len(cum) else float(doy[-1]),
                r7_reached=k7 < len(cum),
                g250=float(gdd[pi:i250 + 1].sum()) if i250 > pi else np.nan,
                gmay=float(gdd[i_lo:i_hi + 1].sum())))
    R = pd.DataFrame(rows)

    # ---------------- A. planting ---------------------------------------------
    print("=" * 78)
    print("A. PLANTING: tune the threshold so the modelled mean meets the observed mean")
    print("=" * 78)
    print(f"{'T (C)':>6} {'mean plant':>11} {'bias (d)':>9} {'r (yearly)':>11}")
    A = []
    for T, g in R.groupby("T"):
        ys = g.groupby("year").plant.mean()
        r = float(np.corrcoef(ys, obs.planted.reindex(ys.index))[0, 1])
        A.append(dict(threshold_c=T, mean_plant_doy=g.plant.mean(),
                      bias_days=g.plant.mean() - obs.planted.mean(), r_yearly=r))
        print(f"{T:6d} {g.plant.mean():11.1f} {g.plant.mean() - obs.planted.mean():+9.1f} {r:11.2f}")
    TA = pd.DataFrame(A)
    TA.round(3).to_csv(RES / "table32_planting_calibration.csv", index=False)
    best = TA.loc[TA.bias_days.abs().idxmin()]
    print(f"\n[25] threshold closest to zero bias: {best.threshold_c:.0f} C "
          f"(bias {best.bias_days:+.1f} d, r = {best.r_yearly:.2f})")

    # ---------------- B. window end -------------------------------------------
    C = R[R["T"] == P.PLANT_TEMP_C].copy()
    unreached = int((~C.r7_reached).sum())
    print(f"\n[25] at the configured {P.PLANT_TEMP_C:.0f} C: thermal R7 is never reached in "
          f"{unreached:,} of {len(C):,} county-years ({unreached / len(C) * 100:.1f}%), "
          f"which is why it is not used to end the window")
    for c in ["r7", "r3", "g250", "gmay"]:
        C[c + "_a"] = C[c] - C.groupby("unit")[c].transform("mean")
    S = C.groupby("year")[["r7_a", "r3_a", "g250_a", "gmay_a"]].mean().join(obs.leaves)
    y, n = S.leaves.values, len(S)
    print(f"\n{'=' * 78}\nB. WINDOW END: predict observed leaf drop, leave-one-out "
          f"(observed sd {y.std():.1f} d, n = {n})\n{'=' * 78}")
    print(f"{'driver':36} {'slope':>9} {'RMSE (d)':>9} {'skill':>7}")
    rows_b, fits = [], {}
    for nm, col in [("0 climatology", None), ("D1 thermal R7 anomaly (imputed)", "r7_a"),
                    ("D2 thermal R3 anomaly  [default]", "r3_a"),
                    ("D3 GDD planting -> day 250", "g250_a"),
                    ("D4 GDD 1 May -> 15 Sep [alternative]", "gmay_a")]:
        pred = []
        for i in range(n):
            tr = np.arange(n) != i
            if col is None:
                pred.append(y[tr].mean())
            else:
                b, a = np.polyfit(S[col].values[tr], y[tr], 1)
                pred.append(a + b * S[col].values[i])
        pred = np.array(pred)
        rm = float(np.sqrt(((pred - y) ** 2).mean()))
        sl = float(np.polyfit(S[col].values, y, 1)[0]) if col else np.nan
        fits[col] = sl
        rows_b.append(dict(driver=nm, slope=sl, rmse_days=rm, skill_pct=(1 - rm / y.std()) * 100))
        print(f"{nm:36} {sl:+9.4f} {rm:9.2f} {(1 - rm / y.std()) * 100:6.0f}%")
    pd.DataFrame(rows_b).round(4).to_csv(RES / "table33_window_end_drivers.csv", index=False)
    print("\n   Every driver beats the plain average date by about the same modest margin,")
    print("   so the record cannot choose between them. They extrapolate differently.")

    # ---------------- C. the window itself: start, end and LENGTH -------------
    from scipy.stats import linregress
    S2 = S.join(obs[["pods"]]).dropna(subset=["pods", "leaves"]).copy()
    S2["interval"] = S2.leaves - S2.pods
    print(f"\n{'=' * 78}\nC. START, END AND LENGTH OF THE WINDOW, on the {len(S2)} years with both "
          f"observations\n{'=' * 78}")
    print(f"   observed pods-to-leaf-drop interval: mean {S2.interval.mean():.1f} d, "
          f"sd {S2.interval.std():.1f}, min {S2.interval.min():.1f}, max {S2.interval.max():.1f}")
    print(f"\n   {'driver':14} {'series':16} {'slope':>10} {'+/- se':>9} {'r':>6} {'p':>7} "
          f"{'LOO skill':>10}")
    print("   (LOO skill is out-of-sample: 1 - RMSE/sd, refitting with each year left out."
          " The fits themselves\n    are in-sample, so agreement with the observed means "
          "below is NOT independent validation.)")
    rows_c, wf = [], {}
    for drv, lab in [("r3_a", "r3 (days)"), ("gmay_a", "gdd (GDD)")]:
        for yv, nm in [("pods", "start (pods)"), ("leaves", "end (leaf drop)"),
                       ("interval", "WINDOW LENGTH")]:
            r = linregress(S2[drv], S2[yv])
            xv, yy = S2[drv].values, S2[yv].values
            loo = []
            for i in range(len(xv)):
                tr = np.arange(len(xv)) != i
                bb, aa = np.polyfit(xv[tr], yy[tr], 1)
                loo.append(aa + bb * xv[i])
            loo_skill = (1 - float(np.sqrt(((np.array(loo) - yy) ** 2).mean())) / yy.std()) * 100
            rows_c.append(dict(driver=lab, series=nm, slope=r.slope, se=r.stderr,
                               r=r.rvalue, p=r.pvalue, intercept=r.intercept, n=len(S2),
                               loo_skill_pct=loo_skill))
            wf[(drv, yv)] = (r.intercept, r.slope)
            print(f"   {lab:14} {nm:16} {r.slope:+10.4f} {r.stderr:9.4f} {r.rvalue:+6.2f} "
                  f"{r.pvalue:7.3f} {loo_skill:9.0f}%")
    pd.DataFrame(rows_c).round(5).to_csv(RES / "table34_window_length_response.csv", index=False)
    print("\n   Both drivers agree on the sign: warm seasons advance pod setting MORE than")
    print("   maturity, so the window gets slightly LONGER. It does not shorten.")

    # ---------------- consistency with _pheno ---------------------------------
    print(f"\n{'=' * 78}\n   CONSTANTS IN _pheno.py AGAINST WHAT THIS SCRIPT RECOMPUTES\n{'=' * 78}")
    checks = [("WINDOW_FIT r3 start a", P.WINDOW_FIT["r3"]["start"][0], wf[("r3_a", "pods")][0], 0.01),
              ("WINDOW_FIT r3 start b", P.WINDOW_FIT["r3"]["start"][1], wf[("r3_a", "pods")][1], 0.001),
              ("WINDOW_FIT r3 end a", P.WINDOW_FIT["r3"]["end"][0], wf[("r3_a", "leaves")][0], 0.01),
              ("WINDOW_FIT r3 end b", P.WINDOW_FIT["r3"]["end"][1], wf[("r3_a", "leaves")][1], 0.001),
              ("WINDOW_FIT gdd start a", P.WINDOW_FIT["gdd"]["start"][0], wf[("gmay_a", "pods")][0], 0.01),
              ("WINDOW_FIT gdd start b", P.WINDOW_FIT["gdd"]["start"][1], wf[("gmay_a", "pods")][1], 0.0002),
              ("WINDOW_FIT gdd end a", P.WINDOW_FIT["gdd"]["end"][0], wf[("gmay_a", "leaves")][0], 0.01),
              ("WINDOW_FIT gdd end b", P.WINDOW_FIT["gdd"]["end"][1], wf[("gmay_a", "leaves")][1], 0.0002),
              ("STAGES['R1']", P.STAGES["R1"], R1_GDD, 1.0),
              ("STAGES['R3']", P.STAGES["R3"], R3_GDD, 1.0),
              ("STAGES['R7']", P.STAGES["R7"], END_GDD, 1.0)]
    ok = True
    for nm, cfg, calc, tol in checks:
        flag = "ok" if abs(cfg - calc) <= tol else "MISMATCH"
        ok &= flag == "ok"
        print(f"   {nm:22} configured {cfg:10.4f}   recomputed {calc:10.4f}   {flag}")
    print("   all constants consistent" if ok else
          "   WARNING: _pheno.py has drifted from the calibration; update it")

    json.dump(dict(
        planting=dict(threshold_c=float(P.PLANT_TEMP_C),
                      bias_days=float(TA.set_index("threshold_c").bias_days[P.PLANT_TEMP_C]),
                      r_yearly=float(TA.set_index("threshold_c").r_yearly[P.PLANT_TEMP_C]),
                      note="a statistical device; real planting is limited by field "
                           "workability, not by a 19 C running mean"),
        window=dict(rule="both ends are regressions on observed NASS pod-setting and "
                         "leaf-drop dates, moved by a county-relative driver anomaly",
                    default_driver=P.END_DRIVER, fit=P.WINDOW_FIT,
                    end_skill_pct={r["driver"]: r["skill_pct"] for r in rows_b},
                    length_response={f"{r['driver']}": dict(slope=r["slope"], se=r["se"], p=r["p"])
                                     for r in rows_c if r["series"] == "WINDOW LENGTH"},
                    thermal_r7_unreached_pct=unreached / len(C) * 100,
                    note="every driver beats the plain average leaf-drop date by about "
                         "10%, and the record cannot choose between them; they agree "
                         "that warm seasons make the window slightly LONGER"),
        thermal_requirement_gdd=dict(R1=R1_GDD, R3=R3_GDD, R7=END_GDD),
        constants_consistent=bool(ok),
        limits=["state-level observation only", "44 years, leave-one-out",
                "interannual slopes extrapolated far beyond the observed range",
                "county-relative anomalies: every county's mean window ends on the "
                "same date, since NASS has no county maturity data"]),
        open(RES / "25_calibration_config.json", "w"), indent=2)
    print("\n[25] wrote table32, table33, results/25_calibration_config.json")


if __name__ == "__main__":
    main()
