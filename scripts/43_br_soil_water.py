"""43 - Brazil soil: fill the SoilGrids gaps and add plant-available water.

Two gaps from docs/DADOS_FALTANTES.md:

  1. SoilGrids was incomplete for ~650 municipalities. br_08 lost whole
     properties (all five depths of, say, pH) whenever one REST call timed
     out. This script re-queries only the missing municipality x property
     pairs and appends them to data/raw/BR/<UF>/soilgrids_horizons.csv.
     Existing rows are never changed. Re-run br_09 afterwards to refresh
     soil_features.csv.

  2. Brazil had no available-water measure (the US has SSURGO's
     soil_aws_0_100cm), so br_10 could not run a soil water balance. Two
     estimates are produced, per municipality centroid:

       soil_aws_0_100cm      cm of water between field capacity (33 kPa) and
                             wilting point (1500 kPa) in the top metre, from
                             SoilGrids' own water-retention maps (wv0033,
                             wv1500). Same name and unit as the US column.
       soil_aws_0_100cm_sr   the same quantity from the Saxton & Rawls (2006)
                             pedotransfer function applied to SoilGrids sand,
                             clay and organic matter. Fitted on US soils and
                             known to misjudge oxidic Ferralsols; kept as a
                             cross-check and for municipalities where the
                             retention maps are empty.

Outputs
  data/raw/BR/<UF>/soilgrids_horizons.csv         (missing rows appended)
  data/raw/BR/<UF>/soilgrids_water_retention.csv  fips5, property, depth, value (vol %)
  data/processed/BR/<UF>/soil_awc_features.csv

Usage:  python scripts/43_br_soil_water.py [--no-download] [BR:MT ...]
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests

from _gap import centroids, log, select_regions
from _indices import saxton_rawls

TAG = "43"
API = "https://rest.isric.org/soilgrids/v2.0/properties/query"
DEPTH_CM = {"0-5cm": 5, "5-15cm": 10, "15-30cm": 15, "30-60cm": 30, "60-100cm": 40}
TOPSOIL = ("0-5cm", "5-15cm", "15-30cm")
# SoilGrids name -> (column name in this repo, divisor to reach its unit);
# identical to br_08 so appended rows match the existing ones
PROPERTIES = {
    "clay": ("clay_pct", 10), "sand": ("sand_pct", 10), "silt": ("silt_pct", 10),
    "soc": ("soc_pct", 100), "phh2o": ("ph_h2o", 10), "bdod": ("bd_kg_dm3", 100),
    "cec": ("cec_cmol_kg", 10),
}
WATER = {"wv0033": ("wv0033_pct", 10), "wv1500": ("wv1500_pct", 10)}
SOC_TO_OM = 1.724             # van Bemmelen factor
WORKERS = 2
RETRIES = 4
TIMEOUT_S = 60
PAUSE_S = 0.5


def query(lon: float, lat: float, names: list[str]) -> dict:
    """{soilgrids_name: {depth_label: raw_mean_or_None}} for one point."""
    params = [("lon", f"{lon:.4f}"), ("lat", f"{lat:.4f}"), ("value", "mean")]
    params += [("property", n) for n in names] + [("depth", d) for d in DEPTH_CM]
    last_error = None
    for attempt in range(RETRIES):
        try:
            response = requests.get(API, params=params, timeout=TIMEOUT_S)
            if response.status_code == 429:
                raise requests.HTTPError("rate limited (429)")
            response.raise_for_status()
            layers = response.json()["properties"]["layers"]
            time.sleep(PAUSE_S)
            return {layer["name"]: {d["label"]: d["values"].get("mean")
                                    for d in layer["depths"]} for layer in layers}
        except (requests.RequestException, KeyError, ValueError) as error:
            last_error = error
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"SoilGrids failed after {RETRIES} tries: {last_error}")


def to_rows(fips5: str, result: dict, mapping: dict) -> list[dict]:
    rows = []
    for name, depths in result.items():
        column, divisor = mapping[name]
        rows += [dict(fips5=fips5, property=column, depth=depth, value=raw / divisor)
                 for depth, raw in depths.items() if raw is not None]
    return rows


def fetch_many(points: pd.DataFrame, names_by_unit: dict, mapping: dict,
               label: str) -> tuple[pd.DataFrame, list]:
    todo = points[points.unit_id.isin(names_by_unit)]
    rows, failed = [], []

    def work(row):
        try:
            result = query(row.lon, row.lat, names_by_unit[row.unit_id])
            return to_rows(row.unit_id, result, mapping), None
        except RuntimeError as error:
            return [], dict(unit_id=row.unit_id, error=str(error))

    with ThreadPoolExecutor(WORKERS) as pool:
        for i, (new_rows, error) in enumerate(
                pool.map(work, todo.itertuples(index=False)), 1):
            rows += new_rows
            if error:
                failed.append(error)
            if i % 50 == 0 or i == len(todo):
                log(TAG, f"{label}: {i}/{len(todo)} points, {len(rows)} values")
    return pd.DataFrame(rows, columns=["fips5", "property", "depth", "value"]), failed


def write_atomic(frame: pd.DataFrame, path) -> None:
    """Write beside the target, then swap, so a crash cannot truncate it."""
    partial = path.with_suffix(".part")
    frame.to_csv(partial, index=False)
    partial.replace(path)


def fill_horizons(region, points: pd.DataFrame) -> dict:
    """Append municipality x property pairs absent from soilgrids_horizons.csv."""
    path = region.raw / "soilgrids_horizons.csv"
    original = pd.read_csv(path, dtype={"fips5": str})
    existing = original.dropna(subset=["value"])
    have = set(zip(existing.fips5, existing.property))
    to_soilgrids = {column: name for name, (column, _) in PROPERTIES.items()}
    missing = {unit: [to_soilgrids[c] for c in to_soilgrids if (unit, c) not in have]
               for unit in points.unit_id}
    missing = {unit: names for unit, names in missing.items() if names}
    if not missing:
        return dict(units_incomplete=0, values_added=0, failed=[])
    new, failed = fetch_many(points, missing, PROPERTIES, f"{region.key} horizons")
    if len(new):
        write_atomic(pd.concat([original, new], ignore_index=True), path)
    return dict(units_incomplete=len(missing), values_added=len(new),
                units_still_incomplete=len(missing) - new.fips5.nunique()
                if len(new) else len(missing), failed=failed)


def fetch_water(region, points: pd.DataFrame) -> dict:
    path = region.raw / "soilgrids_water_retention.csv"
    existing = (pd.read_csv(path, dtype={"fips5": str}) if path.exists()
                else pd.DataFrame(columns=["fips5", "property", "depth", "value"]))
    todo = {u: list(WATER) for u in points.unit_id if u not in set(existing.fips5)}
    if not todo:
        return dict(units_fetched=0, failed=[])
    new, failed = fetch_many(points, todo, WATER, f"{region.key} water")
    combined = pd.concat([existing, new], ignore_index=True) if len(existing) else new
    write_atomic(combined, path)
    return dict(units_fetched=int(new.fips5.nunique()), failed=failed)


def layer_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Long SoilGrids rows to one row per municipality x depth."""
    wide = frame.pivot_table(index=["fips5", "depth"], columns="property",
                             values="value", aggfunc="first").reset_index()
    return wide.assign(thickness_cm=wide.depth.map(DEPTH_CM))


def weighted(layers: pd.DataFrame, column: str, name: str) -> pd.Series:
    """Thickness-weighted mean of `column` per municipality."""
    valid = layers.dropna(subset=[column])
    total = (valid[column] * valid.thickness_cm).groupby(valid.fips5).sum()
    return (total / valid.thickness_cm.groupby(valid.fips5).sum()).rename(name)


def column_cm(layers: pd.DataFrame, column: str, name: str) -> pd.Series:
    """Water column (cm) over the full metre; NaN unless all 5 layers exist."""
    valid = layers.dropna(subset=[column])
    grouped = (valid[column] * valid.thickness_cm).groupby(valid.fips5)
    return grouped.sum().where(grouped.count() == len(DEPTH_CM)).rename(name)


def awc_features(region) -> pd.DataFrame:
    horizons = layer_table(pd.read_csv(region.raw / "soilgrids_horizons.csv",
                                       dtype={"fips5": str}))
    needed = {"sand_pct", "clay_pct", "soc_pct"}
    if not needed <= set(horizons.columns):
        raise ValueError(f"{region.key}: horizons lack {sorted(needed - set(horizons.columns))}")
    estimate = saxton_rawls(horizons.sand_pct, horizons.clay_pct,
                            horizons.soc_pct * SOC_TO_OM)
    horizons = horizons.assign(awc_sr=estimate["awc"], fc_sr=estimate["fc"],
                               wp_sr=estimate["wp"])
    top = horizons[horizons.depth.isin(TOPSOIL)]
    sub = horizons[~horizons.depth.isin(TOPSOIL)]
    columns = [
        weighted(top, "awc_sr", "soil_awc_topsoil_sr"),
        weighted(sub, "awc_sr", "soil_awc_subsoil_sr"),
        weighted(top, "fc_sr", "soil_fc_topsoil_sr"),
        weighted(top, "wp_sr", "soil_wp_topsoil_sr"),
        column_cm(horizons, "awc_sr", "soil_aws_0_100cm_sr"),
    ]
    water_path = region.raw / "soilgrids_water_retention.csv"
    if water_path.exists():
        water = layer_table(pd.read_csv(water_path, dtype={"fips5": str}))
        if {"wv0033_pct", "wv1500_pct"} <= set(water.columns):
            water = water.assign(
                fc=water.wv0033_pct / 100.0, wp=water.wv1500_pct / 100.0,
                awc=np.maximum(water.wv0033_pct - water.wv1500_pct, 0.0) / 100.0)
            top_w = water[water.depth.isin(TOPSOIL)]
            columns += [
                weighted(top_w, "awc", "soil_awc_topsoil"),
                weighted(water[~water.depth.isin(TOPSOIL)], "awc", "soil_awc_subsoil"),
                weighted(top_w, "fc", "soil_fc_topsoil"),
                weighted(top_w, "wp", "soil_wp_topsoil"),
                column_cm(water, "awc", "soil_aws_0_100cm"),
            ]
    return pd.concat(columns, axis=1).rename_axis("fips5").reset_index()


def build_region(region, download: bool) -> None:
    points = centroids(region)
    report = dict(region=region.key, accessed=time.strftime("%Y-%m-%d"),
                  units=len(points), source="ISRIC SoilGrids 2.0 REST", url=API)
    if download:
        report["horizons_gap_fill"] = fill_horizons(region, points)
        report["water_retention"] = fetch_water(region, points)
    features = awc_features(region)
    features.to_csv(region.proc / "soil_awc_features.csv", index=False,
                    float_format="%.4f")
    report["awc_rows"] = len(features)
    report["nulls"] = {c: int(n) for c, n in features.isna().sum().items() if n}
    report["median_aws_0_100cm_sr"] = round(float(features.soil_aws_0_100cm_sr.median()), 2)
    if "soil_aws_0_100cm" in features:
        report["median_aws_0_100cm"] = round(float(features.soil_aws_0_100cm.median()), 2)
    region.res.mkdir(parents=True, exist_ok=True)
    (region.res / "43_soil_water_report.json").write_text(json.dumps(report, indent=2))
    log(TAG, f"{region.key}: {len(features)} municipalities, median AWS 0-100 cm "
             f"SoilGrids={report.get('median_aws_0_100cm')} cm, "
             f"Saxton-Rawls={report['median_aws_0_100cm_sr']} cm")


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--no-download"]
    download = "--no-download" not in sys.argv[1:]
    for region in select_regions(args or ["BR"]):
        if region.country != "BR":
            continue
        try:
            build_region(region, download)
        except (FileNotFoundError, ValueError) as error:
            log(TAG, f"{region.key}: SKIPPED - {error}")


if __name__ == "__main__":
    main()
