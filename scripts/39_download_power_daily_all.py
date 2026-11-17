"""39 - NASA POWER daily weather, both countries, 1981-2025, with soil moisture.

Rebuilds data/raw/<region>/power_daily.csv.gz (git-ignored, so absent from a
fresh clone) for every US county and every soybean-producing Brazilian
municipality, in the exact layout scripts 17/18 and br_04/br_05/br_10 read,
and adds what the literature review found missing:

  gwetroot, gwettop  root-zone (0-100 cm) and surface (0-5 cm) soil wetness,
                     fraction of saturation 0-1 (MERRA-2 land model). The
                     water variable Ortiz-Bobea et al. (2019) show is needed
                     to separate drought from heat. A no-key stand-in for
                     NLDAS-2 / ERA5-Land (scripts 44 and 45 need a login).
  rh_pct             2 m relative humidity
  year 2025          scripts 17 and br_04 stopped at 2024

POWER's daily record starts 1981-01-01; 1980 for the US comes from Daymet
(script 40).

Resumable by region: a region whose file already holds every unit through
2025 is skipped; an incomplete region is fetched again in full. Units that
fail are listed in results/<region>/39_provenance_power_daily.json and are
absent from the file, so check that list before using the features.

Usage:  python scripts/39_download_power_daily_all.py [US|BR|US:IA|BR:MT ...]
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests

from _gap import centroids, log, select_regions

TAG = "39"
API = "https://power.larc.nasa.gov/api/temporal/daily/point"
RENAME = {
    "T2M_MAX": "tmax_c", "T2M_MIN": "tmin_c", "T2M": "tmean_c",
    "T2MDEW": "tdew_c", "PRECTOTCORR": "prcp_mm", "ALLSKY_SFC_SW_DWN": "srad_mj",
    "GWETROOT": "gwetroot", "GWETTOP": "gwettop", "RH2M": "rh_pct",
}
START, END = "19810101", "20251231"
FILL = -999.0
WORKERS = 3            # POWER is a free public service; stay polite
RETRIES = 5
TIMEOUT_S = 300
OUT_NAME = "power_daily.csv.gz"


def fetch(lat: float, lon: float) -> dict:
    params = dict(parameters=",".join(RENAME), community="AG",
                  longitude=f"{lon:.4f}", latitude=f"{lat:.4f}",
                  start=START, end=END, format="JSON")
    last_error = None
    for attempt in range(RETRIES):
        try:
            response = requests.get(API, params=params, timeout=TIMEOUT_S)
            response.raise_for_status()
            return response.json()["properties"]["parameter"]
        except (requests.RequestException, KeyError, ValueError) as error:
            last_error = error
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"POWER failed after {RETRIES} tries: {last_error}")


def to_frame(unit_id: str, parameters: dict) -> pd.DataFrame:
    frame = pd.DataFrame(parameters).rename(columns=RENAME)
    frame.index.name = "date"
    frame = frame.reset_index()
    values = frame[list(RENAME.values())].apply(pd.to_numeric, errors="coerce")
    values = values.replace(FILL, np.nan).astype("float32")
    date = pd.to_datetime(frame["date"], format="%Y%m%d")
    return pd.concat([
        pd.DataFrame({"unit_id": unit_id, "date": date}), values,
        pd.DataFrame({"year": date.dt.year, "doy": date.dt.dayofyear}),
    ], axis=1)


def units_already_done(path) -> set:
    if not path.exists():
        return set()
    try:
        # usecols also proves the file has the soil-moisture columns and is
        # not an older script 17 / br_04 pull; the last date proves it reaches END
        done = pd.read_csv(path, usecols=["unit_id", "date", "gwetroot"],
                           dtype={"unit_id": str})
        if done.date.max() < f"{END[:4]}-{END[4:6]}-{END[6:]}":
            return set()
        return set(done.unit_id)
    except (OSError, ValueError, EOFError) as error:
        log(TAG, f"unreadable {path.name} ({error}); will rebuild")
        return set()


def download_region(region) -> dict:
    points = centroids(region)
    out = region.raw / OUT_NAME
    if set(points.unit_id) <= units_already_done(out):
        log(TAG, f"{region.key}: complete ({len(points)} units), skipping")
        return dict(region=region.key, units=len(points), failed=[], skipped=True)

    log(TAG, f"{region.key}: fetching {len(points)} units")
    frames, failed = [], []

    def work(row):
        try:
            return to_frame(row.unit_id, fetch(row.lat, row.lon)), None
        except Exception as error:  # one bad unit must not abort the region
            return None, dict(unit_id=row.unit_id, error=repr(error))

    started = time.time()
    with ThreadPoolExecutor(WORKERS) as pool:
        for i, (frame, error) in enumerate(
                pool.map(work, points.itertuples(index=False)), 1):
            if error:
                failed.append(error)
                log(TAG, f"{region.key}: {error['unit_id']} FAILED {error['error']}")
            else:
                frames.append(frame)
            if i % 50 == 0 or i == len(points):
                log(TAG, f"{region.key}: {i}/{len(points)} in {time.time()-started:.0f}s")
    if not frames:
        raise SystemExit(f"[{TAG}] {region.key}: nothing retrieved")

    daily = pd.concat(frames, ignore_index=True)
    tmp = out.with_suffix(".tmp.gz")
    daily.to_csv(tmp, index=False, compression="gzip", float_format="%.2f")
    tmp.replace(out)
    region.res.mkdir(parents=True, exist_ok=True)
    report = dict(
        source="NASA POWER daily point API (MERRA-2 reanalysis)", url=API,
        accessed=time.strftime("%Y-%m-%d"), period=f"{START}-{END}",
        variables=RENAME, units_requested=len(points),
        units_returned=int(daily.unit_id.nunique()), daily_records=len(daily),
        failed=failed, fill_value=FILL,
        missing_pct={c: round(float(daily[c].isna().mean() * 100), 3)
                     for c in RENAME.values()},
        note="value of the ~0.5 degree MERRA-2 cell at the unit centroid; "
             "gwetroot/gwettop are fractions of saturation (0-1), not "
             "volumetric water content",
    )
    (region.res / "39_provenance_power_daily.json").write_text(
        json.dumps(report, indent=2))
    log(TAG, f"{region.key}: wrote {out.name} "
             f"({out.stat().st_size/1e6:.0f} MB, {len(daily):,} rows, "
             f"{len(failed)} failed)")
    return dict(region=region.key, units=len(points), failed=failed, skipped=False)


def main() -> None:
    results = [download_region(r) for r in select_regions(sys.argv[1:])]
    failed = sum(len(r["failed"]) for r in results)
    log(TAG, f"done: {len(results)} regions, {failed} failed units")
    if failed:
        log(TAG, "re-run the same command to retry the failed units' regions")


if __name__ == "__main__":
    main()
