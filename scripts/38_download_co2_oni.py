"""38 - Global series: annual atmospheric CO2 and the ONI El Nino index.

Both are single small public files, identical for the US and Brazil, so they
live in data/raw/global/ rather than under a state.

  co2_annual_mlo.csv   NOAA GML Mauna Loa annual mean CO2 (ppm), 1959-present.
                       Input for the CO2-fertilisation term of the projections
                       (Jagermeyr et al. 2021). In a fixed-effects panel the
                       time trend already absorbs CO2; it is only needed when
                       the model has an explicit CO2 response.
  oni_monthly.csv      NOAA CPC Oceanic Nino Index (3-month running mean of
                       Nino-3.4 SST anomalies), 1950-present. Predictor in
                       von Bloh et al. (2023).
  oni_crop_year.csv    ONI averaged over each country's season, one row per
                       crop year, ready to merge on "year".

Usage:  python scripts/38_download_co2_oni.py
"""
import io
import json
import time

import numpy as np
import pandas as pd
import requests

from _gap import GLOBAL_RAW, ROOT, log

TAG = "38"
CO2_URL = "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_annmean_mlo.csv"
ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
TIMEOUT_S = 60
# centre month of each 3-month ONI season label
SEASON_CENTRE_MONTH = {
    "DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6,
    "JJA": 7, "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12,
}
US_SEASON_MONTHS = (5, 6, 7, 8)          # AMJ..JAS centres: the US season
BR_SEASON_MONTHS_CUR = (10, 11, 12)      # SON, OND, NDJ: planting year
BR_SEASON_MONTHS_NEXT = (1, 2)           # DJF, JFM: same season, following year
EL_NINO, LA_NINA = 0.5, -0.5


def get_text(url: str) -> str:
    response = requests.get(url, timeout=TIMEOUT_S)
    response.raise_for_status()
    return response.text


def parse_co2(text: str) -> pd.DataFrame:
    table = pd.read_csv(io.StringIO(text), comment="#")
    table = table.rename(columns={"mean": "co2_ppm", "unc": "co2_unc_ppm"})
    if not {"year", "co2_ppm"} <= set(table.columns):
        raise ValueError(f"unexpected CO2 columns: {list(table.columns)}")
    return table[["year", "co2_ppm", "co2_unc_ppm"]]


def parse_oni(text: str) -> pd.DataFrame:
    table = pd.read_csv(io.StringIO(text), sep=r"\s+")
    table.columns = [c.lower() for c in table.columns]
    if not {"seas", "yr", "anom"} <= set(table.columns):
        raise ValueError(f"unexpected ONI columns: {list(table.columns)}")
    return pd.DataFrame({
        "season": table["seas"],
        "year": table["yr"].astype(int),
        "month": table["seas"].map(SEASON_CENTRE_MONTH).astype(int),
        "oni": table["anom"].astype(float),
    })


def oni_by_crop_year(oni: pd.DataFrame) -> pd.DataFrame:
    """Season-mean ONI per crop year for each country.

    US crop year = calendar year. Brazil crop year = planting year, so
    January-February values are assigned to the previous year (IBGE files
    that crop under planting year + 1; script 47 applies the shift).
    """
    us_all = oni[oni.month.isin(US_SEASON_MONTHS)].groupby("year").oni
    us = (us_all.mean().where(us_all.size() == len(US_SEASON_MONTHS))
          .rename("oni_us_season"))
    cur = oni[oni.month.isin(BR_SEASON_MONTHS_CUR)].assign(crop_year=lambda d: d.year)
    nxt = oni[oni.month.isin(BR_SEASON_MONTHS_NEXT)].assign(crop_year=lambda d: d.year - 1)
    br_all = pd.concat([cur, nxt])
    counts = br_all.groupby("crop_year").oni.size()
    br = (br_all.groupby("crop_year").oni.mean()
          .where(counts == len(BR_SEASON_MONTHS_CUR) + len(BR_SEASON_MONTHS_NEXT))
          .rename("oni_br_season"))
    out = (pd.concat([us, br], axis=1).dropna(how="all").sort_index()
           .rename_axis("year").reset_index())
    for country in ("us", "br"):
        value = out[f"oni_{country}_season"]
        phase = np.select([value <= LA_NINA, value >= EL_NINO],
                          ["la_nina", "el_nino"], default="neutral")
        out[f"enso_{country}"] = pd.Series(phase, index=out.index).where(value.notna())
    return out


def main() -> None:
    GLOBAL_RAW.mkdir(parents=True, exist_ok=True)
    co2 = parse_co2(get_text(CO2_URL))
    oni = parse_oni(get_text(ONI_URL))
    crop = oni_by_crop_year(oni)
    co2.to_csv(GLOBAL_RAW / "co2_annual_mlo.csv", index=False)
    oni.to_csv(GLOBAL_RAW / "oni_monthly.csv", index=False)
    crop.to_csv(GLOBAL_RAW / "oni_crop_year.csv", index=False, float_format="%.3f")
    (ROOT / "results" / "38_provenance_co2_oni.json").write_text(json.dumps(dict(
        accessed=time.strftime("%Y-%m-%d"),
        co2=dict(source="NOAA GML, Mauna Loa annual mean CO2", url=CO2_URL,
                 years=[int(co2.year.min()), int(co2.year.max())], rows=len(co2)),
        oni=dict(source="NOAA CPC Oceanic Nino Index (ERSSTv5)", url=ONI_URL,
                 years=[int(oni.year.min()), int(oni.year.max())], rows=len(oni),
                 thresholds=dict(el_nino=EL_NINO, la_nina=LA_NINA)),
    ), indent=2))
    log(TAG, f"CO2 {co2.year.min()}-{co2.year.max()} ({len(co2)} rows), "
             f"ONI {oni.year.min()}-{oni.year.max()} ({len(oni)} rows) "
             f"-> data/raw/global/")


if __name__ == "__main__":
    main()
