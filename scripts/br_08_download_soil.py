"""BR 08 - Soil properties for every Mato Grosso municipality centroid, from
ISRIC SoilGrids v2.0 -- the global gridded (250m) analogue of SSURGO used by
the US pipeline's script 14. No API key; free REST point-query service.

WHY SOILGRIDS, NOT SSURGO
  SSURGO is a US-only NRCS product. SoilGrids is ISRIC's global machine-
  learning soil map, built from >200,000 profile observations worldwide
  including Brazil's own RADAMBRASIL/EMBRAPA legacy surveys, and it is the
  standard substitute cited in cross-continental soil-yield studies.

WHAT IT PULLS, and what it CANNOT give that SSURGO could
  clay, sand, silt (%), soc (organic carbon, converted to an organic-matter
  proxy via the standard Van Bemmelen factor 1.724), phh2o (pH in water),
  bdod (bulk density), cec (cation exchange capacity) -- one query per
  property, at five depth bins (0-5, 5-15, 15-30, 30-60, 60-100 cm), plus
  the dominant WRB (World Reference Base) soil class, the international
  taxonomy standard -- NOT the USDA order system SSURGO uses, so
  "mollisol_pct" (a US pipeline feature) has no WRB equivalent and is not
  computed here. What SoilGrids has no analogue for at all: available
  water capacity (awc), saturated hydraulic conductivity (ksat), and
  drainage class -- SSURGO-specific lab/mapped attributes with no global
  gridded product. Those three columns simply do not exist in this
  branch; downstream scripts must not assume they do.

REQUEST SHAPE AND PERFORMANCE, both discovered empirically
  Querying more than one property per request (even with all five depths)
  reliably 504-times-out on ISRIC's server, so this makes one request per
  (municipality, property). The classification endpoint's response time
  is wildly inconsistent under real use -- a first manual test returned in
  9s, but a full serial run measured per-point costs swinging from ~65s to
  over 260s with no clear pattern (server-side load, not this script), so
  a first version of this script (serial, one point at a time, no cache)
  took over two hours to reach half the state and lost ALL of that work
  when interrupted, since it only wrote output at the very end. This
  version fixes both problems: a per-municipality JSON cache under
  soilgrids_cache/ means a restart resumes instead of re-fetching, and a
  small thread pool overlaps several municipalities' network waits at
  once (these are I/O-bound waits, not CPU work, so concurrency is safe
  here in a way it would not be for a CPU-bound task).
"""
import sys, json, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _brcfg import RAW, RES, UF

PROP_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
CLASS_URL = "https://rest.isric.org/soilgrids/v2.0/classification/query"
DEPTHS = ["0-5cm", "5-15cm", "15-30cm", "30-60cm", "60-100cm"]
PROPERTIES = {
    "clay": ("clay_pct", 10),
    "sand": ("sand_pct", 10),
    "silt": ("silt_pct", 10),
    # soc's target unit is g/kg, NOT a percentage, unlike clay/sand/silt --
    # verified directly against a live API response after the first version
    # of this script silently used the same d_factor=10 as the percentage
    # properties, which produced soil organic matter around 27% (a peat-bog
    # number) for ordinary Cerrado topsoil. d_factor=100 (10 for the raw
    # scaling, x10 again for g/kg -> %) fixes it to the correct ~2-3% range.
    "soc":  ("soc_pct", 100),
    "phh2o": ("ph_h2o", 10),
    "bdod": ("bd_kg_dm3", 100),
    "cec":  ("cec_cmol_kg", 10),
}
MAX_WORKERS = 6
CACHE = None  # set in main() once RAW is known


def get_json(url, retries=3, timeout=30):
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as f:
                return json.loads(f.read().decode())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                json.JSONDecodeError):
            if attempt == retries - 1:
                return None
            time.sleep(2.0 * (attempt + 1))


def fetch_property(lon, lat, prop):
    url = (f"{PROP_URL}?lon={lon:.4f}&lat={lat:.4f}&property={prop}"
           f"&{'&'.join('depth=' + d for d in DEPTHS)}&value=mean")
    js = get_json(url)
    if not js:
        return {}
    out = {}
    for layer in js.get("properties", {}).get("layers", []):
        for depth in layer["depths"]:
            out[depth["label"]] = depth["values"].get("mean")
    return out


def fetch_classification(lon, lat):
    # single short attempt: the classification endpoint's tail latency is
    # long enough that retrying it here just burns wall time for a value
    # that's a nice-to-have, not load-bearing (br_09 works fine without it)
    url = f"{CLASS_URL}?lon={lon:.4f}&lat={lat:.4f}&number_classes=1"
    js = get_json(url, retries=2, timeout=25)
    return (js or {}).get("wrb_class_name")


def fetch_one(fips5, lon, lat):
    cache_file = CACHE / f"{fips5}.json"
    cached = json.loads(cache_file.read_text()) if cache_file.exists() else None
    # a cache entry's PROPERTIES are only trustworthy if at least one came
    # back with values; an all-empty result from a prior run (server under
    # load, short timeout) must NOT block a retry, or a bad run poisons
    # every future one for that municipality permanently
    props_ok = cached is not None and any(v for v in cached["properties"].values())

    if props_ok:
        result = cached
    else:
        result = {"fips5": fips5, "properties": {}, "wrb_class": None}
        for prop, (col, d_factor) in PROPERTIES.items():
            vals = fetch_property(lon, lat, prop)
            result["properties"][col] = {
                depth_label: (None if v is None else v / d_factor)
                for depth_label, v in vals.items()
            }

    # classification is cheap to retry on its own once properties are
    # already good, so a null from a prior run doesn't get stuck forever
    if not result.get("wrb_class"):
        result["wrb_class"] = fetch_classification(lon, lat)

    if any(v for v in result["properties"].values()):
        cache_file.write_text(json.dumps(result))
    return result


def centroids():
    rows = []
    for line in (RAW / "mt_municipio_boundaries.txt").read_text().splitlines():
        if not line.strip():
            continue
        code, coords = line.split("|", 1)
        pts = np.array([[float(x) for x in p.split(",")] for p in coords.split()])
        if len(pts) > 1 and np.allclose(pts[0], pts[-1]):
            pts = pts[:-1]
        rows.append(dict(fips5=code.strip(), lon=pts[:, 0].mean(), lat=pts[:, 1].mean()))
    return pd.DataFrame(rows)


def main():
    global CACHE
    CACHE = RAW / "soilgrids_cache"
    CACHE.mkdir(parents=True, exist_ok=True)

    pts = centroids()
    already = sum(1 for _ in CACHE.glob("*.json"))
    print(f"[br08] municipalities : {len(pts)}  ({already} already cached from a "
          f"previous run)")
    print(f"[br08] properties     : {list(PROPERTIES)}  x  {len(DEPTHS)} depths each")
    print(f"[br08] concurrency    : {MAX_WORKERS} municipalities at once")

    t0 = time.time()
    results, done = [], 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(fetch_one, r.fips5, r.lon, r.lat): r.fips5
                  for r in pts.itertuples(index=False)}
        for fut in as_completed(futures):
            fips5 = futures[fut]
            try:
                results.append(fut.result())
            except Exception as e:
                print(f"[br08] {fips5} FAILED: {e}", flush=True)
            done += 1
            if done % 10 == 0 or done == len(pts):
                print(f"[br08] {done:>3}/{len(pts)}  {time.time()-t0:5.0f}s", flush=True)

    rows, class_rows = [], []
    for res in results:
        class_rows.append(dict(fips5=res["fips5"], wrb_class=res["wrb_class"]))
        for col, depths in res["properties"].items():
            for depth_label, v in depths.items():
                rows.append(dict(fips5=res["fips5"], property=col,
                                 depth=depth_label, value=v))

    d = pd.DataFrame(rows)
    out = RAW / "soilgrids_horizons.csv"
    d.to_csv(out, index=False)
    cls = pd.DataFrame(class_rows)
    cls_out = RAW / "soilgrids_wrb_class.csv"
    cls.to_csv(cls_out, index=False)

    print(f"\n[br08] property values : {len(d):,}")
    print(f"[br08] municipalities  : {d.fips5.nunique()}")
    print(f"[br08] -> data/raw/BR/{UF}/soilgrids_horizons.csv")
    print(f"[br08] WRB classification, top classes:")
    print(cls.wrb_class.value_counts(dropna=False).head(10).to_string())
    print(f"[br08] -> data/raw/BR/{UF}/soilgrids_wrb_class.csv")

    (RES / "br08_provenance_soil.json").write_text(json.dumps(dict(
        source="ISRIC SoilGrids v2.0, 250m global gridded soil property maps",
        url="https://www.isric.org/explore/soilgrids", api=PROP_URL,
        accessed=time.strftime("%Y-%m-%d"), access_note="free, no key, global",
        properties=list(PROPERTIES.values()), depths=DEPTHS,
        classification="WRB (World Reference Base), NOT USDA soil taxonomy -- "
                       "no mollisol_pct equivalent, see docstring; single-"
                       "attempt best-effort, some municipalities may be null",
        no_equivalent_for=["awc (available water capacity)",
                           "ksat (saturated hydraulic conductivity)",
                           "drainage class"],
        municipalities=int(d.fips5.nunique()),
        wrb_null_count=int(cls.wrb_class.isna().sum()),
    ), indent=2))
    print(f"[br08] -> results/BR/{UF}/br08_provenance_soil.json")


if __name__ == "__main__":
    main()
