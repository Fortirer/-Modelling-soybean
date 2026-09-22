"""29 - County irrigated vs non-irrigated soybean acreage, from the NASS Census of
Agriculture (2017 and 2022).

WHY
  Illinois soybean is overwhelmingly rainfed, but the small irrigated share is
  concentrated in a handful of sandy-soil counties (the Illinois River sand
  plains: Mason, Tazewell, Cass, and a few others), and that could plausibly
  explain some of the county-level heterogeneity in climate sensitivity that
  Section 5.2/5.8 flagged as unexplained by soil alone. This is the same
  question the soil scripts (14-17) asked, with a different county attribute.

WHAT IT PULLS
  The Census of Agriculture is published separately from the annual Survey, as
  its own bulk files (qs.census2017.txt.gz, qs.census2022.txt.gz - about 130
  and 295 MB, far smaller than the 1 GB all-years crops survey file, because
  each covers one census year only). No API key needed. Kept: Illinois,
  soybeans, area harvested, by irrigation status (IRRIGATED / NON-IRRIGATED),
  at whatever geographic levels the Census publishes (county is the target).

  The Census suppresses county values that would identify an individual farm,
  so counties with very little irrigated acreage are expected to come back
  withheld, not zero. That is reported, not silently dropped.
"""
import sys, io, gzip, json, time, urllib.request, urllib.error
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from _cfg import RAW, PROC, RES

BASE = "https://www.nass.usda.gov/datasets/"
FILES = {2017: "qs.census2017.txt.gz", 2022: "qs.census2022.txt.gz"}
STATE = "IL"
COMMODITY = "SOYBEANS"
OUT_RAW = RAW / "nass_il_soybean_irrigation.csv"
ATTEMPTS = 3


WANT_SHORT_DESC = {"SOYBEANS - ACRES HARVESTED", "SOYBEANS, IRRIGATED - ACRES HARVESTED"}


def stream_year(year, fname):
    """Keep exactly two series: total acres harvested (no practice qualifier) and
    irrigated acres harvested. The irrigated_frac covariate needs both; the first
    pass of this script kept only the IRRIGATED rows (a substring match on
    PRODN_PRACTICE_DESC that also would have matched NON-IRRIGATED, except NASS
    does not publish a NON-IRRIGATED line for soybean at all -- the total is
    reported unqualified). Filtering on SHORT_DESC is unambiguous: it also drops
    the "OPERATIONS WITH AREA HARVESTED" (farm-count) rows that share
    STATISTICCAT_DESC="AREA HARVESTED" with the acreage rows and got kept by
    mistake the first time.
    """
    url = BASE + fname
    partial = RAW / f"irrig_{year}.partial"
    for a in range(1, ATTEMPTS + 1):
        try:
            t0 = time.time()
            print(f"[29] {year}: streaming {url}", flush=True)
            resp = urllib.request.urlopen(url, timeout=300)
            text = io.TextIOWrapper(gzip.GzipFile(fileobj=resp), encoding="utf-8", errors="replace")
            header = text.readline().rstrip("\n").split("\t")
            idx = {c: i for i, c in enumerate(header)}
            need = ["COMMODITY_DESC", "STATE_ALPHA", "SHORT_DESC"]
            missing = [c for c in need if c not in idx]
            if missing:
                raise RuntimeError(f"layout changed, missing columns {missing}")
            kept, scanned = 0, 0
            with open(partial, "w", encoding="utf-8", newline="") as out:
                out.write("\t".join(header) + "\n")
                for line in text:
                    scanned += 1
                    if "\tSOYBEANS" not in line or ("\t" + STATE + "\t") not in line:
                        continue
                    f = line.rstrip("\n").split("\t")
                    if len(f) < len(header):
                        f += [""] * (len(header) - len(f))
                    if (f[idx["COMMODITY_DESC"]] == COMMODITY and f[idx["STATE_ALPHA"]] == STATE
                            and f[idx["SHORT_DESC"]] in WANT_SHORT_DESC):
                        out.write("\t".join(f) + "\n")
                        kept += 1
            resp.close()
            print(f"[29] {year}: done, {scanned:,} rows scanned, {kept} kept, "
                  f"{(time.time()-t0)/60:.1f} min", flush=True)
            return partial, kept
        except (urllib.error.URLError, TimeoutError, OSError, EOFError, gzip.BadGzipFile) as e:
            print(f"[29] {year}: attempt {a} failed: {type(e).__name__}: {e}", flush=True)
            if a == ATTEMPTS:
                raise
            time.sleep(10)


def main():
    frames = []
    for year, fname in FILES.items():
        partial, kept = stream_year(year, fname)
        if kept == 0:
            print(f"[29] {year}: no matching rows, skipping")
            continue
        d = pd.read_csv(partial, sep="\t", dtype=str, keep_default_na=False)
        d["CENSUS_YEAR"] = year
        frames.append(d)
        partial.unlink()

    if not frames:
        raise SystemExit("[29] no Census irrigation rows found for either year; nothing written")

    d = pd.concat(frames, ignore_index=True)
    d["VALUE_NUM"] = pd.to_numeric(d.VALUE.str.replace(",", "").str.replace("(D)", "").str.strip(),
                                    errors="coerce")
    d["suppressed"] = d.VALUE.str.contains(r"\(D\)|\(Z\)|\(NA\)", regex=True, na=False)
    d["series"] = np.where(d.SHORT_DESC == "SOYBEANS, IRRIGATED - ACRES HARVESTED",
                           "IRRIGATED", "TOTAL")
    d.to_csv(OUT_RAW, index=False)
    print(f"\n[29] total rows kept: {len(d):,} -> {OUT_RAW}")

    print("\n[29] WHAT EXISTS, by geographic level, year and series")
    g = (d.groupby(["CENSUS_YEAR", "AGG_LEVEL_DESC", "series"])
           .agg(rows=("VALUE", "size"), suppressed=("suppressed", "sum")).reset_index())
    print(g.to_string(index=False))

    # ---- build the county covariate ---------------------------------------------
    cty = d[d.AGG_LEVEL_DESC == "COUNTY"].copy()
    cty["fips5"] = "17" + cty.COUNTY_CODE.str.zfill(3)
    piv = (cty.pivot_table(index=["fips5", "CENSUS_YEAR"], columns="series",
                            values="VALUE_NUM", aggfunc="sum")
              .reset_index())
    piv.columns.name = None
    for c in ("IRRIGATED", "TOTAL"):
        if c not in piv.columns:
            piv[c] = float("nan")
    piv["nonirrigated_acres"] = piv["TOTAL"] - piv["IRRIGATED"].fillna(0)
    piv["irrigated_frac"] = piv["IRRIGATED"].fillna(0) / piv["TOTAL"]
    piv = piv.rename(columns={"IRRIGATED": "irrigated_acres", "TOTAL": "total_acres"})
    # county-level suppression: a county with irrigated acreage below the disclosure
    # threshold withholds the IRRIGATED line but still reports TOTAL, which
    # understates irrigated_frac (treated here as 0 irrigated, not missing). Flag
    # rather than silently accept.
    sup = (cty[cty.series == "IRRIGATED"]
              .groupby(["fips5", "CENSUS_YEAR"]).suppressed.any().rename("irrigated_suppressed"))
    piv = piv.merge(sup, on=["fips5", "CENSUS_YEAR"], how="left")
    piv["irrigated_suppressed"] = piv.irrigated_suppressed.fillna(False)
    # a county absent from the IRRIGATED series entirely (never reported any
    # irrigated soybean acreage, suppressed or not) has irrigated_frac genuinely 0
    piv.loc[piv.irrigated_acres.isna() & ~piv.irrigated_suppressed, "irrigated_frac"] = 0.0

    avg = (piv.groupby("fips5")
              .agg(irrigated_acres_avg=("irrigated_acres", "mean"),
                   total_acres_avg=("total_acres", "mean"),
                   irrigated_frac_avg=("irrigated_frac", "mean"),
                   any_suppressed=("irrigated_suppressed", "any"),
                   census_years_reported=("CENSUS_YEAR", "nunique"))
              .reset_index())
    out_path = PROC / "irrigation_features.csv"
    avg.to_csv(out_path, index=False)
    print(f"\n[29] county covariate ({len(avg)} counties) -> {out_path}")
    print(avg.sort_values("irrigated_frac_avg", ascending=False).head(10).to_string(index=False))
    print(f"\n[29] counties with any (D)-suppressed irrigated-acreage value: "
          f"{int(avg.any_suppressed.sum())} of {len(avg)}")
    print(f"[29] statewide irrigated fraction (Illinois total, unweighted county mean): "
          f"{avg.irrigated_frac_avg.mean()*100:.2f}%")

    (RES / "29_provenance_irrigation.json").write_text(json.dumps(dict(
        source="USDA NASS Census of Agriculture, bulk files qs.census2017.txt.gz / qs.census2022.txt.gz",
        urls=[BASE + f for f in FILES.values()], accessed=time.strftime("%Y-%m-%d"),
        access_note="public bulk files, no API key",
        filter=f"COMMODITY_DESC={COMMODITY}; STATE_ALPHA={STATE}; "
               "PRODN_PRACTICE_DESC contains IRRIGATED; STATISTICCAT_DESC=AREA HARVESTED",
        census_years=list(FILES.keys()), counties=int(len(avg)),
        counties_with_suppressed_values=int(avg.any_suppressed.sum()),
        note="Census disclosure suppression withholds irrigated acreage for counties below "
             "a threshold; irrigated_frac_avg understates true share for those counties, "
             "flagged in any_suppressed rather than imputed.",
    ), indent=2))
    print("[29] -> results/29_provenance_irrigation.json")


if __name__ == "__main__":
    main()
