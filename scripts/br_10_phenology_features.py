"""BR 10 - Daily-resolution process features (GDD, EDD, VPD, ET0, water
deficit) for Mato Grosso, analogue of US script 18, reusing the PHYSICS
functions from _pheno.py (dd_single_sine, svp, et0_penman_monteith -- these
are general thermodynamics, not region-specific) but NOT its planting-
detection or thermal-staging machinery, which is built for and calibrated to
the US Corn Belt and would silently give wrong answers here. Specifically:

WHAT IS NOT PORTED, AND WHY
  - _pheno.py's _plant_index() searches day-of-year 121-175 (May) for a
    7-day warm spell -- a Northern Hemisphere spring rule. Mato Grosso
    plants Sep-Nov (DOY ~244-334), the opposite hemisphere's spring.
  - Its STAGES (R1/R3/R7 thermal-time thresholds) are calibrated against
    NASS's observed crop-progress series (US scripts 23-25). No equivalent
    municipality-or-state-level observed staging series exists here to
    calibrate against, so this script does not claim a phenology model
    at all -- it reports window CONDITIONS (heat, water, VPD) over the
    growing season already established by br_05 (Sep(year)-Apr(year+1),
    critical window Jan(year+1)-Feb(year+1)), not modelled crop STAGES.
  - Frost: _pheno.py's autumn-frost logic (US script 21's maturity-group
    ceiling) has no meaning in tropical Mato Grosso, which does not frost;
    left out entirely rather than computing a number that would always be
    NaN or nonsensical.
  - True water-balance simulation (US script 18's soil-moisture bucket)
    needs total available water (TAW) from SSURGO's soil_aws_0_100cm; no
    SoilGrids equivalent exists (see br_08/09's documented gap). Reported
    here instead: water_deficit_mm = ET0 - precipitation, a demand-minus-
    supply gap with NO soil storage buffering. This overstates day-to-day
    swings a real soil would smooth out; treat it as a cruder signal than
    the US pipeline's wb_stress_days / wb_min_water_frac, not a like-for-
    like substitute.
"""
import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _brcfg import RAW, PROC, RES, UF
from _pheno import dd_single_sine, svp, et0_penman_monteith, T_BASE, T_CAP, T_EXTREME, HEAT_DAY_C

GROW_MONTHS_CUR = {9, 10, 11, 12}
GROW_MONTHS_NEXT = {1, 2, 3, 4}
CRITICAL_MONTHS = {1, 2}


def centroid_lat():
    rows = []
    for line in (RAW / "mt_municipio_boundaries.txt").read_text().splitlines():
        if not line.strip():
            continue
        code, coords = line.split("|", 1)
        pts = np.array([[float(x) for x in p.split(",")] for p in coords.split()])
        if len(pts) > 1 and np.allclose(pts[0], pts[-1]):
            pts = pts[:-1]
        rows.append(dict(unit_id=code.strip(), lat=float(pts[:, 1].mean())))
    return pd.DataFrame(rows)


def main():
    d = pd.read_csv(RAW / "power_daily.csv.gz", dtype={"unit_id": str})
    d["date"] = pd.to_datetime(d.date)
    d["month"] = d.date.dt.month
    lat = centroid_lat().set_index("unit_id").lat.to_dict()
    d["lat"] = d.unit_id.map(lat)
    print(f"[br10] daily rows : {len(d):,}  units {d.unit_id.nunique()}")

    d["gdd"] = dd_single_sine(d.tmin_c, d.tmax_c, T_BASE) - dd_single_sine(d.tmin_c, d.tmax_c, T_CAP)
    d["edd"] = dd_single_sine(d.tmin_c, d.tmax_c, T_EXTREME)
    d["hot_day"] = (d.tmax_c >= HEAT_DAY_C).astype(int)
    es = (svp(d.tmax_c) + svp(d.tmin_c)) / 2.0
    d["vpd"] = np.maximum(es - svp(d.tdew_c), 0.0)
    d["et0"] = et0_penman_monteith(d.tmin_c, d.tmax_c, d.tmean_c, d.tdew_c,
                                   d.srad_mj if "srad_mj" in d else None,
                                   d.lat, d.date.dt.dayofyear)
    print("[br10] daily GDD, EDD, VPD, ET0 computed")

    d["crop_year"] = np.where(d.month.isin(GROW_MONTHS_CUR), d.year,
                      np.where(d.month.isin(GROW_MONTHS_NEXT), d.year - 1, np.nan))
    grow = d.dropna(subset=["crop_year"]).copy()
    grow["crop_year"] = grow.crop_year.astype(int)
    grow["is_critical"] = grow.month.isin(CRITICAL_MONTHS)

    g = grow.groupby(["unit_id", "crop_year"])
    gc = grow[grow.is_critical].groupby(["unit_id", "crop_year"])

    feat = pd.DataFrame({
        "season_gdd": g.gdd.sum(), "season_edd": g.edd.sum(),
        "season_hot_days": g.hot_day.sum(), "season_prcp_mm": g.prcp_mm.sum(),
        "season_et0_mm": g.et0.sum(), "season_days": g.size(),
        "win_gdd": gc.gdd.sum(), "win_edd": gc.edd.sum(),
        "win_hot_days": gc.hot_day.sum(), "win_prcp_mm": gc.prcp_mm.sum(),
        "win_et0_mm": gc.et0.sum(), "win_vpd_mean": gc.vpd.mean(),
        "win_vpd_max": gc.vpd.max(), "win_tmax_mean": gc.tmax_c.mean(),
        "win_days": gc.size(),
    }).reset_index().rename(columns={"unit_id": "fips5", "crop_year": "year"})
    feat["season_water_deficit_mm"] = feat.season_et0_mm - feat.season_prcp_mm
    feat["win_water_deficit_mm"] = feat.win_et0_mm - feat.win_prcp_mm

    out = PROC / "phenology_features.csv"
    feat.to_csv(out, index=False)
    print(f"\n[br10] municipality-years built : {len(feat):,}")
    print(f"[br10] municipalities            : {feat.fips5.nunique()}")
    print(f"[br10] years                     : {int(feat.year.min())}-{int(feat.year.max())}")
    print("\n[br10] WINDOW CONDITIONS (Jan-Feb of the year after planting)")
    cols = ["win_gdd", "win_edd", "win_hot_days", "win_vpd_mean", "win_prcp_mm",
            "win_water_deficit_mm"]
    print(feat[cols].describe().T[["mean", "std", "min", "max"]].round(2).to_string())

    (RES / "br10_phenology_config.json").write_text(json.dumps(dict(
        note="process/window CONDITIONS, not a calibrated phenology model -- "
             "see docstring for what was deliberately not ported from _pheno.py",
        growing_season="Sep(year)-Apr(year+1)",
        critical_window="Jan(year+1)-Feb(year+1)",
        water_balance="ET0 - precipitation, NO soil storage buffering "
                      "(no TAW source for Brazil, see br_08/09)",
        municipality_years=len(feat),
        municipalities=int(feat.fips5.nunique()),
        year_min=int(feat.year.min()), year_max=int(feat.year.max()),
    ), indent=2))
    print(f"\n[br10] -> data/processed/BR/{UF}/phenology_features.csv")
    print(f"[br10] -> results/BR/{UF}/br10_phenology_config.json")


if __name__ == "__main__":
    main()
