"""BR 04 - Daily weather from NASA POWER for every Mato Grosso municipality
centroid. This is the transfer US script 17's docstring names outright: POWER
was chosen there specifically so Illinois and Brazil could share one
consistent daily-weather source. Same API, same variables, same fill-value
handling; only the centroid table and the date range differ (POWER's daily
record starts 1981, so this covers IBGE's production series from 1981
onward, not 1974-1980).
"""
import sys, json, time, urllib.request, urllib.error
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _brcfg import RAW, RES, UF

API = "https://power.larc.nasa.gov/api/temporal/daily/point"
VARS = ["T2M_MAX", "T2M_MIN", "T2M", "T2MDEW", "PRECTOTCORR", "ALLSKY_SFC_SW_DWN"]
START, END = "19810101", "20241231"
FILL = -999.0

RECIPE = f"""
Reproduce one point:
  GET {API}
      ?parameters={','.join(VARS)}
      &community=AG&longitude=<LON>&latitude=<LAT>
      &start={START}&end={END}&format=JSON
No API key. Identical call and variable set to the US pipeline's script 17;
only the centroid table (Brazilian municipalities here) differs.
"""


def centroids():
    rows = []
    for line in (RAW / "mt_municipio_boundaries.txt").read_text().splitlines():
        if not line.strip():
            continue
        code, coords = line.split("|", 1)
        pts = np.array([[float(x) for x in p.split(",")] for p in coords.split()])
        if len(pts) > 1 and np.allclose(pts[0], pts[-1]):
            pts = pts[:-1]
        rows.append(dict(unit_id=code.strip(), lon=pts[:, 0].mean(), lat=pts[:, 1].mean()))
    return pd.DataFrame(rows)


def fetch(lat, lon, retries=4):
    url = (f"{API}?parameters={','.join(VARS)}&community=AG"
           f"&longitude={lon:.4f}&latitude={lat:.4f}"
           f"&start={START}&end={END}&format=JSON")
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=300) as f:
                return json.loads(f.read().decode())["properties"]["parameter"]
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                KeyError, json.JSONDecodeError) as e:
            if attempt == retries - 1:
                raise
            time.sleep(3 * (attempt + 1))
    return {}


def main():
    pts = centroids()
    print(f"[br04] points to fetch : {len(pts)}")
    print(f"[br04] period          : {START} to {END}")

    frames, failed = [], []
    t0 = time.time()
    for i, r in enumerate(pts.itertuples(index=False), 1):
        try:
            par = fetch(r.lat, r.lon)
        except Exception as e:
            print(f"[br04] {r.unit_id} FAILED: {e}", flush=True)
            failed.append(dict(unit_id=r.unit_id, error=str(e)))
            continue
        d = pd.DataFrame(par)
        d.index.name = "date"
        d = d.reset_index()
        d.insert(0, "unit_id", r.unit_id)
        frames.append(d)
        if i % 20 == 0 or i == len(pts):
            print(f"[br04] {i:>3}/{len(pts)}  {time.time()-t0:5.0f}s  "
                  f"{sum(len(f) for f in frames):,} rows", flush=True)
        time.sleep(0.2)

    if not frames:
        raise SystemExit("[br04] nothing retrieved")
    d = pd.concat(frames, ignore_index=True)
    d = d.rename(columns={"T2M_MAX": "tmax_c", "T2M_MIN": "tmin_c", "T2M": "tmean_c",
                          "T2MDEW": "tdew_c", "PRECTOTCORR": "prcp_mm",
                          "ALLSKY_SFC_SW_DWN": "srad_mj"})
    num = ["tmax_c", "tmin_c", "tmean_c", "tdew_c", "prcp_mm", "srad_mj"]
    for c in num:
        d[c] = pd.to_numeric(d[c], errors="coerce").replace(FILL, np.nan)
    d["date"] = pd.to_datetime(d.date, format="%Y%m%d")
    d["year"] = d.date.dt.year
    d["doy"] = d.date.dt.dayofyear

    out = RAW / "power_daily.csv.gz"
    d.to_csv(out, index=False, compression="gzip")
    mb = out.stat().st_size / 1e6
    print(f"\n[br04] daily records : {len(d):,}")
    print(f"[br04] units         : {d.unit_id.nunique()}")
    print(f"[br04] years         : {d.year.min()}-{d.year.max()}")
    print(f"[br04] -> data/raw/BR/{UF}/power_daily.csv.gz  ({mb:.1f} MB)")
    print("\n[br04] missing values by variable")
    for c in num:
        n = int(d[c].isna().sum())
        print(f"     {c:10} {n:>8,}  ({n/len(d)*100:.2f}%)")

    (RES / "br04_provenance_daily_weather.json").write_text(json.dumps(dict(
        source="NASA POWER daily point API (MERRA-2 reanalysis)",
        url=API, portal="https://power.larc.nasa.gov/",
        accessed=time.strftime("%Y-%m-%d"), access_note="free, no API key, global",
        community="AG", period=f"{START}-{END}",
        variables_requested=VARS, units_requested=len(pts),
        units_returned=int(d.unit_id.nunique()), daily_records=int(len(d)),
        failed=failed, fill_value=FILL, recipe=RECIPE.strip(),
        missing_pct={c: round(float(d[c].isna().mean() * 100), 3) for c in num},
        same_source_as="US pipeline script 17 -- see its docstring on why "
                       "POWER was chosen for cross-scale transfer",
    ), indent=2))
    print(f"[br04] -> results/BR/{UF}/br04_provenance_daily_weather.json")
    if failed:
        print(f"[br04] WARNING: {len(failed)} units failed")


if __name__ == "__main__":
    main()
