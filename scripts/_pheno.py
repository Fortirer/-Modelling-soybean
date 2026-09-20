"""Shared thermal-time phenology and process-based climate features.

Extracted from script 18 so that script 20 can run the IDENTICAL code on
CMIP6-perturbed weather. If the scenario path and the observed path ever
diverge, the comparison between them stops meaning anything, so they share one
implementation rather than two that are meant to match.

Calibration provenance. Every constant below marked OBSERVED comes from the real
NASS Quick Stats crop-progress series pulled by script 23 and analysed in scripts
24 and 25. An earlier version of this module used dates written from memory and
described them as calibrated; that description was wrong and is corrected here.
One set of thresholds is applied statewide although maturity group varies, and
NASS publishes no district or county progress, so county-level timing has never
been validated.
"""
import numpy as np, pandas as pd

# thermal time, degC-days base 10 capped 30, accumulated from planting.
#   R1, R3, R7  OBSERVED: median GDD from each year's observed planting date to
#               the observed 50% dates for blooming, setting pods and dropping
#               leaves (script 24), 1981-2024. NASS blooming ~ R1-R2, setting
#               pods ~ R3-R4, dropping leaves ~ R7.
#   VE, R5, R6, R8  NOT validated. NASS has no counterpart. Retained only because
#               script 21 (maturity groups) needs a thermal-time R8 and frost
#               comparison, and because R5/R6 feed the legacy seed-fill columns.
STAGES = {"VE": 110, "R1": 651, "R3": 883, "R5": 1110, "R6": 1390,
          "R7": 1504, "R8": 1550}
T_BASE, T_CAP, T_EXTREME = 10.0, 30.0, 30.0
HEAT_DAY_C = 34.0

# ---- the yield window -------------------------------------------------------
# The yield window runs from R3 (pod set) to R7 (the end of seed dry-matter
# accumulation). Thermal time predicts LATE-season timing worse than the average
# date does (script 24: given observed planting, RMSE 19.5 days for leaf drop
# against an observed sd of 4.8), and soybean maturity is partly photoperiod-
# controlled, so NEITHER end is taken from thermal-time thresholds. Each is an
# empirical regression on the observed NASS record:
#
#     start_doy = a_start + b_start * (driver - county baseline mean)   ~ pod setting
#     end_doy   = a_end   + b_end   * (driver - county baseline mean)   ~ leaf drop
#
# a_* are the observed mean dates; b_* are how far each date moves per unit of
# driver anomaly, fitted on the 41 years with both observations (script 25). The
# anomaly is relative to each COUNTY's own baseline mean, so the north-south
# gradient in thermal time is not misread as a maturity gradient (NASS publishes no
# county maturity data that could justify one). The price: every county's average
# window sits on the same dates.
#
# Why the start is empirical too. Thermal R3 uses one statewide GDD threshold,
# which arrives absurdly late in cool northern county-years (as late as day 285),
# leaving windows of 2 to 8 days. Anchoring the start removes that.
#
# Two drivers, both always defined for every county-year:
#   "r3"   the thermal-time R3 date, the stage validated against NASS (bias -0.9 d,
#          r = 0.67). DEFAULT.
#   "gdd"  GDD accumulated from 1 May to 15 September, independent of the planting
#          rule. A sensitivity.
# The record cannot tell them apart historically (both beat the plain average leaf-
# drop date by about 10%), but they extrapolate differently, so scenarios report
# both. They AGREE on the sign of the window-length response, which is the finding
# that matters:
#
#   window length responds to the driver by -0.22 +/- 0.06 days per day of R3
#   anomaly (p < 0.001), or +0.0097 +/- 0.0049 days per GDD (p = 0.055), i.e. WARM
#   seasons advance pod set MORE than they advance maturity, so the window gets
#   slightly LONGER, not shorter. The earlier thermal-time result that warming
#   shortens seed fill came from thermal-time maturity, which the record rejects.
#
# These are WEATHER-DRIVEN INTERANNUAL slopes at today's level of adaptation, and
# the scenarios extrapolate them to far more warming than the record contains.
#
# WINDOW_FIT[driver] = {"start": (intercept, slope), "end": (intercept, slope)}
WINDOW_FIT = {
    "r3":  {"start": (213.3743, 0.49089), "end": (262.5674, 0.26635)},
    "gdd": {"start": (213.3832, -0.03038), "end": (262.5456, -0.02063)},
}
END_DRIVER = "r3"
GDD_WINDOW_DOY = (121, 258)              # 1 May to 15 September, for the "gdd" driver

# ---- maturity group --------------------------------------------------------
# STAGES is calibrated to the Illinois state average, treated here as MG 3.5.
#
# A longer maturity group STRETCHES the reproductive period, it does not merely
# postpone it. An earlier version of this function added a constant offset to
# every reproductive threshold, which slid the whole R1-R8 sequence later while
# leaving R5 to R6 exactly as long: seed-fill duration came out identical for
# every maturity group, which is wrong and quietly voided the point of the
# exercise. Thresholds are therefore scaled away from emergence, so the
# intervals between stages grow with the group.
#
# FRAC_PER_MG is an ASSUMPTION, not a calibration. Nothing in this repo fits
# it, and every maturity-group result scales with it.
BASELINE_MG = 3.5
FRAC_PER_MG = 0.08

# first autumn day at or below this kills the crop; soybean is usually taken
# as about -2.2 C (28 F), below which pods stop filling
KILLING_FROST_C = -2.2


def stages_for_mg(mg):
    """Thermal-time thresholds for a maturity group, stretched from emergence."""
    scale = 1.0 + (mg - BASELINE_MG) * FRAC_PER_MG
    ve = STAGES["VE"]
    return {k: (v if k == "VE" else ve + (v - ve) * scale)
            for k, v in STAGES.items()}

# planting: first day on or after EARLIEST with a 7-day mean at or above
# PLANT_TEMP_C. Rule-based, so a warmer spring plants earlier on its own.
#
# PLANT_TEMP_C is ANCHORED to the observed state mean planting date, 141.7 (21
# May), not chosen on agronomic grounds. At 19 C the modelled mean bias is -1.4
# days; the old 15 C threshold planted 15.5 days early. A 19 C running mean is not
# a physiological planting threshold, since real planting is limited by field
# workability, so treat it as a statistical device. It also improved year-to-year
# skill (r = 0.45 against 0.26 at 15 C), but that is still weak.
EARLIEST_DOY, LATEST_DOY, PLANT_TEMP_C = 121, 175, 19.0

# water balance
KC = {"initial": 0.40, "mid": 1.15, "late": 0.50}
DEPLETION_FRACTION = 0.50


def dd_single_sine(tmin, tmax, threshold):
    """Degree days above `threshold`, integrating a sine fitted to tmin/tmax.

    Snyder (1985). Using the daily curve rather than the daily mean is what
    lets EDD register a hot afternoon inside an otherwise mild day, the signal
    a monthly mean destroys.
    """
    tmin = np.asarray(tmin, float); tmax = np.asarray(tmax, float)
    amp = (tmax - tmin) / 2.0
    mid = (tmax + tmin) / 2.0
    out = np.zeros_like(mid)
    below = tmax <= threshold
    above = tmin >= threshold
    out[above] = (mid - threshold)[above]
    part = ~below & ~above
    if part.any():
        a = np.where(amp[part] <= 0, 1e-9, amp[part])
        m = mid[part]
        theta = np.arcsin(np.clip((threshold - m) / a, -1.0, 1.0))
        out[part] = ((m - threshold) * (np.pi / 2 - theta)
                     + a * np.cos(theta)) / np.pi
    return np.maximum(out, 0.0)


def svp(t):
    """Saturation vapour pressure, kPa (FAO-56 Tetens)."""
    return 0.6108 * np.exp(17.27 * t / (t + 237.3))


def inv_svp(e):
    """Dewpoint, degC, from actual vapour pressure in kPa. Inverse of svp."""
    x = np.log(np.maximum(e, 1e-6) / 0.6108)
    return 237.3 * x / (17.27 - x)


def rh_from_dewpoint(tmin, tmax, tdew):
    """Relative humidity, %, against the mean of the daily saturation curve."""
    es = (svp(tmax) + svp(tmin)) / 2.0
    return np.clip(svp(tdew) / es * 100.0, 1.0, 100.0)


def dewpoint_from_rh(tmin, tmax, rh):
    """Dewpoint implied by a relative humidity and a daily temperature range."""
    es = (svp(tmax) + svp(tmin)) / 2.0
    return inv_svp(np.clip(rh, 1.0, 100.0) / 100.0 * es)


def ra_mj(lat_deg, doy):
    """Extraterrestrial radiation, MJ/m2/day (FAO-56). Latitude and day only."""
    lat = np.radians(lat_deg)
    dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365.0)
    dec = 0.409 * np.sin(2 * np.pi * doy / 365.0 - 1.39)
    ws = np.arccos(np.clip(-np.tan(lat) * np.tan(dec), -1, 1))
    return (24 * 60 / np.pi) * 0.0820 * dr * (
        ws * np.sin(lat) * np.sin(dec) + np.cos(lat) * np.cos(dec) * np.sin(ws))


def et0_hargreaves(tmin, tmax, tmean, lat, doy):
    """Reference ET, mm/day, from temperature and latitude only.

    Kept as the fallback and for comparison. It is blind to humidity, which is
    why it cannot be the main estimator here: the whole point of pulling CMIP6
    relative humidity is that declining RH raises evaporative demand, and
    Hargreaves cannot see that.
    """
    return np.maximum(0.0023 * ra_mj(lat, doy) * (tmean + 17.8)
                      * np.sqrt(np.maximum(tmax - tmin, 0)) * 0.408, 0.0)


# FAO-56 defaults. Wind is not in the POWER pull, and FAO-56 sanctions 2 m/s
# where no measurement exists. Elevation is a single Illinois value; ET0 is
# only weakly sensitive to it through atmospheric pressure.
DEFAULT_U2, DEFAULT_ELEV_M = 2.0, 200.0
SIGMA = 4.903e-9          # Stefan-Boltzmann, MJ K^-4 m^-2 day^-1
ALBEDO = 0.23             # reference grass
KRS = 0.16                # interior-location coefficient for estimating Rs


def et0_penman_monteith(tmin, tmax, tmean, tdew, srad, lat, doy,
                        elev=DEFAULT_ELEV_M, u2=DEFAULT_U2):
    """FAO-56 Penman-Monteith reference ET, mm/day.

    Unlike Hargreaves this responds to humidity, so a projected fall in relative
    humidity raises evaporative demand and feeds through the water balance.
    That is the mechanistically right channel for vapour pressure deficit to
    affect yield, and it avoids entering VPD as a second regressor alongside
    EDD, which the two are far too collinear to support.

    Where solar radiation is missing -- POWER has no ALLSKY before 1984 -- Rs is
    estimated from the diurnal temperature range by the FAO-56 fallback.
    """
    tmin = np.asarray(tmin, float); tmax = np.asarray(tmax, float)
    tmean = np.asarray(tmean, float); tdew = np.asarray(tdew, float)
    lat = np.asarray(lat, float); doy = np.asarray(doy, float)
    ra = ra_mj(lat, doy)

    rs = np.asarray(srad, float) if srad is not None else np.full_like(ra, np.nan)
    est = KRS * np.sqrt(np.maximum(tmax - tmin, 0)) * ra
    rs = np.where(np.isfinite(rs), rs, est)
    rs = np.minimum(rs, 0.85 * ra)                   # clear-sky ceiling

    es = (svp(tmax) + svp(tmin)) / 2.0
    ea = np.minimum(svp(tdew), es)                   # cannot exceed saturation
    delta = 4098.0 * svp(tmean) / (tmean + 237.3) ** 2
    press = 101.3 * ((293.0 - 0.0065 * elev) / 293.0) ** 5.26
    gamma = 0.000665 * press

    rso = (0.75 + 2e-5 * elev) * ra
    frac = np.clip(rs / np.where(rso > 0, rso, np.nan), 0.25, 1.0)
    rnl = (SIGMA * ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2.0
           * (0.34 - 0.14 * np.sqrt(np.maximum(ea, 0)))
           * (1.35 * frac - 0.35))
    rn = (1 - ALBEDO) * rs - rnl

    num = 0.408 * delta * rn + gamma * (900.0 / (tmean + 273.0)) * u2 * (es - ea)
    den = delta + gamma * (1 + 0.34 * u2)
    return np.maximum(num / den, 0.0)


def add_daily_terms(d, lat_map):
    """Attach the daily derived quantities, vectorised over the whole record."""
    d = d.copy()
    d["gdd"] = (dd_single_sine(d.tmin_c, d.tmax_c, T_BASE)
                - dd_single_sine(d.tmin_c, d.tmax_c, T_CAP))
    d["edd"] = dd_single_sine(d.tmin_c, d.tmax_c, T_EXTREME)
    d["hot_day"] = (d.tmax_c >= HEAT_DAY_C).astype(int)
    es = (svp(d.tmax_c) + svp(d.tmin_c)) / 2.0
    d["vpd"] = np.maximum(es - svp(d.tdew_c), 0.0)
    if "lat" not in d:
        d["lat"] = d.unit_id.map(lat_map)
    d["et0"] = et0_penman_monteith(d.tmin_c, d.tmax_c, d.tmean_c, d.tdew_c,
                                   d.srad_mj if "srad_mj" in d else None,
                                   d.lat, d.doy)
    d["et0_hargreaves"] = et0_hargreaves(d.tmin_c, d.tmax_c, d.tmean_c, d.lat, d.doy)
    return d


def _plant_index(g):
    """Row of the planting date under the temperature rule, or None."""
    run = g.tmean_c.rolling(7, min_periods=7).mean()
    win = g.index[(g.doy >= EARLIEST_DOY) & (g.doy <= LATEST_DOY)]
    hit = [i for i in win if run.iloc[i] >= PLANT_TEMP_C]
    return hit[0] if hit else (win[len(win) // 2] if len(win) else None)


def _driver_value(g, plant_i, driver, r3_gdd):
    """The end-of-window driver for one county-year, always defined.

    "r3"  day of year at which thermal time from planting reaches the R3
          threshold; "gdd"  GDD accumulated over GDD_WINDOW_DOY.
    """
    if driver == "gdd":
        lo, hi = GDD_WINDOW_DOY
        return float(g.gdd[(g.doy >= lo) & (g.doy <= hi)].sum())
    cum = g.gdd.iloc[plant_i:].cumsum().values
    k = int(np.searchsorted(cum, r3_gdd))
    return float(g.doy.iloc[plant_i + k]) if k < len(cum) else np.nan


def county_baseline(d, driver=None, stages=None):
    """Mean end-of-window driver per county under the supplied weather.

    Scenario runs must be measured against the OBSERVED-climate baseline, not
    against their own mean, or warming would cancel itself out of the anomaly.
    Call this once on observed weather and pass the result to build_features.
    """
    driver = driver or END_DRIVER
    r3_gdd = (stages or STAGES)["R3"]
    vals = {}
    for (uid, yr), g in d.sort_values(["unit_id", "date"]).groupby(["unit_id", "year"]):
        if len(g) < 300:
            continue
        g = g.reset_index(drop=True)
        pi = _plant_index(g)
        if pi is None:
            continue
        x = _driver_value(g, pi, driver, r3_gdd)
        if np.isfinite(x):
            vals.setdefault(uid, []).append(x)
    return {u: float(np.mean(v)) for u, v in vals.items()}


def build_features(d, taw, stages=None, end_rule="empirical", driver=None,
                   baseline=None):
    """One row per unit-year: phenology, window conditions, water balance.

    `d` must already carry the daily terms from add_daily_terms.
    `taw` maps unit_id -> total available water in the top metre, mm.
    `stages` overrides the thermal-time thresholds, for maturity-group work;
    it defaults to the observed-calibrated Illinois thresholds.

    `end_rule` chooses how the yield window ends.
      "empirical"  the default: BOTH ends of the window are regressions on the
                   observed NASS record, moved by the driver's anomaly from the
                   county's baseline mean. See WINDOW_FIT and the notes above it.
      "thermal"    the legacy rule, R3 to thermal-time R6. Retained ONLY for script
                   21, whose frost and maturity-group arithmetic needs thermal-time
                   maturity, and because script 24 showed it to be unreliable for
                   late-season timing. Do not use it for inference about when the
                   window ends.
    `driver` is "r3" (default) or "gdd". `baseline` maps unit_id to the county's
    mean driver under OBSERVED weather; computed from `d` itself when omitted,
    which is right for observed runs and WRONG for scenario runs.

    Also returns the autumn killing-frost date and whether the crop reached R8
    before it. Under a longer maturity group the crop can simply run out of
    season, which is the constraint that stops "plant a longer variety" from
    being a free adaptation.
    """
    stages = stages or STAGES
    driver = driver or END_DRIVER
    if end_rule == "empirical" and baseline is None:
        baseline = county_baseline(d, driver, stages)
    d = d.sort_values(["unit_id", "date"])
    rows, skipped = [], 0

    for (uid, yr), g in d.groupby(["unit_id", "year"], sort=True):
        g = g.reset_index(drop=True)
        if len(g) < 300:
            skipped += 1
            continue

        # first killing frost after midsummer; NaN if the year never gets one
        autumn = g[(g.doy > 200) & (g.tmin_c <= KILLING_FROST_C)]
        frost_doy = int(autumn.doy.iloc[0]) if len(autumn) else np.nan

        plant_i = _plant_index(g)
        if plant_i is None:
            skipped += 1
            continue

        gdd_cum = g.gdd.iloc[plant_i:].cumsum().values
        idx = np.arange(plant_i, len(g))

        def stage_i(target):
            k = np.searchsorted(gdd_cum, target)
            return int(idx[k]) if k < len(idx) else None

        si = {s: stage_i(v) for s, v in stages.items()}
        a = si["R3"]                    # thermal R3, used in legacy mode and reported
        driver_x = np.nan
        if end_rule == "thermal":
            b = si["R6"]
        else:
            driver_x = _driver_value(g, plant_i, driver, stages["R3"])
            if not np.isfinite(driver_x) or uid not in baseline:
                a = b = None
            else:
                anom = driver_x - baseline[uid]
                (a0, a1), (b0, b1) = WINDOW_FIT[driver]["start"], WINDOW_FIT[driver]["end"]
                a = int(np.searchsorted(g.doy.values, round(a0 + a1 * anom)))
                a = min(max(a, plant_i + 1), len(g) - 2)
                b = int(np.searchsorted(g.doy.values, round(b0 + b1 * anom)))
                b = min(max(b, a + 1), len(g) - 1)      # never before the start
        if a is None or b is None:
            skipped += 1
            continue
        w = g.iloc[a:b + 1]

        r8_doy = g.doy.iloc[si["R8"]] if si["R8"] is not None else np.nan
        matured = bool(np.isfinite(frost_doy) and np.isfinite(r8_doy)
                       and r8_doy <= frost_doy)

        cap = taw.get(uid, np.nan)
        stress_days = min_frac = deficit = np.nan
        if np.isfinite(cap) and cap > 0:
            s = g.iloc[plant_i:b + 1]
            r1 = si.get("R1") or a
            kc = np.where(s.index.values < r1, KC["initial"], KC["mid"])
            W, thr = cap, DEPLETION_FRACTION * cap
            fr, dfc = [], 0.0
            for p, e0, k in zip(s.prcp_mm.values, s.et0.values, kc):
                ks = 1.0 if W >= thr else max(W / thr, 0.0)
                eta = e0 * k * ks
                W = min(cap, max(0.0, W + p - eta))
                fr.append(W / cap)
                dfc += (e0 * k) - eta
            fr = np.array(fr)
            inw = len(s) - (b - a + 1)
            stress_days = int(np.sum(fr[inw:] < DEPLETION_FRACTION))
            min_frac = float(fr[inw:].min()) if len(fr[inw:]) else np.nan
            deficit = float(dfc)

        rows.append(dict(
            fips5=uid, year=int(yr), plant_doy=int(g.doy.iloc[plant_i]),
            r1_doy=int(g.doy.iloc[si["R1"]]) if si["R1"] else np.nan,
            # thermal R3, the stage validated against NASS; NOT the window start
            r3_doy=(int(g.doy.iloc[si["R3"]]) if si["R3"] is not None else np.nan),
            start_doy=int(g.doy.iloc[a]),
            r5_doy=int(g.doy.iloc[si["R5"]]) if si["R5"] else np.nan,
            # window end. In "damped" mode this is the damped R7 date; in
            # "thermal" mode it is thermal-time R6, as before.
            end_doy=int(g.doy.iloc[b]),
            end_driver=driver_x,
            # thermal-time R6 and R8, UNVALIDATED (NASS has no counterpart); kept
            # for script 21 and for comparison, not for inference
            r6_doy=int(g.doy.iloc[si["R6"]]) if si["R6"] is not None else np.nan,
            r8_doy=int(r8_doy) if np.isfinite(r8_doy) else np.nan,
            frost_doy=frost_doy,
            matured_before_frost=int(matured),
            days_r8_to_frost=(float(frost_doy - r8_doy)
                              if np.isfinite(frost_doy) and np.isfinite(r8_doy)
                              else np.nan),
            window_days=int(b - a + 1),
            podfill_days=int(b - a + 1),             # alias of window_days
            # legacy seed-fill length, thermal mode only: R5 has no observed
            # counterpart, so it is not reported for the damped window
            seedfill_days=(int(b - si["R5"] + 1)
                           if end_rule == "thermal" and si["R5"] is not None
                           else np.nan),
            season_days=int(b - plant_i + 1),
            win_gdd=float(w.gdd.sum()), win_edd=float(w.edd.sum()),
            win_hot_days=int(w.hot_day.sum()),
            win_vpd_mean=float(w.vpd.mean()), win_vpd_max=float(w.vpd.max()),
            win_prcp_mm=float(w.prcp_mm.sum()), win_et0_mm=float(w.et0.sum()),
            win_tmax_mean=float(w.tmax_c.mean()),
            win_water_deficit_mm=float(w.et0.sum() - w.prcp_mm.sum()),
            season_gdd=float(g.gdd.iloc[plant_i:b + 1].sum()),
            season_edd=float(g.edd.iloc[plant_i:b + 1].sum()),
            season_prcp_mm=float(g.prcp_mm.iloc[plant_i:b + 1].sum()),
            wb_stress_days=stress_days, wb_min_water_frac=min_frac,
            wb_season_deficit_mm=deficit))

    return pd.DataFrame(rows), skipped


def centroid_lat(raw_dir):
    rows = []
    for line in (raw_dir / "il_county_boundaries.txt").read_text().splitlines():
        if not line.strip():
            continue
        fips, coords = line.split("|", 1)
        pts = np.array([[float(x) for x in p.split(",")] for p in coords.split()])
        if len(pts) > 1 and np.allclose(pts[0], pts[-1]):
            pts = pts[:-1]
        rows.append(dict(unit_id=fips.strip(), lat=pts[:, 1].mean()))
    return pd.DataFrame(rows)
