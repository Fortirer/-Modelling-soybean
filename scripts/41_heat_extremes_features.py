"""41 - Degree days above 30 C and ETCCDI-style extremes, per unit and crop year.

The gap this closes (docs/DADOS_FALTANTES.md): the US panel measured heat only
as a count of hot MONTHS from monthly nClimDiv. Schlenker & Roberts (2009)
show the damage follows degree days above ~30 C accumulated from DAILY
temperature, and the machine-learning papers (Benso et al. 2025; Parisoto et
al. 2026) add the ETCCDI extremes indices. This script computes both from the
daily files of scripts 39 and 40.

Daily source, chosen per country unless --source is given:
  US      Daymet 1 km, 1980-2025   -> data/processed/<ST>/heat_extremes_daymet.csv
  Brazil  NASA POWER, 1981-2025    -> data/processed/BR/<UF>/heat_extremes_power.csv
  --source power also works for the US and gives a file computed exactly like
  Brazil's, for cross-country models that must not mix data sources.

Two windows per crop year, defined as in 00_config.py / br_05:
  gs_  growing season   US April-September; Brazil September-April
  cw_  critical window  US July-August;     Brazil January-February
Brazil's crop year is the PLANTING year. IBGE reports that crop under the
following (harvest) year; script 47 shifts the key when it builds the panel.

Columns (each with both prefixes):
  gdd_10_30        degree days between 10 and 30 C (beneficial heat)
  edd_29/30/32/34  degree days above each threshold (single-sine, Snyder 1985)
  hot_days_30/32/35  days with Tmax at or above the threshold
  warm_nights_20/24  days with Tmin at or above the threshold
  txx, tnn, tmax_mean, tmin_mean
  wsdi_days        days in spells of >= 6 days with Tmax above the unit's own
                   90th percentile for that calendar month (1981-2010 base).
                   ETCCDI uses a 5-day moving calendar window; the monthly
                   percentile used here is a simplification.
  prcp_mm, dry_days (< 1 mm), cdd (longest dry run), rx1day, rx5day, r20mm
  vpd_mean_kpa     mean daily vapour pressure deficit
  n_days           days found in the window (incomplete seasons are dropped)

Usage:  python scripts/41_heat_extremes_features.py [--source power] [regions]
"""
import json
import sys
import time

import numpy as np
import pandas as pd

from _gap import add_crop_year, log, select_regions
from _indices import degree_days, longest_run, rolling_max_sum, spell_days

TAG = "41"
T_BASE, T_CAP = 10.0, 30.0
EDD_THRESHOLDS = (29, 30, 32, 34)
HOT_DAY_THRESHOLDS = (30, 32, 35)
WARM_NIGHT_THRESHOLDS = (20, 24)
DRY_DAY_MM, HEAVY_RAIN_MM = 1.0, 20.0
BASE_PERIOD = (1981, 2010)
WARM_PERCENTILE = 0.90
MAX_MISSING_DAYS = 5      # a window short by more than this is dropped
SOURCES = {"daymet": "daymet_daily.csv.gz", "power": "power_daily.csv.gz"}
DEFAULT_SOURCE = {"US": "daymet", "BR": "power"}


def svp_kpa(temp_c):
    """Saturation vapour pressure, kPa (FAO-56 Tetens)."""
    return 0.6108 * np.exp(17.27 * temp_c / (temp_c + 237.3))


def load_daily(region, source: str) -> pd.DataFrame:
    path = region.raw / SOURCES[source]
    if not path.exists():
        script = "40_download_daymet_daily.py" if source == "daymet" \
            else "39_download_power_daily_all.py"
        raise FileNotFoundError(f"{path} not found; run scripts/{script} first")
    daily = pd.read_csv(path, dtype={"unit_id": str}, parse_dates=["date"])
    saturation = (svp_kpa(daily.tmax_c) + svp_kpa(daily.tmin_c)) / 2.0
    actual = daily.vp_pa / 1000.0 if source == "daymet" else svp_kpa(daily.tdew_c)
    return daily.assign(vpd_kpa=np.maximum(saturation - actual, 0.0))


def with_daily_terms(daily: pd.DataFrame, country: str) -> pd.DataFrame:
    daily = add_crop_year(daily, country)
    terms = {"gdd_10_30": degree_days(daily.tmin_c, daily.tmax_c, T_BASE)
             - degree_days(daily.tmin_c, daily.tmax_c, T_CAP)}
    for threshold in EDD_THRESHOLDS:
        terms[f"edd_{threshold}"] = degree_days(daily.tmin_c, daily.tmax_c, threshold)
    for threshold in HOT_DAY_THRESHOLDS:
        terms[f"hot_days_{threshold}"] = (daily.tmax_c >= threshold).astype(float)
    for threshold in WARM_NIGHT_THRESHOLDS:
        terms[f"warm_nights_{threshold}"] = (daily.tmin_c >= threshold).astype(float)
    terms["dry_day"] = (daily.prcp_mm < DRY_DAY_MM).astype(float)
    terms["r20mm"] = (daily.prcp_mm >= HEAVY_RAIN_MM).astype(float)

    base = daily[daily.year.between(*BASE_PERIOD)]
    p90 = (base.groupby(["unit_id", "month"]).tmax_c.quantile(WARM_PERCENTILE)
           .rename("tmax_p90").reset_index())
    daily = daily.assign(**terms).merge(p90, on=["unit_id", "month"], how="left")
    return daily.assign(warm_day=daily.tmax_c > daily.tmax_p90)


def summarise(window: pd.DataFrame, prefix: str) -> pd.DataFrame:
    """One row per unit and crop year for the days in `window`."""
    window = window.sort_values(["unit_id", "crop_year", "date"])
    grouped = window.groupby(["unit_id", "crop_year"], sort=False)
    sums = [f"edd_{t}" for t in EDD_THRESHOLDS] \
        + [f"hot_days_{t}" for t in HOT_DAY_THRESHOLDS] \
        + [f"warm_nights_{t}" for t in WARM_NIGHT_THRESHOLDS] \
        + ["gdd_10_30", "r20mm"]
    out = grouped[sums].sum(min_count=1)
    out["txx"] = grouped.tmax_c.max()
    out["tnn"] = grouped.tmin_c.min()
    out["tmax_mean"] = grouped.tmax_c.mean()
    out["tmin_mean"] = grouped.tmin_c.mean()
    out["prcp_mm"] = grouped.prcp_mm.sum(min_count=1)
    out["dry_days"] = grouped.dry_day.sum()
    out["rx1day"] = grouped.prcp_mm.max()
    out["rx5day"] = grouped.prcp_mm.agg(lambda s: rolling_max_sum(s.to_numpy(), 5))
    out["cdd"] = grouped.dry_day.agg(lambda s: longest_run(s.to_numpy() > 0))
    out["wsdi_days"] = grouped.warm_day.agg(lambda s: spell_days(s.to_numpy()))
    out["vpd_mean_kpa"] = grouped.vpd_kpa.mean()
    out["n_days"] = grouped.size()
    return out.add_prefix(prefix)


def complete_only(features: pd.DataFrame, prefix: str) -> pd.DataFrame:
    """Rows whose window has (nearly) all its days; partial seasons removed."""
    full = features[f"{prefix}n_days"].max()
    return features[features[f"{prefix}n_days"] >= full - MAX_MISSING_DAYS]


def build_region(region, source: str) -> dict:
    daily = with_daily_terms(load_daily(region, source), region.country)
    season = daily[daily.in_grow & daily.crop_year.notna()]
    grow = complete_only(summarise(season, "gs_"), "gs_")
    critical = complete_only(summarise(season[season.in_critical], "cw_"), "cw_")
    features = grow.join(critical, how="inner").reset_index().rename(
        columns={"unit_id": "fips5", "crop_year": "year"})
    features["year"] = features.year.astype(int)
    out = region.proc / f"heat_extremes_{source}.csv"
    features.to_csv(out, index=False, float_format="%.3f")
    report = dict(
        region=region.key, source=source, input=SOURCES[source],
        units=int(features.fips5.nunique()), rows=len(features),
        years=[int(features.year.min()), int(features.year.max())],
        mean_gs_edd_30=round(float(features.gs_edd_30.mean()), 2),
        mean_cw_hot_days_32=round(float(features.cw_hot_days_32.mean()), 2),
        nulls=int(features.isna().sum().sum()),
        thresholds=dict(t_base=T_BASE, t_cap=T_CAP, edd=EDD_THRESHOLDS,
                        hot_days=HOT_DAY_THRESHOLDS, base_period=BASE_PERIOD),
        accessed=time.strftime("%Y-%m-%d"),
    )
    region.res.mkdir(parents=True, exist_ok=True)
    (region.res / f"41_heat_extremes_{source}_report.json").write_text(
        json.dumps(report, indent=2))
    log(TAG, f"{region.key} [{source}]: {report['units']} units, "
             f"{report['years'][0]}-{report['years'][1]}, "
             f"mean season EDD>30 = {report['mean_gs_edd_30']}")
    return report


def main() -> None:
    args = sys.argv[1:]
    forced = None
    if "--source" in args:
        at = args.index("--source")
        forced = args[at + 1]
        args = args[:at] + args[at + 2:]
        if forced not in SOURCES:
            raise SystemExit(f"--source must be one of {sorted(SOURCES)}")
    for region in select_regions(args):
        source = forced or DEFAULT_SOURCE[region.country]
        if source == "daymet" and region.country != "US":
            log(TAG, f"{region.key}: Daymet covers North America only, skipping")
            continue
        try:
            build_region(region, source)
        except FileNotFoundError as error:
            log(TAG, f"{region.key}: SKIPPED - {error}")


if __name__ == "__main__":
    main()
