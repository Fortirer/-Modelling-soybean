"""20 - CMIP6 scenarios on a moving crop window, with CO2 made explicit.
Tables 21-23, Figures 26-28.

What changes relative to script 13
  Script 13 applied CMIP6 deltas to monthly aggregates and re-predicted, with
  July and August fixed. Warming therefore made a fixed window hotter and did
  nothing else. Here the deltas are applied to the DAILY record and the whole
  phenology is recomputed through _pheno, the same module script 18 uses on
  observed weather. Warming now does what warming does: thermal time runs
  faster, stages arrive earlier, seed fill shortens, and the R3-R6 window that
  the yield model reads has moved on its own. Nothing in this script tells it
  to; it falls out of the thermal-time accounting.

Two estimators, for the same reason as script 13
  Boosted trees fit best in sample but predict a constant outside their
  training range, which made script 13 report its SMALLEST loss for its
  HOTTEST scenario. The parametric estimator here is the Schlenker-Roberts
  specification: yield on GDD, EDD, precipitation and its square, with county
  fixed effects. EDD enters LINEARLY and that is the point of the construction
  -- the nonlinearity lives in the degree-day accounting, not the functional
  form, so extrapolating it is a straight line in a variable with a physical
  threshold rather than a fitted curve in raw temperature. That is a much
  weaker assumption than script 13's quadratic, though still an assumption.

CO2, which script 13 omitted entirely
  Soybean is a C3 legume and the most CO2-responsive major crop, and SoyFACE,
  the free-air enrichment facility behind the definitive soybean numbers, sits
  in Champaign County, this study's focal unit. Projecting warming losses while
  silently holding CO2 at present levels is a one-sided bias.

  This script does NOT claim to know the CO2 response. It reports three
  explicit variants so the size of the assumption is visible:
      none        beta = 0, script 13's implicit and indefensible assumption
      face        logarithmic, scaled to roughly +15% seed yield at 550 ppm
      saturating  the same curve, capped at its 550 ppm value

  Read the spread between them as the uncertainty this introduces, not as a
  forecast. The FACE response is also known to shrink under heat and to
  interact with drought, neither of which is represented.
"""
import sys, json, time
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import statsmodels.formula.api as smf
from sklearn.ensemble import GradientBoostingRegressor
from _cfg import RAW, PROC, FINAL, RES, FIG, SEED, FOCAL_COUNTY
from _viz import *
import _pheno as P

# ---- CO2, ppm --------------------------------------------------------------
# APPROXIMATE SSP concentration-pathway means. These are round numbers, not
# read from the CMIP6 GHG concentration files (Meinshausen et al. 2020), and
# should be replaced with the published series before anything is quoted.
CO2 = {("baseline", "baseline"): 370.0,
       ("ssp245", "mid_century"): 510.0, ("ssp245", "late_century"): 580.0,
       ("ssp585", "mid_century"): 580.0, ("ssp585", "late_century"): 890.0}
CO2_REF = 370.0
# +15% seed yield at 550 ppm from an ambient near 370, FACE meta-analysis
CO2_BETA = 0.15 / np.log(550.0 / 370.0)
CO2_SATURATE_AT = 550.0

DEW_NOTE = ("relative humidity is taken from the CMIP6 hurs delta and dewpoint is "
            "recomputed from the perturbed temperature range, rather than shifting "
            "dewpoint with temperature. An earlier version did the latter, which "
            "holds RH roughly constant and looks conservative but is not: VPD is "
            "the larger of the two warming channels for yield (Lobell et al.) and "
            "CMIP6 projects RH DECLINING over North America, so holding it fixed "
            "suppressed the dominant damage mechanism")
PRCP_NOTE = ("a monthly ratio scales every wet day equally, so rainfall "
             "intensity changes but wet-day frequency does not; delta methods "
             "cannot represent a change in the rainfall distribution")


def co2_factor(ppm, mode):
    if mode == "none":
        return 1.0
    c = min(ppm, CO2_SATURATE_AT) if mode == "saturating" else ppm
    return 1.0 + CO2_BETA * np.log(c / CO2_REF)


def perturb_daily(d, sub):
    """Apply one model/scenario/horizon's monthly county deltas to daily rows.

    Humidity is handled properly rather than assumed away: the observed daily
    relative humidity is recovered from the observed dewpoint, the CMIP6 hurs
    change is added to it in percentage points, and the dewpoint is rebuilt from
    that humidity against the WARMED temperature range. VPD therefore rises both
    because the saturation curve rises and because RH falls, which is what the
    models project. See DEW_NOTE.
    """
    x = d.copy()
    t = sub.pivot(index="fips5", columns="month", values="d_tas_C")
    tx = sub.pivot(index="fips5", columns="month", values="d_tasmax_C")
    pr = sub.pivot(index="fips5", columns="month", values="pr_ratio")
    rh = sub.pivot(index="fips5", columns="month", values="d_hurs_pct")
    mo = x.date.dt.month.values
    ids = x.unit_id.values
    i = np.arange(len(x))
    dt = t.reindex(ids).to_numpy()[i, mo - 1]
    dtx = tx.reindex(ids).to_numpy()[i, mo - 1]
    rp = pr.reindex(ids).to_numpy()[i, mo - 1]
    drh = rh.reindex(ids).to_numpy()[i, mo - 1]

    rh_obs = P.rh_from_dewpoint(x.tmin_c.values, x.tmax_c.values, x.tdew_c.values)
    x["tmax_c"] = x.tmax_c + dtx
    x["tmin_c"] = x.tmin_c + dt
    x["tmean_c"] = x.tmean_c + dt
    x["tdew_c"] = P.dewpoint_from_rh(x.tmin_c.values, x.tmax_c.values, rh_obs + drh)
    x["prcp_mm"] = x.prcp_mm * rp
    return x


def main():
    t_start = time.time()
    print("[20] loading ...", flush=True)
    daily = pd.read_csv(RAW / "power_daily.csv.gz", dtype={"unit_id": str},
                        parse_dates=["date"])
    lat = P.centroid_lat(RAW).set_index("unit_id").lat.to_dict()
    daily["lat"] = daily.unit_id.map(lat)
    soil = pd.read_csv(PROC / "soil_features.csv", dtype={"fips5": str})
    taw = (soil.set_index("fips5").soil_aws_0_100cm * 10.0).to_dict()
    dl = pd.read_csv(PROC / "cmip6_deltas.csv", dtype={"fips5": str})

    panel = pd.read_csv(FINAL / "soybean_illinois_climate_1980_2025.csv",
                        dtype={"county_ansi": str, "fips5": str})
    panel = panel[panel.in_balanced_panel == 1][
        ["fips5", "county", "year", "yield_bu_ac", "yield_anom"]]
    keep = set(panel.fips5)
    daily = daily[daily.unit_id.isin(keep)].copy()
    print(f"[20] counties in balanced panel : {len(keep)}")

    # ---- observed baseline, through the same module -----------------------
    obs = P.add_daily_terms(daily, lat)
    base_f, _ = P.build_features(obs, taw)
    d0 = panel.merge(base_f, on=["fips5", "year"], how="inner")
    print(f"[20] baseline county-years : {len(d0):,}")

    PROC_F = ["win_edd", "win_hot_days", "win_vpd_mean", "win_prcp_mm",
              "win_et0_mm", "win_water_deficit_mm", "win_tmax_mean",
              "wb_stress_days", "wb_min_water_frac", "wb_season_deficit_mm",
              "seedfill_days", "podfill_days", "season_edd", "season_prcp_mm",
              "season_gdd", "plant_doy", "r6_doy"]

    gbm = GradientBoostingRegressor(n_estimators=200, max_depth=3,
                                    learning_rate=.05, random_state=SEED)
    gbm.fit(d0[PROC_F], d0.yield_anom)
    d0 = d0.assign(pred_gbm=gbm.predict(d0[PROC_F]))

    # Schlenker-Roberts: EDD linear, precipitation quadratic, county effects.
    #
    # VPD is deliberately NOT a separate regressor. It was tried: entered
    # alongside EDD it takes a POSITIVE coefficient, +4.55 bu/acre per kPa,
    # which is backwards physiologically, because VPD and EDD correlate at
    # +0.912 and the pair is not separable. Shipping a model whose humidity
    # term raises yield would have been worse than omitting humidity.
    #
    # Humidity instead enters where it belongs, through evaporative demand:
    # ET0 is FAO-56 Penman-Monteith, so a projected fall in relative humidity
    # raises reference ET and drains the soil water balance faster.
    #
    # For that to reach yield the balance has to be IN the specification. It was
    # not, in the first attempt at this fix: humidity was perturbed, ET0 was
    # rebuilt, and the climate effect came back identical to four decimals,
    # because none of season_gdd, season_edd or precipitation reads the water
    # balance at all. The term below is what closes the circuit.
    #
    # wb_min_water_frac is chosen over the better-fitting wb_season_deficit_mm
    # for two reasons. It is bounded on [0,1], so it cannot run away when
    # extrapolated, which is the failure mode that ruined the tree estimator.
    # And it correlates -0.484 with EDD rather than +0.789, so the heat and
    # water channels stay separable: adding the deficit instead drives the EDD
    # coefficient from -0.084 to -0.018, absorbing the heat signal it is
    # supposed to sit alongside.
    SR = ("yield_anom ~ season_gdd + season_edd + wb_min_water_frac "
          "+ win_prcp_mm + I(win_prcp_mm**2) + C(fips5)")
    sr = smf.ols(SR, data=d0).fit(cov_type="cluster", cov_kwds={"groups": d0.fips5})
    d0 = d0.assign(pred_sr=sr.predict(d0).values)
    print(f"[20] Schlenker-Roberts + water balance  R2 : {sr.rsquared:.3f}  "
          f"(n={int(sr.nobs):,})")
    for term, unit in [("season_edd", "per degree-day above 30 C"),
                       ("wb_min_water_frac", "per unit of soil water fraction"),
                       ("season_gdd", "per degree-day 10-30 C")]:
        print(f"[20]   {term:18} {sr.params[term]:+.4f} bu/acre {unit:32} "
              f"(p={sr.pvalues[term]:.2g})")

    # the two specification choices, recorded rather than asserted
    r_ev = float(np.corrcoef(d0.season_edd, d0.win_vpd_mean)[0, 1])
    r_ew = float(np.corrcoef(d0.season_edd, d0.wb_min_water_frac)[0, 1])
    r_ed = float(np.corrcoef(d0.season_edd, d0.wb_season_deficit_mm)[0, 1])
    with_v = smf.ols(SR.replace("season_edd", "season_edd + win_vpd_mean"),
                     data=d0).fit(cov_type="cluster", cov_kwds={"groups": d0.fips5})
    with_d = smf.ols(SR.replace("wb_min_water_frac", "wb_season_deficit_mm"),
                     data=d0).fit(cov_type="cluster", cov_kwds={"groups": d0.fips5})
    print(f"[20] VPD omitted: corr(EDD,VPD)={r_ev:+.3f} and adding it gives "
          f"{with_v.params['win_vpd_mean']:+.2f} bu/acre per kPa, the wrong sign")
    print(f"[20] water term: min_water_frac corr(EDD)={r_ew:+.3f} keeps EDD at "
          f"{sr.params['season_edd']:+.4f}; the better-fitting season_deficit "
          f"corr(EDD)={r_ed:+.3f} drives EDD to "
          f"{with_d.params['season_edd']:+.4f} (R2 {with_d.rsquared:.3f}) and "
          f"absorbs the heat channel")

    obs_edd_max = float(d0.season_edd.max())
    mean_yield = float(d0.yield_bu_ac.mean())
    print(f"[20] observed season EDD range : 0 - {obs_edd_max:.0f}")

    MODELS = sorted(dl.model.unique())
    combos = [(s, h) for s in sorted(dl.scenario.unique())
              for h in sorted(dl.horizon.unique())]
    print(f"[20] running {len(MODELS)} models x {len(combos)} scenario-horizons "
          f"= {len(MODELS)*len(combos)} phenology rebuilds", flush=True)

    per_model, pheno_rows = [], []
    for scen, hz in combos:
        for mod in MODELS:
            sub = dl[(dl.model == mod) & (dl.scenario == scen) & (dl.horizon == hz)]
            if sub.empty:
                continue
            pert = P.add_daily_terms(perturb_daily(daily, sub), lat)
            fx, _ = P.build_features(pert, taw)
            j = d0[["fips5", "year", "county", "yield_bu_ac",
                    "pred_gbm", "pred_sr"]].merge(fx, on=["fips5", "year"], how="inner")
            dg = gbm.predict(j[PROC_F]) - j.pred_gbm.values
            ds = sr.predict(j).values - j.pred_sr.values
            b = d0.set_index(["fips5", "year"])
            shift_r6 = float(j.set_index(["fips5", "year"]).r6_doy.sub(b.r6_doy).mean())
            shift_sf = float(j.set_index(["fips5", "year"]).seedfill_days
                             .sub(b.seedfill_days).mean())
            oor = float((j.season_edd > obs_edd_max).mean() * 100)
            per_model.append(dict(
                scenario=scen, horizon=hz, model=mod,
                delta_gbm=float(dg.mean()), delta_sr=float(ds.mean()),
                edd_mean=float(j.season_edd.mean()),
                edd_ratio=float(j.season_edd.mean() / d0.season_edd.mean()),
                out_of_range_pct=oor,
                r6_shift_days=shift_r6, seedfill_shift_days=shift_sf,
                dTmax_JA_C=float(sub[sub.month.isin([7, 8])].d_tasmax_C.mean())))
            pheno_rows.append(dict(scenario=scen, horizon=hz, model=mod,
                                   r6_shift=shift_r6, seedfill_shift=shift_sf))
            print(f"[20] {scen} {hz:12} {mod:15} "
                  f"R6 {shift_r6:+5.1f}d  seedfill {shift_sf:+5.1f}d  "
                  f"EDD x{j.season_edd.mean()/d0.season_edd.mean():4.1f}  "
                  f"SR {ds.mean():+6.2f}  GBM {dg.mean():+6.2f}", flush=True)

    PM = pd.DataFrame(per_model)
    PM.round(4).to_csv(RES / "table22_pheno_scenario_model_spread.csv", index=False)

    # ---- headline table, with the CO2 layer made explicit ------------------
    rows = []
    for (scen, hz), g in PM.groupby(["scenario", "horizon"]):
        ppm = CO2[(scen, hz)]
        sr_med = float(np.median(g.delta_sr))
        rec = dict(scenario=scen, horizon=hz, n_models=len(g), co2_ppm=ppm,
                   dTmax_JA_C=g.dTmax_JA_C.mean(),
                   r6_shift_days=g.r6_shift_days.mean(),
                   seedfill_shift_days=g.seedfill_shift_days.mean(),
                   edd_ratio=g.edd_ratio.mean(),
                   out_of_range_pct=g.out_of_range_pct.mean(),
                   climate_gbm_bu=float(np.median(g.delta_gbm)),
                   climate_sr_bu=sr_med,
                   sr_min_bu=g.delta_sr.min(), sr_max_bu=g.delta_sr.max())
        for mode in ["none", "face", "saturating"]:
            gain = (co2_factor(ppm, mode) - 1.0) * mean_yield
            rec[f"co2_{mode}_bu"] = gain
            rec[f"net_{mode}_bu"] = sr_med + gain
        rows.append(rec)
    T = pd.DataFrame(rows).sort_values(["scenario", "horizon"])
    T.round(4).to_csv(RES / "table21_pheno_scenario_summary.csv", index=False)

    print("\n[20] WHAT WARMING DOES TO THE CROP CALENDAR (ensemble mean)")
    print(T[["scenario", "horizon", "dTmax_JA_C", "r6_shift_days",
             "seedfill_shift_days", "edd_ratio", "out_of_range_pct"]]
          .rename(columns={"dTmax_JA_C": "dTmax", "r6_shift_days": "R6_shift",
                           "seedfill_shift_days": "seedfill", "edd_ratio": "EDDx",
                           "out_of_range_pct": "oor_%"}).round(2).to_string(index=False))

    print("\n[20] YIELD EFFECT, bu/acre  (climate, then CO2 as a separate layer)")
    print(T[["scenario", "horizon", "climate_sr_bu", "climate_gbm_bu",
             "co2_none_bu", "co2_face_bu", "co2_saturating_bu",
             "net_none_bu", "net_face_bu", "net_saturating_bu"]]
          .rename(columns={"climate_sr_bu": "clim_SR", "climate_gbm_bu": "clim_GBM",
                           "co2_none_bu": "CO2_none", "co2_face_bu": "CO2_face",
                           "co2_saturating_bu": "CO2_sat", "net_none_bu": "net_none",
                           "net_face_bu": "net_face", "net_saturating_bu": "net_sat"})
          .round(2).to_string(index=False))

    print("\n[20] COMPARISON WITH SCRIPT 13, fixed July-August window, SSP5-8.5 late")
    try:
        old = pd.read_csv(RES / "table11_cmip6_scenario_summary.csv")
        o = old[(old.scenario == "ssp585") & (old.horizon == "late_century")].iloc[0]
        n = T[(T.scenario == "ssp585") & (T.horizon == "late_century")].iloc[0]
        print(f"     script 13 trees      {o.ens_median_delta_bu:+7.2f} bu/acre")
        print(f"     script 13 quadratic  {o.ens_median_parametric_bu:+7.2f}")
        print(f"     script 20 SR climate {n.climate_sr_bu:+7.2f}   (moving window)")
        print(f"     script 20 net, FACE  {n.net_face_bu:+7.2f}   (with CO2)")
    except (FileNotFoundError, IndexError):
        pass

    json.dump(dict(
        method="CMIP6 deltas applied to DAILY weather, phenology recomputed "
               "through _pheno so the crop window moves with the climate",
        estimators=dict(
            schlenker_roberts=SR,
            sr_note="EDD enters linearly; the nonlinearity is in the degree-day "
                    "construction, so extrapolation is a straight line in a "
                    "variable with a physical threshold",
            gbm="gradient boosting on process features; saturates out of range"),
        co2_ppm={f"{k[0]}|{k[1]}": v for k, v in CO2.items()},
        co2_ppm_note="APPROXIMATE round numbers, not the published CMIP6 GHG "
                     "concentration series; replace before quoting",
        co2_response=dict(beta=float(CO2_BETA), reference_ppm=CO2_REF,
                          form="1 + beta * ln(C/C_ref)",
                          calibration="roughly +15% seed yield at 550 ppm, FACE",
                          saturating_cap_ppm=CO2_SATURATE_AT,
                          omitted="CO2 response shrinks under heat and interacts "
                                  "with drought; neither is represented"),
        dewpoint_assumption=DEW_NOTE, precipitation_assumption=PRCP_NOTE,
        observed_season_edd_max=obs_edd_max,
        models=MODELS, runtime_min=round((time.time() - t_start) / 60, 1),
    ), open(RES / "20_pheno_scenario_config.json", "w"), indent=2)

    draw_figures(T)

    print(f"\n[20] runtime {(time.time()-t_start)/60:.1f} min")
    print("[20] wrote table21, table22, fig26, fig27, fig28")


def draw_figures(T):
    """Redraw from the summary table alone, so figures can be adjusted without
    repeating the 32 phenology rebuilds. Run with FIGURES_ONLY=1."""
    # ---------- Figure 26: warming moves and shortens the window ------------
    f, axes = plt.subplots(1, 3, figsize=(13.5, 4.7), dpi=200)
    f.patch.set_facecolor(SURFACE)
    lab = [f"{s.upper()}\n{h.replace('_century','')}"
           for s, h in zip(T.scenario, T.horizon)]
    xp = np.arange(len(T))
    for ax_, (v, yl, col, fmt) in zip(axes, [
            (T.r6_shift_days, "Shift in R6 date (days)", S2, "{:+.1f}"),
            (T.seedfill_shift_days, "Change in seed fill (days)", S1, "{:+.1f}"),
            (T.edd_ratio, "Extreme degree days, multiple of today", S4, "x{:.1f}")]):
        ax_.set_facecolor(SURFACE)
        ax_.bar(xp, v, color=col, width=.58)
        span = max(abs(v.max()), abs(v.min()))
        for i, val in enumerate(v):
            ax_.text(i, val + (0.03 * span * np.sign(val) if val else .02),
                     fmt.format(val), ha="center", fontsize=9.5, color=INK2,
                     va="bottom" if val >= 0 else "top")
        # headroom so the value labels are not clipped by the axis
        lo, hi = min(0, v.min()), max(0, v.max())
        ax_.set_ylim(lo - .18 * span if lo < 0 else 0,
                     hi + .18 * span if hi > 0 else 0)
        ax_.axhline(0, color=INK, lw=1)
        ax_.set_xticks(xp); ax_.set_xticklabels(lab, fontsize=8.5)
        ax_.grid(axis="y", color=GRID, lw=.7); ax_.set_axisbelow(True)
        for s_ in ("top", "right"):
            ax_.spines[s_].set_visible(False)
        ax_.tick_params(colors=MUTED, labelsize=8.5)
        ax_.set_ylabel(yl, fontsize=9.5, color=INK2)
    f.suptitle("Figure 26. Warming moves the crop, not just the weather",
               fontsize=14.5, color=INK, x=.02, ha="left", y=1.06, fontweight="semibold")
    f.text(.02, .975, "Ensemble mean across 8 CMIP6 models. None of this is imposed: "
           "it falls out of recomputing thermal time on perturbed daily weather.",
           fontsize=9.6, color=INK2)
    f.tight_layout(rect=[0, 0, 1, .91])
    f.savefig(FIG / "fig26_warming_moves_the_crop.png", facecolor=SURFACE,
              bbox_inches="tight")
    plt.close(f); print("   figure -> fig26_warming_moves_the_crop.png")

    # ---------- Figure 27: climate loss against CO2 gain --------------------
    f, ax = fig(11, 6.4)
    w = .26
    ax.bar(xp - w, T.climate_sr_bu, w, color=S2, label="climate effect")
    ax.bar(xp, T.co2_face_bu, w, color=S3, label="CO₂ effect, FACE")
    ax.bar(xp + w, T.net_face_bu, w, color=INK, label="net")
    span = max(T.co2_face_bu.max(), abs(T.climate_sr_bu.min()))
    for i in range(len(T)):
        v = T.net_face_bu.iloc[i]
        ax.text(i + w, v + .03 * span * np.sign(v), f"{v:+.1f}", ha="center",
                va="bottom" if v >= 0 else "top", fontsize=9.5, color=INK2)
    ax.set_ylim(min(0, T.climate_sr_bu.min()) - .2 * span,
                max(T.co2_face_bu.max(), T.net_face_bu.max()) + .2 * span)
    ax.axhline(0, color=INK, lw=1.1)
    ax.set_xticks(xp); ax.set_xticklabels(lab, fontsize=9.5)
    style(ax, "Figure 27. The sign of the answer depends on CO₂",
          "Climate effect from the Schlenker-Roberts estimator on a moving crop "
          "window. The CO₂ term is an explicit assumption, not a result: see the "
          "range in Figure 28.",
          None, "Change in yield (bu/acre)", legend=True,
          src="Source: CMIP6 Amon; NASA POWER; USDA NASS; USDA-NRCS SSURGO")
    save(f, FIG / "fig27_climate_vs_co2.png")

    # ---------- Figure 28: how much does the CO2 assumption matter? ---------
    f, ax = fig(11, 6.0)
    for j, (mode, col, nm) in enumerate([("none", S2, "no CO₂ effect"),
                                         ("saturating", S4, "saturating at 550 ppm"),
                                         ("face", S3, "FACE logarithmic")]):
        ax.bar(xp + (j - 1) * .26, T[f"net_{mode}_bu"], .26, color=col, label=nm)
    ax.axhline(0, color=INK, lw=1.1)
    ax.set_xticks(xp); ax.set_xticklabels(lab, fontsize=9.5)
    style(ax, "Figure 28. Three CO₂ assumptions, three different answers",
          "Same climate effect throughout. The spread is the cost of not knowing "
          "the CO₂ response, and script 13 silently assumed the leftmost bar.",
          None, "Net change in yield (bu/acre)", legend=True,
          src="Source: CMIP6 Amon; NASA POWER; FACE meta-analysis")
    save(f, FIG / "fig28_co2_assumption_range.png")


if __name__ == "__main__":
    import os
    if os.environ.get("FIGURES_ONLY"):
        print("[20] FIGURES_ONLY: redrawing from results/table21 ...")
        draw_figures(pd.read_csv(RES / "table21_pheno_scenario_summary.csv"))
    else:
        main()
