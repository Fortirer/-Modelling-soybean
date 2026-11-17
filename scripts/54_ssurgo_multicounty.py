"""54 - SSURGO for counties surveyed inside multi-county survey areas.

Script 14 assumes each SSURGO survey area is one county (areasymbol SD011 ->
FIPS 46011). Some older surveys cover several counties under one symbol in
the 600 range (SD600, MN613, MI605, ...). Their horizons were downloaded but
filed under a non-existent FIPS (46600), so the counties they cover had no
soil: 9 in South Dakota, 2 in Minnesota and 5 in Michigan.

SSURGO's overlap tables say how many acres of each map unit fall in each
county (laoverlap with areatypename 'County or Parish', joined to
muaoverlap). This script queries them for every non-county survey area,
then re-files the already-downloaded horizon rows under the real county,
with muacres replaced by the acres of that map unit inside that county. A map
unit spanning two counties is therefore counted in both, each with its own
acres. Script 15 then aggregates them exactly as for any other county.

The original rows (fips5 46600 etc.) are kept, so nothing is lost; the new
rows are appended. Re-run script 15 for the state afterwards.

Usage:  python scripts/54_ssurgo_multicounty.py [US:SD US:MN US:MI ...]
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request

import pandas as pd

from _gap import log, select_regions

TAG = "54"
SDA_URL = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"
RETRIES = 4
AREA_PATTERN = re.compile(r"[A-Z]{2}\d{3}")
OVERLAP_SQL = """
SELECT lao.areasymbol AS county_symbol, mao.mukey, mao.areaovacres
FROM legend l
JOIN laoverlap lao ON lao.lkey = l.lkey AND lao.areatypename = 'County or Parish'
JOIN muaoverlap mao ON mao.lareaovkey = lao.lareaovkey
WHERE l.areasymbol = '{area}'
"""


def sda(sql: str) -> list[list]:
    body = json.dumps({"format": "JSON+COLUMNNAME", "query": " ".join(sql.split())}).encode()
    last_error = None
    for attempt in range(RETRIES):
        request = urllib.request.Request(SDA_URL, data=body,
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return json.loads(response.read().decode()).get("Table", [])
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                json.JSONDecodeError, UnicodeDecodeError) as error:
            last_error = error
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"Soil Data Access failed: {last_error}")


def region_fips(region) -> str:
    return pd.read_csv(region.proc / "production_clean.csv", dtype=str).fips5.iloc[0][:2]


def refile(region) -> dict:
    path = region.raw / "ssurgo_il_horizons.csv"
    horizons = pd.read_csv(path, dtype={"fips5": str, "areasymbol": str, "mukey": str})
    state_fips = region_fips(region)
    counties = {line.split("|")[0] for line in region.boundaries.read_text().splitlines()
                if line.strip()}
    multi = sorted(set(horizons.areasymbol[~horizons.fips5.isin(counties)]))
    missing = sorted(counties - set(horizons.fips5))
    if not multi:
        return dict(region=region.key, multi_areas=[], added_counties=[])
    overlaps = []
    for area in multi:
        if not AREA_PATTERN.fullmatch(area):        # never format unexpected text into SQL
            raise RuntimeError(f"unexpected survey area symbol {area!r}")
        table = sda(OVERLAP_SQL.format(area=area))
        if len(table) > 1:
            overlaps.append(pd.DataFrame(table[1:], columns=table[0]).assign(areasymbol=area))
    if not overlaps:
        raise RuntimeError("no overlap rows returned")
    overlap = pd.concat(overlaps, ignore_index=True)
    overlap["fips5"] = state_fips + overlap.county_symbol.str[-3:]
    overlap = overlap[overlap.fips5.isin(missing)]
    # one row per area, map unit and county, so no horizon row is counted twice
    overlap = (overlap.assign(areaovacres=pd.to_numeric(overlap.areaovacres, errors="coerce"))
               .groupby(["areasymbol", "mukey", "fips5"], as_index=False).areaovacres.sum())
    source = horizons[horizons.areasymbol.isin(multi)].drop(columns=["fips5", "muacres"])
    added = source.merge(overlap[["areasymbol", "mukey", "fips5", "areaovacres"]],
                         on=["areasymbol", "mukey"], how="inner").rename(
        columns={"areaovacres": "muacres"})[horizons.columns]
    already = set(horizons.fips5)
    added = added[~added.fips5.isin(already)]
    if len(added):
        partial = path.with_suffix(".part")
        pd.concat([horizons, added], ignore_index=True).to_csv(partial, index=False)
        partial.replace(path)
    return dict(region=region.key, multi_areas=multi, missing_before=missing,
                added_counties=sorted(added.fips5.unique()), added_rows=len(added),
                still_missing=sorted(set(missing) - set(added.fips5)))


def main() -> None:
    for region in select_regions(sys.argv[1:] or ["US"]):
        if region.country != "US":
            continue
        try:
            report = refile(region)
        except RuntimeError as error:
            log(TAG, f"{region.key}: FAILED - {error}")
            continue
        if report["multi_areas"]:
            log(TAG, f"{region.key}: added {len(report['added_counties'])} counties "
                     f"({report['added_rows']} horizon rows); still missing "
                     f"{report['still_missing']}")
            region.res.mkdir(parents=True, exist_ok=True)
            (region.res / "54_ssurgo_multicounty_report.json").write_text(
                json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
