"""45 - ERA5-Land monthly soil moisture for Brazilian municipalities.  NEEDS A LOGIN.

The soil-moisture source of Benso et al. (2025), 0.1 degree. Script 42 already
provides MERRA-2 root-zone wetness without a login; this adds the finer
product.

NOT RUN when this script was written (2026-11-16): the Copernicus Climate
Data Store requires a free account and a personal key, and credentials are
never stored in this repository. The request follows the CDS API
documentation but has not been exercised against the live service.

Before running:
  1. Create an account at https://cds.climate.copernicus.eu/ and accept the
     ERA5-Land licence on the dataset page.
  2. Put your key in the file  %USERPROFILE%\\.cdsapirc  (two lines):
         url: https://cds.climate.copernicus.eu/api
         key: <your personal access token>
  3. pip install cdsapi

Output: data/raw/BR/<UF>/era5land_soil_moisture_monthly.csv
  fips5, year, month, swvl1, swvl2, swvl3, swvl_0_100cm   (m3 m-3)
  Layers are 0-7, 7-28 and 28-100 cm; swvl_0_100cm is their depth-weighted
  mean. One NetCDF per state and decade is cached in
  data/raw/global/era5land_cache/ (git-ignored).

Usage:  python scripts/45_download_era5land_soil_moisture.py [BR:MT ...]
"""
import sys

import pandas as pd
import xarray as xr

from _gap import GLOBAL_RAW, centroids, log, select_regions

TAG = "45"
DATASET = "reanalysis-era5-land-monthly-means"
VARIABLES = {"volumetric_soil_water_layer_1": "swvl1",
             "volumetric_soil_water_layer_2": "swvl2",
             "volumetric_soil_water_layer_3": "swvl3"}
LAYER_CM = {"swvl1": 7, "swvl2": 21, "swvl3": 72}
YEAR_BLOCKS = [range(1981, 1991), range(1991, 2001), range(2001, 2011),
               range(2011, 2021), range(2021, 2026)]
CACHE = GLOBAL_RAW / "era5land_cache"
MARGIN_DEG = 0.2


def client():
    try:
        import cdsapi
    except ImportError as error:
        raise SystemExit(f"[{TAG}] cdsapi is not installed: pip install cdsapi") from error
    try:
        return cdsapi.Client()
    except Exception as error:   # cdsapi raises a bare Exception without a key
        raise SystemExit(f"[{TAG}] no CDS key found ({error}). See this script's "
                         f"docstring for the setup steps.") from error


def retrieve(cds, region, points: pd.DataFrame, years: range):
    target = CACHE / f"era5land_{region.code}_{years[0]}_{years[-1]}.nc"
    if target.exists() and target.stat().st_size > 0:
        return target
    partial = target.with_suffix(".part")
    area = [points.lat.max() + MARGIN_DEG, points.lon.min() - MARGIN_DEG,
            points.lat.min() - MARGIN_DEG, points.lon.max() + MARGIN_DEG]
    cds.retrieve(DATASET, {
        "product_type": ["monthly_averaged_reanalysis"],
        "variable": list(VARIABLES),
        "year": [str(y) for y in years],
        "month": [f"{m:02d}" for m in range(1, 13)],
        "time": ["00:00"],
        "area": [round(v, 2) for v in area],     # north, west, south, east
        "data_format": "netcdf", "download_format": "unarchived",
    }, str(partial))
    partial.replace(target)      # an interrupted retrieve never becomes a cache hit
    return target


def sample(path, points: pd.DataFrame) -> pd.DataFrame:
    with xr.open_dataset(path) as dataset:
        names = {v: v for v in VARIABLES.values() if v in dataset.data_vars}
        if len(names) != len(VARIABLES):
            raise ValueError(f"{path.name}: expected {sorted(VARIABLES.values())}, "
                             f"found {sorted(dataset.data_vars)}")
        time_name = "valid_time" if "valid_time" in dataset.coords else "time"
        picked = dataset[list(names)].sel(
            latitude=xr.DataArray(points.lat.to_numpy(), dims="unit"),
            longitude=xr.DataArray(points.lon.to_numpy(), dims="unit"),
            method="nearest").load()
        frame = picked.to_dataframe().reset_index()
    frame["fips5"] = points.unit_id.to_numpy()[frame["unit"].to_numpy()]
    when = pd.to_datetime(frame[time_name])
    frame = frame.assign(year=when.dt.year, month=when.dt.month)
    total_cm = sum(LAYER_CM.values())
    frame["swvl_0_100cm"] = sum(frame[c] * cm for c, cm in LAYER_CM.items()) / total_cm
    return frame[["fips5", "year", "month", *LAYER_CM, "swvl_0_100cm"]]


def main() -> None:
    cds = client()
    CACHE.mkdir(parents=True, exist_ok=True)
    for region in select_regions(sys.argv[1:] or ["BR"]):
        if region.country != "BR":
            continue
        points = centroids(region)
        frames = [sample(retrieve(cds, region, points, years), points)
                  for years in YEAR_BLOCKS]
        table = pd.concat(frames, ignore_index=True).sort_values(
            ["fips5", "year", "month"])
        table.to_csv(region.raw / "era5land_soil_moisture_monthly.csv",
                     index=False, float_format="%.4f")
        log(TAG, f"{region.key}: {table.fips5.nunique()} municipalities, "
                 f"{len(table)} rows, coastal nulls {int(table.swvl1.isna().sum())}")


if __name__ == "__main__":
    main()
