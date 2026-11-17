"""44 - NLDAS-2 Noah monthly soil moisture for US county centroids.  NEEDS A LOGIN.

The soil-moisture source of Ortiz-Bobea et al. (2019). Script 42 already
provides MERRA-2 root-zone wetness for both countries without a login; this
script adds the finer (0.125 degree) North American product for the US.

NOT RUN when this script was written (2026-11-16): NASA GES DISC requires a
free Earthdata account, and credentials are never stored in this repository.
The request and file layout follow the GES DISC documentation but the script
has not been exercised against the live service. Expect to adjust
FILE_TEMPLATE or VARIABLES if GES DISC has changed them.

Before running:
  1. Create an account at https://urs.earthdata.nasa.gov/
  2. Generate a token (Profile -> Generate Token) and, in the SAME terminal:
         PowerShell:  $env:EARTHDATA_TOKEN = "<token>"
         bash:        export EARTHDATA_TOKEN="<token>"
  3. Authorise the "NASA GESDISC DATA ARCHIVE" application in your profile.

Output: data/raw/<ST>/nldas_soil_moisture_monthly.csv
  fips5, year, month, soilm_0_10cm, soilm_0_100cm, soilm_0_200cm   (kg m-2)
The per-month NetCDF files are cached in data/raw/global/nldas_cache/
(git-ignored); delete the folder when done.

Usage:  python scripts/44_download_nldas_soil_moisture.py [US:IA ...]
"""
import os
import sys
import time

import pandas as pd
import requests
import xarray as xr

from _gap import GLOBAL_RAW, centroids, log, select_regions

TAG = "44"
FILE_TEMPLATE = ("https://hydro1.gesdisc.eosdis.nasa.gov/data/NLDAS/"
                 "NLDAS_NOAH0125_M.2.0/{year}/NLDAS_NOAH0125_M.A{year}{month:02d}.020.nc")
VARIABLES = {"SoilM_0_10cm": "soilm_0_10cm", "SoilM_0_100cm": "soilm_0_100cm",
             "SoilM_0_200cm": "soilm_0_200cm"}
YEARS = range(1980, 2026)
CACHE = GLOBAL_RAW / "nldas_cache"
TIMEOUT_S = 300
RETRIES = 3


def token() -> str:
    value = os.environ.get("EARTHDATA_TOKEN", "").strip()
    if not value:
        raise SystemExit(f"[{TAG}] EARTHDATA_TOKEN is not set. See the docstring "
                         f"of this script for the three setup steps.")
    return value


def download(year: int, month: int, bearer: str):
    target = CACHE / f"NLDAS_NOAH0125_M.A{year}{month:02d}.nc"
    if target.exists() and target.stat().st_size > 0:
        return target
    url = FILE_TEMPLATE.format(year=year, month=month)
    for attempt in range(RETRIES):
        try:
            response = requests.get(url, headers={"Authorization": f"Bearer {bearer}"},
                                    timeout=TIMEOUT_S)
            if response.status_code in (401, 403):
                raise SystemExit(f"[{TAG}] access denied ({response.status_code}): "
                                 f"check the token and the GESDISC authorisation")
            response.raise_for_status()
            if response.content[:3] != b"CDF" and response.content[:4] != b"\x89HDF":
                raise SystemExit(f"[{TAG}] {url} did not return NetCDF (a login "
                                 f"page?). Check the token and the authorisation.")
            partial = target.with_suffix(".part")
            partial.write_bytes(response.content)
            partial.replace(target)
            return target
        except requests.RequestException as error:
            log(TAG, f"{year}-{month:02d} attempt {attempt + 1} failed: {error}")
            time.sleep(10 * (attempt + 1))
    return None


def sample(path, points: pd.DataFrame) -> pd.DataFrame:
    """Nearest-cell value of each variable at each point."""
    with xr.open_dataset(path) as dataset:
        missing = set(VARIABLES) - set(dataset.data_vars)
        if missing:
            raise ValueError(f"{path.name} lacks {sorted(missing)}; "
                             f"found {sorted(dataset.data_vars)}")
        picked = dataset[list(VARIABLES)].sel(
            lat=xr.DataArray(points.lat.to_numpy(), dims="unit"),
            lon=xr.DataArray(points.lon.to_numpy(), dims="unit"),
            method="nearest").isel(time=0, drop=True).load()
    frame = picked.to_dataframe()[list(VARIABLES)].rename(columns=VARIABLES)
    return frame.assign(unit_id=points.unit_id.to_numpy()).reset_index(drop=True)


def main() -> None:
    bearer = token()
    regions = [r for r in select_regions(sys.argv[1:]) if r.country == "US"]
    points = pd.concat([centroids(r).assign(region=r.key) for r in regions],
                       ignore_index=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    frames, skipped = [], []
    for year in YEARS:
        for month in range(1, 13):
            path = download(year, month, bearer)
            if path is None:
                skipped.append(f"{year}-{month:02d}")
                continue
            frames.append(sample(path, points).assign(year=year, month=month))
        log(TAG, f"{year} done ({len(frames)} months so far)")
    if not frames:
        raise SystemExit(f"[{TAG}] nothing retrieved")
    table = pd.concat(frames, ignore_index=True).merge(
        points[["unit_id", "region"]], on="unit_id")
    for region in regions:
        part = table[table.region == region.key].drop(columns="region")
        part = part.rename(columns={"unit_id": "fips5"})[
            ["fips5", "year", "month", *VARIABLES.values()]]
        part.to_csv(region.raw / "nldas_soil_moisture_monthly.csv", index=False,
                    float_format="%.2f")
        log(TAG, f"{region.key}: {part.fips5.nunique()} counties, {len(part)} rows")
    if skipped:
        log(TAG, f"WARNING: {len(skipped)} months could not be downloaded: {skipped[:6]}...")


if __name__ == "__main__":
    main()
