"""49 - Brazil: a critical window per municipality, placed by ZARC planting dates.

Every Brazilian script so far uses January-February as the critical window
for all ten states. ZARC's lowest-risk sowing date (br_20) says planting is
not simultaneous: the state medians run from mid November in Paraná and Mato
Grosso do Sul to late January in Maranhão. A fixed window therefore catches
pod filling in the South and Centre-West but mostly vegetative growth in
Matopiba.

This script moves the window with the crop. For each municipality:

  sowing date     ZARC lowest-risk decade, mean over the three maturity groups
                  (br26_zarc_recommended_window.csv), in days after 1 September
  critical window sowing + POD_FILL_START .. sowing + POD_FILL_END days

POD_FILL_START and POD_FILL_END (60 and 105 days) are an ASSUMPTION standing
in for the R3-R6 interval of a cultivar of about 120 days; Brazil has no
observed crop-progress data to calibrate them (see the README, "Still open").
They are constants below so the sensitivity to them can be checked.

Outputs
  data/processed/BR/<UF>/regional_window_features.csv
      fips5, year (harvest year), sowing_day_from_sep1, rw_tmax_mean,
      rw_tmin_mean, rw_prcp_mm, rw_edd_30, rw_hot_days_32, rw_dry_days,
      rw_vpd_mean_kpa, rw_n_days
  results/_literature_models/br_regional_window_comparison.csv
      for each state and pooled: within-municipality R2 of the same quadratic
      temperature-rainfall model fitted with the fixed January-February
      window and with the ZARC-placed one, on the same rows

ZARC names municipalities, not codes; they are matched to IBGE names after
removing accents and case. Unmatched municipalities are reported and keep
only the fixed window.

SOWING SOURCE (--sowing). `zarc` (default) as above. `conab` uses instead the
OBSERVED state-level date at which half the soybean area was sown, from the
Conab weekly progress series (script 52), as its five-year mean curve. It is
one date per state, not per municipality, but it is what farmers did rather
than what the risk model recommends: the median, over the seasons whose
weekly series crosses 50%, of the day on which half the area was sown. Results go to br_regional_window_comparison_<source>.csv.

Usage:  python scripts/49_br_regional_window.py [--sowing zarc|conab] [BR:MT ...]
"""
import json
import sys
import time
import unicodedata

import numpy as np
import pandas as pd
import statsmodels.api as sm

from _gap import ROOT, log, select_regions
from _indices import degree_days

TAG = "49"
POD_FILL_START, POD_FILL_END = 60, 105     # days after sowing (assumed R3-R6)
SEASON_START_MONTH = 9                     # the season year starts on 1 September
MIN_YEARS = 20
MAX_MISSING_DAYS = 3
OUT = ROOT / "results" / "_literature_models"


def plain(name: str) -> str:
    """Upper-case name without accents, state suffix or punctuation."""
    text = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    text = text.split(" - ")[0].upper().replace("-", " ").replace("'", " ")
    return " ".join(text.split())


def sowing_days(region) -> pd.DataFrame:
    """fips5 -> ZARC sowing day (days after 1 September), matched by name."""
    zarc_file = region.res / "br26_zarc_recommended_window.csv"
    if not zarc_file.exists():
        raise FileNotFoundError(f"{zarc_file} not found; run br_19 and br_20 first")
    zarc = pd.read_csv(zarc_file)
    by_name = (zarc.assign(key=zarc.municipio.map(plain))
               .groupby("key").recommended_day_from_sep1.mean())
    units = (pd.read_csv(region.proc / "production_clean.csv", dtype={"fips5": str})
             [["fips5", "county"]].drop_duplicates("fips5"))
    units = units.assign(sowing_day_from_sep1=units.county.map(plain).map(by_name))
    return units[["fips5", "sowing_day_from_sep1"]]


STATE_NAMES = {"MT": "MATO GROSSO", "PR": "PARANA", "GO": "GOIAS",
               "RS": "RIO GRANDE DO SUL", "MS": "MATO GROSSO DO SUL",
               "MG": "MINAS GERAIS", "BA": "BAHIA", "TO": "TOCANTINS",
               "SP": "SAO PAULO", "MA": "MARANHAO"}
CONAB_DATES = ROOT / "data" / "processed" / "BR" / "conab_soja_progress_dates.csv"


def conab_sowing(region) -> pd.DataFrame:
    """Every producing municipality gets its state's observed 50%-sown date.

    The median, over the seasons in which Conab's weekly series crosses 50%
    (day50_from_sep1 not missing), of the day on which half the area was sown.
    """
    if not CONAB_DATES.exists():
        raise FileNotFoundError(f"{CONAB_DATES} not found; run script 52 first")
    dates = pd.read_csv(CONAB_DATES)
    dates = dates[dates.operation == "semeadura"].assign(key=dates.state.map(plain))
    state = dates[(dates.key == STATE_NAMES[region.code]) & dates.day50_from_sep1.notna()]
    if state.empty:
        raise FileNotFoundError(f"no complete Conab sowing season for {region.code}")
    log(TAG, f"{region.key}: Conab sowing from seasons {sorted(state.season.tolist())}")
    units = pd.read_csv(region.proc / "production_clean.csv", dtype={"fips5": str})
    return pd.DataFrame({"fips5": units.fips5.unique(),
                         "sowing_day_from_sep1": state.day50_from_sep1.median()})


def window_features(region, sowing: pd.DataFrame) -> pd.DataFrame:
    daily = pd.read_csv(region.raw / "power_daily.csv.gz", dtype={"unit_id": str},
                        usecols=["unit_id", "date", "tmax_c", "tmin_c", "tdew_c", "prcp_mm"],
                        parse_dates=["date"]).rename(columns={"unit_id": "fips5"})
    daily = daily.merge(sowing.dropna(), on="fips5", how="inner")
    # harvest year: the season that starts on 1 September of year t-1 is filed under t
    starts_new_season = daily.date.dt.month >= SEASON_START_MONTH
    harvest_year = daily.date.dt.year + starts_new_season.astype(int)
    season_start = pd.to_datetime(dict(year=harvest_year - 1, month=SEASON_START_MONTH, day=1))
    day = (daily.date - season_start).dt.days
    first = daily.sowing_day_from_sep1.round() + POD_FILL_START
    last = daily.sowing_day_from_sep1.round() + POD_FILL_END
    window = daily[(day >= first) & (day <= last)].assign(year=harvest_year)
    saturation = (0.6108 * np.exp(17.27 * window.tmax_c / (window.tmax_c + 237.3))
                  + 0.6108 * np.exp(17.27 * window.tmin_c / (window.tmin_c + 237.3))) / 2.0
    actual = 0.6108 * np.exp(17.27 * window.tdew_c / (window.tdew_c + 237.3))
    window = window.assign(
        vpd=np.maximum(saturation - actual, 0.0),
        edd=degree_days(window.tmin_c, window.tmax_c, 30.0),
        hot=(window.tmax_c >= 32).astype(float),
        dry=(window.prcp_mm < 1.0).astype(float))
    grouped = window.groupby(["fips5", "year"])
    features = grouped.agg(
        sowing_day_from_sep1=("sowing_day_from_sep1", "first"),
        rw_tmax_mean=("tmax_c", "mean"), rw_tmin_mean=("tmin_c", "mean"),
        rw_prcp_mm=("prcp_mm", "sum"), rw_edd_30=("edd", "sum"),
        rw_hot_days_32=("hot", "sum"), rw_dry_days=("dry", "sum"),
        rw_vpd_mean_kpa=("vpd", "mean"), rw_n_days=("prcp_mm", "size")).reset_index()
    full = POD_FILL_END - POD_FILL_START + 1
    return features[features.rw_n_days >= full - MAX_MISSING_DAYS]


def within_r2(frame: pd.DataFrame, temperature: str, rain: str) -> dict:
    """R2 of anomaly ~ T + T2 + P + P2, all demeaned within municipality."""
    columns = {"t": frame[temperature], "t2": frame[temperature] ** 2,
               "p": frame[rain], "p2": frame[rain] ** 2}
    x = pd.DataFrame(columns)
    x = x - x.groupby(frame.fips5).transform("mean")
    y = frame.anomaly - frame.groupby("fips5").anomaly.transform("mean")
    fit = sm.OLS(y, x).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(frame.fips5)[0]})
    return dict(r2=float(fit.rsquared), t_coef=float(fit.params["t"]),
                t2_coef=float(fit.params["t2"]), t_p=float(fit.pvalues["t"]))


def comparison_rows(region, features: pd.DataFrame) -> tuple[pd.DataFrame, dict | None]:
    """Rows with both windows and the detrended log-yield anomaly."""
    yields = pd.read_csv(region.proc / "production_clean.csv", dtype={"fips5": str},
                         usecols=["fips5", "year", "yield_kg_ha"])
    yields = yields[yields.yield_kg_ha > 0].assign(log_yield=lambda d: np.log(d.yield_kg_ha))
    fixed = pd.read_csv(region.proc / "climate_features.csv", dtype={"fips5": str},
                        usecols=["fips5", "year", "tmax_critical", "pcp_critical"])
    rows = yields.merge(fixed, on=["fips5", "year"]).merge(features, on=["fips5", "year"]).dropna()
    rows = rows[rows.groupby("fips5").year.transform("size") >= MIN_YEARS].copy()
    if rows.empty:
        return rows, None

    def detrend(group):
        slope, intercept = np.polyfit(group.year, group.log_yield, 1)
        return group.log_yield - (slope * group.year + intercept)

    rows["anomaly"] = rows.groupby("fips5", group_keys=False).apply(detrend, include_groups=False)
    fixed_fit = within_r2(rows, "tmax_critical", "pcp_critical")
    moved_fit = within_r2(rows, "rw_tmax_mean", "rw_prcp_mm")
    summary = dict(
        region=region.code, municipalities=int(rows.fips5.nunique()), n=len(rows),
        sowing_day_median=float(rows.sowing_day_from_sep1.median()),
        r2_fixed_jan_feb=fixed_fit["r2"], r2_zarc_window=moved_fit["r2"],
        r2_gain=moved_fit["r2"] - fixed_fit["r2"],
        tmax_coef_fixed=fixed_fit["t_coef"], tmax_coef_zarc=moved_fit["t_coef"])
    return rows.assign(region=region.code), summary


def main() -> None:
    args = sys.argv[1:]
    source = "zarc"
    if "--sowing" in args:
        at = args.index("--sowing")
        source = args[at + 1]
        args = args[:at] + args[at + 2:]
    if source not in ("zarc", "conab"):
        raise SystemExit(f"[{TAG}] --sowing must be zarc or conab")
    OUT.mkdir(parents=True, exist_ok=True)
    summaries, pooled = [], []
    for region in select_regions(args or ["BR"]):
        if region.country != "BR":
            continue
        try:
            sowing = sowing_days(region) if source == "zarc" else conab_sowing(region)
            features = window_features(region, sowing)
        except FileNotFoundError as error:
            log(TAG, f"{region.key}: SKIPPED - {error}")
            continue
        features.to_csv(region.proc / f"regional_window_features_{source}.csv", index=False,
                        float_format="%.3f")
        unmatched = int(sowing.sowing_day_from_sep1.isna().sum())
        rows, summary = comparison_rows(region, features)
        if summary:
            summary["municipalities_without_zarc_match"] = unmatched
            summaries.append(summary)
            pooled.append(rows)
            log(TAG, f"{region.key}: sowing day {summary['sowing_day_median']:.0f}, "
                     f"R2 fixed {summary['r2_fixed_jan_feb']:.3f} -> {source} window "
                     f"{summary['r2_zarc_window']:.3f} ({unmatched} unmatched)")
    if not summaries:
        raise SystemExit(f"[{TAG}] nothing computed")
    everything = pd.concat(pooled, ignore_index=True)
    fixed_fit = within_r2(everything, "tmax_critical", "pcp_critical")
    moved_fit = within_r2(everything, "rw_tmax_mean", "rw_prcp_mm")
    summaries.append(dict(
        region="ALL", municipalities=int(everything.fips5.nunique()), n=len(everything),
        sowing_day_median=float(everything.sowing_day_from_sep1.median()),
        r2_fixed_jan_feb=fixed_fit["r2"], r2_zarc_window=moved_fit["r2"],
        r2_gain=moved_fit["r2"] - fixed_fit["r2"],
        tmax_coef_fixed=fixed_fit["t_coef"], tmax_coef_zarc=moved_fit["t_coef"]))
    table = pd.DataFrame(summaries)
    table.to_csv(OUT / f"br_regional_window_comparison_{source}.csv", index=False,
                 float_format="%.4f")
    (OUT / f"br_regional_window_config_{source}.json").write_text(json.dumps(dict(
        run=time.strftime("%Y-%m-%d"), pod_fill_days_after_sowing=[POD_FILL_START, POD_FILL_END],
        sowing_source="ZARC lowest-risk decade, mean of three maturity groups (br_20)"
        if source == "zarc" else "Conab five-year-mean date of 50% sown, by state (script 52)",
        model="detrended log yield ~ Tmax + Tmax^2 + rain + rain^2, within municipality",
        min_years=MIN_YEARS,
        caveat="the pod-fill offsets are assumed, not calibrated on observed phenology",
    ), indent=2))
    log(TAG, f"-> {(OUT / f'br_regional_window_comparison_{source}.csv').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
