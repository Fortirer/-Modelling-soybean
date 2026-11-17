"""46 - NEX-GDDP-CMIP6 daily projections at unit centroids (optional, heavy).

Why: the open question at the end of docs/DADOS_FALTANTES.md. Scripts 12 and
br_12 hold MONTHLY CMIP6 deltas. A monthly delta shifts every day of the month
by the same amount, so it cannot change how often a day crosses 30 C the way a
model's own daily series does. If projections use degree days (script 41),
the daily, bias-corrected, 0.25 degree NEX-GDDP-CMIP6 is the matching input
(Thrasher et al. 2022).

Source: public AWS bucket s3://nex-gddp-cmip6, read over HTTPS, no login.

COST. Each file is one model x scenario x variable x year for the whole globe,
about 245 MB, and there is no public subsetting service, so the whole file is
downloaded, sampled at the centroids and deleted. One model, one scenario,
30 years, tasmax + tasmin + pr = 90 files = ~22 GB of transfer (about 1-2 h on
a fast line). The full 8-model design of script 12 with a historical baseline
and two SSPs x two horizons is ~3,600 files (~900 GB). Start small.

Output, one file per region x model x scenario, appended year by year so an
interrupted run resumes:
  data/raw/<region>/nex_gddp/<model>_<scenario>.csv.gz
      unit_id, date, tmax_c, tmin_c, prcp_mm

Usage (defaults: MPI-ESM1-2-LR, ssp585, 2041-2070, all regions):
  python scripts/46_download_nex_gddp_daily.py --model MPI-ESM1-2-LR \
      --scenario ssp245 --years 2041 2070 BR:MT US:IL
  python scripts/46_download_nex_gddp_daily.py --scenario historical --years 1981 2010
"""
import argparse
import re
import tempfile
from pathlib import Path

import pandas as pd
import requests
import xarray as xr

from _gap import centroids, log, select_regions

TAG = "46"
BUCKET = "https://nex-gddp-cmip6.s3.us-west-2.amazonaws.com/"
# same ensemble members as script 12
MEMBERS = {
    "INM-CM5-0": "r1i1p1f1", "GFDL-ESM4": "r1i1p1f1", "MIROC6": "r1i1p1f1",
    "MPI-ESM1-2-LR": "r1i1p1f1", "MRI-ESM2-0": "r1i1p1f1",
    "ACCESS-ESM1-5": "r1i1p1f1", "EC-Earth3": "r1i1p1f1", "CanESM5": "r1i1p1f1",
    "UKESM1-0-LL": "r1i1p1f2",
}
VARIABLES = {"tasmax": "tmax_c", "tasmin": "tmin_c", "pr": "prcp_mm"}
KELVIN = 273.15
SECONDS_PER_DAY = 86400.0     # pr is kg m-2 s-1
TIMEOUT_S = 600
CHUNK_BYTES = 1 << 20


def find_key(model: str, scenario: str, variable: str, year: int) -> str:
    """Bucket key of one year file, preferring the corrected _v2.0 release."""
    prefix = f"NEX-GDDP-CMIP6/{model}/{scenario}/{MEMBERS[model]}/{variable}/"
    response = requests.get(BUCKET, params={"prefix": prefix, "list-type": "2",
                                            "max-keys": "1000"}, timeout=60)
    response.raise_for_status()
    keys = [k for k in re.findall(r"<Key>([^<]+)</Key>", response.text)
            if re.search(rf"_{year}(_v\d\.\d)?\.nc$", k)]
    if not keys:
        raise FileNotFoundError(f"no {variable} file for {model} {scenario} {year}")
    return sorted(keys)[-1]          # "..._v2.0.nc" sorts after "....nc"


def download(key: str, folder: Path) -> Path:
    target = folder / Path(key).name
    with requests.get(BUCKET + key, stream=True, timeout=TIMEOUT_S) as response:
        response.raise_for_status()
        with open(target, "wb") as handle:
            for chunk in response.iter_content(CHUNK_BYTES):
                handle.write(chunk)
    return target


def sample(path: Path, variable: str, points: pd.DataFrame) -> pd.DataFrame:
    """Daily series of the nearest 0.25 degree cell for every point."""
    coder = xr.coders.CFDatetimeCoder(use_cftime=True)
    with xr.open_dataset(path, decode_times=coder) as dataset:
        picked = dataset[variable].sel(
            lat=xr.DataArray(points.lat.to_numpy(), dims="unit"),
            lon=xr.DataArray(points.lon.to_numpy() % 360.0, dims="unit"),
            method="nearest").load()
    values = picked.to_numpy()
    values = values * SECONDS_PER_DAY if variable == "pr" else values - KELVIN
    # model calendars differ (noleap, 360-day); keep the date as text
    dates = [f"{t.year:04d}-{t.month:02d}-{t.day:02d}" for t in picked["time"].to_numpy()]
    frame = pd.DataFrame(values, index=dates, columns=points.unit_id.to_numpy())
    return (frame.rename_axis("date").reset_index()
            .melt(id_vars="date", var_name="unit_id", value_name=VARIABLES[variable]))


def years_done(path: Path) -> set:
    if not path.exists():
        return set()
    try:
        dates = pd.read_csv(path, usecols=["date"]).date
    except EOFError as error:
        raise SystemExit(f"[{TAG}] {path} is truncated (an earlier run was "
                         f"interrupted). Delete it and run again.") from error
    return set(dates.str[:4].astype(int))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model", default="MPI-ESM1-2-LR", choices=sorted(MEMBERS))
    parser.add_argument("--scenario", default="ssp585",
                        choices=["historical", "ssp126", "ssp245", "ssp370", "ssp585"])
    parser.add_argument("--years", nargs=2, type=int, default=[2041, 2070],
                        metavar=("FIRST", "LAST"))
    parser.add_argument("regions", nargs="*")
    args = parser.parse_args()

    regions = select_regions(args.regions)
    points = {r.key: centroids(r) for r in regions}
    outputs = {r.key: r.raw / "nex_gddp" / f"{args.model}_{args.scenario}.csv.gz"
               for r in regions}
    for path in outputs.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    done = {key: years_done(path) for key, path in outputs.items()}

    for year in range(args.years[0], args.years[1] + 1):
        pending = [r for r in regions if year not in done[r.key]]
        if not pending:
            continue
        merged = {r.key: None for r in pending}
        with tempfile.TemporaryDirectory() as folder:
            for variable in VARIABLES:
                path = download(find_key(args.model, args.scenario, variable, year),
                                Path(folder))
                for region in pending:
                    part = sample(path, variable, points[region.key])
                    previous = merged[region.key]
                    merged[region.key] = part if previous is None else previous.merge(
                        part, on=["date", "unit_id"])
                path.unlink()
        for region in pending:
            out = outputs[region.key]
            merged[region.key][["unit_id", "date", *VARIABLES.values()]].to_csv(
                out, mode="a", header=not out.exists(), index=False,
                compression="gzip", float_format="%.2f")
        log(TAG, f"{args.model} {args.scenario} {year}: {len(pending)} regions written")


if __name__ == "__main__":
    main()
