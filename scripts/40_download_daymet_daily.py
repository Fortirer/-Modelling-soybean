"""40 - Daymet daily weather for every US county centroid, 1980-2025.

Closes two gaps named in docs/DADOS_FALTANTES.md:

  * US daily climate for 1980 and 2025. NASA POWER (script 17) starts in
    1981 and was pulled to 2024, so the first and last yield years had no
    daily weather and no degree days.
  * Daily Tmax/Tmin on a fine grid, which is what the >30 C degree-day
    specification of Schlenker & Roberts (2009) needs. Daymet is 1 km;
    POWER is ~50 km.

Daymet is also the exact weather source of Khaki, Wang & Archontoulis
(2020): precipitation, solar radiation, Tmax, Tmin and vapour pressure. The
report suggests PRISM or gridMET; both need whole-CONUS grids (tens of GB)
or a point service that took ~2 minutes per variable per county when tested
on 2026-11-16. Daymet's single-pixel API returns all variables for the full
record in ~2 s, with no key.

Output: data/raw/<state>/daymet_daily.csv.gz
  unit_id, date, tmax_c, tmin_c, prcp_mm, srad_wm2, vp_pa, dayl_s, year, doy

Daymet has no 31 December in leap years (every year is 365 days).

Usage:  python scripts/40_download_daymet_daily.py [US:IA ...]
"""
import io
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

from _gap import centroids, log, select_regions

TAG = "40"
API = "https://daymet.ornl.gov/single-pixel/api/data"
VARS = "tmax,tmin,prcp,srad,vp,dayl"
START, END = "1980-01-01", "2025-12-31"
RENAME = {
    "tmax (deg c)": "tmax_c", "tmin (deg c)": "tmin_c",
    "prcp (mm/day)": "prcp_mm", "srad (W/m^2)": "srad_wm2",
    "vp (Pa)": "vp_pa", "dayl (s)": "dayl_s",
}
WORKERS = 3
RETRIES = 5
TIMEOUT_S = 180
OUT_NAME = "daymet_daily.csv.gz"


def parse(text: str, unit_id: str) -> pd.DataFrame:
    """Daymet CSV (a free-text header, then a table) to a tidy frame."""
    lines = text.splitlines()
    header_at = next((i for i, line in enumerate(lines)
                      if line.startswith("year,yday")), None)
    if header_at is None:
        raise ValueError("no 'year,yday' header in Daymet response")
    table = pd.read_csv(io.StringIO("\n".join(lines[header_at:])))
    missing = set(RENAME) - set(table.columns)
    if missing:
        raise ValueError(f"Daymet response lacks columns {sorted(missing)}")
    date = pd.to_datetime(table["year"].astype(str), format="%Y") \
        + pd.to_timedelta(table["yday"] - 1, unit="D")
    values = table[list(RENAME)].rename(columns=RENAME).astype("float32")
    return pd.concat([
        pd.DataFrame({"unit_id": unit_id, "date": date}), values,
        pd.DataFrame({"year": table["year"], "doy": table["yday"]}),
    ], axis=1)


def fetch(lat: float, lon: float) -> str:
    params = dict(lat=f"{lat:.4f}", lon=f"{lon:.4f}", vars=VARS,
                  start=START, end=END)
    last_error = None
    for attempt in range(RETRIES):
        try:
            response = requests.get(API, params=params, timeout=TIMEOUT_S)
            response.raise_for_status()
            return response.text
        except requests.RequestException as error:
            last_error = error
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Daymet failed after {RETRIES} tries: {last_error}")


def units_already_done(path) -> set:
    if not path.exists():
        return set()
    try:
        return set(pd.read_csv(path, usecols=["unit_id"], dtype=str).unit_id)
    except (OSError, ValueError, EOFError) as error:
        log(TAG, f"unreadable {path.name} ({error}); will rebuild")
        return set()


def download_region(region) -> dict:
    points = centroids(region)
    out = region.raw / OUT_NAME
    if set(points.unit_id) <= units_already_done(out):
        log(TAG, f"{region.key}: complete ({len(points)} units), skipping")
        return dict(region=region.key, failed=[])

    log(TAG, f"{region.key}: fetching {len(points)} units")
    frames, failed = [], []

    def work(row):
        try:
            return parse(fetch(row.lat, row.lon), row.unit_id), None
        except Exception as error:  # one bad unit must not abort the state
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
    (region.res / "40_provenance_daymet_daily.json").write_text(json.dumps(dict(
        source="Daymet V4 R1 daily surface weather, 1 km (ORNL DAAC)",
        doi="https://doi.org/10.3334/ORNLDAAC/2129", url=API,
        accessed=time.strftime("%Y-%m-%d"), period=f"{START}..{END}",
        variables=RENAME, units_requested=len(points),
        units_returned=int(daily.unit_id.nunique()), daily_records=len(daily),
        years=[int(daily.year.min()), int(daily.year.max())], failed=failed,
        note="value of the 1 km pixel at the county centroid, not a cropland-"
             "weighted county mean; no 31 December in leap years",
    ), indent=2))
    log(TAG, f"{region.key}: wrote {out.name} "
             f"({out.stat().st_size/1e6:.0f} MB, {len(daily):,} rows, "
             f"{len(failed)} failed)")
    return dict(region=region.key, failed=failed)


def main() -> None:
    regions = [r for r in select_regions(sys.argv[1:]) if r.country == "US"]
    results = [download_region(r) for r in regions]
    failed = sum(len(r["failed"]) for r in results)
    log(TAG, f"done: {len(results)} states, {failed} failed units")


if __name__ == "__main__":
    main()
