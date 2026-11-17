"""57 - Per-state inventory: coverage of each variable group, descriptive statistics
and within-unit correlation of detrended yield with candidate drivers.

Outputs results/_state_inventory/state_{coverage,descriptive,yield_correlations}.csv
Usage:  python scripts/57_state_inventory.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "_state_inventory"
OUT.mkdir(parents=True, exist_ok=True)

GROUPS = {
    "yield": "yield_kg_ha",
    "monthly_climate": "pcp_grow",
    "pdsi": "pdsi_jja",
    "daily_extremes": "gs_edd_30",
    "critical_window": "cw_edd_30",
    "power_extremes_us": "pw_gs_edd_30",
    "spei": "spei3_critical",
    "soil_moisture": "gwetroot_critical",
    "phenology_window": "win_edd",
    "planting_doy": "plant_doy",
    "water_balance": None,
    "soil_texture": "soil_clay_topsoil",
    "soil_water": "soil_aws_0_100cm",
    "irrigation": None,
    "co2_enso": "oni_season",
}
EXTRA_FILES = {
    "monthly_weather": "monthly_weather_features.csv",
    "weekly_weather": "weekly_weather_features.csv",
    "cmip6_deltas": "cmip6_deltas.csv",
    "modis_ndvi": "modis_ndvi_features.csv",
    "regional_window": "regional_window_features_conab.csv",
}


def coverage(panel: pd.DataFrame, country: str) -> pd.DataFrame:
    wb = "wb_season_deficit_mm" if country == "US" else "season_water_deficit_mm"
    irr = "irrigated_frac_avg" if country == "US" else "irrigated_area_ha"
    rows = []
    for region, g in panel.groupby("region"):
        bal = g[g.in_balanced_panel == 1]
        y = g[g.yield_kg_ha.notna()]
        row = {"country": country, "state": region,
               "units": g.fips5.nunique(), "units_balanced": bal.fips5.nunique(),
               "unit_years_yield": len(y),
               "years": f"{int(y.year.min())}-{int(y.year.max())}"}
        for name, col in GROUPS.items():
            col = {"water_balance": wb, "irrigation": irr}.get(name, col)
            row[name] = round(g.loc[g.yield_kg_ha.notna(), col].notna().mean() * 100, 1) \
                if col in g else np.nan
        proc = ROOT / "data" / "processed" / (f"BR/{region}" if country == "BR" else ("" if region == "IL" else region))
        for name, fname in EXTRA_FILES.items():
            row[name] = "yes" if (proc / fname).exists() else "-"
        rows.append(row)
    return pd.DataFrame(rows)


def describe(panel: pd.DataFrame, country: str) -> pd.DataFrame:
    """Climate means and yield statistics in the recent decade (2016-2025)."""
    recent = panel[panel.year.between(2016, 2025) & panel.yield_kg_ha.notna()]
    wb = "wb_season_deficit_mm" if country == "US" else "season_water_deficit_mm"
    rows = []
    for region, g in recent.groupby("region"):
        full = panel[(panel.region == region) & panel.yield_kg_ha.notna()]
        state_year = full.groupby("year").apply(
            lambda d: np.average(d.yield_kg_ha, weights=d.area_harvested_ha.fillna(1).clip(lower=1)),
            include_groups=False)
        slope = np.polyfit(state_year.index, state_year.values, 1)[0]
        detr = state_year - np.polyval(np.polyfit(state_year.index, state_year.values, 1), state_year.index)
        rows.append({
            "country": country, "state": region,
            "yield_2016_25_kg_ha": g.yield_kg_ha.median(),
            "trend_kg_ha_yr": slope,
            "yield_cv_detrended_pct": detr.std() / state_year.mean() * 100,
            "worst_year": int(detr.idxmin()), "worst_dev_pct": detr.min() / state_year.mean() * 100,
            "area_2016_25_kha": g.groupby("year").area_harvested_ha.sum().mean() / 1e3,
            "season_tmax_c": g.gs_tmax_mean.median(),
            "season_prcp_mm": g.gs_prcp_mm.median(),
            "season_edd30": g.gs_edd_30.median(),
            "cw_edd30": g.cw_edd_30.median(),
            "cw_vpd_kpa": g.cw_vpd_mean_kpa.median(),
            "water_deficit_mm": g[wb].median() if wb in g else np.nan,
            "soil_aws_cm": g.soil_aws_0_100cm.median(),
            "soil_clay_pct": g.soil_clay_topsoil.median(),
        })
    return pd.DataFrame(rows)


def correlations(panel: pd.DataFrame, country: str) -> pd.DataFrame:
    """Within-unit correlation of detrended yield with each candidate driver."""
    drivers = ["cw_edd_30", "cw_tmax_mean", "cw_prcp_mm", "cw_vpd_mean_kpa", "spei3_critical",
               "gwetroot_critical", "gs_edd_30", "gs_prcp_mm", "cw_cdd", "win_edd"]
    d = panel[panel.in_balanced_panel == 1].dropna(subset=["yield_anom"])
    rows = []
    for region, g in d.groupby("region"):
        row = {"country": country, "state": region, "n": len(g)}
        for v in drivers:
            if v not in g or g[v].notna().sum() < 100:
                row[v] = np.nan
                continue
            x = g[v] - g.groupby("fips5")[v].transform("mean")
            ok = x.notna()
            row[v] = np.corrcoef(x[ok], g.yield_anom[ok])[0, 1]
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    cov, desc, cor = [], [], []
    for country in ["US", "BR"]:
        panel = pd.read_csv(ROOT / "data" / "final" / f"model_panel_{country.lower()}.csv.gz",
                            dtype={"fips5": str}, low_memory=False)
        cov.append(coverage(panel, country))
        desc.append(describe(panel, country))
        cor.append(correlations(panel, country))
    for name, frames in [("coverage", cov), ("descriptive", desc), ("yield_correlations", cor)]:
        table = pd.concat(frames, ignore_index=True)
        table.to_csv(OUT / f"state_{name}.csv", index=False, float_format="%.3f")
        with pd.option_context("display.width", 250, "display.max_columns", 40):
            print(f"\n=== {name} ===")
            print(table.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
