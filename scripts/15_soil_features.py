"""15 - Aggregate SSURGO horizons into county soil features.

Weighting, applied in this order and kept explicit so it can be argued with:
  horizon   -> thickness of its overlap with the depth band
  component -> comppct_r, the component's share of the map unit
  map unit  -> muacres, the map unit's area in the county

Depth bands follow the agronomy rather than SSURGO's own layers: 0-30 cm is the
zone that dominates early growth and nutrient supply, 30-100 cm is the reservoir
soybeans draw on during the July-August seed fill that sets yield in this panel.

Nulls are dropped per property and the weights renormalised, so a property
missing from one horizon does not silently pull a county's mean toward zero.
"""
import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _cfg import RAW, PROC, RES

BANDS = {"topsoil": (0, 30), "subsoil": (30, 100)}
PROPS = {"claytotal_r": "clay", "sandtotal_r": "sand", "silttotal_r": "silt",
         "om_r": "om", "awc_r": "awc", "ph1to1h2o_r": "ph",
         "dbthirdbar_r": "bd", "ksat_r": "ksat", "cec7_r": "cec"}
NUM = list(PROPS) + ["muacres", "comppct_r", "slope_r", "hzdept_r", "hzdepb_r"]


def wmean(v, w):
    """Weighted mean ignoring nulls in v; None when nothing is left."""
    k = v.notna() & w.notna() & (w > 0)
    return float(np.average(v[k], weights=w[k])) if k.any() and w[k].sum() > 0 else np.nan


def main():
    d = pd.read_csv(RAW / "ssurgo_il_horizons.csv", dtype={"fips5": str})
    for c in NUM:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["drainagecl"] = d.drainagecl.astype(str).str.strip()
    d["taxorder"] = d.taxorder.astype(str).str.strip()
    print(f"[15] horizon records : {len(d):,}  counties {d.fips5.nunique()}")

    rows = []
    for f5, g in d.groupby("fips5"):
        rec = {"fips5": f5}

        # ---- horizon properties, per depth band ------------------------------
        for band, (top, bot) in BANDS.items():
            ov = (np.minimum(g.hzdepb_r, bot) - np.maximum(g.hzdept_r, top)).clip(lower=0)
            w = ov * g.comppct_r * g.muacres
            for col, short in PROPS.items():
                rec[f"soil_{short}_{band}"] = wmean(g[col], w)

        # ---- plant-available water in the top metre --------------------------
        # awc is cm water per cm soil, so awc * thickness integrates to cm of water
        ov100 = (np.minimum(g.hzdepb_r, 100) - np.maximum(g.hzdept_r, 0)).clip(lower=0)
        cw = g.comppct_r * g.muacres
        contrib = g.awc_r * ov100
        k = contrib.notna() & cw.notna() & (cw > 0)
        rec["soil_aws_0_100cm"] = (float((contrib[k] * cw[k]).sum() / cw[k].sum())
                                   if k.any() else np.nan)

        # ---- component-level attributes, area weighted -----------------------
        comp = g.drop_duplicates("cokey")
        cwt = comp.comppct_r * comp.muacres
        rec["soil_slope"] = wmean(comp.slope_r, cwt)
        tot = cwt.sum()
        for lab, key in [("Poorly drained", "poorly"),
                         ("Somewhat poorly drained", "somewhat_poorly"),
                         ("Well drained", "well"),
                         ("Moderately well drained", "mod_well")]:
            rec[f"soil_drain_{key}_pct"] = (
                float(cwt[comp.drainagecl == lab].sum() / tot * 100) if tot > 0 else np.nan)
        rec["soil_mollisol_pct"] = (
            float(cwt[comp.taxorder == "Mollisols"].sum() / tot * 100) if tot > 0 else np.nan)
        rows.append(rec)

    s = pd.DataFrame(rows).sort_values("fips5").reset_index(drop=True)
    s.to_csv(PROC / "soil_features.csv", index=False)

    feat = [c for c in s.columns if c != "fips5"]
    print(f"[15] counties {len(s)}  features {len(feat)}")
    print(f"[15] nulls    {int(s[feat].isna().sum().sum())}")
    print("\n[15] COUNTY SOIL FEATURES (across 102 counties)")
    desc = s[feat].describe().T[["mean", "std", "min", "max"]]
    print(desc.round(2).to_string())

    (RES / "15_soil_processing_report.json").write_text(json.dumps(dict(
        counties=len(s), features=feat, n_features=len(feat),
        horizon_records=int(len(d)),
        depth_bands={k: f"{v[0]}-{v[1]} cm" for k, v in BANDS.items()},
        weighting="horizon overlap thickness x comppct_r x muacres",
        null_handling="dropped per property, weights renormalised",
        aws_note="soil_aws_0_100cm is cm of plant-available water in the top metre",
        nulls_total=int(s[feat].isna().sum().sum()),
    ), indent=2))
    print(f"\n[15] -> data/processed/soil_features.csv")
    print(f"[15] -> results/15_soil_processing_report.json")


if __name__ == "__main__":
    main()
