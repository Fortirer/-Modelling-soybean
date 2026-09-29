"""BR 12 - CMIP6 change factors for Mato Grosso municipalities. Direct port
of US script 12, changed only where geography and hemisphere require it:
  - centroids read from the Brazil municipality boundary file (br_03)
  - the "critical window" printed live during the run is Jan-Feb (the
    Brazilian-summer analogue of the US July-August window, see br_05/07's
    crop-year documentation), not Jul-Aug
Everything else -- the delta change-factor method, the S3 zarr access, the
institution-index caching, the nearest-neighbour interpolation fallback for
coarse-grid models, the per-combo NaN drop -- is identical, because none of
it is US-specific. This is exactly the kind of script br_00_config.py's
docstring flagged as "should port with no change in principle, not yet
tried" -- this is that attempt.
"""
import sys, json, warnings
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _brcfg import RAW, PROC, RES, UF

warnings.filterwarnings("ignore", category=FutureWarning)

BUCKET = "cmip6-pds"
MEMBERS = {
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
BASELINE  = (1985, 2014)
HORIZONS  = {"mid_century": (2040, 2069), "late_century": (2070, 2099)}
SCENARIOS = ["ssp245", "ssp585"]
BOX_PAD   = 3.0


def centroids():
    fname = RAW / "mt_municipio_boundaries.txt"
    if not fname.exists():
        raise SystemExit(f"[br12] {fname} not found. Run br_03 first.")
    rows = []
    for line in fname.read_text().splitlines():
        if not line.strip():
            continue
        fips, coords = line.split("|", 1)
        pts = np.array([[float(x) for x in p.split(",")] for p in coords.split()])
        if len(pts) > 1 and np.allclose(pts[0], pts[-1]):
            pts = pts[:-1]
        rows.append(dict(fips5=fips.strip(), lon=pts[:, 0].mean(), lat=pts[:, 1].mean()))
    d = pd.DataFrame(rows)
    print(f"[br12] municipality centroids : {len(d)}  "
          f"lat {d.lat.min():.2f}-{d.lat.max():.2f}  lon {d.lon.min():.2f}-{d.lon.max():.2f}")
    return d


ACTIVITY = {"historical": "CMIP", "ssp245": "ScenarioMIP", "ssp585": "ScenarioMIP"}
INDEX_CACHE = None


def build_index(fs, cache_path):
    if cache_path.exists():
        raw = json.loads(cache_path.read_text())
        idx = {tuple(k.split("|")): v for k, v in raw.items()}
        print(f"[br12] institution index    : {len(idx)} entries (cached)")
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
        print(f"[br12] indexed activity     : {act}", flush=True)
    cache_path.write_text(json.dumps({f"{a}|{m}": i for (a, m), i in idx.items()}, indent=1))
    print(f"[br12] institution index    : {len(idx)} entries (written to {cache_path.name})")
    return idx


def find_store(fs, model, exp, member, var):
    inst = INDEX_CACHE.get((ACTIVITY[exp], model))
    if inst is None:
        return None
    base = f"{BUCKET}/CMIP6/{ACTIVITY[exp]}/{inst}/{model}/{exp}/{member}/Amon/{var}"
    try:
        grids = fs.ls(base, detail=False)
    except Exception:
        return None
    best = None
    for gp in grids:
        try:
            vers = fs.ls(gp, detail=False)
        except Exception:
            continue
        for vp in sorted(vers):
            best = vp
    return best


def monthly_clim(xr, fs, path, y0, y1, pts, box):
    ds = xr.open_zarr(fs.get_mapper(path), consolidated=True, decode_times=True)
    name = [v for v in ds.data_vars if v in VARS][0]
    da = ds[name]

    lon360 = float(da.lon.max()) > 180.0
    tlon = pts.lon.values % 360 if lon360 else pts.lon.values
    blon = tuple(v % 360 for v in box["lon"]) if lon360 else box["lon"]

    da = da.sortby("lat").sortby("lon")
    da = da.sel(lat=slice(*box["lat"]), lon=slice(*sorted(blon)))

    yr = da.time.dt.year
    da = da.isel(time=((yr >= y0) & (yr <= y1)).values)
    if da.sizes["time"] == 0:
        raise ValueError(f"no months in {y0}-{y1}")

    clim = da.groupby("time.month").mean("time").load()
    out = clim.interp(
        lat=("muni", pts.lat.values), lon=("muni", tlon), method="linear"
    )
    arr = out.transpose("month", "muni").values
    if np.isnan(arr).any():
        near = clim.interp(lat=("muni", pts.lat.values), lon=("muni", tlon),
                           method="nearest",
                           kwargs=dict(fill_value=None)).transpose("month", "muni").values
        arr = np.where(np.isnan(arr), near, arr)
    return arr


def main():
    global INDEX_CACHE
    import xarray as xr, s3fs
    fs = s3fs.S3FileSystem(anon=True, config_kwargs=dict(
        connect_timeout=30, read_timeout=60,
        retries=dict(max_attempts=3, mode="standard")))
    pts = centroids()
    box = dict(lat=(float(pts.lat.min()) - BOX_PAD, float(pts.lat.max()) + BOX_PAD),
              lon=(float(pts.lon.min()) - BOX_PAD, float(pts.lon.max()) + BOX_PAD))
    print(f"[br12] interpolation box     : lat {box['lat']}  lon {box['lon']}")
    INDEX_CACHE = build_index(fs, PROC / "cmip6_path_index.json")

    rows, skipped = [], []
    for model, member in MEMBERS.items():
        base = {}
        try:
            for v in VARS:
                p = find_store(fs, model, "historical", member, v)
                if p is None:
                    raise FileNotFoundError(f"historical/{v}")
                base[v] = monthly_clim(xr, fs, p, *BASELINE, pts, box)
            print(f"[br12] {model:15} baseline {BASELINE[0]}-{BASELINE[1]} ok", flush=True)
        except Exception as e:
            print(f"[br12] {model:15} SKIPPED baseline: {e}", flush=True)
            skipped.append(dict(model=model, stage="historical", error=str(e)))
            continue

        for scen in SCENARIOS:
            for hz, (y0, y1) in HORIZONS.items():
                try:
                    fut = {}
                    for v in VARS:
                        p = find_store(fs, model, scen, member, v)
                        if p is None:
                            raise FileNotFoundError(f"{scen}/{v}")
                        fut[v] = monthly_clim(xr, fs, p, y0, y1, pts, box)
                except Exception as e:
                    print(f"[br12] {model:15} {scen} {hz:12} SKIPPED: {e}", flush=True)
                    skipped.append(dict(model=model, stage=f"{scen}/{hz}", error=str(e)))
                    continue

                d_tas  = fut["tas"]    - base["tas"]
                d_tmax = fut["tasmax"] - base["tasmax"]
                ratio  = fut["pr"] / np.where(base["pr"] == 0, np.nan, base["pr"])
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
                jj = slice(0, 2)   # Jan-Feb, the Brazilian critical window
                print(f"[br12] {model:15} {scen} {hz:12} "
                      f"Jan-Feb dTmax {d_tmax[jj].mean():+.2f} C  "
                      f"precip x{ratio[jj].mean():.3f}  "
                      f"RH {d_hurs[jj].mean():+.2f} pp", flush=True)

    if not rows:
        raise SystemExit("[br12] no deltas computed - nothing written")

    d = pd.DataFrame(rows)
    bad_cols = ["d_tas_C", "d_tasmax_C", "pr_ratio", "d_hurs_pct"]
    has_nan = d.groupby(["model", "scenario", "horizon"])[bad_cols].apply(
        lambda g: bool(g.isna().any().any()))
    nan_combos = has_nan[has_nan].index.tolist()
    if nan_combos:
        for model, scen, hz in nan_combos:
            n_bad = int(d[(d.model == model) & (d.scenario == scen) & (d.horizon == hz)][bad_cols]
                       .isna().any(axis=1).sum())
            print(f"[br12] {model:15} {scen} {hz:12} DROPPED: {n_bad} of "
                  f"{len(d[(d.model==model)&(d.scenario==scen)&(d.horizon==hz)])} rows "
                  f"interpolated to NaN", flush=True)
            skipped.append(dict(model=model, stage=f"{scen}/{hz}",
                                error=f"{n_bad} municipality-months interpolated to NaN"))
        mask = pd.Series(True, index=d.index)
        for model, scen, hz in nan_combos:
            mask &= ~((d.model == model) & (d.scenario == scen) & (d.horizon == hz))
        d = d[mask].reset_index(drop=True)

    d.to_csv(PROC / "cmip6_deltas.csv", index=False)
    n_models = d.model.nunique()
    print(f"\n[br12] wrote {len(d):,} rows  ({n_models} models x {d.scenario.nunique()} "
          f"scenarios x {d.horizon.nunique()} horizons x {d.fips5.nunique()} "
          f"municipalities x 12 months)")
    print(f"[br12] -> data/processed/BR/{UF}/cmip6_deltas.csv")

    prov = dict(
        source="CMIP6 monthly means (Amon), AWS Open Data registry s3://cmip6-pds",
        access="anonymous, no credentials", url="https://registry.opendata.aws/cmip6/",
        method="delta change-factor; additive for temperature, multiplicative for precipitation",
        baseline=f"{BASELINE[0]}-{BASELINE[1]} (historical experiment)",
        horizons={k: f"{v[0]}-{v[1]}" for k, v in HORIZONS.items()},
        scenarios=SCENARIOS, variables=VARS,
        models_requested=MEMBERS, models_delivered=sorted(d.model.unique()),
        n_models=int(n_models), skipped=skipped,
        spatial="bilinear interpolation from the native GCM grid to municipality "
                "centroids, same method as the US pipeline's script 12",
        critical_window="Jan-Feb (Brazilian-summer analogue of the US Jul-Aug window)",
        caveats=[
            "One realisation per model; internal variability is not sampled.",
            "Monthly means only; no change in day-to-day or within-month extremes.",
            "No Palmer drought index equivalent to perturb for Brazil (see br_05).",
            "No agronomic adaptation, cultivar change or planting-date shift is assumed.",
        ])
    (RES / "br12_provenance_cmip6.json").write_text(json.dumps(prov, indent=2))
    print(f"[br12] -> results/BR/{UF}/br12_provenance_cmip6.json")

    jan_feb = d[d.month.isin([1, 2])]
    s = (jan_feb.groupby(["scenario", "horizon"])
                .agg(dTmax_C=("d_tasmax_C", "mean"), pr_ratio=("pr_ratio", "mean"),
                     dRH_pp=("d_hurs_pct", "mean"))
                .reset_index())
    s["precip_pct"] = (s.pr_ratio - 1) * 100
    print("\n[br12] ENSEMBLE MEAN, JAN-FEB CRITICAL WINDOW")
    print(s.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
