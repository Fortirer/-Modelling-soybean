"""Shared thermal-time phenology and process-based climate features.

Extracted from script 18 so that script 20 can run the IDENTICAL code on
CMIP6-perturbed weather. If the scenario path and the observed path ever
diverge, the comparison between them stops meaning anything, so they share one
implementation rather than two that are meant to match.

Parameter provenance is documented in script 18's header: the thermal-time
thresholds are calibrated to Illinois NASS crop-progress norms, not taken from
a paper, and one set is applied statewide although maturity group varies.
"""
import numpy as np, pandas as pd

# thermal time, degC-days base 10 capped 30, accumulated from planting
STAGES = {"VE": 110, "R1": 610, "R3": 860, "R5": 1110, "R6": 1390, "R8": 1550}
T_BASE, T_CAP, T_EXTREME = 10.0, 30.0, 30.0
HEAT_DAY_C = 34.0

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
EARLIEST_DOY, LATEST_DOY, PLANT_TEMP_C = 121, 175, 15.0

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


def ra_mj(lat_deg, doy):
    """Extraterrestrial radiation, MJ/m2/day (FAO-56). Latitude and day only."""
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
    d["et0"] = et0_hargreaves(d.tmin_c, d.tmax_c, d.tmean_c, d.lat, d.doy)
    return d


def build_features(d, taw, stages=None):
    """One row per unit-year: phenology, window conditions, water balance.

    `d` must already carry the daily terms from add_daily_terms.
    `taw` maps unit_id -> total available water in the top metre, mm.
    `stages` overrides the thermal-time thresholds, for maturity-group work;
    it defaults to the calibrated Illinois average.

    Also returns the autumn killing-frost date and whether the crop reached R8
    before it. Under a longer maturity group the crop can simply run out of
    season, which is the constraint that stops "plant a longer variety" from
    being a free adaptation.
    """
    stages = stages or STAGES
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

        run = g.tmean_c.rolling(7, min_periods=7).mean()
        win = g.index[(g.doy >= EARLIEST_DOY) & (g.doy <= LATEST_DOY)]
        hit = [i for i in win if run.iloc[i] >= PLANT_TEMP_C]
        plant_i = hit[0] if hit else (win[len(win) // 2] if len(win) else None)
        if plant_i is None:
            skipped += 1
            continue

        gdd_cum = g.gdd.iloc[plant_i:].cumsum().values
        idx = np.arange(plant_i, len(g))

        def stage_i(target):
            k = np.searchsorted(gdd_cum, target)
            return int(idx[k]) if k < len(idx) else None

        si = {s: stage_i(v) for s, v in stages.items()}
        a, b = si["R3"], si["R6"]
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
            r3_doy=int(g.doy.iloc[a]),
            r5_doy=int(g.doy.iloc[si["R5"]]) if si["R5"] else np.nan,
            r6_doy=int(g.doy.iloc[b]),
            r8_doy=int(r8_doy) if np.isfinite(r8_doy) else np.nan,
            frost_doy=frost_doy,
            matured_before_frost=int(matured),
            days_r8_to_frost=(float(frost_doy - r8_doy)
                              if np.isfinite(frost_doy) and np.isfinite(r8_doy)
                              else np.nan),
            podfill_days=int(b - a + 1),
            seedfill_days=int(b - si["R5"] + 1) if si["R5"] else np.nan,
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
