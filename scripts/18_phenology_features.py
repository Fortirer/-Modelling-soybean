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

PARAMETER PROVENANCE, READ THIS BEFORE QUOTING ANY RESULT
  The thermal-time thresholds below were CALIBRATED to Illinois crop-progress
  norms, not taken from a paper. The first version of this script used round
  literature numbers for a mid maturity group and produced a 22 April planting
  date and a 29 October maturity, with 22% of county-years never completing
  seed fill. Both are wrong for Illinois.

  The thresholds here are instead the median accumulated GDD, over the whole
  1981-2024 record, at the 50%-progress dates USDA NASS publishes for Illinois
  soybean: planting 20 May, blooming 10 July, pod set 28 July, full seed
  ~5 September, maturity ~20 September.

  Two consequences to keep in mind. The stage dates now reproduce the Illinois
  average by construction, so agreement with those norms is not evidence of
  anything. And maturity group varies north to south across the state, while
  one set of thresholds is applied everywhere. Calibrating per county, or
  against observed county phenology, remains undone.
"""
import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _cfg import RAW, PROC, RES

# ---- thermal time, degC-days base 10 capped 30, accumulated from planting ----
# Calibrated to Illinois NASS crop-progress 50% dates; see header. R5 is
# interpolated between the R3 and R6 anchors, having no published 50% date.
STAGES = {"VE": 110, "R1": 610, "R3": 860, "R5": 1110, "R6": 1390, "R8": 1550}
T_BASE, T_CAP, T_EXTREME = 10.0, 30.0, 30.0
HEAT_DAY_C = 34.0                 # "a genuinely hot day" for a simple count

# ---- planting rule ----------------------------------------------------------
# First day on or after EARLIEST with a 7-day mean air temperature at or above
# PLANT_TEMP_C, giving up at LATEST. Rule-based rather than a fixed date so it
# responds to a warming spring and so it can be pointed at another region.
# PLANT_TEMP_C is set so the median planting date lands on the Illinois norm of
# about 20 May; the 7-day mean on that date is 17.0 C in the median year.
EARLIEST_DOY, LATEST_DOY, PLANT_TEMP_C = 121, 175, 15.0

# ---- crop coefficients for the water balance (FAO-56 style, soybean) --------
KC = {"initial": 0.40, "mid": 1.15, "late": 0.50}
DEPLETION_FRACTION = 0.50         # stress begins once half the reservoir is gone


def dd_single_sine(tmin, tmax, threshold):
    """Degree days above `threshold`, integrating a sine fitted to tmin/tmax.

    Snyder (1985). Using the daily curve rather than the daily mean is what
    lets EDD register a hot afternoon inside a mild day, which is precisely
    the signal a monthly mean destroys.
    """
    tmin = np.asarray(tmin, float); tmax = np.asarray(tmax, float)
    amp = (tmax - tmin) / 2.0
    mid = (tmax + tmin) / 2.0
    out = np.zeros_like(mid)

    below = tmax <= threshold                      # never reaches the threshold
    above = tmin >= threshold                      # never drops below it
    out[above] = (mid - threshold)[above]

    part = ~below & ~above                         # crosses it during the day
    if part.any():
        a = amp[part]; m = mid[part]
        a = np.where(a <= 0, 1e-9, a)
        theta = np.arcsin(np.clip((threshold - m) / a, -1.0, 1.0))
        out[part] = ((m - threshold) * (np.pi / 2 - theta)
                     + a * np.cos(theta)) / np.pi
    return np.maximum(out, 0.0)


def svp(t):
    """Saturation vapour pressure, kPa (FAO-56 Tetens)."""
    return 0.6108 * np.exp(17.27 * t / (t + 237.3))


def ra_mj(lat_deg, doy):
    """Extraterrestrial radiation, MJ/m2/day (FAO-56). Needs only latitude."""
    lat = np.radians(lat_deg)
    dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365.0)
    dec = 0.409 * np.sin(2 * np.pi * doy / 365.0 - 1.39)
    ws = np.arccos(np.clip(-np.tan(lat) * np.tan(dec), -1, 1))
    return (24 * 60 / np.pi) * 0.0820 * dr * (
        ws * np.sin(lat) * np.sin(dec) + np.cos(lat) * np.cos(dec) * np.sin(ws))


def et0_hargreaves(tmin, tmax, tmean, lat, doy):
    """Reference ET, mm/day. Temperature and latitude only, so it travels."""
    return np.maximum(0.0023 * ra_mj(lat, doy) * (tmean + 17.8)
                      * np.sqrt(np.maximum(tmax - tmin, 0)) * 0.408, 0.0)


def centroid_lat():
    rows = []
    for line in (RAW / "il_county_boundaries.txt").read_text().splitlines():
        if not line.strip():
            continue
        fips, coords = line.split("|", 1)
        pts = np.array([[float(x) for x in p.split(",")] for p in coords.split()])
        if len(pts) > 1 and np.allclose(pts[0], pts[-1]):
            pts = pts[:-1]
        rows.append(dict(unit_id=fips.strip(), lat=pts[:, 1].mean()))
    return pd.DataFrame(rows)


def main():
    print("[18] reading daily weather ...", flush=True)
    d = pd.read_csv(RAW / "power_daily.csv.gz", dtype={"unit_id": str},
                    parse_dates=["date"])
    lat = centroid_lat().set_index("unit_id").lat.to_dict()

    soil = pd.read_csv(PROC / "soil_features.csv", dtype={"fips5": str})
    # soil_aws_0_100cm is cm of plant-available water in the top metre -> mm
    taw = (soil.set_index("fips5").soil_aws_0_100cm * 10.0).to_dict()
    print(f"[18] daily rows {len(d):,} | units {d.unit_id.nunique()} | "
          f"soil for {len(taw)} units")

    # ---- daily derived quantities, vectorised over the whole record ---------
    d["gdd"] = dd_single_sine(d.tmin_c, d.tmax_c, T_BASE) \
             - dd_single_sine(d.tmin_c, d.tmax_c, T_CAP)
    d["edd"] = dd_single_sine(d.tmin_c, d.tmax_c, T_EXTREME)
    d["hot_day"] = (d.tmax_c >= HEAT_DAY_C).astype(int)
    es = (svp(d.tmax_c) + svp(d.tmin_c)) / 2.0
    d["vpd"] = np.maximum(es - svp(d.tdew_c), 0.0)
    d["lat"] = d.unit_id.map(lat)
    d["et0"] = et0_hargreaves(d.tmin_c, d.tmax_c, d.tmean_c, d.lat, d.doy)
    print("[18] daily GDD, EDD, VPD and ET0 computed", flush=True)

    d = d.sort_values(["unit_id", "date"]).reset_index(drop=True)
    rows, skipped = [], 0

    for (uid, yr), g in d.groupby(["unit_id", "year"], sort=True):
        g = g.reset_index(drop=True)
        if len(g) < 300:
            skipped += 1
            continue

        # ---- planting date: 7-day running mean crosses the threshold --------
        run = g.tmean_c.rolling(7, min_periods=7).mean()
        win = g[(g.doy >= EARLIEST_DOY) & (g.doy <= LATEST_DOY)].index
        hit = [i for i in win if run.iloc[i] >= PLANT_TEMP_C]
        plant_i = hit[0] if hit else (win[len(win) // 2] if len(win) else None)
        if plant_i is None:
            skipped += 1
            continue
        plant_doy = int(g.doy.iloc[plant_i])

        # ---- accumulate thermal time from planting --------------------------
        gdd_cum = g.gdd.iloc[plant_i:].cumsum().values
        idx = np.arange(plant_i, len(g))

        def stage_i(target):
            """Row index where cumulative GDD first reaches `target`."""
            k = np.searchsorted(gdd_cum, target)
            return int(idx[k]) if k < len(idx) else None

        si = {s: stage_i(v) for s, v in STAGES.items()}
        if si["R6"] is None:          # season never completes seed fill
            skipped += 1
            continue

        # ---- the yield-setting window: R3 to R6 -----------------------------
        a, b = si["R3"], si["R6"]
        if a is None:
            skipped += 1
            continue
        w = g.iloc[a:b + 1]

        # ---- daily bucket water balance over the whole season ---------------
        cap = taw.get(uid, np.nan)
        stress_days = np.nan; min_frac = np.nan; deficit = np.nan
        if np.isfinite(cap) and cap > 0:
            s = g.iloc[plant_i:b + 1]
            kc = np.where(s.index.values < si.get("R1", a), KC["initial"],
                          np.where(s.index.values <= b, KC["mid"], KC["late"]))
            W = cap                       # start the season at field capacity
            fr, st, dfc = [], 0, 0.0
            thr = DEPLETION_FRACTION * cap
            for p, e0, k in zip(s.prcp_mm.values, s.et0.values, kc):
                ks = 1.0 if W >= thr else max(W / thr, 0.0)
                eta = e0 * k * ks
                W = min(cap, max(0.0, W + p - eta))
                fr.append(W / cap)
                if ks < 1.0:
                    st += 1
                dfc += (e0 * k) - eta     # unmet demand
            in_window = len(s) - (b - a + 1)
            fr = np.array(fr)
            stress_days = int(np.sum(fr[in_window:] < DEPLETION_FRACTION))
            min_frac = float(fr[in_window:].min()) if len(fr[in_window:]) else np.nan
            deficit = float(dfc)

        rows.append(dict(
            fips5=uid, year=int(yr),
            plant_doy=plant_doy,
            r1_doy=int(g.doy.iloc[si["R1"]]) if si["R1"] else np.nan,
            r3_doy=int(g.doy.iloc[a]), r5_doy=int(g.doy.iloc[si["R5"]]) if si["R5"] else np.nan,
            r6_doy=int(g.doy.iloc[b]),
            r8_doy=int(g.doy.iloc[si["R8"]]) if si["R8"] else np.nan,
            podfill_days=int(b - a + 1),
            seedfill_days=int(b - si["R5"] + 1) if si["R5"] else np.nan,
            season_days=int(b - plant_i + 1),
            # --- conditions inside the moving R3-R6 window -------------------
            win_gdd=float(w.gdd.sum()), win_edd=float(w.edd.sum()),
            win_hot_days=int(w.hot_day.sum()),
            win_vpd_mean=float(w.vpd.mean()), win_vpd_max=float(w.vpd.max()),
            win_prcp_mm=float(w.prcp_mm.sum()), win_et0_mm=float(w.et0.sum()),
            win_tmax_mean=float(w.tmax_c.mean()),
            win_water_deficit_mm=float(w.et0.sum() - w.prcp_mm.sum()),
            # --- whole season ------------------------------------------------
            season_gdd=float(g.gdd.iloc[plant_i:b + 1].sum()),
            season_edd=float(g.edd.iloc[plant_i:b + 1].sum()),
            season_prcp_mm=float(g.prcp_mm.iloc[plant_i:b + 1].sum()),
            # --- water balance -----------------------------------------------
            wb_stress_days=stress_days, wb_min_water_frac=min_frac,
            wb_season_deficit_mm=deficit,
        ))

    f = pd.DataFrame(rows)
    f.to_csv(PROC / "phenology_features.csv", index=False)
    print(f"\n[18] county-years built : {len(f):,}   skipped {skipped}")
    print(f"[18] counties           : {f.fips5.nunique()}   years {f.year.min()}-{f.year.max()}")

    print("\n[18] PHENOLOGY, MEAN DAY OF YEAR ACROSS THE RECORD")
    for c in ["plant_doy", "r1_doy", "r3_doy", "r5_doy", "r6_doy", "r8_doy"]:
        if f[c].notna().any():
            print(f"     {c:10} {f[c].mean():6.1f}   "
                  f"({pd.Timestamp('2001-01-01') + pd.Timedelta(days=f[c].mean()-1):%d %b})")
    print(f"     {'podfill':10} {f.podfill_days.mean():6.1f} days")
    print(f"     {'seedfill':10} {f.seedfill_days.mean():6.1f} days")

    # has the window already moved over the record?
    early = f[f.year <= 1990]; late = f[f.year >= 2015]
    print("\n[18] HAS THE WINDOW ALREADY MOVED?  1981-1990 vs 2015-2024")
    for c in ["plant_doy", "r3_doy", "r6_doy", "podfill_days", "seedfill_days"]:
        print(f"     {c:14} {early[c].mean():7.1f} -> {late[c].mean():7.1f}   "
              f"({late[c].mean()-early[c].mean():+.1f})")

    print("\n[18] WINDOW CONDITIONS")
    cols = ["win_gdd", "win_edd", "win_hot_days", "win_vpd_mean", "win_prcp_mm",
            "win_water_deficit_mm", "wb_stress_days", "wb_min_water_frac"]
    print(f[cols].describe().T[["mean", "std", "min", "max"]].round(2).to_string())

    (RES / "18_phenology_config.json").write_text(json.dumps(dict(
        thermal_time=dict(base_c=T_BASE, cap_c=T_CAP, extreme_c=T_EXTREME,
                          method="single sine (Snyder 1985) over the daily curve"),
        stages_gdd_from_planting=STAGES,
        stages_note="UNCALIBRATED literature values for a mid maturity group; "
                    "an explicit assumption, not a fitted result",
        planting_rule=dict(earliest_doy=EARLIEST_DOY, latest_doy=LATEST_DOY,
                           temp_c=PLANT_TEMP_C,
                           rule="first day with a 7-day mean at or above temp_c"),
        water_balance=dict(kc=KC, depletion_fraction=DEPLETION_FRACTION,
                           capacity="SSURGO available water, top metre, mm",
                           et0="Hargreaves, temperature and latitude only"),
        county_years=int(len(f)), skipped=int(skipped),
        transferable="every quantity derives from temperature, dewpoint, "
                     "precipitation and latitude, so the same code runs on "
                     "Brazilian municipalities",
    ), indent=2))
    print("\n[18] -> data/processed/phenology_features.csv")
    print("[18] -> results/18_phenology_config.json")


if __name__ == "__main__":
    main()
