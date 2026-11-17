"""42 - SPI, SPEI and root-zone soil moisture, both countries, from NASA POWER.

Closes two gaps of docs/DADOS_FALTANTES.md with one consistent source:

  * Drought index for Brazil. The US panel has Palmer PDSI and Z from
    nClimDiv; Brazil had only rainfall-deficit proxies. SPI and SPEI at 3 and
    6 months are what Parisoto et al. (2026) and Benso et al. (2025) use.
  * Soil moisture for both countries. Ortiz-Bobea et al. (2019) show yield
    responds to water in the soil, not to rainfall as such.

Method
  Daily POWER (script 39) is summed to months. ET0 is Hargreaves-Samani, which
  needs only temperature and latitude and so exists for the whole record
  (POWER radiation is missing before 1984). SPI fits a gamma distribution and
  SPEI a log-logistic one, separately for each unit and calendar month, on the
  unit's full 1981-2025 record (_indices.py). Soil moisture is MERRA-2
  root-zone wetness (0-100 cm, fraction of saturation), averaged per window
  and also expressed as a z-score against the unit's own climatology.

Outputs, per region
  data/processed/<region>/drought_monthly.csv
      fips5, year, month, prcp_mm, et0_mm, spi3, spi6, spei3, spei6,
      gwetroot, gwettop
  data/processed/<region>/drought_soil_moisture_features.csv
      one row per unit and crop year (Brazil: planting year; IBGE's yield for
      that crop is filed under year + 1, a shift script 47 applies):
      spei3_critical / spi3_critical   3-month index ending in the last month
                                       of the critical window (US August;
                                       Brazil February)
      spei6_season / spi6_season       6-month index ending at season end
                                       (US September; Brazil March)
      spei3_min_grow                   driest 3-month index in the season
      drought_months_grow              season months with SPEI-3 below -1
      gwetroot_grow, gwetroot_critical, gwettop_critical   mean wetness
      gwetroot_critical_z              z-score of gwetroot_critical
      gwetroot_min_month               driest monthly root-zone wetness

Read with care: MERRA-2 is ~50 km and its soil moisture is a land-model
estimate driven by corrected precipitation, not a measurement. It is the
no-login stand-in for NLDAS-2 (script 44) and ERA5-Land (script 45).

Usage:  python scripts/42_drought_soil_moisture.py [regions]
"""
import json
import sys
import time

import numpy as np
import pandas as pd

from _gap import (BR_CRITICAL_MONTHS, BR_GROW_MONTHS_CUR, BR_GROW_MONTHS_NEXT,
                  US_CRITICAL_MONTHS, US_GROW_MONTHS, centroids, log,
                  select_regions)
from _indices import hargreaves_et0, spei, spi

TAG = "42"
SCALES = (3, 6)
DROUGHT_Z = -1.0
SEASON_END_MONTH = {"US": 9, "BR": 3}
DAILY_FILE = "power_daily.csv.gz"
MIN_DAYS_PER_MONTH = 25


def monthly_table(region) -> pd.DataFrame:
    path = region.raw / DAILY_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found; run scripts/39_download_power_daily_all.py first")
    columns = ["unit_id", "date", "tmax_c", "tmin_c", "prcp_mm", "gwetroot",
               "gwettop", "year", "doy"]
    daily = pd.read_csv(path, dtype={"unit_id": str}, usecols=columns,
                        parse_dates=["date"])
    latitude = centroids(region, producing_only=False).set_index("unit_id").lat
    daily = daily.assign(
        month=daily.date.dt.month,
        et0_mm=hargreaves_et0(daily.tmin_c, daily.tmax_c,
                              daily.unit_id.map(latitude), daily.doy))
    grouped = daily.groupby(["unit_id", "year", "month"])
    monthly = grouped.agg(prcp_mm=("prcp_mm", "sum"), et0_mm=("et0_mm", "sum"),
                          gwetroot=("gwetroot", "mean"), gwettop=("gwettop", "mean"),
                          n_days=("et0_mm", "count")).reset_index()
    return monthly[monthly.n_days >= MIN_DAYS_PER_MONTH].drop(columns="n_days")


def add_indices(monthly: pd.DataFrame) -> pd.DataFrame:
    """SPI and SPEI at each scale, fitted unit by unit."""
    pieces, skipped = [], []
    for _, unit in monthly.sort_values(["unit_id", "year", "month"]).groupby("unit_id"):
        expected = (unit.year.max() - unit.year.min()) * 12 \
            + unit.month.iloc[-1] - unit.month.iloc[0] + 1
        if len(unit) != expected:      # a gap would break the accumulation
            skipped.append(str(unit.unit_id.iloc[0]))
            continue
        months = unit.month.to_numpy()
        added = {}
        for scale in SCALES:
            added[f"spi{scale}"] = spi(unit.prcp_mm.to_numpy(), months, scale)
            added[f"spei{scale}"] = spei(unit.prcp_mm.to_numpy(),
                                         unit.et0_mm.to_numpy(), months, scale)
        pieces.append(unit.assign(**added))
    if skipped:
        log(TAG, f"{len(skipped)} units skipped, monthly record has gaps: {skipped[:10]}")
    if not pieces:
        raise ValueError("no unit has a continuous monthly record")
    return pd.concat(pieces, ignore_index=True)


def crop_year_features(monthly: pd.DataFrame, country: str) -> pd.DataFrame:
    if country == "US":
        in_grow = monthly.month.isin(US_GROW_MONTHS)
        crop_year = monthly.year
        critical_months, n_grow = US_CRITICAL_MONTHS, len(US_GROW_MONTHS)
    else:
        nxt = monthly.month.isin(BR_GROW_MONTHS_NEXT)
        in_grow = monthly.month.isin(BR_GROW_MONTHS_CUR) | nxt
        crop_year = monthly.year.where(~nxt, monthly.year - 1)
        critical_months = BR_CRITICAL_MONTHS
        n_grow = len(BR_GROW_MONTHS_CUR) + len(BR_GROW_MONTHS_NEXT)
    season = monthly[in_grow].assign(crop_year=crop_year[in_grow])
    critical = season[season.month.isin(critical_months)]
    keys = ["unit_id", "crop_year"]
    grow_group, critical_group = season.groupby(keys), critical.groupby(keys)

    def at_month(month: int, columns: dict) -> pd.DataFrame:
        rows = season[season.month == month].set_index(keys)
        return rows[list(columns)].rename(columns=columns)

    features = pd.concat([
        at_month(max(critical_months), {"spei3": "spei3_critical",
                                        "spi3": "spi3_critical"}),
        at_month(SEASON_END_MONTH[country], {"spei6": "spei6_season",
                                             "spi6": "spi6_season"}),
        grow_group.spei3.min().rename("spei3_min_grow"),
        grow_group.spei3.agg(lambda s: int((s < DROUGHT_Z).sum()))
                  .rename("drought_months_grow"),
        grow_group.gwetroot.mean().rename("gwetroot_grow"),
        grow_group.gwetroot.min().rename("gwetroot_min_month"),
        critical_group.gwetroot.mean().rename("gwetroot_critical"),
        critical_group.gwettop.mean().rename("gwettop_critical"),
        grow_group.size().rename("n_months"),
    ], axis=1)
    features = features[features.n_months == n_grow].drop(columns="n_months")
    by_unit = features.groupby(level="unit_id").gwetroot_critical
    spread = by_unit.transform("std").replace(0, np.nan)
    features = features.assign(
        gwetroot_critical_z=(features.gwetroot_critical - by_unit.transform("mean")) / spread)
    return features.reset_index().rename(columns={"unit_id": "fips5", "crop_year": "year"})


def build_region(region) -> dict:
    monthly = add_indices(monthly_table(region))
    features = crop_year_features(monthly, region.country)
    monthly.rename(columns={"unit_id": "fips5"}).to_csv(
        region.proc / "drought_monthly.csv", index=False, float_format="%.3f")
    features.to_csv(region.proc / "drought_soil_moisture_features.csv",
                    index=False, float_format="%.3f")
    report = dict(
        region=region.key, units=int(features.fips5.nunique()),
        rows=len(features), monthly_rows=len(monthly),
        years=[int(features.year.min()), int(features.year.max())],
        spei3_critical_mean=round(float(features.spei3_critical.mean()), 3),
        spei3_critical_sd=round(float(features.spei3_critical.std()), 3),
        gwetroot_critical_mean=round(float(features.gwetroot_critical.mean()), 3),
        nulls={c: int(n) for c, n in features.isna().sum().items() if n},
        et0="Hargreaves-Samani", scales_months=SCALES,
        accessed=time.strftime("%Y-%m-%d"),
    )
    region.res.mkdir(parents=True, exist_ok=True)
    (region.res / "42_drought_soil_moisture_report.json").write_text(
        json.dumps(report, indent=2))
    log(TAG, f"{region.key}: {report['units']} units, "
             f"{report['years'][0]}-{report['years'][1]}, SPEI-3 critical "
             f"mean {report['spei3_critical_mean']} sd {report['spei3_critical_sd']}")
    return report


def main() -> None:
    for region in select_regions(sys.argv[1:]):
        try:
            build_region(region)
        except (FileNotFoundError, ValueError) as error:
            log(TAG, f"{region.key}: SKIPPED - {error}")


if __name__ == "__main__":
    main()
