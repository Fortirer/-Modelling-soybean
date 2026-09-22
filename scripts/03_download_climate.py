"""03 - Acquire NOAA nClimDiv county monthly climate (ERA5 analogue).

nClimDiv fixed-width county layout (NCEI county-readme.txt):
  cols 1-2   NOAA climdiv state code (NOT Census FIPS -- Illinois=11, Iowa=13;
             see STATE_REGISTRY in 00_config.py)
  cols 3-5   county FIPS (3 digit)
  cols 6-7   element code
  cols 8-11  year
  cols 12-95 12 monthly values, each a right-justified 7-char field (f7.2)
             precipitation missing sentinel -9.99, temperature/PDSI/Z-index -99.99

ILLINOIS: uses the manually staged, pre-filtered CSVs in data/raw/, exactly as
the original study did.

ANY OTHER STATE: auto-downloads and parses the national fixed-width files
directly from NCEI (public, no key) and writes the same two CSVs this script
has always produced, so 04_process_climate.py needs no changes either way.
"""
import sys, json, time, urllib.request
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _cfg import RAW, RES, PROVENANCE, STATE, CLIMDIV_CODE

LAYOUT = dict(state_code="cols 1-2 (NOAA climdiv code, not Census FIPS)",
              county_fips="cols 3-5", element="cols 6-7", year="cols 8-11",
              months="12 fields of width 7 (f7.2)",
              missing="precip <= -9 treated as null; temp/PDSI/Z-index <= -99 treated as null")
RECIPE = """
Reproduce:
  base=https://www.ncei.noaa.gov/pub/data/cirs/climdiv/
  for f in climdiv-pcpncy climdiv-tmpccy climdiv-tmaxcy climdiv-tmincy \\
           climdiv-pdsicy climdiv-zndxcy ; do
      curl -O ${base}${f}-v1.0.0-<latest-date>
  done
Filter lines beginning with the state's NOAA climdiv code (see
county-readme.txt STATE CODE TABLE -- these do NOT match Census FIPS).
Version-date suffix changes monthly; list the directory for the current one.
"""

# NCEI updates this suffix roughly monthly; bump if a download 404s.
VERSION = "v1.0.0-20260904"
BASE = "https://www.ncei.noaa.gov/pub/data/cirs/climdiv/"
FILES = {"pcp": "climdiv-pcpncy", "tmax": "climdiv-tmaxcy", "tmin": "climdiv-tmincy",
         "tmp": "climdiv-tmpccy", "pdsi": "climdiv-pdsicy", "zndx": "climdiv-zndxcy"}
MISSING = {"pcp": -9.0}   # everything else uses -99 as the sentinel threshold


def parse_fixed_width(text_lines, state_code, var):
    """One row per (county_ansi, year), 12 monthly values named f"{var}{month:02d}"."""
    thresh = MISSING.get(var, -99.0)
    rows = []
    for line in text_lines:
        if len(line) < 95 or line[:2] != state_code:
            continue
        county = line[2:5]
        year = int(line[7:11])
        vals = []
        for m in range(12):
            s = line[11 + m*7 : 18 + m*7].strip()
            try:
                v = float(s)
            except ValueError:
                v = np.nan
            vals.append(np.nan if v <= thresh else v)
        rows.append((county, year, *vals))
    cols = ["county_ansi", "year"] + [f"{var}{m:02d}" for m in range(1, 13)]
    return pd.DataFrame(rows, columns=cols)


def fetch(var, fname):
    url = f"{BASE}{fname}-{VERSION}"
    print(f"[03] {var}: downloading {url}", flush=True)
    t0 = time.time()
    with urllib.request.urlopen(url, timeout=300) as resp:
        text = resp.read().decode("utf-8", errors="replace").splitlines()
    df = parse_fixed_width(text, CLIMDIV_CODE, var)
    print(f"[03] {var}: {len(text):,} national lines, {len(df):,} kept for state "
          f"code {CLIMDIV_CODE}, {time.time()-t0:.0f}s", flush=True)
    return df


def auto_download():
    print(f"[03] {STATE}: no staged files found; auto-downloading nClimDiv county "
          f"files from NCEI (no API key needed)", flush=True)
    d = {v: fetch(v, f) for v, f in FILES.items()}

    # ---- file 1: pcp + tmp, April-September (matches 04_process_climate.py) ----
    grow = list(range(4, 10))
    a = d["pcp"][["county_ansi", "year"] + [f"pcp{m:02d}" for m in grow]].merge(
        d["tmp"][["county_ansi", "year"] + [f"tmp{m:02d}" for m in grow]],
        on=["county_ansi", "year"], validate="one_to_one")
    a.to_csv(RAW / "nclimdiv_pcp_tmp_county.csv", index=False)

    # ---- file 2: winter/drought/extreme-temperature extras --------------------
    pcp = d["pcp"].set_index(["county_ansi", "year"])
    tmin, tmax = d["tmin"].set_index(["county_ansi", "year"]), d["tmax"].set_index(["county_ansi", "year"])
    pdsi, zndx = d["pdsi"].set_index(["county_ansi", "year"]), d["zndx"].set_index(["county_ansi", "year"])

    idx = pcp.index
    prev = pd.MultiIndex.from_arrays([idx.get_level_values(0), idx.get_level_values(1) - 1])
    pcp11_prev = pcp.pcp11.reindex(prev).values
    pcp12_prev = pcp.pcp12.reindex(prev).values

    b = pd.DataFrame(index=idx).reset_index()
    b["pcp_win"] = pcp12_prev + pcp.pcp01.values + pcp.pcp02.values
    b["pcp_prevND"] = pcp11_prev + pcp12_prev
    for m in (4, 5, 9, 10):
        b[f"tmin{m:02d}"] = tmin[f"tmin{m:02d}"].values
    for m in (7, 8):
        b[f"tmax{m:02d}"] = tmax[f"tmax{m:02d}"].values
    b["tmax_jja"] = tmax[["tmax06", "tmax07", "tmax08"]].mean(axis=1).values
    for m in (6, 7, 8):
        b[f"pdsi{m:02d}"] = pdsi[f"pdsi{m:02d}"].values
    b["pdsi_jja"] = pdsi[["pdsi06", "pdsi07", "pdsi08"]].mean(axis=1).values
    b["pdsi_may"] = pdsi["pdsi05"].values
    for m in (7, 8):
        b[f"zndx{m:02d}"] = zndx[f"zndx{m:02d}"].values
    b["zndx_jja"] = zndx[["zndx06", "zndx07", "zndx08"]].mean(axis=1).values
    b.to_csv(RAW / "nclimdiv_drought_temp_extra.csv", index=False)

    print(f"[03] {STATE}: wrote {len(a):,} rows -> nclimdiv_pcp_tmp_county.csv, "
          f"{len(b):,} rows -> nclimdiv_drought_temp_extra.csv "
          f"({int(b.pcp_win.isna().sum())} rows null in pcp_win, the first observed "
          f"year for each county with no prior-year data)")


def main():
    files = [RAW/"nclimdiv_pcp_tmp_county.csv", RAW/"nclimdiv_drought_temp_extra.csv"]
    if not all(f.exists() for f in files):
        if STATE == "IL":
            missing = [f for f in files if not f.exists()][0]
            raise SystemExit(f"Missing {missing}\n{RECIPE}")
        auto_download()
    for f in files:
        print(f"[03] staged: {f.name}  rows={len(pd.read_csv(f)):,}")
    (RES/"03_provenance_climate.json").write_text(json.dumps(
        {**PROVENANCE['climate'], "fixed_width_layout": LAYOUT, "recipe": RECIPE.strip(),
         "climdiv_state_code": CLIMDIV_CODE}, indent=2))
    print("[03] provenance written : results/03_provenance_climate.json")

if __name__ == "__main__":
    main()
