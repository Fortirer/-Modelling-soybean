"""23 - Observed soybean crop progress and condition, from NASS Quick Stats.

WHY THIS EXISTS
  The thermal-time thresholds in script 18 were described as "calibrated to
  Illinois NASS crop-progress norms". They were not calibrated to anything that
  was downloaded: the 50%-progress dates used (planting 20 May, blooming 10 July,
  pod set 28 July, and so on) were written from memory. The stage dates the
  phenology produces therefore agree with those numbers by construction and prove
  nothing. This script fetches the actual series, so the phenology can be checked
  against observed stages year by year instead.

WHAT IT PULLS
  Weekly Illinois soybean PROGRESS (percent planted, emerged, blooming, setting
  pods, dropping leaves, harvested) and CONDITION (percent very poor through
  excellent), at whatever geographic levels NASS publishes: state, agricultural
  district, county. What exists at which level is reported, not assumed.

HOW
  The Quick Stats API needs a key. The bulk file does not, so this streams
  qs.crops_<date>.txt.gz (about 1.1 GB, the whole national crops database) and
  keeps only the matching rows. Nothing close to that size is written to disk;
  the kept rows are a few MB.

  The stream cannot be resumed mid-way, so a failure restarts it. Kept rows go to
  a partial file that is renamed only on success, so a half-finished run never
  masquerades as a complete one.
"""
import sys, io, json, gzip, time, urllib.request, urllib.error, collections
import pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _cfg import RAW, RES, STATE

URL = "https://www.nass.usda.gov/datasets/qs.crops_20260922.txt.gz"
OUT = RAW / "nass_il_soybean_progress.csv"
PARTIAL = RAW / "nass_il_soybean_progress.csv.partial"
COMMODITY = "SOYBEANS"
KEEP_CATS = ("PROGRESS", "CONDITION")       # also matches "PROGRESS, 5 YEAR AVG" etc.
ATTEMPTS = 3
LOG_EVERY_MB = 100


class Counting:
    """Counts compressed bytes read, so progress can be reported."""
    def __init__(self, raw):
        self.raw, self.n = raw, 0
    def read(self, k=-1):
        b = self.raw.read(k)
        self.n += len(b)
        return b


def stream_once():
    t0 = time.time()
    resp = urllib.request.urlopen(URL, timeout=300)
    total = int(resp.headers.get("Content-Length") or 0)
    src = Counting(resp)
    text = io.TextIOWrapper(gzip.GzipFile(fileobj=src), encoding="utf-8", errors="replace")
    header = text.readline().rstrip("\n").split("\t")
    idx = {c: i for i, c in enumerate(header)}
    need = ["COMMODITY_DESC", "STATE_ALPHA", "STATISTICCAT_DESC"]
    missing = [c for c in need if c not in idx]
    if missing:
        raise RuntimeError(f"file layout changed, missing columns {missing}")

    kept, scanned, next_log = 0, 0, LOG_EVERY_MB
    with open(PARTIAL, "w", encoding="utf-8", newline="") as out:
        out.write("\t".join(header) + "\n")
        for line in text:
            scanned += 1
            # cheap substring test first: splitting every line of a multi-GB file
            # in Python is far slower than rejecting most of them on a substring
            if "\tSOYBEANS\t" not in line or ("\t" + STATE + "\t") not in line:
                continue
            f = line.rstrip("\n").split("\t")
            if len(f) < len(header):
                f += [""] * (len(header) - len(f))
            if (f[idx["COMMODITY_DESC"]] == COMMODITY and f[idx["STATE_ALPHA"]] == STATE
                    and f[idx["STATISTICCAT_DESC"]].startswith(KEEP_CATS)):
                out.write("\t".join(f) + "\n")
                kept += 1
            if src.n / 1e6 >= next_log:
                pct = f" ({src.n / total * 100:.0f}%)" if total else ""
                print(f"[23] {src.n/1e6:7.0f} MB{pct}  rows scanned {scanned:>11,}  "
                      f"kept {kept:,}  {time.time()-t0:5.0f}s", flush=True)
                next_log += LOG_EVERY_MB
    resp.close()
    print(f"[23] stream complete: {scanned:,} rows scanned, {kept:,} kept, "
          f"{(time.time()-t0)/60:.1f} min", flush=True)
    return kept, scanned


def main():
    kept = scanned = 0
    for a in range(1, ATTEMPTS + 1):
        try:
            print(f"[23] attempt {a}/{ATTEMPTS}: streaming {URL}", flush=True)
            kept, scanned = stream_once()
            break
        except (urllib.error.URLError, TimeoutError, OSError, EOFError,
                gzip.BadGzipFile) as e:
            print(f"[23] attempt {a} failed: {type(e).__name__}: {e}", flush=True)
            if a == ATTEMPTS:
                raise SystemExit("[23] all attempts failed; nothing written")
            time.sleep(10)
    if not kept:
        raise SystemExit("[23] stream finished but no Illinois soybean progress rows "
                         "matched; refusing to write an empty result")
    PARTIAL.replace(OUT)

    d = pd.read_csv(OUT, sep="\t", dtype=str, keep_default_na=False)
    d["YEAR"] = d.YEAR.astype(int)
    d["VALUE_NUM"] = pd.to_numeric(d.VALUE.str.replace(",", ""), errors="coerce")
    d.to_csv(OUT, index=False)
    print(f"\n[23] kept rows            : {len(d):,}")
    print(f"[23] years                : {d.YEAR.min()} - {d.YEAR.max()}")
    print(f"[23] -> data/raw/nass_il_soybean_progress.csv")

    print("\n[23] WHAT EXISTS, by geographic level")
    g = (d.groupby(["AGG_LEVEL_DESC", "STATISTICCAT_DESC"])
           .agg(rows=("VALUE", "size"), first_year=("YEAR", "min"),
                last_year=("YEAR", "max"), stats=("SHORT_DESC", "nunique"))
           .reset_index())
    print(g.to_string(index=False))

    print("\n[23] WHAT THE PROGRESS SERIES ARE, at the state level")
    st = d[(d.AGG_LEVEL_DESC == "STATE") & (d.STATISTICCAT_DESC == "PROGRESS")]
    s = (st.groupby("SHORT_DESC")
           .agg(rows=("VALUE", "size"), first_year=("YEAR", "min"),
                last_year=("YEAR", "max")).reset_index())
    s["SHORT_DESC"] = s.SHORT_DESC.str.replace("SOYBEANS - PROGRESS, MEASURED IN ", "")
    print(s.to_string(index=False))

    (RES / "23_provenance_crop_progress.json").write_text(json.dumps(dict(
        source="USDA NASS Quick Stats bulk file, qs.crops",
        url=URL, accessed=time.strftime("%Y-%m-%d"),
        access_note="public bulk file, no API key; streamed and filtered, "
                    f"{scanned:,} rows scanned",
        filter=f"COMMODITY_DESC={COMMODITY}; STATE_ALPHA={STATE}; "
               f"STATISTICCAT_DESC startswith {list(KEEP_CATS)}",
        rows_kept=int(len(d)), years=[int(d.YEAR.min()), int(d.YEAR.max())],
        levels=sorted(d.AGG_LEVEL_DESC.unique().tolist()),
        replaces="the remembered 50%-progress dates written into script 18's header",
    ), indent=2))
    print("[23] -> results/23_provenance_crop_progress.json")


if __name__ == "__main__":
    main()
