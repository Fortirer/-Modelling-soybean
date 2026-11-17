"""Pure climate and soil index functions used by scripts 41-43.

No file access and no configuration: arrays in, arrays out, so every function
here is unit tested (tests/test_indices.py).

  degree_days            Snyder (1985) single-sine degree days above a threshold
  hargreaves_et0         reference evapotranspiration from temperature only
  spi, spei              standardised precipitation (and precipitation minus
                         ET0) indices, McKee et al. (1993) and
                         Vicente-Serrano et al. (2010)
  longest_run, spell_days, rolling_max_sum, wsdi_days
                         building blocks of the ETCCDI extremes indices
  saxton_rawls           field capacity, wilting point and available water
                         from texture and organic matter (Saxton & Rawls 2006)
"""
from __future__ import annotations

import numpy as np
from scipy import special, stats

Z_LIMIT = 3.0                 # standardised indices are clipped to +-3
MIN_FIT_YEARS = 20            # fewer values than this per calendar month: NaN
WSDI_MIN_SPELL = 6            # ETCCDI: warm spell = at least 6 consecutive days
SOLAR_CONSTANT = 0.0820       # MJ m-2 min-1 (FAO-56)
MJ_TO_MM = 0.408              # MJ m-2 day-1 of radiation to mm of water


def degree_days(tmin, tmax, threshold: float) -> np.ndarray:
    """Degree days above `threshold` from a sine fitted through tmin and tmax.

    Same formula as _pheno.dd_single_sine (kept here without that module's
    import-time side effects). A day with tmax <= threshold contributes 0; a
    day entirely above contributes mean - threshold.
    """
    tmin = np.asarray(tmin, float)
    tmax = np.asarray(tmax, float)
    amp = (tmax - tmin) / 2.0
    mid = (tmax + tmin) / 2.0
    out = np.zeros_like(mid)
    above = tmin >= threshold
    out[above] = (mid - threshold)[above]
    part = (tmax > threshold) & ~above
    if part.any():
        a = np.where(amp[part] <= 0, 1e-9, amp[part])
        m = mid[part]
        theta = np.arcsin(np.clip((threshold - m) / a, -1.0, 1.0))
        out[part] = ((m - threshold) * (np.pi / 2 - theta) + a * np.cos(theta)) / np.pi
    out = np.maximum(out, 0.0)
    out[np.isnan(tmin) | np.isnan(tmax)] = np.nan
    return out


def extraterrestrial_radiation(lat_deg, doy) -> np.ndarray:
    """Daily extraterrestrial radiation, MJ m-2 day-1 (FAO-56 eq. 21)."""
    lat = np.radians(np.asarray(lat_deg, float))
    doy = np.asarray(doy, float)
    dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365.0)
    dec = 0.409 * np.sin(2 * np.pi * doy / 365.0 - 1.39)
    ws = np.arccos(np.clip(-np.tan(lat) * np.tan(dec), -1, 1))
    return (24 * 60 / np.pi) * SOLAR_CONSTANT * dr * (
        ws * np.sin(lat) * np.sin(dec) + np.cos(lat) * np.cos(dec) * np.sin(ws))


def hargreaves_et0(tmin, tmax, lat_deg, doy) -> np.ndarray:
    """Reference ET, mm/day, Hargreaves & Samani (1985).

    Needs only temperature and latitude, so it is available for every day of
    both records (solar radiation is missing in POWER before 1984).
    """
    tmin = np.asarray(tmin, float)
    tmax = np.asarray(tmax, float)
    tmean = (tmin + tmax) / 2.0
    ra = extraterrestrial_radiation(lat_deg, doy)
    return np.maximum(0.0023 * ra * (tmean + 17.8)
                      * np.sqrt(np.maximum(tmax - tmin, 0.0)) * MJ_TO_MM, 0.0)


def rolling_sum(values, window: int) -> np.ndarray:
    """Trailing sum over `window` steps.

    NaN until the window is full, and NaN for any window that contains a
    missing value (a missing value does not affect later windows).
    """
    values = np.asarray(values, float)
    out = np.full(values.shape, np.nan)
    if window < 1 or len(values) < window:
        return out
    out[window - 1:] = np.lib.stride_tricks.sliding_window_view(values, window).sum(axis=-1)
    return out


def _gamma_z(sample: np.ndarray) -> np.ndarray:
    """Gamma-based standard normal scores, with a point mass at zero."""
    positive = sample[sample > 0]
    p_zero = 1.0 - len(positive) / len(sample)
    if len(positive) < 4 or np.ptp(positive) == 0:
        return np.full(sample.shape, np.nan)
    shape, _, scale = stats.gamma.fit(positive, floc=0)
    cdf = p_zero + (1 - p_zero) * stats.gamma.cdf(sample, shape, loc=0, scale=scale)
    # an exact zero sits in the middle of its probability mass (Stagge 2015)
    cdf = np.where(sample <= 0, p_zero / 2.0 if p_zero > 0 else cdf, cdf)
    return stats.norm.ppf(np.clip(cdf, 1e-6, 1 - 1e-6))


def _loglogistic_z(sample: np.ndarray) -> np.ndarray:
    """Log-logistic scores, fitted by L-moments.

    The three-parameter log-logistic of Vicente-Serrano et al. (2010) written
    as the generalised logistic distribution (Hosking 1990), which is how the
    reference R package SPEI fits it. Unlike the original moment equations
    this form also fits water balances with zero or negative skew.
    """
    n = len(sample)
    ordered = np.sort(sample)
    rank = np.arange(n)
    b0 = ordered.mean()
    b1 = np.sum(rank / (n - 1) * ordered) / n
    b2 = np.sum(rank * (rank - 1) / ((n - 1) * (n - 2)) * ordered) / n
    l2 = 2 * b1 - b0
    l3 = 6 * b2 - 6 * b1 + b0
    if l2 <= 0:
        return np.full(sample.shape, np.nan)
    k = -l3 / l2
    if abs(k) < 1e-6:
        y = (sample - b0) / l2
    else:
        alpha = l2 * np.sin(k * np.pi) / (k * np.pi)
        xi = b0 - alpha * (1 / k - np.pi / np.sin(k * np.pi))
        inside = 1 - k * (sample - xi) / alpha
        # outside the fitted support: beyond the upper bound if k > 0,
        # below the lower bound if k < 0
        beyond = np.inf if k > 0 else -np.inf
        with np.errstate(divide="ignore", invalid="ignore"):
            y = np.where(inside > 0, -np.log(np.maximum(inside, 1e-300)) / k, beyond)
    cdf = special.expit(y)
    return stats.norm.ppf(np.clip(cdf, 1e-6, 1 - 1e-6))


def _standardise(series, months, scale: int, scorer) -> np.ndarray:
    """Accumulate over `scale` months, then score each calendar month apart."""
    series = np.asarray(series, float)
    months = np.asarray(months, int)
    if series.shape != months.shape:
        raise ValueError("series and months must have the same length")
    accumulated = rolling_sum(series, scale)
    out = np.full(series.shape, np.nan)
    for month in range(1, 13):
        index = np.where((months == month) & np.isfinite(accumulated))[0]
        if len(index) < MIN_FIT_YEARS:
            continue
        out[index] = scorer(accumulated[index])
    return np.clip(out, -Z_LIMIT, Z_LIMIT)


def spi(precip_mm, months, scale: int = 3) -> np.ndarray:
    """Standardised Precipitation Index on a continuous monthly series."""
    return _standardise(precip_mm, months, scale, _gamma_z)


def spei(precip_mm, et0_mm, months, scale: int = 3) -> np.ndarray:
    """Standardised Precipitation-Evapotranspiration Index, monthly series."""
    balance = np.asarray(precip_mm, float) - np.asarray(et0_mm, float)
    return _standardise(balance, months, scale, _loglogistic_z)


def run_lengths(flags) -> np.ndarray:
    """Lengths of every run of consecutive True values, in order."""
    padded = np.concatenate(([0], np.asarray(flags, bool).astype(np.int8), [0]))
    edges = np.diff(padded)
    return np.flatnonzero(edges == -1) - np.flatnonzero(edges == 1)


def longest_run(flags) -> int:
    """Length of the longest run of True values (CDD on dry-day flags)."""
    lengths = run_lengths(flags)
    return int(lengths.max()) if len(lengths) else 0


def spell_days(flags, min_length: int = WSDI_MIN_SPELL) -> int:
    """Number of True days in runs of at least `min_length` (WSDI on hot flags)."""
    lengths = run_lengths(flags)
    return int(lengths[lengths >= min_length].sum())


def rolling_max_sum(values, window: int) -> float:
    """Largest `window`-day total (Rx5day with window=5).

    Windows containing a missing day are ignored, never counted as dry. NaN
    if no complete window exists.
    """
    sums = rolling_sum(values, window)
    return float(np.nanmax(sums)) if np.isfinite(sums).any() else float("nan")


def saxton_rawls(sand_pct, clay_pct, om_pct) -> dict[str, np.ndarray]:
    """Volumetric water at field capacity and wilting point, and their gap.

    Saxton & Rawls (2006, SSSAJ 70:1569-1578), eqs. 1 and 2. Inputs are
    percentages by weight; outputs are volume fractions (m3 m-3):
      fc   water held at 33 kPa
      wp   water held at 1500 kPa
      awc  plant-available water, fc - wp

    The equations were fitted on US soils. They are known to misjudge the
    oxidic, strongly aggregated clays (Ferralsols) that dominate Brazilian
    soybean land, which drain like sands at low tension. Use as a relative
    ranking between municipalities, not as an absolute water volume.
    """
    sand = np.asarray(sand_pct, float) / 100.0
    clay = np.asarray(clay_pct, float) / 100.0
    om = np.asarray(om_pct, float)
    wp_t = (-0.024 * sand + 0.487 * clay + 0.006 * om + 0.005 * sand * om
            - 0.013 * clay * om + 0.068 * sand * clay + 0.031)
    wp = wp_t + (0.14 * wp_t - 0.02)
    fc_t = (-0.251 * sand + 0.195 * clay + 0.011 * om + 0.006 * sand * om
            - 0.027 * clay * om + 0.452 * sand * clay + 0.299)
    fc = fc_t + (1.283 * fc_t ** 2 - 0.374 * fc_t - 0.015)
    return {"fc": fc, "wp": wp, "awc": np.maximum(fc - wp, 0.0)}
