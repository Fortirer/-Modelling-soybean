"""56 - Projected change in degree days from daily NEX-GDDP-CMIP6 series.

The open question of the literature review: monthly CMIP6 deltas (scripts 12,
br_12) shift every day of a month by the same amount and cannot change how
often a day crosses 30 C the way a model's own daily series does. Projections
built on degree days need daily data. This script takes the daily,
bias-corrected NEX-GDDP-CMIP6 series pulled by script 46 and computes, per
unit, the change in season degree days between a historical and a future
period of the same model:

  d_gdd_10_30   change in degree days between 10 and 30 C
  d_edd_30      change in degree days above 30 C
  d_prcp_pct    change in season precipitation, %

Seasons as everywhere else: April-September in the US, September-April in
Brazil keyed by harvest year. Degree days by single-sine integration, the
same function as script 41.

The implied yield change applies the Schlenker-Roberts coefficients of script
48 (log yield per 100 GDD, per 10 EDD, per 100 mm and its square) for that
country:
  d_log_yield = b_gdd * d_gdd/100 + b_edd * d_edd/10
                + b_rain * d_rain/100 + b_rain2 * (rain_fut^2 - rain_hist^2)/100^2

Read with care: one model, one realisation, ten-year periods. Ten years of a
single model sample its internal variability poorly; this is a demonstration
of the daily method, not a projection to report on its own. Add models and
years with script 46 (same command, other --model / --years) and re-run.

Output: results/_literature_models/degree_day_projection_<model>.csv
        (one row per unit) and _by_state.csv (state medians)
Usage:  python scripts/56_degree_day_projection.py [--model MPI-ESM1-2-LR]
            [--historical 2005 2014] [--future ssp585 2051 2060]
"""
import argparse

import numpy as np
import pandas as pd

from _gap import ROOT, add_crop_year, all_regions, log
from _indices import degree_days

TAG = "56"
OUT = ROOT / "results" / "_literature_models"
COEFFICIENTS = OUT / "coefficients.csv"
MIN_SEASONS = 5


def season_totals(path, country: str, first: int, last: int) -> pd.DataFrame:
    daily = pd.read_csv(path, dtype={"unit_id": str})
    # model calendars may lack 29 February or use 30-day months; keep valid dates
    daily["date"] = pd.to_datetime(daily.date, errors="coerce")
    daily = add_crop_year(daily.dropna(subset=["date"]), country)
    if country == "BR":
        # add_crop_year keys Brazil by PLANTING year; this script, like the
        # panels, uses the harvest year, so --historical 2005 2014 means the
        # harvests of 2005-2014 in both countries
        daily = daily.assign(crop_year=daily.crop_year + 1)
    daily = daily[daily.in_grow & daily.crop_year.between(first, last)]
    daily = daily.assign(
        gdd=degree_days(daily.tmin_c, daily.tmax_c, 10.0) - degree_days(daily.tmin_c, daily.tmax_c, 30.0),
        edd=degree_days(daily.tmin_c, daily.tmax_c, 30.0))
    seasons = daily.groupby(["unit_id", "crop_year"]).agg(
        gdd=("gdd", "sum"), edd=("edd", "sum"), prcp=("prcp_mm", "sum"), days=("gdd", "size"))
    # complete seasons only: Brazil's first harvest of a file lacks its
    # September-December, its last planting lacks January-April
    seasons = seasons[seasons.days >= seasons.days.max() - 5]
    return seasons.groupby("unit_id").agg(gdd=("gdd", "mean"), edd=("edd", "mean"),
                                          prcp=("prcp", "mean"), seasons=("gdd", "size"))


def schlenker_roberts(country: str) -> dict:
    table = pd.read_csv(COEFFICIENTS)
    rows = table[(table.country == country) & (table.model == "schlenker_roberts_2009")]
    return dict(zip(rows.term, rows.coefficient))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="MPI-ESM1-2-LR")
    parser.add_argument("--historical", nargs=2, type=int, default=[2005, 2014])
    parser.add_argument("--future", nargs=3, default=["ssp585", "2051", "2060"])
    args = parser.parse_args()
    scenario, f0, f1 = args.future[0], int(args.future[1]), int(args.future[2])
    rows = []
    for region in all_regions():
        folder = region.raw / "nex_gddp"
        hist_file = folder / f"{args.model}_historical.csv.gz"
        fut_file = folder / f"{args.model}_{scenario}.csv.gz"
        if not (hist_file.exists() and fut_file.exists()):
            continue
        hist = season_totals(hist_file, region.country, *args.historical)
        fut = season_totals(fut_file, region.country, f0, f1)
        both = hist.join(fut, lsuffix="_hist", rsuffix="_fut", how="inner")
        both = both[(both.seasons_hist >= MIN_SEASONS) & (both.seasons_fut >= MIN_SEASONS)]
        if both.empty:
            continue
        b = schlenker_roberts(region.country)
        d_log = (b["gdd_100"] * (both.gdd_fut - both.gdd_hist) / 100
                 + b["edd30_10"] * (both.edd_fut - both.edd_hist) / 10
                 + b["rain_100mm"] * (both.prcp_fut - both.prcp_hist) / 100
                 + b["rain_100mm^2"] * (both.prcp_fut ** 2 - both.prcp_hist ** 2) / 100 ** 2)
        rows.append(pd.DataFrame({
            "country": region.country, "region": region.code, "fips5": both.index,
            "gdd_hist": both.gdd_hist, "edd_30_hist": both.edd_hist,
            "d_gdd_10_30": both.gdd_fut - both.gdd_hist,
            "d_edd_30": both.edd_fut - both.edd_hist,
            "d_prcp_pct": (both.prcp_fut / both.prcp_hist - 1) * 100,
            "yield_change_pct": np.expm1(d_log) * 100}))
        log(TAG, f"{region.key}: {len(both)} units")
    if not rows:
        raise SystemExit(f"[{TAG}] no unit has both periods; run script 46 for "
                         f"historical {args.historical} and {scenario} {f0}-{f1}")
    units = pd.concat(rows, ignore_index=True)
    stem = f"degree_day_projection_{args.model}_{scenario}_{f0}_{f1}"
    units.to_csv(OUT / f"{stem}.csv", index=False, float_format="%.3f")
    by_state = units.groupby(["country", "region"]).agg(
        units=("fips5", "size"), edd_30_hist=("edd_30_hist", "median"),
        d_edd_30=("d_edd_30", "median"), d_gdd_10_30=("d_gdd_10_30", "median"),
        d_prcp_pct=("d_prcp_pct", "median"), yield_change_pct=("yield_change_pct", "median"),
        share_units_worse=("yield_change_pct", lambda v: float((v < 0).mean() * 100)))
    by_state.reset_index().to_csv(OUT / f"{stem}_by_state.csv", index=False, float_format="%.2f")
    log(TAG, f"-> {stem}_by_state.csv")
    print(by_state.round(1).to_string())


if __name__ == "__main__":
    main()
