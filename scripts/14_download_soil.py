"""14 - Acquire SSURGO soil properties for Illinois counties.

Motivation: the panel has no soil data at all, so every persistent difference
between counties -- drainage, texture, organic matter, water-holding capacity --
is absorbed into the county fixed effect, where it cannot be examined. Khaki,
Wang & Archontoulis (2020) feed soil at ten depth layers to their CNN-RNN and
find it carries a large share of the explained variance.

Source: USDA-NRCS Soil Data Access (SDA), the public query service over SSURGO.
No API key. Illinois soil survey areas are county-based, so areasymbol 'IL019'
is Champaign County and maps directly to FIPS 17019.

Raw horizon records are staged unaggregated; script 15 does the aggregation, so
the weighting choices stay visible and reviewable.
"""
import sys, json, time, urllib.request, urllib.error
import pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _cfg import RAW, RES, STATE, STATE_FIPS, STATE_NAME

SDA_URL = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"

COLUMNS = """
       mu.mukey, mu.muacres, c.cokey, c.comppct_r, c.majcompflag, c.slope_r,
       c.drainagecl, c.taxorder, c.hydgrp,
       ch.hzdept_r, ch.hzdepb_r, ch.claytotal_r, ch.sandtotal_r, ch.silttotal_r,
       ch.om_r, ch.awc_r, ch.ph1to1h2o_r, ch.dbthirdbar_r, ch.ksat_r, ch.cec7_r
"""
JOINS = """
FROM legend l
JOIN mapunit  mu ON mu.lkey  = l.lkey
JOIN component c ON c.mukey  = mu.mukey
JOIN chorizon ch ON ch.cokey = c.cokey
"""
RECIPE = f"""
Reproduce:
  POST {SDA_URL}
  Content-Type: application/json
  {{"format": "JSON+COLUMNNAME", "query": "SELECT {' '.join(COLUMNS.split())} {' '.join(JOINS.split())} WHERE l.areasymbol = '<AREASYMBOL>'"}}
Survey areas are listed by:
  SELECT areasymbol, areaname FROM legend WHERE areasymbol LIKE '{STATE}%'
Illinois survey areas are county-based: areasymbol {STATE}019 -> FIPS {STATE_FIPS}019.
SSURGO is revised annually; record the access date with any results.
"""


def sda(sql, retries=3):
    body = json.dumps({"format": "JSON+COLUMNNAME", "query": sql}).encode()
    for attempt in range(retries):
        req = urllib.request.Request(SDA_URL, data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as f:
                return json.loads(f.read().decode()).get("Table", [])
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    return []


def main():
    areas = sda(f"SELECT areasymbol, areaname FROM legend "
                f"WHERE areasymbol LIKE '{STATE}%' ORDER BY areasymbol")[1:]
    # county surveys only: two letters plus three digits
    areas = [(a, n) for a, n in areas
             if len(a) == 5 and a[:2] == STATE and a[2:].isdigit()]
    print(f"[14] {STATE_NAME.title()} county soil survey areas : {len(areas)}")

    frames, failed = [], []
    for i, (asym, aname) in enumerate(areas, 1):
        try:
            rows = sda(f"SELECT {COLUMNS} {JOINS} WHERE l.areasymbol = '{asym}'")
        except Exception as e:
            print(f"[14] {asym} {aname:34} FAILED: {e}", flush=True)
            failed.append(dict(areasymbol=asym, areaname=aname, error=str(e)))
            continue
        if len(rows) < 2:
            print(f"[14] {asym} {aname:34} no rows", flush=True)
            failed.append(dict(areasymbol=asym, areaname=aname, error="no rows"))
            continue
        d = pd.DataFrame(rows[1:], columns=rows[0])
        d.insert(0, "fips5", STATE_FIPS + asym[2:])
        d.insert(1, "areasymbol", asym)
        frames.append(d)
        if i % 20 == 0 or i == len(areas):
            print(f"[14] {i:>3}/{len(areas)} areas, {sum(len(f) for f in frames):,} rows",
                  flush=True)

    if not frames:
        raise SystemExit("[14] no soil data retrieved")
    d = pd.concat(frames, ignore_index=True)
    d.to_csv(RAW / "ssurgo_il_horizons.csv", index=False)
    print(f"\n[14] horizon records : {len(d):,}")
    print(f"[14] counties        : {d.fips5.nunique()}")
    print(f"[14] map units       : {d.mukey.nunique():,}")
    print(f"[14] -> data/raw/ssurgo_il_horizons.csv")

    (RES / "14_provenance_soil.json").write_text(json.dumps(dict(
        source="USDA-NRCS Soil Data Access (SDA), SSURGO tabular",
        url=SDA_URL, portal="https://sdmdataaccess.sc.egov.usda.gov/",
        accessed=time.strftime("%Y-%m-%d"),
        access_note="public query service, no API key",
        tables=["legend", "mapunit", "component", "chorizon"],
        areas_requested=len(areas), areas_returned=int(d.fips5.nunique()),
        horizon_records=len(d), map_units=int(d.mukey.nunique()),
        failed=failed, recipe=RECIPE.strip(),
        representative_values="all *_r columns are SSURGO representative values",
        aggregation="none here; script 15 aggregates to county level",
    ), indent=2))
    print(f"[14] -> results/14_provenance_soil.json")
    if failed:
        print(f"[14] WARNING: {len(failed)} survey areas missing")


if __name__ == "__main__":
    main()
