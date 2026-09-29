"""BR 09 - Aggregate SoilGrids point values into municipality soil features,
analogue of US script 15. SoilGrids already reports discrete depth BINS
(0-5, 5-15, 15-30, 30-60, 60-100cm) rather than SSURGO's variable-length
horizons, so the overlap-weighting script 15 needs is replaced here by a
simpler thickness-weighted average of whichever bins fall inside each band:
  topsoil  0-30cm  = bins 0-5, 5-15, 15-30 (thickness-weighted: 5,10,15 cm)
  subsoil 30-100cm = bins 30-60, 60-100    (thickness-weighted: 30,40 cm)
soc is converted to an organic-matter proxy via the Van Bemmelen factor
(OM% = OC% x 1.724), the same conversion US SSURGO-derived om_r already
represents (SSURGO's om_r IS organic matter, not organic carbon, so this
makes the two comparable).
"""
import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _brcfg import RAW, PROC, RES, UF

BINS = {"0-5cm": (0, 5), "5-15cm": (5, 15), "15-30cm": (15, 30),
        "30-60cm": (30, 60), "60-100cm": (60, 100)}
TOPSOIL_BINS = ["0-5cm", "5-15cm", "15-30cm"]
SUBSOIL_BINS = ["30-60cm", "60-100cm"]
VAN_BEMMELEN = 1.724


def band_mean(g, bins):
    """Thickness-weighted mean of a property across the given depth bins,
    skipping any bin with a missing value rather than treating it as zero."""
    sub = g[g.depth.isin(bins)].dropna(subset=["value"])
    if not len(sub):
        return np.nan
    w = sub.depth.map(lambda b: BINS[b][1] - BINS[b][0])
    return float(np.average(sub.value, weights=w))


def main():
    d = pd.read_csv(RAW / "soilgrids_horizons.csv", dtype={"fips5": str})
    cls = pd.read_csv(RAW / "soilgrids_wrb_class.csv", dtype={"fips5": str})
    print(f"[br09] property values : {len(d):,}  municipalities {d.fips5.nunique()}")

    PROP_TO_COL = {
        "clay_pct": "clay", "sand_pct": "sand", "silt_pct": "silt",
        "soc_pct": "om",  # converted below
        "ph_h2o": "ph", "bd_kg_dm3": "bd", "cec_cmol_kg": "cec",
    }

    rows = []
    for fips5, g in d.groupby("fips5"):
        rec = {"fips5": fips5}
        for prop, col in PROP_TO_COL.items():
            gp = g[g.property == prop]
            top = band_mean(gp, TOPSOIL_BINS)
            sub = band_mean(gp, SUBSOIL_BINS)
            if col == "om":
                top, sub = top * VAN_BEMMELEN, sub * VAN_BEMMELEN
            rec[f"soil_{col}_topsoil"] = top
            rec[f"soil_{col}_subsoil"] = sub
        rows.append(rec)

    s = pd.DataFrame(rows).merge(cls, on="fips5", how="left")
    feat = [c for c in s.columns if c not in ("fips5", "wrb_class")]

    out = PROC / "soil_features.csv"
    s.to_csv(out, index=False)
    print(f"[br09] municipalities  : {len(s)}  features {len(feat)}")
    print(f"[br09] nulls           : {int(s[feat].isna().sum().sum())}")
    print("\n[br09] MUNICIPALITY SOIL FEATURES")
    print(s[feat].describe().T[["mean", "std", "min", "max"]].round(2).to_string())
    print("\n[br09] WRB soil classification (dominant class per municipality)")
    print(s.wrb_class.value_counts(dropna=False).to_string())

    (RES / "br09_soil_processing_report.json").write_text(json.dumps(dict(
        municipalities=len(s), features=feat, n_features=len(feat),
        depth_bands={"topsoil": "0-30 cm (SoilGrids bins 0-5,5-15,15-30cm)",
                    "subsoil": "30-100 cm (SoilGrids bins 30-60,60-100cm)"},
        weighting="depth-bin-thickness weighted mean",
        om_conversion="soc_pct x 1.724 (Van Bemmelen factor) -> organic matter %",
        wrb_class_counts=s.wrb_class.value_counts(dropna=False).to_dict(),
        no_us_equivalent=["soil_awc", "soil_ksat", "soil_mollisol_pct",
                          "soil_drain_*_pct -- see br08's docstring"],
        nulls_total=int(s[feat].isna().sum().sum()),
    ), indent=2))
    print(f"\n[br09] -> data/processed/BR/{UF}/soil_features.csv")
    print(f"[br09] -> results/BR/{UF}/br09_soil_processing_report.json")


if __name__ == "__main__":
    main()
