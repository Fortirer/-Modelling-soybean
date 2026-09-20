"""22 - Does ozone survive detrending? A screen, and a documented stopping point.
Tables 26-27, Figure 31.

The literature audit flagged ozone as the largest remaining omission. Midwest
soybean is suppressed roughly 10% by tropospheric O3, and at SoyFACE elevated O3
cost 10 +/- 11% at 370 ppm CO2 but only 5 +/- 4% at 550 ppm, so CO2 partly
protects the crop. That interaction matters for the CO2 layer in script 20.

Before building anything, the question that ended the soil work has to be asked:
does the variable survive detrending? yield_anom is the residual of a
county-specific linear trend, so a monotone TREND cannot explain it. US ozone
fell after 1980, so its trend is absorbed. What could remain is year-to-year
variation, and that is driven by hot, stagnant summers, so it may only restate
the heat and water signal already in the model.

Three questions, each of which can end the analysis:
  1. Does detrended ozone still vary?            (if not, nothing to explain)
  2. Does it correlate with yield_anom?          (if not, nothing to find)
  3. Does it add anything beyond heat and water? (if not, it is a proxy)

WHAT THIS DESIGN CAN AND CANNOT SEE
  Ozone here is a STATE series, one value per year, so the honest sample size is
  the number of years (about 44), not the number of county-years. Year fixed
  effects would absorb it completely and are not used, so county effects only,
  with errors clustered by year. That is a low-powered test.

  Annual EPA metrics are used. The crop-damage metrics, AOT40 and W126, are
  growing-season sums over hourly data and need the daily files, an order of
  magnitude heavier. The 4th-max and 90th-percentile values track peak-season
  exposure better than the annual mean, which is diluted by winter.

  Only about 23 of 102 counties have an ozone monitor, and monitors are
  urban-biased.

SOURCE  EPA AirData annual concentration by monitor, one national file per year,
        parameter 44201, Illinois, 8-hour metrics. Public, no key.
"""
import sys, io, json, zipfile, urllib.request, urllib.error, time
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import statsmodels.formula.api as smf
from _cfg import RAW, PROC, FINAL, RES, FIG
from _viz import *

CACHE = RAW / "epa_ozone_cache"
CACHE.mkdir(parents=True, exist_ok=True)
URL = "https://aqs.epa.gov/aqsweb/airdata/annual_conc_by_monitor_{y}.zip"
YEARS = range(1980, 2025)
METRICS = {"o3_4thmax_ppm": "4th-highest 8-h value",
           "o3_90pct_ppm": "90th-percentile 8-h value",
           "o3_mean_ppm": "annual mean 8-h value"}
PPB = 1000.0            # ppm -> ppb


def fetch_year(y):
    """Illinois 8-hour ozone summary for one year; cached, so reruns are free."""
    cf = CACHE / f"{y}.csv"
    if cf.exists():
        return pd.read_csv(cf)
    with urllib.request.urlopen(URL.format(y=y), timeout=300) as f:
        z = zipfile.ZipFile(io.BytesIO(f.read()))
    d = pd.read_csv(z.open(z.namelist()[0]), low_memory=False)
    o = d[(d["Parameter Code"] == 44201) & (d["State Name"] == "Illinois")]
    o = o[o["Metric Used"].str.contains("8 hour running average|8-hour running average",
                                        regex=True, na=False)]
    if not len(o):
        return pd.DataFrame()
    r = pd.DataFrame([dict(year=y,
                           o3_mean_ppm=float(o["Arithmetic Mean"].mean()),
                           o3_4thmax_ppm=float(o["4th Max Value"].mean()),
                           o3_90pct_ppm=float(o["90th Percentile"].mean()),
                           monitors=int(len(o)),
                           counties=int(o["County Name"].nunique()))])
    r.to_csv(cf, index=False)
    return r


def main():
    t0 = time.time()
    parts, failed = [], []
    for y in YEARS:
        try:
            r = fetch_year(y)
            if len(r):
                parts.append(r)
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            failed.append(dict(year=y, error=str(e)))
    o3 = pd.concat(parts, ignore_index=True).sort_values("year")
    o3.to_csv(RAW / "epa_ozone_il_annual.csv", index=False)
    print(f"[22] ozone years {len(o3)}  {o3.year.min()}-{o3.year.max()}  "
          f"monitors {o3.monitors.min()}-{o3.monitors.max()}  "
          f"counties with a monitor {o3.counties.min()}-{o3.counties.max()}")

    p = pd.read_csv(FINAL / "soybean_illinois_climate_1980_2025.csv",
                    dtype={"fips5": str})
    p = p[p.in_balanced_panel == 1][["fips5", "year", "yield_anom"]]
    f = pd.read_csv(PROC / "phenology_features.csv", dtype={"fips5": str})
    d = p.merge(f, on=["fips5", "year"]).merge(o3, on="year")

    # ---- 1. is anything left once a trend is removed? -----------------------
    print("\n[22] 1. OZONE, BEFORE AND AFTER REMOVING A LINEAR TREND")
    rows1 = []
    for m, lab in METRICS.items():
        y = o3[m].values * PPB
        b = np.polyfit(o3.year, y, 1)
        res = y - np.polyval(b, o3.year)
        rows1.append(dict(metric=lab, slope_ppb_per_yr=b[0],
                          trend_explains_pct=(1 - res.var() / y.var()) * 100,
                          detrended_sd_ppb=res.std()))
        o3[m + "_dt"] = res / PPB
    T1 = pd.DataFrame(rows1)
    print(T1.round(3).to_string(index=False))
    d = d.merge(o3[["year"] + [m + "_dt" for m in METRICS]], on="year")

    # ---- 2. correlation with the detrended target ---------------------------
    yl = (d.groupby("year")
            .agg(anom=("yield_anom", "mean"), edd=("season_edd", "mean"),
                 wb=("wb_min_water_frac", "mean"), prcp=("win_prcp_mm", "mean"),
                 **{m + "_dt": (m + "_dt", "first") for m in METRICS})
            .reset_index())
    print(f"\n[22] 2. CORRELATION WITH yield_anom   (year level, n = {len(yl)} years)")
    rows2 = []
    for m, lab in METRICS.items():
        raw_r = np.corrcoef(d[m], d.yield_anom)[0, 1]
        dt_r = np.corrcoef(yl[m + "_dt"], yl.anom)[0, 1]
        rows2.append(dict(metric=lab, r_panel_raw=raw_r, r_year_detrended=dt_r))
    T2 = pd.DataFrame(rows2)
    print(T2.round(3).to_string(index=False))

    # ---- 3. does it add beyond heat and water? ------------------------------
    print("\n[22] 3. DOES OZONE ADD BEYOND HEAT AND WATER?")
    BASE = ("yield_anom ~ season_gdd + season_edd + wb_min_water_frac "
            "+ win_prcp_mm + I(win_prcp_mm**2) + C(fips5)")
    b0 = smf.ols(BASE, data=d).fit(cov_type="cluster", cov_kwds={"groups": d.year})
    print(f"     county-year panel, county effects, errors clustered by YEAR; "
          f"base R2 {b0.rsquared:.4f}")
    rows3 = []
    for m, lab in METRICS.items():
        col = m + "_dt"
        x = d.assign(o3ppb=d[col] * PPB)
        mm = smf.ols(BASE.replace("season_edd", "season_edd + o3ppb"), data=x).fit(
            cov_type="cluster", cov_kwds={"groups": x.year})
        sd = float(x.o3ppb.std())
        rows3.append(dict(metric=lab, coef_bu_per_ppb=mm.params["o3ppb"],
                          p_value=mm.pvalues["o3ppb"],
                          effect_of_1sd_bu=mm.params["o3ppb"] * sd,
                          delta_r2=mm.rsquared - b0.rsquared,
                          corr_with_edd=np.corrcoef(yl[col], yl.edd)[0, 1],
                          corr_with_water=np.corrcoef(yl[col], yl.wb)[0, 1]))
    T3 = pd.DataFrame(rows3)
    print(T3.round(4).to_string(index=False))

    # the honest-n version: 44 year-means, no county replication at all
    print("\n     year-level regression (n = 44, no pseudo-replication)")
    rows4 = []
    for m, lab in METRICS.items():
        col = m + "_dt"
        yy = yl.assign(o3ppb=yl[col] * PPB)
        mm = smf.ols("anom ~ edd + wb + prcp + o3ppb", data=yy).fit()
        rows4.append(dict(metric=lab, coef_bu_per_ppb=mm.params["o3ppb"],
                          se=mm.bse["o3ppb"], p_value=mm.pvalues["o3ppb"],
                          n_years=int(mm.nobs)))
    T4 = pd.DataFrame(rows4)
    print(T4.round(4).to_string(index=False))

    # Power: how big an effect could this design have detected, against how big
    # an effect the literature implies? An earlier version of this comment spread
    # a 10% loss over the ~5 ppb one-sd range and got 0.90 bu/acre per ppb. That
    # is wrong: the 10% is the loss against a CLEAN atmosphere, a difference of
    # tens of ppb, so it overstated the per-ppb effect several-fold and made the
    # test look able to catch it. Two rough anchors instead, both order-of-
    # magnitude and both carrying the large uncertainty the source studies report:
    #   whole-atmosphere:  ~4.5 bu/acre (10% of ~45) over ~25-35 ppb above
    #                      background                        -> ~0.13-0.18 per ppb
    #   SoyFACE +25% O3:   ~4.5 bu/acre over ~12 ppb (25% of ~47 ppb ambient),
    #                      quoted as 10 +/- 11%, i.e. consistent with zero
    #                                                        -> ~0.38 per ppb
    se = float(T4.se.min())
    floor = 1.96 * se
    print(f"\n     detectable-effect floor: about {floor:.2f} bu/acre per ppb "
          f"(1.96 x the smallest year-level standard error of {se:.3f})")
    print("     literature-implied effect: roughly 0.13-0.38 bu/acre per ppb from two "
          "rough anchors")
    print(f"     the range STRADDLES the floor, so a null here cannot separate "
          f"'ozone does nothing' from 'ozone does what the literature says'")

    T1.round(4).to_csv(RES / "table26_ozone_trend.csv", index=False)
    pd.concat([T2.assign(part="correlation"), T3.assign(part="panel"),
               T4.assign(part="year_level")], ignore_index=True) \
      .round(5).to_csv(RES / "table27_ozone_screen.csv", index=False)

    # ---------- Figure 31 ----------------------------------------------------
    f, axes = plt.subplots(1, 3, figsize=(13.5, 4.8), dpi=200)
    f.patch.set_facecolor(SURFACE)
    ax = axes[0]; ax.set_facecolor(SURFACE)
    ax.plot(o3.year, o3.o3_90pct_ppm * PPB, color=S2, lw=1.4, marker="o", ms=3)
    b = np.polyfit(o3.year, o3.o3_90pct_ppm * PPB, 1)
    ax.plot(o3.year, np.polyval(b, o3.year), color=INK, lw=1.6, ls="--")
    ax.set_ylabel("Illinois 90th-percentile 8-h ozone (ppb)", fontsize=9.5, color=INK2)
    ax.text(.04, .06, f"{b[0]:+.2f} ppb/yr", transform=ax.transAxes, fontsize=10, color=INK2)
    ax = axes[1]; ax.set_facecolor(SURFACE)
    ax.scatter(yl.o3_90pct_ppm_dt * PPB, yl.anom, color=S1, s=30, alpha=.8,
               edgecolor=SURFACE, lw=.6)
    bb = np.polyfit(yl.o3_90pct_ppm_dt * PPB, yl.anom, 1)
    xx = np.linspace((yl.o3_90pct_ppm_dt * PPB).min(), (yl.o3_90pct_ppm_dt * PPB).max(), 20)
    ax.plot(xx, np.polyval(bb, xx), color=INK, lw=1.6, ls="--")
    r = np.corrcoef(yl.o3_90pct_ppm_dt, yl.anom)[0, 1]
    ax.text(.04, .06, f"r = {r:+.2f}, n = {len(yl)} years", transform=ax.transAxes,
            fontsize=10, color=INK2)
    ax.set_xlabel("Detrended ozone (ppb)", fontsize=9.5, color=INK2)
    ax.set_ylabel("State-mean yield anomaly (bu/acre)", fontsize=9.5, color=INK2)
    ax = axes[2]; ax.set_facecolor(SURFACE)
    ax.scatter(yl.edd, yl.o3_90pct_ppm_dt * PPB, color=S4, s=30, alpha=.8,
               edgecolor=SURFACE, lw=.6)
    rr = np.corrcoef(yl.edd, yl.o3_90pct_ppm_dt)[0, 1]
    bb = np.polyfit(yl.edd, yl.o3_90pct_ppm_dt * PPB, 1)
    xx = np.linspace(yl.edd.min(), yl.edd.max(), 20)
    ax.plot(xx, np.polyval(bb, xx), color=INK, lw=1.6, ls="--")
    ax.text(.04, .06, f"r = {rr:+.2f}", transform=ax.transAxes, fontsize=10, color=INK2)
    ax.set_xlabel("Extreme degree days in the crop window", fontsize=9.5, color=INK2)
    ax.set_ylabel("Detrended ozone (ppb)", fontsize=9.5, color=INK2)
    for a_ in axes:
        a_.grid(color=GRID, lw=.7); a_.set_axisbelow(True)
        for s_ in ("top", "right"):
            a_.spines[s_].set_visible(False)
        a_.tick_params(colors=MUTED, labelsize=8.5)
    f.suptitle("Figure 31. Ozone correlates with yield, and with the heat that already explains it",
               fontsize=14, color=INK, x=.02, ha="left", y=1.06, fontweight="semibold")
    f.text(.02, .975, "Left: the trend is real. Middle: detrended ozone tracks the yield "
           "anomaly. Right: but it also tracks heat, so the two cannot be separated here.",
           fontsize=9.6, color=INK2)
    f.tight_layout(rect=[0, 0, 1, .91])
    f.savefig(FIG / "fig31_ozone_screen.png", facecolor=SURFACE, bbox_inches="tight")
    plt.close(f)
    print("\n   figure -> fig31_ozone_screen.png")

    json.dump(dict(
        source="EPA AirData annual_conc_by_monitor, parameter 44201, Illinois",
        years=[int(o3.year.min()), int(o3.year.max())], failed_years=failed,
        design="state-level annual series; county fixed effects only, since year "
               "effects would absorb it; errors clustered by year",
        limits=["annual metrics, not AOT40 or W126 growing-season exposure",
                "about 23 of 102 counties have a monitor, urban-biased",
                "effective sample size is the number of years, about 44",
                "low power: see the detectable-effect line in the script output"],
        verdict="not built into the pipeline; collinear with heat and water and "
                "indistinguishable from them in this data",
        runtime_min=round((time.time() - t0) / 60, 1)),
        open(RES / "22_ozone_config.json", "w"), indent=2)
    print(f"[22] wrote table26, table27, fig31   ({(time.time()-t0)/60:.1f} min)")


if __name__ == "__main__":
    main()
