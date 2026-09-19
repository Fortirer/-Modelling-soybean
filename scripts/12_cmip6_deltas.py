"""12 - CMIP6 change factors for Illinois counties (replaces the arbitrary
perturbations of script 09 with scenario-grounded deltas).

Method: delta change-factor. Raw GCM output is not fed to the yield model --
it carries systematic bias and the model was trained on nClimDiv scales. Instead
we take each GCM's CHANGE between a historical baseline and a future window and
apply that change to the observed county record (script 13).

  temperature : additive        delta_T = future_mean - baseline_mean  (K == degC)
  precipitation: multiplicative ratio   = future_mean / baseline_mean
  humidity    : additive        delta_RH = future_mean - baseline_mean (% points)

Relative humidity is pulled because holding it constant is not the neutral
choice it appears to be. Vapour pressure deficit is the larger of the two
warming channels for yield -- Lobell and colleagues attribute more loss at 2 C
warming to the associated VPD rise than to the warming itself -- and CMIP6
projects substantial RH decline over North America in summer. Assuming RH
constant therefore suppresses the dominant damage mechanism.

Deltas are computed per calendar month, per model, per scenario, per horizon,
and bilinearly interpolated from the GCM grid to each county centroid, so the
north-south gradient across Illinois is retained at whatever resolution the
model actually resolves.

Source: CMIP6 monthly means (Amon) from the AWS Open Data registry, bucket
s3://cmip6-pds. Anonymous access, no credentials. Zarr, so only the Illinois
subset is transferred.
"""
import sys, json, warnings
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _cfg import RAW, PROC, RES

warnings.filterwarnings("ignore", category=FutureWarning)

BUCKET = "cmip6-pds"
MEMBERS = {                      # one realisation per model, spanning low->high ECS
    "INM-CM5-0":     "r1i1p1f1",
    "GFDL-ESM4":     "r1i1p1f1",
    "MIROC6":        "r1i1p1f1",
    "MPI-ESM1-2-LR": "r1i1p1f1",
    "MRI-ESM2-0":    "r1i1p1f1",
    "ACCESS-ESM1-5": "r1i1p1f1",
    "EC-Earth3":     "r1i1p1f1",
    "CanESM5":       "r1i1p1f1",
    "UKESM1-0-LL":   "r1i1p1f2",
}
VARS      = ["tas", "tasmax", "pr", "hurs"]
BASELINE  = (1985, 2014)                      # historical reference period
HORIZONS  = {"mid_century": (2040, 2069), "late_century": (2070, 2099)}
SCENARIOS = ["ssp245", "ssp585"]
BOX       = dict(lat=(33.0, 46.0), lon=(-95.0, -83.0))   # generous, for interpolation


def centroids():
    """County centroid (lon, lat) from the staged polygon file, keyed by fips5."""
    rows = []
    for line in (RAW / "il_county_boundaries.txt").read_text().splitlines():
        if not line.strip():
            continue
        fips, coords = line.split("|", 1)
        pts = np.array([[float(x) for x in p.split(",")] for p in coords.split()])
        # polygon is closed (last point repeats the first); drop the duplicate
        if len(pts) > 1 and np.allclose(pts[0], pts[-1]):
            pts = pts[:-1]
        rows.append(dict(fips5=fips.strip(), lon=pts[:, 0].mean(), lat=pts[:, 1].mean()))
    d = pd.DataFrame(rows)
    print(f"[12] county centroids     : {len(d)}  "
          f"lat {d.lat.min():.2f}-{d.lat.max():.2f}  lon {d.lon.min():.2f}-{d.lon.max():.2f}")
    return d


ACTIVITY = {"historical": "CMIP", "ssp245": "ScenarioMIP", "ssp585": "ScenarioMIP"}
INDEX_CACHE = None          # set in main(); {(activity, model): institution}


def build_index(fs, cache_path):
    """Map (activity, model) -> institution by listing two levels, once.

    Globbing '<bucket>/CMIP6/*/*/<model>/...' per store walks the whole bucket
    tree on every call, which is why the first version of this script stalled.
    Two listings up front replace all of it.
    """
    if cache_path.exists():
        raw = json.loads(cache_path.read_text())
        idx = {tuple(k.split("|")): v for k, v in raw.items()}
        print(f"[12] institution index    : {len(idx)} entries (cached)")
        return idx
    idx = {}
    for act in sorted(set(ACTIVITY.values())):
        for ip in fs.ls(f"{BUCKET}/CMIP6/{act}", detail=False):
            inst = ip.rstrip("/").split("/")[-1]
            try:
                models = fs.ls(ip, detail=False)
            except Exception:
                continue
            for mp in models:
                idx[(act, mp.rstrip("/").split("/")[-1])] = inst
        print(f"[12] indexed activity     : {act}", flush=True)
    cache_path.write_text(json.dumps({f"{a}|{m}": i for (a, m), i in idx.items()}, indent=1))
    print(f"[12] institution index    : {len(idx)} entries (written to {cache_path.name})")
    return idx


def find_store(fs, model, exp, member, var):
    """Newest version of one Zarr store, addressed exactly. None if absent."""
    inst = INDEX_CACHE.get((ACTIVITY[exp], model))
    if inst is None:
        return None
    base = f"{BUCKET}/CMIP6/{ACTIVITY[exp]}/{inst}/{model}/{exp}/{member}/Amon/{var}"
    try:
        grids = fs.ls(base, detail=False)
    except Exception:
        return None
    best = None
    for gp in grids:                       # usually one grid label, e.g. 'gn'
        try:
            vers = fs.ls(gp, detail=False)
        except Exception:
            continue
        for vp in sorted(vers):
            best = vp                      # versions sort chronologically (vYYYYMMDD)
    return best


def monthly_clim(xr, fs, path, y0, y1, pts):
    """Monthly climatology over [y0,y1] interpolated to the county centroids.

    Returns a (12, n_county) array, month index 1-12 on axis 0.
    """
    ds = xr.open_zarr(fs.get_mapper(path), consolidated=True, decode_times=True)
    name = [v for v in ds.data_vars if v in VARS][0]
    da = ds[name]

    # longitude convention: CMIP6 is usually 0-360
    lon360 = float(da.lon.max()) > 180.0
    tlon = pts.lon.values % 360 if lon360 else pts.lon.values
    blon = tuple(v % 360 for v in BOX["lon"]) if lon360 else BOX["lon"]

    da = da.sortby("lat").sortby("lon")
    da = da.sel(lat=slice(*BOX["lat"]), lon=slice(*sorted(blon)))

    yr = da.time.dt.year
    da = da.isel(time=((yr >= y0) & (yr <= y1)).values)
    if da.sizes["time"] == 0:
        raise ValueError(f"no months in {y0}-{y1}")

    clim = da.groupby("time.month").mean("time").load()
    out = clim.interp(
        lat=("county", pts.lat.values), lon=("county", tlon), method="linear"
    )
    arr = out.transpose("month", "county").values
    if np.isnan(arr).any():                      # coarse grid, fall back to nearest
        near = clim.interp(lat=("county", pts.lat.values), lon=("county", tlon),
                           method="nearest").transpose("month", "county").values
        arr = np.where(np.isnan(arr), near, arr)
    return arr


def main():
    global INDEX_CACHE
    import xarray as xr, s3fs
    fs = s3fs.S3FileSystem(anon=True)
    pts = centroids()
    INDEX_CACHE = build_index(fs, PROC / "cmip6_path_index.json")

    rows, skipped = [], []
    for model, member in MEMBERS.items():
        # ---- baseline (historical) -----------------------------------------
        base = {}
        try:
            for v in VARS:
                p = find_store(fs, model, "historical", member, v)
                if p is None:
                    raise FileNotFoundError(f"historical/{v}")
                base[v] = monthly_clim(xr, fs, p, *BASELINE, pts)
            print(f"[12] {model:15} baseline {BASELINE[0]}-{BASELINE[1]} ok", flush=True)
        except Exception as e:
            print(f"[12] {model:15} SKIPPED baseline: {e}", flush=True)
            skipped.append(dict(model=model, stage="historical", error=str(e)))
            continue

        # ---- futures --------------------------------------------------------
        for scen in SCENARIOS:
            for hz, (y0, y1) in HORIZONS.items():
                try:
                    fut = {}
                    for v in VARS:
                        p = find_store(fs, model, scen, member, v)
                        if p is None:
                            raise FileNotFoundError(f"{scen}/{v}")
                        fut[v] = monthly_clim(xr, fs, p, y0, y1, pts)
                except Exception as e:
                    print(f"[12] {model:15} {scen} {hz:12} SKIPPED: {e}", flush=True)
                    skipped.append(dict(model=model, stage=f"{scen}/{hz}", error=str(e)))
                    continue

                d_tas  = fut["tas"]    - base["tas"]         # K == degC, additive
                d_tmax = fut["tasmax"] - base["tasmax"]
                ratio  = fut["pr"] / np.where(base["pr"] == 0, np.nan, base["pr"])
                # relative humidity is a percentage, so its change is additive in
                # percentage points. It is pulled because holding RH constant
                # suppresses the vapour-pressure-deficit rise, and VPD is the
                # larger of the two warming channels for yield (Lobell et al.).
                d_hurs = fut["hurs"] - base["hurs"]

                for mi in range(12):
                    for ci, f5 in enumerate(pts.fips5.values):
                        rows.append(dict(
                            model=model, member=member, scenario=scen, horizon=hz,
                            year_start=y0, year_end=y1, fips5=f5, month=mi + 1,
                            d_tas_C=float(d_tas[mi, ci]),
                            d_tasmax_C=float(d_tmax[mi, ci]),
                            pr_ratio=float(ratio[mi, ci]),
                            d_hurs_pct=float(d_hurs[mi, ci])))
                jj = slice(6, 8)   # Jul-Aug, the critical window
                print(f"[12] {model:15} {scen} {hz:12} "
                      f"Jul-Aug dTmax {d_tmax[jj].mean():+.2f} C  "
                      f"precip x{ratio[jj].mean():.3f}  "
                      f"RH {d_hurs[jj].mean():+.2f} pp", flush=True)

    if not rows:
        raise SystemExit("[12] no deltas computed - nothing written")

    d = pd.DataFrame(rows)
    d.to_csv(PROC / "cmip6_deltas.csv", index=False)
    n_models = d.model.nunique()
    print(f"\n[12] wrote {len(d):,} rows  ({n_models} models x {d.scenario.nunique()} "
          f"scenarios x {d.horizon.nunique()} horizons x {d.fips5.nunique()} counties x 12 months)")
    print(f"[12] -> data/processed/cmip6_deltas.csv")

    prov = dict(
        source="CMIP6 monthly means (Amon), AWS Open Data registry s3://cmip6-pds",
        access="anonymous, no credentials", url="https://registry.opendata.aws/cmip6/",
        method="delta change-factor; additive for temperature, multiplicative for precipitation",
        baseline=f"{BASELINE[0]}-{BASELINE[1]} (historical experiment)",
        horizons={k: f"{v[0]}-{v[1]}" for k, v in HORIZONS.items()},
        scenarios=SCENARIOS, variables=VARS,
        models_requested=MEMBERS, models_delivered=sorted(d.model.unique()),
        n_models=int(n_models), skipped=skipped,
        spatial="bilinear interpolation from the native GCM grid to county centroids; "
                "GCM resolution is coarser than a county, so within-state gradients are "
                "only as sharp as the model resolves",
        caveats=[
            "One realisation per model; internal variability is not sampled.",
            "Monthly means only; no change in day-to-day or within-month extremes.",
            "Palmer drought indices (PDSI, Z-index) are NOT perturbed - CMIP6 does not "
            "supply them and deriving them needs a water-balance model. Scenario results "
            "therefore understate drought-driven yield loss.",
            "No agronomic adaptation, cultivar change or planting-date shift is assumed.",
        ])
    (RES / "12_provenance_cmip6.json").write_text(json.dumps(prov, indent=2))
    print(f"[12] -> results/12_provenance_cmip6.json")

    # headline ensemble signal, Jul-Aug critical window
    jul_aug = d[d.month.isin([7, 8])]
    s = (jul_aug.groupby(["scenario", "horizon"])
                .agg(dTmax_C=("d_tasmax_C", "mean"), pr_ratio=("pr_ratio", "mean"),
                     dRH_pp=("d_hurs_pct", "mean"))
                .reset_index())
    s["precip_pct"] = (s.pr_ratio - 1) * 100
    print("\n[12] ENSEMBLE MEAN, JULY-AUGUST CRITICAL WINDOW")
    print(s.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
