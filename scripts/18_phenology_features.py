"""18 - Thermal-time phenology and process-relevant climate features.

This script replaces two assumptions that the rest of the pipeline inherited
without testing, and that break under a changed climate.

  1. THE CRITICAL WINDOW IS NOT JULY AND AUGUST.
     It is R3 to R6, pod set through seed fill. Those stages fall in July and
     August in today's Illinois climate, which is why the fixed window has
     worked so far. Under warming, thermal time accumulates faster: the crop
     reaches R6 EARLIER and seed fill is SHORTER. A fixed calendar window
     cannot represent either effect, so the CMIP6 scenarios in script 13 are
     asking the wrong question. Here the window is derived from accumulated
     thermal time and moves with the crop.

     This also matters for transfer. July and August are winter in Brazil. A
     northern-hemisphere calendar window is not merely suboptimal there, it is
     meaningless. Thermal time is the only formulation that survives the trip.

  2. MONTHLY MEANS ERASE THE EXTREMES THAT DO THE DAMAGE.
     Schlenker & Roberts (2009, PNAS) show soybean yield rising with
     temperature to roughly 30 C and falling steeply above it, with damage
     tracking the distribution of daily temperature rather than its mean.
     Degree days here are integrated with the single-sine method (Snyder 1985)
     over the daily temperature curve, giving GDD(10,30) and EDD(>30)
     separately, exactly the Schlenker-Roberts construction.

Everything derived here is computable from temperature, dewpoint,
precipitation and latitude alone, so it can be reproduced anywhere on earth.

The phenology itself lives in _pheno.py, not here, so that script 20 can run
the IDENTICAL code on CMIP6-perturbed weather. Two implementations meant to
match would eventually stop matching, and the scenario comparison would
quietly lose its meaning.

PARAMETER PROVENANCE, READ THIS BEFORE QUOTING ANY RESULT
  The thermal-time thresholds were CALIBRATED to Illinois crop-progress norms,
  not taken from a paper. The first version of this script used round
  literature numbers for a mid maturity group and produced a 22 April planting
  date and a 29 October maturity, with 22% of county-years never completing
  seed fill. Both are wrong for Illinois.

  The thresholds are instead the median accumulated GDD, over the whole
  1981-2024 record, at the 50%-progress dates USDA NASS publishes for Illinois
  soybean: planting 20 May, blooming 10 July, pod set 28 July, full seed
  ~5 September, maturity ~20 September.

  Two consequences to keep in mind. The stage dates now reproduce the Illinois
  average by construction, so agreement with those norms is not evidence of
  anything. And maturity group varies north to south across the state, while
  one set of thresholds is applied everywhere. Calibrating per county, or
  against observed county phenology, remains undone.

UPDATE, script 24: the dates above were written from MEMORY and never
downloaded, so the description of these thresholds as "calibrated to NASS
norms" overstated what was done. Script 23 has since pulled the real NASS
series and script 24 checked them. The thresholds turned out to be within
about 5% of the observed thermal requirement (blooming 651 GDD, pod setting
883, leaf drop 1504, from observed planting). The larger problems are the
planting rule below, which runs about 15 days early and tracks real planting
poorly (r = 0.18), and that thermal time predicts LATE-season timing worse
than the mean date. Neither has been fixed here.
"""
import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _cfg import RAW, PROC, RES
import _pheno as P


def main():
    print("[18] reading daily weather ...", flush=True)
    d = pd.read_csv(RAW / "power_daily.csv.gz", dtype={"unit_id": str},
                    parse_dates=["date"])
    lat = P.centroid_lat(RAW).set_index("unit_id").lat.to_dict()
    soil = pd.read_csv(PROC / "soil_features.csv", dtype={"fips5": str})
    # soil_aws_0_100cm is cm of plant-available water in the top metre -> mm
    taw = (soil.set_index("fips5").soil_aws_0_100cm * 10.0).to_dict()
    print(f"[18] daily rows {len(d):,} | units {d.unit_id.nunique()} | "
          f"soil for {len(taw)} units")

    d = P.add_daily_terms(d, lat)
    print("[18] daily GDD, EDD, VPD and ET0 computed", flush=True)
    f, skipped = P.build_features(d, taw)
    f.to_csv(PROC / "phenology_features.csv", index=False)

    print(f"\n[18] county-years built : {len(f):,}   skipped {skipped}")
    print(f"[18] counties           : {f.fips5.nunique()}   "
          f"years {f.year.min()}-{f.year.max()}")

    print("\n[18] PHENOLOGY, MEAN DAY OF YEAR ACROSS THE RECORD")
    for c in ["plant_doy", "r1_doy", "r3_doy", "r5_doy", "r6_doy", "r8_doy"]:
        if f[c].notna().any():
            when = pd.Timestamp("2001-01-01") + pd.Timedelta(days=f[c].mean() - 1)
            print(f"     {c:10} {f[c].mean():6.1f}   ({when:%d %b})")
    print(f"     {'podfill':10} {f.podfill_days.mean():6.1f} days")
    print(f"     {'seedfill':10} {f.seedfill_days.mean():6.1f} days")

    early, late = f[f.year <= 1990], f[f.year >= 2015]
    print("\n[18] HAS THE WINDOW ALREADY MOVED?  1981-1990 vs 2015-2024")
    for c in ["plant_doy", "r3_doy", "r6_doy", "podfill_days", "seedfill_days"]:
        print(f"     {c:14} {early[c].mean():7.1f} -> {late[c].mean():7.1f}   "
              f"({late[c].mean() - early[c].mean():+.1f})")

    print("\n[18] WINDOW CONDITIONS")
    cols = ["win_gdd", "win_edd", "win_hot_days", "win_vpd_mean", "win_prcp_mm",
            "win_water_deficit_mm", "wb_stress_days", "wb_min_water_frac"]
    print(f[cols].describe().T[["mean", "std", "min", "max"]].round(2).to_string())

    (RES / "18_phenology_config.json").write_text(json.dumps(dict(
        thermal_time=dict(base_c=P.T_BASE, cap_c=P.T_CAP, extreme_c=P.T_EXTREME,
                          method="single sine (Snyder 1985) over the daily curve"),
        stages_gdd_from_planting=P.STAGES,
        stages_note="written from remembered NASS 50%-progress dates, NOT downloaded "
                    "data; checked in script 24 against the real series and found "
                    "within about 5% of the observed thermal requirement "
                    "(blooming 651, pod setting 883, leaf drop 1504 GDD from "
                    "observed planting). Late-season timing is not well predicted "
                    "by thermal time; see script 24",
        planting_rule=dict(earliest_doy=P.EARLIEST_DOY, latest_doy=P.LATEST_DOY,
                           temp_c=P.PLANT_TEMP_C,
                           rule="first day with a 7-day mean at or above temp_c"),
        water_balance=dict(kc=P.KC, depletion_fraction=P.DEPLETION_FRACTION,
                           capacity="SSURGO available water, top metre, mm",
                           et0="FAO-56 Penman-Monteith, humidity-responsive; "
                               "Hargreaves retained in _pheno for comparison"),
        county_years=int(len(f)), skipped=int(skipped),
        shared_module="_pheno.py, also used by script 20 for CMIP6 scenarios",
    ), indent=2))
    print("\n[18] -> data/processed/phenology_features.csv")
    print("[18] -> results/18_phenology_config.json")


if __name__ == "__main__":
    main()
