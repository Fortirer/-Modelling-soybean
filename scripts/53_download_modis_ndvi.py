"""53 - MODIS NDVI and EVI in the critical window, Brazilian municipalities.

The vegetation indices that von Bloh et al. (2023), Schwalbert et al. (2020)
and Azevedo & Boccato (2026) add to weather for WITHIN-SEASON yield
prediction. They are not usable for projections (no future NDVI exists),
which is why they enter only the prediction comparison, never the scenarios.

Source: MOD13Q1 v6.1 (Terra, 16-day composites, 250 m) through the ORNL DAAC
MODIS subset web service, no login. The service returns at most 10
composites per request, so each municipality costs one request per season
and band.

For each municipality centroid (the same point as every weather variable)
and each harvest year 2001-2025, the composites falling in January and
February are retrieved and summarised:

  ndvi_jf_max, ndvi_jf_mean, n_composites   (and evi_* if EVI is enabled)

Composites flagged as cloud or snow by the companion pixel-reliability band
are not requested separately: the 16-day maximum-value compositing already
favours clear observations, and requesting the flag would add a third call
per season. Low values from residual cloud therefore remain possible.

Limits. A 250 m pixel at the centroid is not a cropland mask (Schwalbert et
al. used the CAR registry for that); in municipalities where soy is a small
share of the land the pixel may be pasture or forest. Only municipalities in
the balanced panel (at least 20 years of yield and weather) are queried.

Outputs
  data/raw/BR/<UF>/modis_cache/<fips5>.json      one per municipality (resumable)
  data/processed/BR/<UF>/modis_ndvi_features.csv fips5, year, the columns above

Usage:  python scripts/53_download_modis_ndvi.py [BR:RS BR:PR ...]
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests

from _gap import centroids, log, select_regions

TAG = "53"
API = "https://modis.ornl.gov/rst/api/v1/MOD13Q1/subset"
# NDVI only by default: EVI is strongly correlated with it and doubles the
# download time. Add "evi": "250m_16_days_EVI" here to fetch it too.
BANDS = {"ndvi": "250m_16_days_NDVI"}
SCALE = 0.0001
FILL_MIN = -2000                     # values below this are fill
YEARS = range(2001, 2026)            # MOD13Q1 starts February 2000
WINDOW_DOY = (1, 59)                 # 1 January to 28 February
WORKERS = 8
RETRIES = 4
TIMEOUT_S = 120
DEFAULT_ORDER = ["RS", "PR", "MS", "SP", "GO", "MT", "MG", "TO", "MA", "BA"]
MIN_YEARS = 20


def request(lat: float, lon: float, band: str, year: int) -> list[dict]:
    params = dict(latitude=f"{lat:.5f}", longitude=f"{lon:.5f}",
                  startDate=f"A{year}{WINDOW_DOY[0]:03d}",
                  endDate=f"A{year}{WINDOW_DOY[1]:03d}",
                  kmAboveBelow=0, kmLeftRight=0, band=band)
    last_error = None
    for attempt in range(RETRIES):
        try:
            response = requests.get(API, params=params, timeout=TIMEOUT_S,
                                    headers={"Accept": "application/json"})
            response.raise_for_status()
            return [dict(date=s["calendar_date"], value=s["data"][0])
                    for s in response.json().get("subset", []) if s.get("data")]
        except (requests.RequestException, ValueError, KeyError) as error:
            last_error = error
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"MODIS subset failed: {last_error}")


def fetch_unit(cache_dir, row) -> str | None:
    """Download every season and band for one municipality into its cache file."""
    target = cache_dir / f"{row.unit_id}.json"
    if target.exists():
        cached = json.loads(target.read_text())
        if set(BANDS) <= set(cached.get("series", {})):
            return None                     # complete for the bands asked now
    record = {"fips5": row.unit_id, "lat": row.lat, "lon": row.lon,
              "window_doy": list(WINDOW_DOY), "series": {}}
    try:
        for name, band in BANDS.items():
            record["series"][name] = {str(y): request(row.lat, row.lon, band, y)
                                      for y in YEARS}
    except RuntimeError as error:
        return f"{row.unit_id}: {error}"
    if not any(record["series"][name][str(y)] for name in BANDS for y in YEARS):
        return f"{row.unit_id}: every response was empty; not cached, will retry"
    partial = target.with_suffix(".part")
    partial.write_text(json.dumps(record))
    partial.replace(target)
    return None


def summarise(cache_dir, units: set) -> pd.DataFrame:
    """Season summaries for the requested municipalities only.

    The 18 February composite spans about 18 February to 5 March, so the
    January-February window includes the first days of March.
    """
    rows = []
    for path in sorted(cache_dir.glob("*.json")):
        if path.stem not in units:
            continue
        record = json.loads(path.read_text())
        for year in YEARS:
            out = {"fips5": record["fips5"], "year": year}
            for name in BANDS:
                values = np.array([v["value"] for v in record["series"].get(name, {}).get(str(year), [])],
                                  dtype=float)
                values = values[values > FILL_MIN] * SCALE
                out[f"{name}_jf_max"] = values.max() if len(values) else np.nan
                out[f"{name}_jf_mean"] = values.mean() if len(values) else np.nan
                out["n_composites"] = len(values)
            rows.append(out)
    return pd.DataFrame(rows)


def balanced_units(region) -> set:
    final = region.proc.parent.parent.parent / "final" / "BR" / region.code \
        / "soja_mt_climate_1981_2024.csv"
    panel = pd.read_csv(final, dtype={"fips5": str}, usecols=["fips5", "in_balanced_panel"])
    return set(panel.fips5[panel.in_balanced_panel == 1])


def main() -> None:
    regions = [r for r in select_regions(sys.argv[1:] or ["BR"]) if r.country == "BR"]
    regions.sort(key=lambda r: DEFAULT_ORDER.index(r.code) if r.code in DEFAULT_ORDER else 99)
    for region in regions:
        points = centroids(region)
        points = points[points.unit_id.isin(balanced_units(region))]
        cache_dir = region.raw / "modis_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        todo = [r for r in points.itertuples(index=False)
                if not (cache_dir / f"{r.unit_id}.json").exists()]
        log(TAG, f"{region.key}: {len(points)} municipalities, {len(todo)} to fetch")
        failures = []
        started = time.time()
        with ThreadPoolExecutor(WORKERS) as pool:
            for i, error in enumerate(pool.map(lambda r: fetch_unit(cache_dir, r), todo), 1):
                if error:
                    failures.append(error)
                if i % 10 == 0 or i == len(todo):
                    log(TAG, f"{region.key}: {i}/{len(todo)} in {time.time() - started:.0f}s")
        features = summarise(cache_dir, set(points.unit_id))
        if len(features):
            features.to_csv(region.proc / "modis_ndvi_features.csv", index=False,
                            float_format="%.4f")
        log(TAG, f"{region.key}: wrote {features.fips5.nunique() if len(features) else 0} "
                 f"municipalities, {len(failures)} failed (re-run to retry)")


if __name__ == "__main__":
    main()
