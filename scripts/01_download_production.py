"""01 - Acquire USDA NASS county soybean production (IBGE analogue).

ILLINOIS: uses the manually staged query-tool CSV export in data/raw/ (see
RECIPE below), exactly as the original study did.

ANY OTHER STATE: auto-downloads. The Quick Stats API requires a key; the
public bulk file (same one script 23 streams for crop progress) does not, and
it covers every state, so it is streamed and filtered here instead of
requiring a manual browser export. This makes the pipeline reproducible for a
new state with no manual step and no key.
"""
import sys, io, gzip, json, time, urllib.request, urllib.error
import pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _cfg import RAW, RES, PROVENANCE, STATE, STATE_NAME

SRC = RAW/"nass_il_soybeans_county_raw.csv"   # literal name kept across states,
                                               # harmless once RAW is state-namespaced

RECIPE = f"""
Reproduce this export:
  1. https://quickstats.nass.usda.gov/
  2. Program        = SURVEY
     Sector         = CROPS
     Commodity      = SOYBEANS
     Data Item      = ACRES PLANTED / ACRES HARVESTED /
                      PRODUCTION MEASURED IN BU / YIELD MEASURED IN BU / ACRE
     Geographic Lvl = COUNTY
     State          = {STATE_NAME}
     Year           = 1980-2025
  3. Get Data -> Spreadsheet
Programmatic equivalent (needs a Quick Stats key, separate from api.data.gov):
  GET /api/api_GET/?key=KEY&source_desc=SURVEY&commodity_desc=SOYBEANS
      &agg_level_desc=COUNTY&state_name={STATE_NAME}&year__GE=1980&format=CSV
NOTE: the 50,000-row API cap binds for multi-state pulls; use the bulk file
      https://www.nass.usda.gov/datasets/qs.crops_<YYYYMMDD>.txt.gz instead
      (see the auto-download path below, used for every state but Illinois).
"""

BULK_URL = "https://www.nass.usda.gov/datasets/qs.crops_20260922.txt.gz"
WANT_STATCAT = {"AREA PLANTED", "AREA HARVESTED", "PRODUCTION", "YIELD"}
RENAME = {"AREA PLANTED": "acres_planted", "AREA HARVESTED": "acres_harvested",
          "PRODUCTION": "production_bu", "YIELD": "yield_bu_ac"}


def auto_download():
    """Stream the national bulk crops file and keep county-level SOYBEANS rows
    for STATE, total domain, the four statistics 02_clean_production.py needs.
    Same streaming discipline as script 23: nothing close to the 1 GB file is
    held in memory or written to disk, only the kept rows are.
    """
    print(f"[01] {STATE}: no staged export found; auto-downloading from the bulk "
          f"crops file (no API key needed)", flush=True)
    t0 = time.time()
    resp = urllib.request.urlopen(BULK_URL, timeout=300)
    text = io.TextIOWrapper(gzip.GzipFile(fileobj=resp), encoding="utf-8", errors="replace")
    header = text.readline().rstrip("\n").split("\t")
    idx = {c: i for i, c in enumerate(header)}
    rows, scanned = [], 0
    for line in text:
        scanned += 1
        if "\tSOYBEANS\t" not in line or ("\t" + STATE + "\t") not in line:
            continue
        f = line.rstrip("\n").split("\t")
        if len(f) < len(header):
            f += [""] * (len(header) - len(f))
        if not (f[idx["COMMODITY_DESC"]] == "SOYBEANS" and f[idx["STATE_ALPHA"]] == STATE
                and f[idx["AGG_LEVEL_DESC"]] == "COUNTY" and f[idx["SOURCE_DESC"]] == "SURVEY"
                and f[idx["DOMAIN_DESC"]] == "TOTAL"
                and f[idx["STATISTICCAT_DESC"]] in WANT_STATCAT
                and 1980 <= int(f[idx["YEAR"]]) <= 2025):
            continue
        rows.append({c: f[idx[c]] for c in
                     ["STATE_NAME", "STATE_ANSI", "COUNTY_NAME", "COUNTY_ANSI", "ASD_DESC",
                      "ASD_CODE", "YEAR", "STATISTICCAT_DESC", "VALUE"]})
    resp.close()
    print(f"[01] {STATE}: {scanned:,} rows scanned, {len(rows)} matched, "
          f"{(time.time()-t0)/60:.1f} min", flush=True)
    if not rows:
        raise SystemExit(f"[01] no SOYBEANS county rows found for STATE={STATE} in the bulk file")

    d = pd.DataFrame(rows)
    d["VALUE_NUM"] = pd.to_numeric(d.VALUE.str.replace(",", ""), errors="coerce")
    piv = (d.pivot_table(index=["STATE_NAME", "STATE_ANSI", "COUNTY_NAME", "COUNTY_ANSI",
                                "ASD_DESC", "ASD_CODE", "YEAR"],
                         columns="STATISTICCAT_DESC", values="VALUE_NUM", aggfunc="first")
             .reset_index().rename(columns=RENAME))
    piv.columns.name = None
    for c in RENAME.values():
        if c not in piv.columns:
            piv[c] = float("nan")
    piv = piv.rename(columns={"STATE_NAME": "state", "STATE_ANSI": "state_ansi",
                              "COUNTY_NAME": "county", "COUNTY_ANSI": "county_ansi",
                              "ASD_DESC": "ag_district", "ASD_CODE": "ag_district_code",
                              "YEAR": "year"})
    piv["is_county_estimate"] = 1   # overwritten by 02_clean_production.py; placeholder only
    piv.to_csv(SRC, index=False)
    print(f"[01] {STATE}: wrote {len(piv):,} county-year rows -> {SRC}")
    return len(piv)


def main():
    if SRC.exists():
        d = pd.read_csv(SRC, dtype=str)
        print(f"[01] raw production rows : {len(d):,} (already staged)")
    elif STATE == "IL":
        raise SystemExit(f"Missing raw export: {SRC}\n{RECIPE}")
    else:
        n = auto_download()
        d = pd.read_csv(SRC, dtype=str)
        assert len(d) == n

    print(f"[01] columns             : {list(d.columns)}")
    (RES/"01_provenance_production.json").write_text(
        json.dumps({**PROVENANCE['production'], "rows": len(d), "recipe": RECIPE.strip()}, indent=2))
    print(f"[01] provenance written  : results/01_provenance_production.json")

if __name__ == "__main__":
    main()
