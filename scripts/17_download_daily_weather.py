"""17 - Daily weather from NASA POWER for every county centroid.

Why daily, when the pipeline already has monthly nClimDiv:

  Monthly means erase the extremes that actually damage the crop. Schlenker &
  Roberts (2009, PNAS) show soybean yield rises with temperature to roughly
  30 C and falls steeply above it, and that the damage tracks the DISTRIBUTION
  of daily temperatures, not the monthly mean. In a monthly dataset a August
  averaging 30 C with no day above 34 and one with five days at 38 are the same
  number. They are not the same August.

Why NASA POWER rather than Daymet or PRISM:

  POWER is global. Daymet is better over North America but stops at the border.
  This analysis is intended as the source domain for Brazilian soybean (Zhang,
  Guan et al. 2025), and transfer learning needs features computed identically
  in both places. A slightly coarser but consistent source beats two better but
  incompatible ones.

Source: NASA POWER daily point API, MERRA-2 reanalysis. Free, no key, global.
One request returns the full record for one point.

Variables, chosen so that everything script 18 derives is computable anywhere:
  T2M_MAX, T2M_MIN, T2M  degC   temperature, for GDD / EDD / thermal time
  T2MDEW                 degC   dewpoint, gives actual vapour pressure for VPD
  PRECTOTCORR            mm/day bias-corrected precipitation, for water balance
  ALLSKY_SFC_SW_DWN      MJ/m2  solar radiation (sparse before 1984; script 18
                                falls back to Hargreaves, which needs only
                                temperature and latitude)
"""
import sys, json, time, urllib.request, urllib.error
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _cfg import RAW, RES, STATE

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
No API key. Values of {FILL} are POWER's fill marker and are read as null here.
The same call works for any latitude and longitude on earth, which is the point
of choosing POWER: Brazilian municipal centroids go through this script
unchanged, only the centroid table differs.
"""


def centroids():
    """County centroid (lon, lat) from the staged polygon file, keyed by fips5.

    Filename is state-aware; nothing below depends on the points being Illinois
    counties, which is the point of choosing a global source (POWER).
    """
    rows = []
    for line in (RAW / f"{STATE.lower()}_county_boundaries.txt").read_text().splitlines():
        if not line.strip():
            continue
        fips, coords = line.split("|", 1)
        pts = np.array([[float(x) for x in p.split(",")] for p in coords.split()])
        if len(pts) > 1 and np.allclose(pts[0], pts[-1]):
            pts = pts[:-1]
        rows.append(dict(unit_id=fips.strip(), lon=pts[:, 0].mean(), lat=pts[:, 1].mean()))
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
    print(f"[17] points to fetch : {len(pts)}")
    print(f"[17] period          : {START} to {END}")

    frames, failed = [], []
    t0 = time.time()
    for i, r in enumerate(pts.itertuples(index=False), 1):
        try:
            par = fetch(r.lat, r.lon)
        except Exception as e:
            print(f"[17] {r.unit_id} FAILED: {e}", flush=True)
            failed.append(dict(unit_id=r.unit_id, error=str(e)))
            continue
        d = pd.DataFrame(par)
        d.index.name = "date"
        d = d.reset_index()
        d.insert(0, "unit_id", r.unit_id)
        frames.append(d)
        if i % 20 == 0 or i == len(pts):
            print(f"[17] {i:>3}/{len(pts)}  {time.time()-t0:5.0f}s  "
                  f"{sum(len(f) for f in frames):,} rows", flush=True)
        time.sleep(0.2)          # be polite to a free public service

    if not frames:
        raise SystemExit("[17] nothing retrieved")
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
    print(f"\n[17] daily records : {len(d):,}")
    print(f"[17] units         : {d.unit_id.nunique()}")
    print(f"[17] years         : {d.year.min()}-{d.year.max()}")
    print(f"[17] -> data/raw/power_daily.csv.gz  ({mb:.1f} MB)")
    print("\n[17] missing values by variable")
    for c in num:
        n = int(d[c].isna().sum())
        print(f"     {c:10} {n:>8,}  ({n/len(d)*100:.2f}%)")

    (RES / "17_provenance_daily_weather.json").write_text(json.dumps(dict(
        source="NASA POWER daily point API (MERRA-2 reanalysis)",
        url=API, portal="https://power.larc.nasa.gov/",
        accessed=time.strftime("%Y-%m-%d"), access_note="free, no API key, global",
        community="AG", period=f"{START}-{END}",
        variables_requested=VARS, units_requested=len(pts),
        units_returned=int(d.unit_id.nunique()), daily_records=int(len(d)),
        failed=failed, fill_value=FILL, recipe=RECIPE.strip(),
        missing_pct={c: round(float(d[c].isna().mean() * 100), 3) for c in num},
        spatial_note="POWER is ~0.5 degree MERRA-2, coarser than a county; values "
                     "are the containing grid cell at the county centroid, not a "
                     "polygon average",
        why_power="global coverage, so Illinois and Brazil use one consistent "
                  "source for cross-scale transfer learning",
    ), indent=2))
    print(f"[17] -> results/17_provenance_daily_weather.json")
    if failed:
        print(f"[17] WARNING: {len(failed)} units failed")


if __name__ == "__main__":
    main()
