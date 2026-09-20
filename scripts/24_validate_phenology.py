"""24 - Validate the phenology against observed NASS crop progress.
Tables 28-30, Figure 32.

Script 18's thermal-time thresholds were described as calibrated to NASS norms
but were written from memory, so the stage dates agreed with those numbers by
construction. This script replaces that with observation: the actual weekly
Illinois progress series from script 23.

FOUR QUESTIONS, in order, because each one can change the next

  1. What were the remembered dates, against the real ones?
  2. What thermal time does the crop ACTUALLY need between observed planting and
     each observed stage, and how stable is it across years? Stable means
     thermal time is a sound model of timing; unstable means the model has
     structural error that no threshold can fix.
  3. Does the modelled phenology track observed timing year by year? The
     correlation of year-to-year anomalies is the real test, since bias can be
     corrected by recalibrating and correlation cannot.
  4. Do farmers' condition ratings agree with the model's stress variables?

ORDER OF RUNNING, AND WHAT IS IN-SAMPLE
  This script was first run BEFORE the recalibration of script 25, and found the
  problems that motivated it. It is now run against the recalibrated phenology.
  Read the output accordingly: the empirical window start and end (start_doy,
  end_doy) are regressions on the very observations compared against here, and the
  planting threshold and R1/R3/R7 thresholds were fitted to the observed means, so
  agreement on MEAN dates is by construction. What is not by construction is the
  year-to-year correlation, the trend comparison, and the leave-one-out skill
  reported by script 25.

WHAT THESE COMPARISONS CANNOT DO
  NASS publishes progress at the STATE level only, as the date by which half the
  acreage reached a stage. The model works per county. State-mean model dates
  are compared with state-level observed dates, which are close but not the same
  statistic. Stage definitions also differ: NASS "blooming" is roughly R1-R2,
  "setting pods" roughly R3-R4, "dropping leaves" roughly R7. Model R5 and R6
  have no NASS counterpart, so they are compared against the nearest stage and
  the mapping is stated wherever it is used.
"""
import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _cfg import RAW, PROC, FINAL, RES, FIG
from _viz import *
import _pheno as P

STAGE = {"PCT PLANTED": "planted", "PCT BLOOMING": "blooming",
         "PCT SETTING PODS": "pods", "PCT DROPPING LEAVES": "leaves",
         "PCT HARVESTED": "harvested"}
# what I wrote into script 18's header from memory, as day of year
REMEMBERED = {"planted": ("20 May", 140), "blooming": ("10 July", 191),
              "pods": ("28 July", 209), "leaves": ("~20 Sept, called maturity", 263)}
MODEL_FOR = {"planted": ["plant_doy"], "blooming": ["r1_doy"],
             "pods": ["r3_doy", "start_doy"],
             "leaves": ["end_doy", "r6_doy", "r8_doy"]}
STAGE_THRESH = {"blooming": P.STAGES["R1"], "pods": P.STAGES["R3"],
                "leaves": P.STAGES["R7"]}          # current model thresholds, GDD


def date50(g):
    """Day of year at which the series crosses 50%, by linear interpolation."""
    g = g.dropna(subset=["VALUE_NUM"]).sort_values("doy")
    v, t = g.VALUE_NUM.values, g.doy.values
    for i in range(1, len(v)):
        if v[i - 1] < 50 <= v[i]:
            return float(t[i - 1] + (50 - v[i - 1]) / (v[i] - v[i - 1]) * (t[i] - t[i - 1]))
    return np.nan


def main():
    nass = pd.read_csv(RAW / "nass_il_soybean_progress.csv", low_memory=False)
    nass["date"] = pd.to_datetime(nass.WEEK_ENDING, errors="coerce")
    nass["doy"] = nass.date.dt.dayofyear
    st = nass[(nass.AGG_LEVEL_DESC == "STATE") & (nass.STATISTICCAT_DESC == "PROGRESS")].copy()
    st["stage"] = st.SHORT_DESC.str.replace("SOYBEANS - PROGRESS, MEASURED IN ", "").map(STAGE)
    st = st.dropna(subset=["stage"])

    rows = []
    for (yr, stg), g in st.groupby(["YEAR", "stage"]):
        rows.append(dict(year=int(yr), stage=stg, doy50=date50(g)))
    obs = pd.DataFrame(rows).pivot(index="year", columns="stage", values="doy50").reset_index()
    obs.round(2).to_csv(RES / "table28_nass_observed_dates.csv", index=False)
    yrs = obs[(obs.year >= 1981) & (obs.year <= 2024)]
    print(f"[24] observed 50%-dates built: {len(obs)} years, "
          f"analysis window 1981-2024 ({len(yrs)} years)")

    # ================= 1. remembered vs real ===================================
    print("\n[24] 1. THE DATES I WROTE FROM MEMORY, AGAINST THE REAL ONES  (mean day of year)")
    r1 = []
    for stg, (label, doy) in REMEMBERED.items():
        real = yrs[stg].mean()
        r1.append(dict(stage=stg, remembered=label, remembered_doy=doy,
                       observed_mean_doy=round(real, 1), error_days=round(doy - real, 1),
                       observed_sd_days=round(yrs[stg].std(), 1), n_years=int(yrs[stg].notna().sum())))
    print(pd.DataFrame(r1).to_string(index=False))

    # ================= 2. observed thermal requirement ==========================
    daily = pd.read_csv(RAW / "power_daily.csv.gz", dtype={"unit_id": str}, parse_dates=["date"])
    daily["gdd"] = (P.dd_single_sine(daily.tmin_c, daily.tmax_c, P.T_BASE)
                    - P.dd_single_sine(daily.tmin_c, daily.tmax_c, P.T_CAP))
    sm = daily.groupby("date").gdd.mean().reset_index()
    sm["year"], sm["doy"] = sm.date.dt.year, sm.date.dt.dayofyear
    cum = {y: g.set_index("doy").gdd.cumsum() for y, g in sm.groupby("year")}

    def gdd_between(y, d0, d1):
        c = cum.get(y)
        if c is None or not np.isfinite(d0) or not np.isfinite(d1):
            return np.nan
        d0i, d1i = int(round(d0)), int(round(d1))
        if d0i not in c.index or d1i not in c.index:
            return np.nan
        return float(c.loc[d1i] - c.loc[d0i])

    req = []
    for _, r in yrs.iterrows():
        for stg in ["blooming", "pods", "leaves"]:
            req.append(dict(year=int(r.year), stage=stg,
                            gdd=gdd_between(int(r.year), r.planted, r[stg])))
    R = pd.DataFrame(req).dropna()
    print("\n[24] 2. THERMAL TIME FROM OBSERVED PLANTING TO EACH OBSERVED STAGE  (GDD 10-30 C)")
    t30 = []
    for stg, g in R.groupby("stage"):
        med = g.gdd.median()
        t30.append(dict(stage=stg, median_gdd=round(med, 0), p25=round(g.gdd.quantile(.25), 0),
                        p75=round(g.gdd.quantile(.75), 0), sd=round(g.gdd.std(), 0),
                        cv_pct=round(g.gdd.std() / g.gdd.mean() * 100, 1),
                        my_threshold=STAGE_THRESH[stg],
                        threshold_error=round(STAGE_THRESH[stg] - med, 0), n_years=len(g)))
    T30 = pd.DataFrame(t30)
    print(T30.to_string(index=False))
    T30.to_csv(RES / "table30_observed_thermal_requirement.csv", index=False)
    print("     A low CV means thermal time is a good model of timing. A high CV means")
    print("     there is structural error that no choice of threshold can remove.")

    # ================= 3. year-by-year tracking =================================
    ph = pd.read_csv(PROC / "phenology_features.csv", dtype={"fips5": str})
    mod = ph.groupby("year")[["plant_doy", "r1_doy", "r3_doy", "start_doy", "end_doy",
                              "r6_doy", "r8_doy"]].mean().reset_index()
    m = yrs.merge(mod, on="year")
    print("\n[24] 3. DOES THE MODEL TRACK OBSERVED TIMING YEAR BY YEAR?  (1981-2024)")
    from scipy.stats import linregress
    rows3 = []
    for stg, cols in MODEL_FOR.items():
        for c in cols:
            k = m[[stg, c]].dropna()
            yy = m.loc[k.index, "year"]
            ra = np.corrcoef(k[stg] - k[stg].mean(), k[c] - k[c].mean())[0, 1]
            lo, lm = linregress(yy, k[stg]), linregress(yy, k[c])
            gap = (lm.slope - lo.slope) / np.hypot(lo.stderr, lm.stderr)
            rows3.append(dict(observed=stg, model=c, n=len(k),
                              bias_days=round((k[c] - k[stg]).mean(), 1),
                              rmse_days=round(float(np.sqrt(((k[c] - k[stg]) ** 2).mean())), 1),
                              anomaly_corr=round(ra, 2),
                              obs_trend=round(lo.slope * 10, 2),
                              obs_trend_se=round(lo.stderr * 10, 2),
                              model_trend=round(lm.slope * 10, 2),
                              trend_gap_in_se=round(gap, 1)))
    T29 = pd.DataFrame(rows3)
    print(T29.to_string(index=False))
    print("     trends in days per decade; trend_gap_in_se is (model - observed) over "
          "the combined standard error")
    T29.to_csv(RES / "table29_phenology_validation.csv", index=False)

    # ---- 3b. separate the planting rule from the thermal thresholds ----------
    # The model plants by a temperature rule. If the timing errors above come from
    # that rule rather than from thermal time, feeding the model the OBSERVED
    # planting date should remove most of the bias. Predict each stage as the day
    # the state-mean GDD since observed planting first reaches the observed median.
    def date_at_gdd(y, d0, target):
        c = cum.get(y)
        if c is None or not np.isfinite(d0):
            return np.nan
        d0i = int(round(d0))
        if d0i not in c.index:
            return np.nan
        hit = c.index[c.values >= c.loc[d0i] + target]
        return float(hit[0]) if len(hit) else np.nan

    med = T30.set_index("stage").median_gdd.to_dict()
    print("\n[24] 3b. TIMING PREDICTED FROM OBSERVED PLANTING PLUS THE OBSERVED MEDIAN GDD")
    rows3b = []
    for stg in ["blooming", "pods", "leaves"]:
        pred = np.array([date_at_gdd(int(r.year), r.planted, med[stg]) for _, r in yrs.iterrows()])
        ob = yrs[stg].values
        ok = np.isfinite(pred) & np.isfinite(ob)
        e = pred[ok] - ob[ok]
        rows3b.append(dict(stage=stg, n=int(ok.sum()), bias_days=round(e.mean(), 1),
                           rmse_days=round(float(np.sqrt((e ** 2).mean())), 1),
                           observed_sd_days=round(float(ob[ok].std()), 1),
                           corr=round(float(np.corrcoef(pred[ok], ob[ok])[0, 1]), 2),
                           skill_pct=round(float((1 - np.sqrt((e ** 2).mean()) / ob[ok].std()) * 100), 0)))
    T3b = pd.DataFrame(rows3b)
    print(T3b.to_string(index=False))
    print("     skill_pct is 1 - RMSE/sd: how much better than predicting the mean date")
    T3b.to_csv(RES / "table29b_thermal_time_given_planting.csv", index=False)

    # ================= 4. condition ratings =====================================
    cond = nass[(nass.AGG_LEVEL_DESC == "STATE") & (nass.STATISTICCAT_DESC == "CONDITION")].copy()
    cond["level"] = cond.SHORT_DESC.str.replace("SOYBEANS - CONDITION, MEASURED IN PCT ", "")
    aug = cond[(cond.date.dt.month == 8) & cond.level.isin(["GOOD", "EXCELLENT"])]
    ge = aug.groupby(["YEAR", "date"]).VALUE_NUM.sum().groupby("YEAR").mean().rename("ge_aug").reset_index()
    pan = pd.read_csv(FINAL / "soybean_illinois_climate_1980_2025.csv", dtype={"fips5": str})
    pan = pan[pan.in_balanced_panel == 1]
    ya = pan.groupby("year").yield_anom.mean().rename("yield_anom").reset_index()
    fe = ph.groupby("year")[["season_edd", "wb_min_water_frac", "win_prcp_mm"]].mean().reset_index()
    c4 = ge.rename(columns={"YEAR": "year"}).merge(ya, on="year").merge(fe, on="year")
    print(f"\n[24] 4. FARMERS' AUGUST CONDITION RATING (% good+excellent) vs THE MODEL  "
          f"(n = {len(c4)} years, {c4.year.min()}-{c4.year.max()})")
    for col, lab in [("yield_anom", "state yield anomaly"), ("season_edd", "season EDD"),
                     ("wb_min_water_frac", "min soil water fraction"), ("win_prcp_mm", "R3-R6 precipitation")]:
        print(f"     corr(condition, {lab:24}) = {np.corrcoef(c4.ge_aug, c4[col])[0,1]:+.3f}")
    c4.round(3).to_csv(RES / "table31_condition_vs_model.csv", index=False)

    # ================= figure ===================================================
    f, axes = plt.subplots(1, 3, figsize=(13.5, 4.8), dpi=200)
    f.patch.set_facecolor(SURFACE)
    ax = axes[0]; ax.set_facecolor(SURFACE)
    ax.plot(m.year, m.pods, color=INK, lw=1.5, marker="o", ms=3, label="observed, setting pods")
    ax.plot(m.year, m.r3_doy, color=S2, lw=1.5, marker="o", ms=3, label="model, R3")
    ax.set_ylabel("Day of year", fontsize=9.5, color=INK2)
    ax.legend(frameon=False, fontsize=8.5, labelcolor=INK2)
    ax = axes[1]; ax.set_facecolor(SURFACE)
    # explicit order: groupby sorts alphabetically (blooming, leaves, pods), which
    # silently swapped two of the three x-axis labels in the first version
    for i, stg in enumerate(["blooming", "pods", "leaves"]):
        g = R[R.stage == stg]
        ax.scatter(np.full(len(g), i) + np.random.RandomState(1).uniform(-.12, .12, len(g)),
                   g.gdd, s=16, color=S1, alpha=.6, edgecolor=SURFACE, lw=.4)
        ax.hlines(STAGE_THRESH[stg], i - .3, i + .3, color=S2, lw=2.4)
    ax.set_xticks(range(3)); ax.set_xticklabels(["blooming", "setting pods", "dropping leaves"], fontsize=9)
    ax.set_ylabel("GDD from observed planting", fontsize=9.5, color=INK2)
    ax.text(.03, .95, "orange bar = threshold in script 18", transform=ax.transAxes,
            fontsize=8.5, color=S2, va="top")
    ax = axes[2]; ax.set_facecolor(SURFACE)
    ax.scatter(c4.ge_aug, c4.yield_anom, s=26, color=S3, alpha=.8, edgecolor=SURFACE, lw=.5)
    b = np.polyfit(c4.ge_aug, c4.yield_anom, 1)
    xx = np.linspace(c4.ge_aug.min(), c4.ge_aug.max(), 20)
    ax.plot(xx, np.polyval(b, xx), color=INK, lw=1.6, ls="--")
    ax.text(.04, .94, f"r = {np.corrcoef(c4.ge_aug, c4.yield_anom)[0,1]:+.2f}",
            transform=ax.transAxes, fontsize=10, color=INK2, va="top")
    ax.set_xlabel("August good+excellent (%)", fontsize=9.5, color=INK2)
    ax.set_ylabel("State yield anomaly (bu/acre)", fontsize=9.5, color=INK2)
    for a_ in axes:
        a_.grid(color=GRID, lw=.7); a_.set_axisbelow(True)
        for s_ in ("top", "right"):
            a_.spines[s_].set_visible(False)
        a_.tick_params(colors=MUTED, labelsize=8.5)
    f.suptitle("Figure 32. The phenology against what NASS observed",
               fontsize=14.5, color=INK, x=.02, ha="left", y=1.06, fontweight="semibold")
    f.text(.02, .975, "Left: timing, year by year. Middle: the thermal time the crop really "
           "needed, against the thresholds in use. Right: farmers' own assessment.",
           fontsize=9.6, color=INK2)
    f.tight_layout(rect=[0, 0, 1, .91])
    f.savefig(FIG / "fig32_phenology_validation.png", facecolor=SURFACE, bbox_inches="tight")
    plt.close(f)
    print("\n   figure -> fig32_phenology_validation.png")

    json.dump(dict(
        source="script 23, NASS Quick Stats weekly Illinois soybean progress and condition",
        level="state only; NASS publishes no district or county series in the bulk file",
        window="1981-2024, limited by the POWER weather record",
        remembered_dates_replaced=True,
        caveats=["state-level observed dates against state-mean model dates",
                 "NASS blooming ~R1-R2, setting pods ~R3-R4, dropping leaves ~R7; "
                 "model R5 and R6 have no counterpart",
                 "leap years shift day-of-year by one, ignored"]),
        open(RES / "24_validation_config.json", "w"), indent=2)
    print("[24] wrote table28, table29, table30, table31, fig32")


if __name__ == "__main__":
    main()
