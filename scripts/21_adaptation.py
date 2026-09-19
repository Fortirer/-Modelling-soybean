"""21 - Maturity-group adaptation: what this pipeline can and cannot answer.
Tables 23-25, Figures 29-30.

Every scenario before this one assumes a grower watches R6 arrive up to a month
earlier, every season for seventy-five years, and changes nothing. That is not
a conservative assumption, it is an implausible one.

The standard response is to move to a longer maturity group, spending the extra
thermal time instead of maturing early into an empty autumn. The room exists:
at the current state-average maturity the median county-year reaches R8
fifty-five days before the first killing frost.

THIS SCRIPT DELIBERATELY STOPS SHORT OF PICKING A MATURITY GROUP

  The first version of this script did pick one, and the answer was worthless.
  Predicted yield came out exactly linear in maturity group -- at the baseline
  climate, -5.55, -3.73, -1.88, -0.03, +1.78, +3.65, +5.53 across MG 2.0 to
  5.0, a clean +1.85 per half group. That is nothing but the fitted season_gdd
  coefficient multiplied by the thermal time each half group adds. The
  "optimum" was therefore always the longest variety the frost constraint
  allowed, which is a property of the regression, not of soybean.

  The reason is identification. season_gdd varies in the training data because
  seasons vary, at ONE maturity group. Nothing in the record varies maturity
  group while holding the season fixed, so the coefficient cannot be read as
  "a longer variety yields more". Extrapolating along it manufactures a
  number with no evidence behind it.

  So this script reports the part that IS identified -- what maturity group
  does to phenology, frost exposure and heat exposure, all of which come from
  thermal-time accounting on daily weather and need no yield model -- and
  states plainly that converting those into a yield optimum requires a crop
  model carrying yield potential. That is precisely the argument Peng et al.
  (2020) make for process-based models, and it is where this line of work
  runs out of road.

ENSEMBLE
  Ensemble-median CMIP6 delta across the 8 models. Model spread is carried by
  script 20; the question here is what a variety choice does, not how much the
  climate models disagree.
"""
import sys, json, time
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import statsmodels.formula.api as smf
from _cfg import RAW, PROC, FINAL, RES, FIG
from _viz import *
import _pheno as P

MG_LIST = [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
MIN_MATURE_RATE = 0.90
SR = ("yield_anom ~ season_gdd + season_edd + win_prcp_mm "
      "+ I(win_prcp_mm**2) + C(fips5)")


def perturb_daily(d, med):
    x = d.copy()
    mo = x.date.dt.month.values
    ids = x.unit_id.values
    i = np.arange(len(x))
    t = med.pivot(index="fips5", columns="month", values="d_tas_C")
    tx = med.pivot(index="fips5", columns="month", values="d_tasmax_C")
    pr = med.pivot(index="fips5", columns="month", values="pr_ratio")
    x["tmax_c"] = x.tmax_c + tx.reindex(ids).to_numpy()[i, mo - 1]
    dt = t.reindex(ids).to_numpy()[i, mo - 1]
    x["tmin_c"] = x.tmin_c + dt
    x["tmean_c"] = x.tmean_c + dt
    x["tdew_c"] = x.tdew_c + dt
    x["prcp_mm"] = x.prcp_mm * pr.reindex(ids).to_numpy()[i, mo - 1]
    return x


def main():
    t0 = time.time()
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
    daily = daily[daily.unit_id.isin(set(panel.fips5))].copy()
    print(f"[21] counties {panel.fips5.nunique()} | MG {MG_LIST} | "
          f"stretch {P.FRAC_PER_MG:.0%} per group", flush=True)

    med = (dl.groupby(["scenario", "horizon", "fips5", "month"])
             [["d_tas_C", "d_tasmax_C", "pr_ratio"]].median().reset_index())
    climates = [("baseline", "baseline", None)]
    for s in sorted(dl.scenario.unique()):
        for h in sorted(dl.horizon.unique()):
            climates.append((s, h, med[(med.scenario == s) & (med.horizon == h)]))

    obs = P.add_daily_terms(daily, lat)
    base35, _ = P.build_features(obs, taw, P.stages_for_mg(P.BASELINE_MG))
    d0 = panel.merge(base35, on=["fips5", "year"], how="inner")
    sr = smf.ols(SR, data=d0).fit(cov_type="cluster", cov_kwds={"groups": d0.fips5})
    keep = set(d0.fips5)
    print(f"[21] yield model R2 {sr.rsquared:.3f}  "
          f"GDD {sr.params['season_gdd']:+.5f}  EDD {sr.params['season_edd']:+.5f}")

    recs = []
    for scen, hz, delta in climates:
        dd = obs if delta is None else P.add_daily_terms(perturb_daily(daily, delta), lat)
        for mg in MG_LIST:
            f, _ = P.build_features(dd, taw, P.stages_for_mg(mg))
            j = panel.merge(f, on=["fips5", "year"], how="inner")
            j = j[j.fips5.isin(keep)]
            j = j.assign(pred=sr.predict(j).values)
            recs.append(dict(
                scenario=scen, horizon=hz, mg=mg,
                mature_rate=float(j.matured_before_frost.mean()),
                seedfill=float(j.seedfill_days.mean()),
                podfill=float(j.podfill_days.mean()),
                r6_doy=float(j.r6_doy.mean()), r8_doy=float(j.r8_doy.mean()),
                frost_margin=float(j.days_r8_to_frost.mean()),
                season_edd=float(j.season_edd.mean()),
                win_edd=float(j.win_edd.mean()),
                water_deficit=float(j.wb_season_deficit_mm.mean()),
                pred=float(j.pred.mean())))
            print(f"[21] {scen:9} {hz:12} MG {mg:.1f}  "
                  f"mature {recs[-1]['mature_rate']*100:5.1f}%  "
                  f"seedfill {recs[-1]['seedfill']:5.1f}d  "
                  f"EDD {recs[-1]['season_edd']:6.1f}  "
                  f"pred {recs[-1]['pred']:+6.2f}", flush=True)

    R = pd.DataFrame(recs)
    R.round(4).to_csv(RES / "table24_mg_grid.csv", index=False)

    # ---- 1. the identified part: what a variety choice does physically -----
    print("\n[21] PHENOLOGY AND EXPOSURE BY MATURITY GROUP  (no yield model)")
    for (scen, hz), g in R.groupby(["scenario", "horizon"], sort=False):
        print(f"\n     {scen} {hz}")
        print(g[["mg", "mature_rate", "seedfill", "r8_doy", "frost_margin",
                 "season_edd"]]
              .assign(mature_rate=lambda x: (x.mature_rate * 100).round(1))
              .rename(columns={"mature_rate": "mature_%", "frost_margin": "frost_d"})
              .round(1).to_string(index=False))

    # ---- 2. the frost-constrained ceiling, which needs no yield model ------
    ceil = []
    for (scen, hz), g in R.groupby(["scenario", "horizon"], sort=False):
        ok = g[g.mature_rate >= MIN_MATURE_RATE]
        mx = float(ok.mg.max()) if len(ok) else np.nan
        row = g[g.mg == mx].iloc[0] if len(ok) else g.iloc[0]
        base = g[g.mg == P.BASELINE_MG].iloc[0]
        ceil.append(dict(scenario=scen, horizon=hz, max_viable_mg=mx,
                         seedfill_at_max=row.seedfill,
                         seedfill_at_3_5=base.seedfill,
                         edd_at_max=row.season_edd, edd_at_3_5=base.season_edd,
                         frost_margin_3_5=base.frost_margin,
                         mature_3_5=base.mature_rate))
    C = pd.DataFrame(ceil)
    C.round(4).to_csv(RES / "table23_mg_frost_ceiling.csv", index=False)
    print(f"\n[21] LONGEST MATURITY GROUP MATURING BEFORE FROST IN "
          f">={MIN_MATURE_RATE:.0%} OF YEARS")
    print(C[["scenario", "horizon", "max_viable_mg", "frost_margin_3_5",
             "seedfill_at_3_5", "seedfill_at_max", "edd_at_3_5", "edd_at_max"]]
          .round(1).to_string(index=False))

    # ---- 3. the part that is NOT identified, shown as such -----------------
    lin = R[R.scenario == "baseline"].sort_values("mg")
    step = np.diff(lin.pred.values)
    print("\n[21] WHY THIS SCRIPT DOES NOT PICK A MATURITY GROUP")
    print(f"     predicted yield across MG at the baseline climate: "
          f"{', '.join(f'{v:+.2f}' for v in lin.pred)}")
    print(f"     first differences: {', '.join(f'{v:+.2f}' for v in step)}")
    print(f"     standard deviation of those differences: {step.std():.4f}")
    print("     The response is a straight line in maturity group, because it is")
    print("     the season_gdd coefficient times the thermal time each group adds.")
    print("     season_gdd is identified from seasons varying at ONE maturity")
    print("     group, so it cannot be read as the value of a longer variety.")
    print("     Any optimum from this model is a property of the regression.")

    json.dump(dict(
        mg_list=MG_LIST, baseline_mg=P.BASELINE_MG,
        frac_per_mg=P.FRAC_PER_MG,
        frac_per_mg_note="ASSUMPTION, not calibrated; all MG results scale with it",
        parameterisation="reproductive thresholds scaled away from emergence, so "
                         "stage INTERVALS stretch; an earlier version added a "
                         "constant offset, which shifted the sequence without "
                         "lengthening seed fill and voided the exercise",
        killing_frost_c=P.KILLING_FROST_C, min_mature_rate=MIN_MATURE_RATE,
        ensemble="ensemble-median CMIP6 delta; spread not propagated here",
        model=SR, model_r2=float(sr.rsquared),
        not_identified="predicted yield is linear in maturity group because "
                       "season_gdd is identified from seasons varying at one "
                       "maturity group; no optimum is reported",
        needs="a crop model carrying yield potential, per Peng et al. 2020",
        runtime_min=round((time.time() - t0) / 60, 1),
    ), open(RES / "21_adaptation_config.json", "w"), indent=2)

    # ---------- Figure 29: the physical trade-off ---------------------------
    order = [("baseline", "baseline"), ("ssp245", "mid_century"),
             ("ssp245", "late_century"), ("ssp585", "mid_century"),
             ("ssp585", "late_century")]
    cols = [INK, S1, S3, S4, S2]
    f, axes = plt.subplots(1, 3, figsize=(13.5, 4.8), dpi=200)
    f.patch.set_facecolor(SURFACE)
    panels = [("mature_rate", "Years maturing before frost (%)", 100),
              ("seedfill", "Seed-fill duration (days)", 1),
              ("season_edd", "Extreme degree days >30 °C", 1)]
    for ax_, (col, yl, mult) in zip(axes, panels):
        ax_.set_facecolor(SURFACE)
        for (scen, hz), c in zip(order, cols):
            g = R[(R.scenario == scen) & (R.horizon == hz)].sort_values("mg")
            if g.empty:
                continue
            nm = "today" if scen == "baseline" else f"{scen.upper()} {hz.replace('_century','')}"
            ax_.plot(g.mg, g[col] * mult, color=c, lw=1.8, marker="o", ms=3.6, label=nm)
        if col == "mature_rate":
            ax_.axhline(MIN_MATURE_RATE * 100, color=MUTED, lw=1, ls=":")
        ax_.grid(color=GRID, lw=.7); ax_.set_axisbelow(True)
        for s_ in ("top", "right"):
            ax_.spines[s_].set_visible(False)
        ax_.tick_params(colors=MUTED, labelsize=8.5)
        ax_.set_xlabel("Maturity group", fontsize=9.5, color=INK2)
        ax_.set_ylabel(yl, fontsize=9.5, color=INK2)
    axes[0].legend(frameon=False, fontsize=8.5, labelcolor=INK2, loc="lower left")
    f.suptitle("Figure 29. What a longer variety actually buys, and costs",
               fontsize=14.5, color=INK, x=.02, ha="left", y=1.06, fontweight="semibold")
    f.text(.02, .975, "Thermal-time accounting on daily weather. No yield model is "
           "involved in any of these three panels, so none of it depends on a fitted "
           "coefficient.", fontsize=9.6, color=INK2)
    f.tight_layout(rect=[0, 0, 1, .91])
    f.savefig(FIG / "fig29_mg_tradeoff.png", facecolor=SURFACE, bbox_inches="tight")
    plt.close(f); print("\n   figure -> fig29_mg_tradeoff.png")

    # ---------- Figure 30: the regression is a straight line ---------------
    f, ax = fig(10.5, 6.0)
    for (scen, hz), c in zip(order, cols):
        g = R[(R.scenario == scen) & (R.horizon == hz)].sort_values("mg")
        if g.empty:
            continue
        nm = "today" if scen == "baseline" else f"{scen.upper()} {hz.replace('_century','')}"
        ax.plot(g.mg, g.pred, color=c, lw=1.8, marker="o", ms=4, label=nm)
    style(ax, "Figure 30. Why no maturity group is recommended",
          "Predicted yield is exactly linear in maturity group: it is the season_gdd "
          "coefficient times the thermal time each group adds. The model has never "
          "seen maturity group vary, so it cannot price it.",
          "Maturity group", "Predicted yield anomaly (bu/acre)", legend=True,
          src="Source: NASA POWER; CMIP6 Amon; USDA NASS")
    save(f, FIG / "fig30_mg_not_identified.png")

    print(f"[21] runtime {(time.time()-t0)/60:.1f} min")
    print("[21] wrote table23, table24, fig29, fig30")


if __name__ == "__main__":
    main()
