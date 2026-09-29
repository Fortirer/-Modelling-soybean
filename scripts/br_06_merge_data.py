"""BR 06 - Merge production and climate into the analytical panel, and build
the detrended yield target. Same construction as US script 05: yield_anom is
the residual of a municipality-specific linear trend, so technology/cultivar
adoption (which in Mato Grosso is a STEEPER trend than any US state, given
the state's soybean area roughly quintupled since 2000) doesn't get absorbed
into and invert the climate coefficients.

MIN_YEARS is lower than the US pipeline's 42: climate coverage here starts
1981 (NASA POWER), giving a 44-year ceiling (1981-2024) even before
accounting for Mato Grosso's own soybean expansion -- many municipalities
only became soy producers in the 1990s-2000s, decades after Illinois. A
42-year rule would empty the panel almost completely; 20 is used instead,
documented here rather than silently choosing whatever number happens to
keep enough rows.
"""
import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _brcfg import PROC, FINAL, RES, FOCAL_CODE

MIN_YEARS = 20


def main():
    p = pd.read_csv(PROC / "production_clean.csv", dtype={"fips5": str})
    c = pd.read_csv(PROC / "climate_features.csv", dtype={"fips5": str})

    rep = {"production_rows": len(p), "climate_rows": len(c)}
    m = p.merge(c, on=["fips5", "year"], how="inner")
    rep["merged_rows"] = len(m)
    rep["production_rows_outside_climate_coverage"] = len(p) - len(m)
    rep["municipalities"] = int(m.fips5.nunique())
    rep["years"] = int(m.year.nunique())

    # ---- municipality-specific trend and detrended target --------------------
    m = m.sort_values(["fips5", "year"]).reset_index(drop=True)
    m["trend_slope"] = np.nan
    m["yield_trend"] = np.nan
    for muni, idx in m.groupby("fips5").groups.items():
        g = m.loc[idx]
        if len(g) < 3:
            continue
        s, i = np.polyfit(g.year.values, g.yield_bu_ac.values, 1)
        m.loc[idx, "trend_slope"] = s
        m.loc[idx, "yield_trend"] = s * g.year.values + i
    m["yield_anom"] = m.yield_bu_ac - m.yield_trend
    m["log_yield"] = np.log(m.yield_bu_ac)

    # ---- panel balance ---------------------------------------------------------
    n = m.groupby("fips5").year.count()
    m["n_years_muni"] = m.fips5.map(n)
    m["in_balanced_panel"] = (m.n_years_muni >= MIN_YEARS).astype(int)
    m["is_focal"] = (m.fips5 == FOCAL_CODE).astype(int)
    rep["min_years_rule"] = MIN_YEARS
    rep["municipalities_in_balanced_panel"] = int((n >= MIN_YEARS).sum())
    rep["rows_in_balanced_panel"] = int(m.in_balanced_panel.sum())
    rep["focal_code"] = FOCAL_CODE
    rep["focal_rows"] = int(m.is_focal.sum())
    if m.is_focal.sum():
        rep["focal_year_range"] = [int(m.loc[m.is_focal == 1, "year"].min()),
                                    int(m.loc[m.is_focal == 1, "year"].max())]
    valid_trend = m.groupby("fips5").trend_slope.first().dropna()
    rep["trend_slope_min"] = round(float(valid_trend.min()), 3)
    rep["trend_slope_max"] = round(float(valid_trend.max()), 3)

    out = FINAL / "soja_mt_climate_1981_2024.csv"
    m.to_csv(out, index=False)
    (RES / "br06_merge_report.json").write_text(json.dumps(rep, indent=2))
    for k, v in rep.items():
        print(f"[br06] {k:36} {v}")
    print(f"[br06] {'final columns':36} {m.shape[1]}")
    print(f"[br06] -> {out.relative_to(FINAL.parents[3])}")


if __name__ == "__main__":
    main()
