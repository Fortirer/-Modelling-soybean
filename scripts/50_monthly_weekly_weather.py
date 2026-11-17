"""50 - Monthly and weekly in-season weather, per unit and crop year.

Inputs for the two reviewed papers script 48 could not fit:

  Mourtzinis et al. (2015)  month-by-month temperature and precipitation
                            effects over the season
  Khaki et al. (2020)       weekly means of daily weather as a sequence

Season months and weeks are numbered from the start of the local season so
the two countries line up: month 1 is May in the US and October in Brazil;
week 1 starts on 1 April in the US and 1 September in Brazil.

  US      Daymet (script 40): tmax, tmin, prcp, srad, vapour pressure
  Brazil  NASA POWER (script 39): tmax, tmin, prcp, dew point

Outputs, one row per unit and year (Brazil: HARVEST year, as in br_05):
  data/processed/<region>/monthly_weather_features.csv
      m1_tmean .. m5_tmean, m1_prcp .. m5_prcp     (US May-Sep; Brazil Oct-Feb)
  data/processed/<region>/weekly_weather_features.csv
      w01_tmax .. w26_tmax, and the same for tmin, prcp, vpd (26 weeks)

Usage:  python scripts/50_monthly_weekly_weather.py [regions]
"""
import sys

import numpy as np
import pandas as pd

from _gap import log, select_regions

TAG = "50"
N_WEEKS = 26
SEASON_START = {"US": (4, 1), "BR": (9, 1)}          # month, day of week 1
MONTHS = {"US": (5, 6, 7, 8, 9), "BR": (10, 11, 12, 1, 2)}
SOURCE = {"US": "daymet_daily.csv.gz", "BR": "power_daily.csv.gz"}
MIN_DAYS_PER_MONTH, MIN_DAYS_PER_WEEK = 25, 6


def svp_kpa(temp_c):
    return 0.6108 * np.exp(17.27 * temp_c / (temp_c + 237.3))


def load_daily(region) -> pd.DataFrame:
    path = region.raw / SOURCE[region.country]
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; run scripts 39 and 40 first")
    daily = pd.read_csv(path, dtype={"unit_id": str}, parse_dates=["date"])
    saturation = (svp_kpa(daily.tmax_c) + svp_kpa(daily.tmin_c)) / 2.0
    actual = daily.vp_pa / 1000.0 if "vp_pa" in daily else svp_kpa(daily.tdew_c)
    month, year = daily.date.dt.month, daily.date.dt.year
    start_month, start_day = SEASON_START[region.country]
    # season year = harvest year: in Brazil the season that starts in
    # September of t-1 is filed under t; in the US it is the calendar year
    crosses = region.country == "BR"
    season_year = year + ((month >= start_month) & crosses).astype(int)
    season_start = pd.to_datetime(dict(year=season_year - int(crosses),
                                       month=start_month, day=start_day))
    return daily.assign(
        tmean_c=(daily.tmax_c + daily.tmin_c) / 2.0,
        vpd_kpa=np.maximum(saturation - actual, 0.0), month=month,
        season_year=season_year, season_day=(daily.date - season_start).dt.days)


def monthly(daily: pd.DataFrame, country: str) -> pd.DataFrame:
    order = {month: i + 1 for i, month in enumerate(MONTHS[country])}
    rows = daily[daily.month.isin(order)].assign(m=lambda d: d.month.map(order))
    grouped = rows.groupby(["unit_id", "season_year", "m"])
    table = grouped.agg(tmean=("tmean_c", "mean"), prcp=("prcp_mm", "sum"),
                        n=("tmean_c", "count")).reset_index()
    table = table[table.n >= MIN_DAYS_PER_MONTH]
    wide = table.pivot(index=["unit_id", "season_year"], columns="m",
                       values=["tmean", "prcp"])
    wide.columns = [f"m{m}_{name}" for name, m in wide.columns]
    return wide.dropna().reset_index()


def weekly(daily: pd.DataFrame) -> pd.DataFrame:
    rows = daily[(daily.season_day >= 0) & (daily.season_day < 7 * N_WEEKS)]
    rows = rows.assign(w=rows.season_day // 7 + 1)
    grouped = rows.groupby(["unit_id", "season_year", "w"])
    table = grouped.agg(tmax=("tmax_c", "mean"), tmin=("tmin_c", "mean"),
                        prcp=("prcp_mm", "sum"), vpd=("vpd_kpa", "mean"),
                        n=("tmax_c", "count")).reset_index()
    table = table[table.n >= MIN_DAYS_PER_WEEK]
    wide = table.pivot(index=["unit_id", "season_year"], columns="w",
                       values=["tmax", "tmin", "prcp", "vpd"])
    wide.columns = [f"w{w:02d}_{name}" for name, w in wide.columns]
    return wide.dropna().reset_index()


def main() -> None:
    for region in select_regions(sys.argv[1:]):
        try:
            daily = load_daily(region)
        except FileNotFoundError as error:
            log(TAG, f"{region.key}: SKIPPED - {error}")
            continue
        names = {"unit_id": "fips5", "season_year": "year"}
        month_table = monthly(daily, region.country).rename(columns=names)
        week_table = weekly(daily).rename(columns=names)
        month_table.to_csv(region.proc / "monthly_weather_features.csv", index=False,
                           float_format="%.3f")
        week_table.to_csv(region.proc / "weekly_weather_features.csv", index=False,
                          float_format="%.3f")
        log(TAG, f"{region.key}: monthly {len(month_table)} rows, weekly "
                 f"{len(week_table)} rows, {week_table.year.min()}-{week_table.year.max()}")


if __name__ == "__main__":
    main()
