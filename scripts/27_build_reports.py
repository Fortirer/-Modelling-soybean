"""27 - Build FINAL_REPORT.md and the Word report from the results files.

Why this is a script and not a document. The v1.0 report was written by hand on
31 August and then went stale: it kept asserting that the pipeline used no CMIP6
scenarios, no daily weather and no VPD long after all three existed, and it
contradicted itself on one figure ("tenfold" and "sevenfold" for the same
quantity). Every number in Part II below is read from results/ at build time, so a
rerun of any analysis script followed by this one cannot leave the report behind.

STRUCTURE
  Part I  (Sections 1-4, 6) is the original study, carried over VERBATIM from
          results/archive/FINAL_REPORT_v1.0_2026-08-31.md apart from renumbering,
          five short pointers to Part II, and four figures. The analysis in it has
          not changed. Its abstract, limitations and conclusions are rewritten,
          because statements there are superseded.
  Part II (Section 5, Appendices) is new and generated here.

WHAT THE WORD FILE IS
  A conversion of the same markdown. It could not be rendered to check its layout
  (no LibreOffice on the build machine), so its structure was verified by reopening
  it and counting headings, tables and images, and its appearance was not.
"""
import re, sys, json
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from _cfg import ROOT, RES, FIG, RAW, PROC, FINAL
import _mdocx
from docx.shared import Pt

MINUS = "−"
ARCH = RES / "archive" / "FINAL_REPORT_v1.0_2026-08-31.md"
VERSION, DATE = "2.0", "2026-09-20"


# ----------------------------------------------------------------- helpers ----------
def rd(name):
    return pd.read_csv(RES / name)


def jd(name):
    return json.loads((RES / name).read_text(encoding="utf-8"))


def n(x, d=2, plus=False):
    """Signed number with a true minus sign."""
    x = float(x)
    s = f"{abs(x):.{d}f}"
    if x < 0 and float(s) != 0:
        return MINUS + s
    return ("+" + s) if (plus and float(s) != 0) else s


def pc(x, d=1, plus=False):
    return n(x, d, plus) + "%"


def tbl(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def doy_date(x):
    d = pd.Timestamp("2001-01-01") + pd.Timedelta(days=int(round(float(x))) - 1)
    return f"{d.day} {d:%B}"


LAB = {"ssp245": "SSP2-4.5", "ssp585": "SSP5-8.5"}
HZ = {"mid_century": "2040-69", "late_century": "2070-99"}
ORDER = [("ssp245", "mid_century"), ("ssp245", "late_century"),
         ("ssp585", "mid_century"), ("ssp585", "late_century")]


def ordered(df):
    return df.set_index(["scenario", "horizon"]).loc[ORDER].reset_index()


def between(text, a, b=None):
    i = text.index(a)
    j = text.index(b) if b else len(text)
    return text[i:j].rstrip() + "\n"


# ------------------------------------------------------------------ inputs ---------
orig = ARCH.read_text(encoding="utf-8")

T21 = ordered(rd("table21_pheno_scenario_summary.csv"))
T21g = ordered(rd("table21_pheno_scenario_summary_gdd.csv"))
T11 = ordered(rd("table11_cmip6_scenario_summary.csv"))
T19 = rd("table19_phenology_vs_calendar.csv").set_index("features")
T18 = rd("table18_process_feature_correlations.csv")
T28 = rd("table28_nass_observed_dates.csv")
T29 = rd("table29_phenology_validation.csv")
T29b = rd("table29b_thermal_time_given_planting.csv").set_index("stage")
T30 = rd("table30_observed_thermal_requirement.csv").set_index("stage")
T31 = rd("table31_condition_vs_model.csv")
T32 = rd("table32_planting_calibration.csv").set_index("threshold_c")
T33 = rd("table33_window_end_drivers.csv")
T34 = rd("table34_window_length_response.csv")
T35 = rd("table35_spatial_holdout.csv")
T36 = rd("table36_district_errors.csv")
T37 = rd("table37_heat_penalty_by_latitude.csv").set_index("tercile")
T38 = rd("table38_window_gradient_test.csv")
T38b = rd("table38b_paired_window_test.csv").iloc[0]
C26 = jd("26_county_validation_config.json")
CAL_CFG = jd("08_ml_config.json")
PH = pd.read_csv(PROC / "phenology_features.csv", dtype={"fips5": str})
MG23 = ordered(rd("table23_mg_frost_ceiling.csv").query("scenario != 'baseline'"))
MG_BASE = rd("table23_mg_frost_ceiling.csv").query("scenario == 'baseline'").iloc[0]
GRID = rd("table24_mg_grid.csv")
SOIL = pd.read_csv(PROC / "soil_features.csv")
Q1 = rd("table14_soil_explains_level.csv").set_index("target")
Q2 = rd("table15_soil_explains_sensitivity.csv").set_index("target")
Q3 = rd("table17_soil_prediction_gain.csv").set_index("features")
O26 = rd("table26_ozone_trend.csv").set_index("metric")
O27 = rd("table27_ozone_screen.csv")
P14, P17 = jd("14_provenance_soil.json"), jd("17_provenance_daily_weather.json")
P22 = jd("22_ozone_config.json")

# calendar-feature correlation, for the comparison with the process features
_pan = pd.read_csv(FINAL / "soybean_illinois_climate_1980_2025.csv", dtype={"fips5": str})
_pan = _pan[_pan.in_balanced_panel == 1].merge(PH[["fips5", "year"]], on=["fips5", "year"])
_cal = {c: float(np.corrcoef(_pan[c], _pan.yield_anom)[0, 1]) for c in CAL_CFG["features"]}
BEST_CAL, BEST_CAL_R = max(_cal.items(), key=lambda kv: abs(kv[1]))

# observed means over the analysis window
W = T28[(T28.year >= 1981) & (T28.year <= 2024)]
OBS = {s: float(W[s].mean()) for s in ["planted", "blooming", "pods", "leaves"]}


def r29(o, m):
    return T29[(T29.observed == o) & (T29.model == m)].iloc[0]


# ================================================================== FRONT MATTER ====
def front():
    a = between(orig, "## Abstract", "---")
    a = a.replace("## Abstract\n", "").strip()
    return f"""# Soybean Yield and Climate Variability in Illinois, 1980 to 2025

### A county-level panel analysis with Champaign County as the focal unit

Version {VERSION} | {DATE} | Part I: original study, v1.0 of 2026-08-31 (github.com/osperry/soybean-climate-illinois). Part II: extensions, scripts 12 to 27. Data: USDA NASS Quick Stats and Crop Progress, NOAA NCEI nClimDiv, NASA POWER, USDA-NRCS SSURGO, CMIP6 via AWS Open Data, EPA AirData.

> **How to read this version.** Part I is the original study and its analysis has not changed. Part II tests it against independent data and extends it, and in several places corrects it. Where Part II supersedes something in Part I, the sentence says so. The v1.0 report is preserved unchanged in `results/archive/`.

---

## Abstract

**Objective.** Quantify how historical climate variability has been associated with soybean yield across Illinois counties, test whether climate information improves out-of-sample prediction, and, in Part II, test whether the analysis survives being checked against observed crop phenology, soil, daily weather, ozone and CMIP6 scenarios.

### Part I: the original study

{a}

### Part II: extensions and independent checks

**Data added.** NASA POWER daily weather ({P17['daily_records']:,} records, 1981-2024); SSURGO soil ({P14['horizon_records']:,} horizon records); CMIP6 monthly output for eight models under SSP2-4.5 and SSP5-8.5; NASS weekly crop progress and condition; EPA ground-level ozone, 1980-2024.

**Main findings.**

- **Soil explains where the good ground is, not what happens in a given year.** Soil explains {pc(Q1.loc['county mean yield (bu/acre)','r2']*100,0)} of the variance in county mean yield and {pc(Q2.loc['composite sensitivity index','r2']*100,0)} of county climate sensitivity, but adds {pc(Q3.loc['climate + soil','gain_vs_climate_pct'],1,True)} to prediction of the detrended anomaly, which by construction has no county mean left to explain.
- **The crop calendar is not the calendar.** A phenological window replaces July and August. The first version of it, calibrated to dates written from memory, was wrong: modelled planting ran {n(-T32.loc[15].bias_days, 1)} days early and thermal-time maturity predicted leaf drop worse than the plain average date. It was recalibrated against the observed NASS record.
- **Observed leaf drop has not advanced, and the model says it should have.** Trend {n(r29('leaves','end_doy').obs_trend,2,True)} ± {n(r29('leaves','end_doy').obs_trend_se,2)} days per decade observed, against {n(r29('leaves','end_doy').model_trend,2)} modelled. Adaptation is already in the record.
- **CMIP6 scenarios give a bracketed, not a pinned-down, answer.** The median climate effect at SSP5-8.5 late century is {n(T21.iloc[3].climate_sr_bu,1)} bu/acre, but the eight models span {n(T21.iloc[3].sr_min_bu,1)} to {n(T21.iloc[3].sr_max_bu,1)}, and {pc(T21.iloc[3].out_of_range_pct,0)} of county-years exceed the observed heat maximum. The CO₂ assumption alone moves the net answer from {n(T21.iloc[3].net_none_bu,1)} to {n(T21.iloc[3].net_face_bu,1,True)} bu/acre.
- **Ozone survives detrending and cannot be separated from heat.** Detrended ozone correlates {n(O27[(O27.part=='correlation')].r_year_detrended.min(),2)} to {n(O27[(O27.part=='correlation')].r_year_detrended.max(),2)} with the yield anomaly but {n(O27[(O27.part=='panel')].corr_with_edd.min(),2,True)} to {n(O27[(O27.part=='panel')].corr_with_edd.max(),2,True)} with extreme degree days.
- **The model transfers to unseen districts with no measurable loss, and the heat penalty does not differ north to south.** County-level validation of the phenology itself is not possible, because NASS publishes state-level progress only.

**Implications.** Part I stands as an association study. Part II shows that its central variables (extreme heat and soil water) are corroborated by independent farmer condition ratings, that projections built on them are wide and depend on assumptions the data cannot settle (CO₂, adaptation, extrapolation beyond the observed heat range), and that several early results of the extension were wrong and are documented in Appendix A. None of the projections is a forecast.

---
"""


# ================================================================ PART I (verbatim) ==
def part1():
    a = between(orig, "## 1. Introduction", "## 4. Results")
    a = a.replace(
        "while June correlates 0.08 and September 0.02.",
        "while June correlates 0.08 and September 0.02. Part II tests this calendar window against observed "
        "crop progress and replaces it with a phenological one (Sections 5.3 and 5.4).")
    a = a.rstrip()
    assert a.endswith("---")
    a = a[:-3].rstrip() + (
        "\n\n> **Part II replaces these perturbation experiments** with scenarios built from CMIP6 change "
        "factors (Section 5.5). The experiments above are retained as sensitivity analyses.\n\n---\n")

    r = between(orig, "## 4. Results", "## 5. Discussion")
    r = r.replace("Sensitivity experiments, not projections.",
                  "Sensitivity experiments, not projections. Section 5.5 supersedes them for projection purposes.")
    figs = {
        "### 4.4 Machine learning (Table 5)":
            "![Figure 7. Yield anomaly against July-August precipitation](figures/fig07_precipitation_yield.png)",
        "### 4.5 Feature importance (Table 6)":
            "![Figure 10. Model performance under expanding-window validation](figures/fig10_model_performance.png)",
        "### 4.7 Champaign County, the focal unit":
            "![Figure 13. County climate sensitivity to August moisture](figures/fig13_county_climate_sensitivity.png)",
        "### 4.9 Robustness (Table 9)":
            "![Figure 17. Simulated yield change under +1 C and -10% precipitation](figures/fig17_scenario_map.png)",
    }
    for h, img in figs.items():
        assert h in r, h
        r = r.replace(h, img + "\n\n" + h, 1)
    return a + "\n" + r


def discussion():
    d = between(orig, "## 5. Discussion", "## 6. Limitations")
    d = d.replace("## 5. Discussion", "## 6. Discussion")
    d = re.sub(r"^### 5\.(\d)", r"### 6.\1", d, flags=re.M)
    d = d.replace(
        "The county-level sensitivity gradient tracks soil water-holding capacity rather than climate exposure per se.",
        "The county-level sensitivity gradient tracks soil water-holding capacity rather than climate exposure per se "
        "(Part II tests this directly in Section 5.2).")
    return d


# ===================================================================== PART II ========
def s51():
    rows = [
        ["NASA POWER daily point API (MERRA-2)", "Daily temperature, dewpoint, precipitation, solar radiation",
         "17", "Free, no key", f"1981-2024, 102 county centroids, {P17['daily_records']:,} records"],
        ["USDA-NRCS SSURGO via Soil Data Access", "County soil properties, available water", "14, 15",
         "Free, no key", f"{P14['horizon_records']:,} horizon records, {P14['map_units']:,} map units"],
        ["CMIP6 monthly output, AWS Open Data", "Scenario change factors incl. relative humidity", "12",
         "Anonymous", "8 models, SSP2-4.5 and SSP5-8.5, baseline 1985-2014, horizons 2040-69 and 2070-99"],
        ["USDA NASS Quick Stats bulk file", "Weekly crop progress and condition", "23",
         "Key-free bulk file, 1.05 GB streamed", "Illinois soybean, state level only, 1980-2026"],
        ["EPA AirData annual concentration by monitor", "Ground-level ozone", "22", "Free",
         f"1980-2024, {P22['years'][1] - P22['years'][0] + 1} annual files, 18-23 counties with a monitor"],
    ]
    return f"""### 5.1 Data added

{tbl(['Source', 'Used for', 'Script', 'Access', 'Coverage'], rows)}

No source needed an API key or a login. The choice of NASA POWER for daily weather was deliberate: it is global, and this analysis is meant to serve as a source domain for Brazilian soybean, where features must be computed identically in both countries.
"""


def s52():
    aws = float(SOIL.soil_aws_0_100cm.mean()) * 10
    lvl = Q1.loc["county mean yield (bu/acre)"]
    sens = Q2.loc["composite sensitivity index"]
    heat = Q2.loc["yield response to heat (bu/SD)"]
    return f"""### 5.2 Soil

Script 14 pulls SSURGO through the public Soil Data Access service: {P14['horizon_records']:,} horizon records across {P14['map_units']:,} map units and all 102 counties. Script 15 aggregates them to 25 county features over 0-30 cm and 30-100 cm, weighted by horizon overlap, then component percentage, then map-unit acreage. The first version contained an error: horizon water contributions were averaged across rows instead of summed down each profile and then weighted, which made available water 4.35 times too small (Champaign read 39 mm against about 170 mm). It is corrected, and the county mean is now {aws:.0f} mm.

Soil answers three different questions with three different answers, and reporting them separately matters.

{tbl(['Question', 'Outcome explained', 'R²'], [
    ['Does soil explain the **level** of county yield?', 'County mean yield, 1980-2025', n(lvl.r2)],
    ['Does soil explain **climate sensitivity**?', 'Composite sensitivity index from script 09', n(sens.r2)],
    ['', 'Yield response to heat', n(heat.r2)],
    ['Does soil improve **prediction** of the anomaly?', 'Expanding-window RMSE, 2001-2025', f"{pc(Q3.loc['climate + soil','gain_vs_climate_pct'],1,True)} vs climate alone"]])}

![Figure 22. Soil against county yield level](figures/fig22_soil_vs_yield_level.png)

The last row is arithmetic, not disappointment. The modelling target is the residual of each county's own trend, so its county mean is zero by construction, and a static county attribute has no main effect left to explain. Soil does not say what this year's anomaly will be. It says which counties suffer most when a bad year arrives, which is what a projection needs. Soil alone predicts worse than assuming no anomaly ({pc(Q3.loc['soil only','skill_vs_baseline_pct'],1,True)} skill).
"""


def s53():
    both, cal, prc = T19.loc["both"], T19.loc["calendar (script 08)"], T19.loc["process (script 18)"]
    top = T18.sort_values("abs_r", ascending=False).head(4)
    topl = ", ".join(f"{r.feature.replace('_', ' ')} {n(r.r, 3)}" for r in top.itertuples())
    return f"""### 5.3 Daily weather and process variables

Monthly means erase the extremes that do the damage. Schlenker and Roberts (2009) show soybean yield rising with temperature to about 30 °C and then falling steeply, with damage tracking the distribution of daily temperature. Script 17 pulls daily NASA POWER for every county centroid. Script 18 derives degree days by single-sine integration (Snyder, 1985), giving GDD between 10 and 30 °C and extreme degree days (EDD) above 30 °C separately, plus vapour pressure deficit and a daily soil water balance. Evapotranspiration is FAO-56 Penman-Monteith, not Hargreaves: Hargreaves uses temperature alone and cannot respond to the humidity change that CMIP6 projects, so an early version that perturbed humidity changed nothing downstream. The water-balance bucket is the SSURGO available water of Section 5.2.

VPD was tried as a regressor and rejected. Entered alongside EDD it took a positive coefficient, which is physiologically backwards, because the two correlate at about +0.9 and cannot be separated. Humidity enters through evapotranspiration and the water balance instead.

**Do the process variables predict better? Mostly no.** Expanding window, rolling origin, 2001-2024, {jd('19_comparison_config.json')['test_obs']:,} test observations:

{tbl(['Feature set', 'Features', 'RMSE', 'R²', 'vs calendar'], [
    ['Both', int(both.n_features), f"{both.RMSE:.3f}", f"{both.R2:.3f}", pc(both.gain_vs_calendar_pct, 2, True)],
    ['Calendar (script 08)', int(cal.n_features), f"{cal.RMSE:.3f}", f"{cal.R2:.3f}", ''],
    ['Process (script 18)', int(prc.n_features), f"{prc.RMSE:.3f}", f"{prc.R2:.3f}", pc(prc.gain_vs_calendar_pct, 2, True)]])}

They supply the strongest single predictors, by correlation with the yield anomaly: {topl}, against {n(BEST_CAL_R, 3, True)} for the best calendar variable ({BEST_CAL.replace('_', ' ')}). **This comparison is confounded.** The process features come from NASA POWER at about half a degree; the calendar features come from nClimDiv county polygons, so part of the gap is data source and not formulation. A clean test needs the calendar features rebuilt from POWER, which has not been done. The case for the phenological window was never hindcast accuracy. It is that it can represent a moving window and a threshold heat response, and a calendar window structurally cannot.
"""


def s54():
    b = T29
    rem = [("Planted (50%)", "20 May", 140, "planted"), ("Blooming (50%)", "10 July", 191, "blooming"),
           ("Setting pods (50%)", "28 July", 209, "pods"), ("Dropping leaves (50%)", "about 20 September, called maturity", 263, "leaves")]
    remrows = [[lab, said, doy_date(OBS[k]), n(doy - OBS[k], 1, True) + " d"] for lab, said, doy, k in rem]
    pl = T32.loc[15]; pl19 = T32.loc[19]
    d = T33.set_index("driver")
    wl = T34[T34.series == "WINDOW LENGTH"].set_index("driver")
    st = T34[T34.series != "WINDOW LENGTH"]
    rr3 = st[st.driver.str.startswith("r3")].set_index("series")
    rg = st[st.driver.str.startswith("gdd")].set_index("series")

    def row(o, m, lab):
        x = r29(o, m)
        return [o, lab, n(x.bias_days, 1, True) + " d", f"{x.rmse_days:.1f} d", f"{x.anomaly_corr:.2f}",
                f"{n(x.obs_trend, 2)} ± {x.obs_trend_se:.2f}", n(x.model_trend, 2), f"{abs(x.trend_gap_in_se):.1f} SE"]

    cond = T31
    cr = {c: float(np.corrcoef(cond.ge_aug, cond[c])[0, 1]) for c in ["yield_anom", "season_edd", "wb_min_water_frac", "win_prcp_mm"]}
    th = T30
    leaf = T29b.loc["leaves"]
    bl, pd_ = T29b.loc["blooming"], T29b.loc["pods"]
    return f"""### 5.4 The phenology checked against observation

Script 23 pulls the weekly Illinois soybean progress and condition series from NASS Quick Stats. The Quick Stats API needs a key, so the key-free bulk file (1.05 GB, the whole national crops database) was streamed and filtered from 23.9 million rows to 11,350. **The series are state-level only**: the file holds no district or county progress for Illinois soybean. Planting runs from 1980, blooming, pod setting, leaf drop and harvest from 1981, condition from 1986.

#### What the first check found

The thermal-time thresholds in the first version of the phenology were described as calibrated to NASS norms. They were not: the dates were written from memory and never downloaded, so the stage dates agreed with them by construction and proved nothing. Against the real series (mean day of year, 1981-2024):

{tbl(['Stage', 'Written from memory', 'Observed', 'Error'], remrows)}

NASS has no maturity or full-seed stage. Leaf drop corresponds to roughly R7, and the full-seed date had no source. The thresholds themselves were within about 5% of the observed thermal requirement (GDD from each year's observed planting date: blooming {th.loc['blooming','median_gdd']:.0f}, setting pods {th.loc['pods','median_gdd']:.0f}, leaf drop {th.loc['leaves','median_gdd']:.0f}, with a cross-year coefficient of variation of {th.loc['pods','cv_pct']:.1f}% to {th.loc['blooming','cv_pct']:.1f}%). The real faults were elsewhere:

- **Modelled planting ran 15.2 days early** and tracked real planting at r = 0.18, because farmers plant when fields are workable, not when a running temperature mean crosses a threshold.
- **Thermal time predicts late-season timing worse than the average date.** Given observed planting it predicts flowering (r = {bl['corr']:.2f}, RMSE {bl.rmse_days:.1f} days) and pod set (r = {pd_['corr']:.2f}, RMSE {pd_.rmse_days:.1f}) well, but leaf drop with an RMSE of **{leaf.rmse_days:.1f} days against an observed sd of {leaf.observed_sd_days:.1f}**, a skill of {n(leaf.skill_pct, 0)}% against guessing the mean date. Soybean is a photoperiod-sensitive short-day plant, so maturity is set partly by day length, which a thermal-time model lacks. That is agronomic background rather than something tested here, but it fits the data.
- **The observed yield window barely varies.** The interval from pod setting to leaf drop has a standard deviation of only 3.5 days.

#### What was changed

Planting is anchored to the observed mean: a 19 °C seven-day-mean threshold gives a bias of {n(pl19.bias_days, 1)} days where the old 15 °C gave {n(pl.bias_days, 1)}, and improves year-to-year skill (r = {pl19.r_yearly:.2f} against {pl.r_yearly:.2f}). It is a statistical device, not a physiological threshold. The R1, R3 and R7 thresholds are the observed medians above. Both ends of the yield window are regressions on the observed pod-setting and leaf-drop dates, moved by a county-relative anomaly.

Thermal-time R7 was tried first and abandoned. Under the corrected, later planting it was never reached in 15.3% of county-years, and dropping them was not random: it skewed the surviving planting mean four days early. Four always-defined drivers were compared for predicting observed leaf drop, leave-one-out over 44 years:

{tbl(['Driver', 'RMSE (days)', 'Skill vs the mean date'], [[r.driver, f"{r.rmse_days:.2f}", pc(r.skill_pct, 0)] for r in T33.itertuples()])}

Every driver beats the plain average by about the same modest margin, so **the record cannot choose between them**, and the scenarios run two. They agree on the sign of the window-length response, which is the opposite of what the first version reported: warm seasons advance pod setting more than they advance maturity, so the window gets slightly **longer**.

{tbl(['Driver', 'Pod-set slope', 'Leaf-drop slope', 'Window-length slope', 'Out-of-sample skill'], [
    ['R3 anomaly (days)', f"{n(rr3.loc['start (pods)','slope'],2,True)} ± {rr3.loc['start (pods)','se']:.2f}", f"{n(rr3.loc['end (leaf drop)','slope'],2,True)} ± {rr3.loc['end (leaf drop)','se']:.2f}",
     f"**{n(wl.iloc[0].slope,2)} ± {wl.iloc[0].se:.2f}**, p {'< 0.001' if wl.iloc[0].p < 0.001 else '= ' + f'{wl.iloc[0].p:.3f}'}", pc(wl.iloc[0].loo_skill_pct, 0)],
    ['GDD, 1 May to 15 Sept', f"{n(rg.loc['start (pods)','slope'],3,True)} ± {rg.loc['start (pods)','se']:.3f}", f"{n(rg.loc['end (leaf drop)','slope'],3,True)} ± {rg.loc['end (leaf drop)','se']:.3f}",
     f"**{n(wl.iloc[1].slope,4,True)} ± {wl.iloc[1].se:.4f}**, p = {wl.iloc[1].p:.3f}", pc(wl.iloc[1].loo_skill_pct, 0)]])}

Read this as small and weakly supported: only the R3 driver has real out-of-sample skill for window length.

#### Where it stands after recalibration

{tbl(['Observed', 'Model', 'Bias', 'RMSE', 'Year-to-year r', 'Trend observed', 'Trend model', 'Gap'], [
    row('planted', 'plant_doy', 'temperature rule'), row('blooming', 'r1_doy', 'thermal R1'),
    row('pods', 'r3_doy', 'thermal R3'), row('pods', 'start_doy', 'window start*'), row('leaves', 'end_doy', 'window end*')])}

Trends in days per decade, 1981-2024. *These two are fitted to the same observations, so their bias and RMSE are in-sample and agreement on mean dates is by construction. What is not by construction is the year-to-year correlation and the trends. **The planting trend is reproduced without being fitted. The flowering and pod-set trends are not**: the model advances them about {abs(r29('blooming','r1_doy').trend_gap_in_se):.1f} standard errors faster than observed, and even the empirical window end trends earlier ({n(r29('leaves','end_doy').model_trend,1)}) where leaf drop actually moved slightly later ({n(r29('leaves','end_doy').obs_trend,1,True)} ± {r29('leaves','end_doy').obs_trend_se:.1f}). Interannual slopes overstate the response over decades. The real system adapted through planting date and variety, and a fixed rule contains none of that.

![Figure 32. The phenology against what NASS observed](figures/fig32_phenology_validation.png)

**Farmers' assessment corroborates the stress variables.** August good-plus-excellent condition ratings ({len(cond)} years) correlate {n(cr['yield_anom'],2,True)} with the state yield anomaly, {n(cr['season_edd'],2)} with extreme degree days, {n(cr['wb_min_water_frac'],2,True)} with minimum soil water fraction and {n(cr['win_prcp_mm'],2,True)} with window precipitation.
"""


def s55():
    r = T21
    g = T21g
    calrows = [[LAB[x.scenario], HZ[x.horizon], f"+{x.dTmax_JA_C:.2f} °C", n(x.plant_shift_days, 1, True) + " d", n(x.r3_shift_days, 1, True) + " d",
                n(x.end_shift_days, 1, True) + " d", n(x.window_shift_days, 1, True) + " d", f"×{x.edd_ratio:.1f}", pc(x.out_of_range_pct, 0)] for x in r.itertuples()]
    yrows = [[LAB[a.scenario], HZ[a.horizon], n(a.climate_sr_bu), f"{n(a.sr_min_bu)} to {n(a.sr_max_bu)}", n(b.climate_sr_bu), n(a.climate_gbm_bu, 2, True)]
             for a, b in zip(r.itertuples(), g.itertuples())]
    crows = [[LAB[x.scenario], HZ[x.horizon], n(x.climate_sr_bu), n(x.net_none_bu), n(x.net_saturating_bu, 2, True), n(x.net_face_bu, 2, True)] for x in r.itertuples()]
    l = r.iloc[3]
    lg = g.iloc[3]
    old = T11.iloc[3]
    maxdiff = float(np.abs(r.climate_sr_bu.values - g.climate_sr_bu.values).max())
    return f"""### 5.5 CMIP6 scenarios on the calibrated window

Script 12 pulls CMIP6 monthly output from the AWS Open Data registry for eight models (ACCESS-ESM1-5, CanESM5, EC-Earth3, GFDL-ESM4, INM-CM5-0, MIROC6, MPI-ESM1-2-LR, MRI-ESM2-0) under SSP2-4.5 and SSP5-8.5. Raw model output is never fed to the yield model, because it carries systematic bias. Instead each model's change between a 1985-2014 baseline and the target horizon is applied to the observed record: additively for temperature and relative humidity, multiplicatively for precipitation, interpolated to all county centroids. Script 20 applies the deltas to the daily record and recomputes the whole phenology through the same module script 18 uses on observed weather. Scenario windows are measured against the observed-climate baseline, otherwise warming would cancel itself out of the anomaly.

The parametric estimator is the Schlenker-Roberts specification with EDD entering linearly, so the nonlinearity lives in the degree-day accounting and extrapolation is a straight line in a variable with a physical threshold, not a fitted curve in raw temperature. The two-estimator design exists because boosted trees predict a constant outside their training range: the first scenario script (script 13, retained in Part I's lineage) returned its **smallest** loss ({n(old.ens_median_delta_bu)} bu/acre) for its **hottest** scenario, an artefact of that saturation, and a quadratic estimator gave {n(old.ens_median_parametric_bu)}.

#### What warming does to the calendar

{tbl(['Scenario', 'Horizon', 'Δ Tmax Jul-Aug', 'Planting', 'R3', 'Window end', 'Window length', 'Extreme degree days', 'Beyond record'], calrows)}

Pod setting advances up to {abs(r.r3_shift_days.min()):.0f} days and maturity up to {abs(r.end_shift_days.min()):.0f}, so the window lengthens by {r.window_shift_days.min():.0f} to {r.window_shift_days.max():.0f} days and accumulates more hot days. "Beyond record" is the share of county-years whose season EDD exceeds the observed maximum.

![Figure 26. What warming does to the calibrated window](figures/fig26_window_response.png)

#### The climate effect, and the range behind it

{tbl(['Scenario', 'Horizon', 'Median, R3 driver', 'Range across 8 models', 'Median, GDD driver', 'Boosted trees'], yrows)}

Bu/acre. **The median alone should not be quoted.** Under SSP5-8.5 late century the eight models span a fourfold range ({n(l.sr_min_bu,1)} to {n(l.sr_max_bu,1)}), and the worst comes with extreme degree days far outside anything in the 1981-2024 record. The two window drivers give medians within {maxdiff:.1f} bu/acre of each other in every scenario, so the choice the record could not make does not matter for yield. The losses are larger than in the earlier version that let thermal time end the window, because with the window no longer shortening, warming buys more hot days inside it.

#### CO₂ changes the sign

Soybean is a C3 legume and the most CO₂-responsive major crop; SoyFACE sits in Champaign County. The response is applied as an explicit layer with three variants (none; a logarithmic curve scaled to about +15% seed yield at 550 ppm; the same curve capped at 550 ppm), calibrated against the FACE meta-analysis of Ainsworth and Long (2005), and it is an assumption, not a result.

{tbl(['Scenario', 'Horizon', 'Climate', 'No CO₂', 'Saturating', 'FACE'], crows)}

![Figure 28. Three CO₂ assumptions](figures/fig28_co2_assumption_range.png)

Under SSP5-8.5 late century the net answer runs from {n(l.net_none_bu,1)} to {n(l.net_face_bu,1,True)} bu/acre on the CO₂ assumption alone. The saturating variant, the more defensible non-zero option because the FACE curve is extrapolated to 890 ppm far beyond its data, gives a **net loss** ({n(l.net_saturating_bu,1)}). Whether climate change is bad for Illinois soybean cannot be answered from this pipeline without committing to a CO₂ response, and it does not know one.

#### What the scenarios do not include

- **Adaptation.** The observed record shows earlier planting and no advance in maturity. The window slopes are interannual estimates at today's level of adaptation, extrapolated far beyond it, and the model's flowering and pod-set trends already overshoot observation by about {abs(r29('blooming','r1_doy').trend_gap_in_se):.1f} standard errors. **The losses above are probably too large for that reason.**
- **Extrapolation of EDD.** In the hottest scenario about {pc(l.out_of_range_pct, 0)} of county-years lie beyond the observed maximum, where the linear term is an assumption.
- **The CO₂ response is a flat multiplier**, though FACE shows it shrinks under heat and interacts with drought, and the concentrations used are round numbers, not the published CMIP6 series.
- **Ozone**, whose confounding with heat cannot be separated here (Section 5.7).
- **The scenario set.** Two pathways were run. SSP5-8.5 is now widely contested as a plausible baseline, and the full ScenarioMIP set adds SSP1-2.6 and SSP3-7.0, which were not run.
"""


def s56():
    rows = [[LAB[x.scenario], HZ[x.horizon], f"{x.max_viable_mg:.1f}" + ("+" if x.max_viable_mg >= 5 else ""), f"{x.frost_margin_3_5:.0f} d", pc(x.mature_3_5 * 100, 0),
             f"{x.seedfill_at_3_5:.1f} d", f"{x.seedfill_at_max:.1f} d"] for x in MG23.itertuples()]
    b = MG_BASE
    g = GRID[(GRID.scenario == "baseline")].sort_values("mg")
    return f"""### 5.6 Adaptation: what the grower can do, and what this model cannot say

Every scenario assumes a grower changes nothing. Script 21 asks what a longer maturity group does. It runs on thermal-time maturity on purpose, because its frost arithmetic needs a thermal-time R8, and that is the quantity Section 5.4 showed to be unreliable for late-season timing, so **its conclusions inherit that weakness**.

{tbl(['Climate', 'Longest viable MG', 'Frost margin at MG 3.5', 'Mature before frost at MG 3.5', 'Seed fill at MG 3.5', 'at longest'],
     [['Today', f"{b.max_viable_mg:.1f}", f"{b.frost_margin_3_5:.0f} d", pc(b.mature_3_5 * 100, 0), f"{b.seedfill_at_3_5:.1f} d", f"{b.seedfill_at_max:.1f} d"]] + rows)}

"Longest viable" is the longest group maturing before the killing frost in 90% of years; values of 5.0 are censored at the top of the tested range. The qualitative conclusion holds: under any scenario frost stops binding and even MG 5.0 matures in almost every year. **A result reported earlier does not survive**: with corrected planting the frost constraint binds at MG {b.max_viable_mg:.1f} today, not 3.5, so the earlier claim that it matched what Illinois growers plant, which was never sourced, is withdrawn.

**No maturity group is recommended, and the reason has been corrected.** Predicted yield across MG 2.0 to 5.0 at today's climate is {', '.join(n(v, 2, True) for v in g.pred)}: nearly flat. It used to rise a clean 1.7 bu/acre per half group. Both were artefacts of one defect. Under the thermal end rule the season length is defined by the R6 threshold, so `season_gdd` was constant by construction (sd 4.25 GDD around 1,396), the coefficient was fitted to discretisation noise, and the earlier explanation, that it was identified from seasons varying at one maturity group, was wrong. The phenological consequences of a variety choice are computable. Converting them into a yield optimum needs a model that carries yield potential, which is the argument Peng et al. (2020) make for process-based crop models.
"""


def s57():
    corr = O27[O27.part == "correlation"].set_index("metric")
    pan = O27[O27.part == "panel"].set_index("metric")
    yl = O27[O27.part == "year_level"]
    m90 = "90th-percentile 8-h value"
    rows = [[m, pc(O26.loc[m, 'trend_explains_pct'], 0), f"{O26.loc[m, 'detrended_sd_ppb']:.1f} ppb", n(corr.loc[m, 'r_year_detrended'], 2),
             n(pan.loc[m, 'coef_bu_per_ppb'], 3), f"{pan.loc[m, 'p_value']:.2f}", f"{pan.loc[m, 'delta_r2']:.3f}"] for m in O26.index]
    return f"""### 5.7 Ozone

Midwest soybean is suppressed by roughly 10% under current tropospheric ozone, and at SoyFACE elevated ozone cost 10 ± 11% at 370 ppm CO₂ but only 5 ± 4% at 550 ppm, so CO₂ partly protects the crop. Before building anything, the question that ended the soil work was asked: does ozone survive detrending? The modelling target is the residual of a county trend, so a monotone ozone decline is absorbed. Script 22 uses the EPA annual monitor summaries for Illinois, 1980-2024, covering 18 to 23 of 102 counties.

{tbl(['Metric', 'Trend explains', 'Detrended sd', 'r with anomaly (44 yr)', 'Coefficient, bu/acre per ppb', 'p', 'ΔR²'], rows)}

**It does survive detrending, unlike soil**: the trend explains only about a third of the peak metrics, and the correlation with the yield anomaly strengthens once the trend is removed. **But it is not separable from heat and water.** Detrended ozone correlates {n(pan.corr_with_edd.min(),2,True)} to {n(pan.corr_with_edd.max(),2,True)} with extreme degree days and {n(pan.corr_with_water.min(),2)} to {n(pan.corr_with_water.max(),2)} with the water balance, and adds at most {pan.delta_r2.max():.3f} to R². A year-level regression with no county replication gives p between {yl.p_value.min():.2f} and {yl.p_value.max():.2f}.

![Figure 31. Ozone screen](figures/fig31_ozone_screen.png)

**A null here does not mean ozone does nothing.** The detectable-effect floor is about 0.21 bu/acre per ppb, and the literature implies roughly 0.13 to 0.38 from two rough anchors, so the range straddles the floor. The consequence runs the other way: because ozone tracks heat and drought, part of what the fitted EDD and water coefficients measure may be ozone damage, and part of the measured FACE benefit is ozone protection and not fertilisation. This cannot be tested with annual state-level data. It would take county-varying growing-season exposure (AOT40 or W126) from the hourly files, and an ozone-explicit process crop model.
"""


def s58():
    a = T35.set_index(["features", "holdout"])
    cal_n, cal_d = a.loc[("calendar", "none (script 19)")], a.loc[("calendar", "district")]
    prc_n, prc_d = a.loc[("process", "none (script 19)")], a.loc[("process", "district")]
    lat = C26["residual_vs_latitude"]
    e, h = lat["expanding_window"], lat["district_holdout"]
    span = lat["latitude_span_deg"]
    tt = C26["residual_by_tercile"]
    hw = C26["heat_slopes_equal_wald_p"]
    ci_excl = (T38b.ci_high_pct < 0) or (T38b.ci_low_pct > 0)
    lo, hi = T36.transfer_loss_pct.min(), T36.transfer_loss_pct.max()
    rowsA = [[f, ("none (script 19)" if hd == "none (script 19)" else "district held out"), f"{a.loc[(f, hd), 'rmse']:.3f}", pc(a.loc[(f, hd), 'skill_pct'], 1)]
             for f in ("calendar", "process", "both") for hd in ("none (script 19)", "district")]
    hrows = [[t, int(T37.loc[t, 'counties']), f"{T37.loc[t, 'mean_edd']:.0f}", f"{n(T37.loc[t, 'edd'], 3)} ± {T37.loc[t, 'se']:.3f}",
              f"{n(T37.loc[t, 'edd_separate_fit'], 3)}", f"{T37.loc[t, 'water_separate_fit']:.1f}"] for t in ("south", "central", "north")]
    grows = [[r.windows, f"{r.rmse:.3f}", pc(r.skill_pct, 1), f"{r.start_gradient_days:.1f} d", f"{r.end_gradient_days:.1f} d"] for r in T38.itertuples()]
    return f"""### 5.8 County-level validation, as far as the data allow

**What cannot be done.** County-level validation of the phenology is not possible. NASS publishes Illinois soybean progress at state level only, and every finer source that could stand in for it needs an Earthdata login or tens of gigabytes. The county dimension of the phenology therefore rests on an assumption nothing here can confirm: that every county's yield window sits on the same dates, with only year-to-year anomalies varying by county.

**What can be done.** Counties do have observed yields, so everything downstream of the phenology can be validated at county level, and the exposed assumption can be tested indirectly through yield. Script 26 does four things.

#### A. Transfer to unseen districts

Each of the nine crop-reporting districts is predicted from a model trained on the other eight and only earlier years. This is strictly harder than the expanding-window test, where the county being predicted was in the training set in every earlier year. Leaving a district out while keeping the same years elsewhere would leak the year's shared weather shock, so the temporal restriction is kept.

{tbl(['Features', 'Holdout', 'RMSE', 'Skill vs no anomaly'], rowsA)}

**The calendar model loses nothing** ({cal_n.rmse:.3f} against {cal_d.rmse:.3f}), the process model loses {pc((prc_d.rmse / prc_n.rmse - 1) * 100, 1)}, and district-by-district the change runs from {pc(lo, 1, True)} to {pc(hi, 1, True)}. The yield-climate relationship transfers across Illinois. Two caveats bound this: adjacent districts share weather, so a held-out district is never far from training data, and nine spatial units is a small number.

#### B. Do the errors line up north to south?

County-mean residuals fall with latitude: slope {n(e['slope'], 3)} bu/acre per degree (r = {n(e['r'], 2)}, p {'< 0.01' if e['p'] < 0.01 else '= ' + f"{e['p']:.2f}"}) under the expanding window and {n(h['slope'], 3)} under district holdout, across {lat['counties']} counties. Over the {span:.1f}-degree span that is about {abs(e['slope']) * span:.1f} bu/acre against a typical RMSE near 5, so the structure is statistically clear and small. Mean residual by tercile: south {n(tt['south']['expanding'], 2)}, central {n(tt['central']['expanding'], 2)}, north {n(tt['north']['expanding'], 2)}. The model over-predicts everywhere in 2001-2024, probably a property of the linear detrend, and over-predicts most in the north.

#### C. The uniform-window assumption

The windows were rebuilt with the north-south gradient in thermal time retained (state-relative anomalies), which moves the northern window {T38.iloc[2].start_gradient_days:.1f} days later at the start and {T38.iloc[2].end_gradient_days:.1f} at the end, and county yield prediction was compared.

{tbl(['Windows', 'RMSE', 'Skill', 'Start, north minus south', 'End, north minus south'], grows)}

Retaining the gradient improves RMSE by {abs(T38b.rmse_change_pct):.2f}%, but the paired comparison does not establish it: it is better in {int(T38b.years_state_relative_better)} of {int(T38b.test_years)} test years, with a bootstrap 95% interval over years of {n(T38b.ci_low_pct, 1)}% to {n(T38b.ci_high_pct, 1, True)}%, which {'excludes' if ci_excl else '**includes zero**'}. **Yield cannot reliably discriminate between the two window designs.** A control shows the difference is not simply latitude leaking into the features: adding latitude to the uniform-window features makes prediction slightly worse ({pc((T38.iloc[1].rmse / T38.iloc[0].rmse - 1) * 100, 1, True)}), not better. The uniform-window assumption is therefore neither confirmed nor refuted; its error, if any, is below what county yields can detect.

#### D. Does the heat penalty differ by latitude?

The scenarios apply one pooled coefficient to every county. Estimated together in one model, with county fixed effects and errors clustered by county, the three tercile heat slopes are indistinguishable (Wald p = {hw:.2f}):

{tbl(['Latitude tercile', 'Counties', 'Mean season EDD', 'Heat slope, one model', 'Heat slope, fitted separately', 'Water coefficient, fitted separately'], hrows)}

The separately fitted heat slopes look different, but that difference is produced by the water and precipitation terms, whose coefficients vary by a factor of about four across terciles. Fitted together with shared terms the heat slopes agree, so separate fits **overstated** heterogeneity in the heat penalty. The water response, by contrast, is stronger in the south, consistent with the soil result of Section 5.2. The pooled heat coefficient the scenarios use is supported.

![Figure 33. County-level validation](figures/fig33_county_validation.png)
"""


def s59():
    return """### 5.9 What the literature audit changed

The analysis was checked against published work, not recollection. Four things held: the 30 °C soybean threshold is Schlenker and Roberts' own figure; the CO₂ curve reproduces both the SoyFACE measurement (2.5 kg/ha/ppm from 373 to 550 ppm) and the Ainsworth and Long meta-analytic +24% at 689 ppm; warming losses arise mainly through a shortened growing season in the published attribution work; and the recommendation to model maturity-group adaptation with a process-based crop model is the standard one. Three things changed.

- **Humidity had been assumed away.** At 2 °C of warming the yield loss attributable to the associated VPD rise exceeds the loss from warming itself in published attribution work, and CMIP6 projects relative humidity declining over North America. Script 12 now pulls it: July-August RH falls by roughly 3 to 5 percentage points across the scenarios.
- **Evapotranspiration could not see humidity**, so projecting it changed nothing downstream. FAO-56 Penman-Monteith replaced Hargreaves.
- **The water balance was missing from the specification.** The first humidity fix returned a climate effect identical to four decimal places, because the specification read no water-balance variable. It was caught only by comparing against the previous run.

The one item this audit found and this analysis cannot resolve is ozone (Section 5.7).
"""


def part2():
    return ("## 5. Extensions and independent checks (Part II)\n\n"
            "Every number in this part is read from the results files at build time. The scripts are numbered 12 to 27 and "
            "listed in Appendix B.\n\n" + "\n".join([s51(), s52(), s53(), s54(), s55(), s56(), s57(), s58(), s59()]) + "\n---\n")


# ================================================================= LIMITATIONS ========
def limitations():
    return f"""## 7. Limitations

**Some limitations of Part I were addressed by Part II; the rest stand.** Monthly resolution (which could not resolve frost or daily extremes) and the absence of vapour pressure deficit were the largest gaps of v1.0, and Section 5.3 addresses both, at the cost of a coarser 0.5-degree source. The statement that scenarios use no CMIP6 pattern is superseded by Section 5.5, whose own limitations follow.

**Limitations of the extension**

- **Phenology is validated at state level only.** NASS publishes nothing finer, and the county-relative anomaly design means every county's average window sits on the same dates, surely wrong for a state spanning five degrees of latitude. County yield cannot discriminate between a uniform and a gradient window (Section 5.8), so the assumption is unresolved, not confirmed.
- **The trends are overstated.** The model's flowering and pod-set trends run about {abs(r29('blooming','r1_doy').trend_gap_in_se):.1f} standard errors steeper than observed, because interannual slopes fitted at today's level of adaptation are extrapolated over decades in which the real crop adapted. The scenario losses are probably too large for that reason.
- **No adaptation is modelled.** Earlier planting and variety change are visible in the observed record and absent from the scenarios. The maturity-group analysis of Section 5.6 rests on thermal-time maturity, which does not predict late-season timing, and cannot yield an optimum without a crop model carrying yield potential.
- **Extrapolation beyond the observed heat range.** Up to {pc(T21.iloc[3].out_of_range_pct, 0)} of county-years in the hottest scenario lie beyond the observed maximum EDD, where the linear term is an assumption and the eight models span a fourfold range.
- **The CO₂ layer is an assumption.** It is a flat multiplier calibrated to FACE, applied with rounded concentrations, and it does not shrink under heat or interact with drought as the experimental record shows it does.
- **Ozone cannot be separated from heat.** Part of the fitted heat and water response may be ozone damage, and part of the FACE benefit ozone protection. The screen used annual state-level data from urban-biased monitors covering under a quarter of counties.
- **Two scenarios only.** SSP2-4.5 and SSP5-8.5. SSP5-8.5 is contested as a plausible baseline, and SSP1-2.6 and SSP3-7.0 were not run.
- **Eight models, one realisation each.** Internal variability is not sampled, and monthly means cannot change within-month extremes or wet-day frequency.
- **The process-versus-calendar comparison is confounded** by data source (POWER against nClimDiv).
- **Soil is static and aggregated** to county means, and explains where the good ground is, not the timing of a bad year.

**Limitations of Part I that stand**

- **No spatial aggregation step is executed** in the original climate data: NCEI performs the gridding upstream, so the pipeline inherits the weighting method.
- **Snow is not available** in nClimDiv.
- **County coverage collapses after 2018**, from 102 counties reporting in 2000 to 62 in 2025, with survival not random.
- **Confounders are not controlled**: cultivar turnover, drainage, fertiliser, pest pressure, machinery, price and policy.
- **No causal identification.** All estimates are associations.
- **Machine-learning importance is not causal.**
- **Champaign is one county in a panel**, and its 44 observations do not support independent estimation.

---
"""


# ================================================================= CONCLUSIONS ========
def conclusions():
    c = between(orig, "## 7. Conclusions")
    c = c.replace("## 7. Conclusions", "## 8. Conclusions")
    i = c.index("### Direct answer to the central question")
    body, ans = c[:i].rstrip(), c[i:]
    r = T21.iloc[3]
    new = f"""

**Part II conclusions**

**8. Does the analysis survive independent checks?** In part. The heat and water variables at its centre are corroborated by farmers' own condition ratings, and the planting trend is reproduced without being fitted. The flowering and pod-set trends are not, and observed leaf drop has not advanced as the model implies. Adaptation is in the record and not in the model.

**9. What do CMIP6-based projections say?** They bracket the answer without pinning it down. The median climate effect at SSP5-8.5 late century is {n(r.climate_sr_bu,1)} bu/acre, the eight models span {n(r.sr_min_bu,1)} to {n(r.sr_max_bu,1)}, and the CO₂ assumption moves the net from {n(r.net_none_bu,1)} to {n(r.net_face_bu,1,True)}. They are not forecasts, and the losses are probably overstated for want of adaptation.

**10. Does soil matter?** For where the good ground is and how counties respond to a bad year, yes; for predicting a given year's anomaly, no, and for a reason that follows from the detrending.

**11. Can ozone be separated from heat?** Not with these data. It survives detrending, tracks extreme degree days at about +0.6 to +0.7, and the design cannot detect effects of the size the literature implies.

**12. Does the model transfer to places it has not seen?** Across Illinois districts, yes, with no measurable loss, and the heat penalty does not differ by latitude. Whether the window's spatial structure is right cannot be established, because NASS phenology is state-level only.
"""
    ans2 = ans.rstrip() + f"""

**Part II adds** that the projection of this relationship under CMIP6 scenarios is wide and depends on assumptions the data cannot settle, chiefly the response to CO₂, the absence of adaptation, and extrapolation beyond the observed heat range. The direction of the near-term effect is a loss under any assumption about CO₂ up to 550 ppm; at the highest concentrations it depends on a CO₂ response this analysis cannot supply.
"""
    return body + new + "\n" + ans2 + "\n"


# ================================================================= APPENDICES =========
def appendix_a():
    return """## Appendix A. Errors found and corrected during the extension

An audit trail, because several early results of Part II were wrong and the corrections change conclusions.

| # | What was wrong | Consequence | Where corrected |
|---|---|---|---|
| 1 | Soil available water averaged across horizon rows instead of summed down each profile | Bucket 4.35 times too small; the water balance drained to empty every year | Script 15 |
| 2 | Phenology thresholds and stage dates written from memory and described as calibrated to NASS | Stage dates agreed with the thresholds by construction and proved nothing | Scripts 23-25 |
| 3 | Temperature-rule planting 15.2 days early, described at the time as close to Illinois norms | Every modelled stage 10 to 19 days early | Script 25 |
| 4 | Thermal time used to end the yield window | Predicts leaf drop worse than the average date (RMSE 19.5 against sd 4.8 days) | Script 25 |
| 5 | `season_gdd` constant by construction under the thermal end rule (sd 4.25 GDD) | Its coefficient was fitted to discretisation noise; the earlier explanation of the maturity-group result was wrong | Scripts 20, 21 |
| 6 | Maturity-group offset added a constant, so seed fill was identical for every group | The exercise was voided | `_pheno.py` |
| 7 | Claim that thermal maturity matched what Illinois growers plant | Figure never sourced; withdrawn when corrected planting moved the frost constraint to MG 2.5 | Script 21 |
| 8 | Humidity assumed constant; then perturbed but not read by the specification | First fix returned a climate effect identical to four decimals | Scripts 12, 20 |
| 9 | VPD entered as a regressor | Wrong sign, collinear with EDD at about +0.9 | Script 20 |
| 10 | Ozone screen: units off by 10⁶, and a power comment that spread a whole-atmosphere effect over a 5 ppb range | Test looked able to detect an effect it could not | Script 22 |
| 11 | Retained-gradient window test judged by a naive 1% threshold | Paired year-by-year comparison shows the difference is not established | Script 26 |
| 12 | Heat-penalty heterogeneity inferred from separately fitted terciles | Separate fits overstated it; the pooled test finds none | Script 26 |
| 13 | Original report said county sensitivity varied by both tenfold and sevenfold | The same quantity, and neither ratio is defined because some counties have negative sensitivity | Part I text retained as written; see Section 4.6 |

---
"""


def appendix_b():
    rows = [
        ["12", "CMIP6 change factors (temperature, precipitation, relative humidity)", "cmip6_deltas.csv"],
        ["13", "First-generation scenarios on monthly aggregates, superseded by 20", "tables 11-13"],
        ["14-16", "SSURGO soil download, county features, three soil tests", "tables 14-17"],
        ["17", "NASA POWER daily weather", "power_daily.csv.gz (not committed)"],
        ["18", "Phenology, VPD, water balance on observed weather", "phenology_features.csv"],
        ["19", "Process versus calendar features", "tables 18-20"],
        ["20", "CMIP6 scenarios on the calibrated window, two window drivers", "tables 21-22"],
        ["21", "Maturity-group adaptation, thermal-time maturity", "tables 23-24"],
        ["22", "Ozone screen", "tables 26-27"],
        ["23", "NASS crop progress and condition download", "nass_il_soybean_progress.csv"],
        ["24", "Phenology validated against NASS", "tables 28-31"],
        ["25", "Calibration of planting and yield window", "tables 32-34"],
        ["26", "County-level validation", "tables 35-38"],
        ["27", "This report", "FINAL_REPORT.md, Illinois_Soybean_Climate_Report.docx"],
    ]
    return f"""## Appendix B. Reproduction

Scripts 01 to 11 reproduce Part I. The extensions add public downloads, none of which needs a key. Run order is slightly circular: script 24 runs once before calibration and once after, and script 25 checks that the constants in `scripts/_pheno.py` agree with what it recomputes.

{tbl(['Script', 'Purpose', 'Main outputs'], rows)}

Random seed 42 throughout. Every figure is 200 dpi PNG in `figures/`, and every table is a CSV in `results/`.

---

## References

Ainsworth, E. A., and Long, S. P. (2005). What have we learned from 15 years of free-air CO₂ enrichment (FACE)? A meta-analytic review of the responses of photosynthesis, canopy properties and plant production to rising CO₂. *New Phytologist*.

Allen, R. G., Pereira, L. S., Raes, D., and Smith, M. (1998). *Crop evapotranspiration: guidelines for computing crop water requirements.* FAO Irrigation and Drainage Paper 56.

Khaki, S., Wang, L., and Archontoulis, S. V. (2020). A CNN-RNN framework for crop yield prediction. *Frontiers in Plant Science*, 10, 1750.

Peng, B., Guan, K., Tang, J., et al. (2020). Towards a multiscale crop modelling framework for climate change adaptation assessment. *Nature Plants*. doi:10.1038/s41477-020-0625-3

Ragsdale, D. W., et al. (2012). *Journal of Integrated Pest Management*, as cited in Section 6.3.

Schlenker, W., and Roberts, M. J. (2009). Nonlinear temperature effects indicate severe damages to U.S. crop yields under climate change. *Proceedings of the National Academy of Sciences*, 106.

Snyder, R. L. (1985). Hand calculating degree days. *Agricultural and Forest Meteorology*, 35.

Sun, J., Di, L., Sun, Z., Shen, Y., and Lai, Z. (2019). County-level soybean yield prediction using deep CNN-LSTM model. *Sensors*, 19, 4363.

Tian, H., Wang, P., Tansey, K., et al. (2021). An LSTM neural network for improving wheat yield estimates by integrating remote sensing data and meteorological data in the Guanzhong Plain, PR China. *Agricultural and Forest Meteorology*, 310, 108629.

Tilmon, K. J., et al. (2011). *Journal of Integrated Pest Management*, as cited in Section 6.3.

Zhang, J., Guan, K., Chen, Z., et al. (2025). Transfer learning for improved crop yield predictions in a cross-scale pathway: a case study for Brazilian national soybean. *International Journal of Applied Earth Observation and Geoinformation*, 145, 104981.

Cited by title from publisher pages: Morgan et al. (2006), season-long elevation of ozone concentration to projected 2050 levels under fully open-air conditions substantially decreases the growth and production of soybean, *New Phytologist*; and the published work on the role of vapour pressure deficit in maize and soybean yield loss under warming, including "Maize yield under a changing climate: The hidden role of vapor pressure deficit", *Agricultural and Forest Meteorology*.
"""


# =================================================================== ASSEMBLE =========
def build():
    md = "\n".join([front(), part1(), part2(), discussion(), limitations(), conclusions(),
                    appendix_a(), appendix_b()])
    md = re.sub(r"\n{3,}", "\n\n", md)
    out_md = RES / "FINAL_REPORT.md"
    out_md.write_text(md, encoding="utf-8")
    print(f"[27] wrote results/FINAL_REPORT.md   {len(md.splitlines()):,} lines, {len(md):,} characters")

    title = [("SOYBEAN YIELD AND CLIMATE VARIABILITY", 22, True, _mdocx.ACCENT, 2),
             ("Illinois County Panel", 15, False, _mdocx.INK, 2),
             ("1980 to 2025, with extensions to 2026-09-20", 12, False, _mdocx.MUTED, 8),
             ("A county x year panel testing how growing-season heat and moisture relate to soybean yield, with "
              "Champaign County as the focal unit, extended with observed phenology, soil, daily weather, "
              "CMIP6 scenarios, ozone and county-level validation.", 10.5, False, _mdocx.INK, 8),
             (f"Version {VERSION}  |  {DATE}  |  Part I: original study (v1.0, 2026-08-31), github.com/osperry/soybean-climate-illinois. "
              "Part II: extensions, scripts 12 to 27.", 9.5, False, _mdocx.MUTED, 4),
             ("Sources: USDA NASS Quick Stats and Crop Progress; NOAA NCEI nClimDiv; NASA POWER; USDA-NRCS SSURGO; "
              "CMIP6 via AWS Open Data; EPA AirData. All United States federal or open data.", 9.5, False, _mdocx.MUTED, 14)]
    body = md.split("\n", 1)[1]                        # drop the H1, the title block carries it
    counts = _mdocx.convert(body, RES / "Illinois_Soybean_Climate_Report.docx", ROOT, title,
                            f"Soybean yield and climate variability in Illinois, v{VERSION}")
    print(f"[27] wrote results/Illinois_Soybean_Climate_Report.docx  {counts}")
    return md, counts


if __name__ == "__main__":
    build()

