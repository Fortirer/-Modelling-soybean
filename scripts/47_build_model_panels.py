"""47 - One model-ready panel per country, with every variable the papers use.

Joins, on unit (fips5) and crop year, everything the pipeline already had with
everything scripts 38-43 added, so the models of the reviewed papers can be
fitted without further assembly (script 48 does exactly that).

  data/final/model_panel_us.csv.gz    12 states, county x year, 1980-2025
  data/final/model_panel_br.csv.gz    10 states, municipality x year
  data/final/MODEL_PANEL_COLUMNS.csv  every column: source file, coverage

Base table: production_clean.csv (all years with a reported yield), NOT the
older final panels, which stop in 2023/2024. Columns of the older final panel
(monthly nClimDiv features for the US, seasonal POWER features for Brazil)
are carried over where they exist.

Blocks merged, each optional (a missing file is reported, not fatal):
  heat_extremes_*              script 41   degree days, ETCCDI extremes
  drought_soil_moisture        script 42   SPI, SPEI, root-zone wetness
  phenology_features           script 18 / br_10
  soil_features                script 15 / br_09
  soil_awc_features            script 43   (Brazil only)
  irrigation_features          script 30 / br_15
  co2, ONI                     script 38   global, by year

BRAZIL, YEAR ALIGNMENT. IBGE's PAM "ano" is the HARVEST year: the crop sown
in September-December of t-1 and filled in January-February of t is reported
under t. Scripts 41 and 42 key their files by planting year, so here their
columns are shifted by one year before the merge (planting year 2021 ->
panel year 2022); `planting_year` keeps the original. Evidence: Rio Grande do
Sul's yield collapses fall in PAM 2005, 2012 and 2022, the harvests of the
2004/05, 2011/12 and 2021/22 droughts, and the correlation between yield
anomaly and critical-window SPEI-3 in RS, PR and MS is 0.36-0.45 with this
alignment and about zero without it. br_05 uses the harvest year too since
2026-11-16, so the columns carried over from the Brazilian final panel
(pcp_*, tmp_*, tmax_*) are aligned. br_10 still treats "ano" as the planting
year, so its columns (season_*, win_*) are one year late until it is changed
and re-run; prefer the gs_/cw_/spei/gwetroot columns for Brazil.

The US heat
block comes from Daymet (us_power_ columns hold the same variables computed
from NASA POWER, i.e. exactly like Brazil, for pooled two-country models).

Usage:  python scripts/47_build_model_panels.py
"""
import json
import time

import numpy as np
import pandas as pd

from _gap import GLOBAL_RAW, ROOT, all_regions, log

TAG = "47"
FINAL = ROOT / "data" / "final"
US_PANEL = "soybean_illinois_climate_1980_2025.csv"
BR_PANEL = "soja_mt_climate_1981_2024.csv"
KEYS = ["fips5", "year"]
POWER_PREFIX = "pw_"
BR_HARVEST_LAG = 1      # IBGE "ano" = planting year + 1 (see docstring)


def read(path, **kwargs) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return pd.read_csv(path, dtype={"fips5": str}, **kwargs)


def merge_block(panel: pd.DataFrame, block: pd.DataFrame | None, on: list[str],
                name: str, source: str, catalog: list, region: str) -> pd.DataFrame:
    """Left-join `block`, keeping only columns the panel does not have yet."""
    if block is None:
        catalog.append(dict(region=region, block=name, source=source,
                            status="MISSING", columns=0))
        return panel
    new = [c for c in block.columns if c not in panel.columns]
    overlap = [c for c in block.columns if c in panel.columns and c not in on]
    duplicates = int(block.duplicated(on).sum())
    if duplicates:
        raise ValueError(f"{region} {name}: {duplicates} duplicate keys on {on}")
    block = block[on + new]
    catalog.append(dict(region=region, block=name, source=source, status="ok",
                        columns=len(new), column_names=new,
                        already_in_panel_not_merged=overlap))
    return panel.merge(block, on=on, how="left")


def to_harvest_year(block: pd.DataFrame | None) -> pd.DataFrame | None:
    """Re-key a planting-year table to the harvest year IBGE reports under."""
    if block is None:
        return None
    return block.assign(year=block.year + BR_HARVEST_LAG)


def brazil_irrigation(region) -> pd.DataFrame | None:
    table = read(region.raw / "ibge_irrigation_2017.csv")
    if table is None:
        return None
    return table.drop(columns=["county"], errors="ignore")


def build_region(region, catalog: list) -> pd.DataFrame | None:
    base = read(region.proc / "production_clean.csv")
    if base is None:
        log(TAG, f"{region.key}: no production_clean.csv, skipped")
        return None
    base = base[base.yield_kg_ha.notna() & (base.yield_kg_ha > 0)].copy()
    base.insert(0, "country", region.country)
    base.insert(1, "region", region.code)
    base["log_yield_kg_ha"] = np.log(base.yield_kg_ha)

    is_us = region.country == "US"
    old_dir = FINAL / ("" if region.code == "IL" else region.code) if is_us \
        else FINAL / "BR" / region.code
    blocks = [("existing_panel", read(old_dir / (US_PANEL if is_us else BR_PANEL)), KEYS)]
    primary = "daymet" if is_us else "power"
    align = (lambda block: block) if is_us else to_harvest_year
    blocks.append((f"heat_extremes_{primary}",
                   align(read(region.proc / f"heat_extremes_{primary}.csv")), KEYS))
    if is_us:
        power = read(region.proc / "heat_extremes_power.csv")
        if power is not None:
            power = power.rename(columns={c: POWER_PREFIX + c for c in power.columns
                                          if c not in KEYS})
        blocks.append(("heat_extremes_power", power, KEYS))
    blocks += [
        ("drought_soil_moisture",
         align(read(region.proc / "drought_soil_moisture_features.csv")), KEYS),
        ("phenology_features", read(region.proc / "phenology_features.csv"), KEYS),
        ("soil_features", read(region.proc / "soil_features.csv"), ["fips5"]),
    ]
    if is_us:
        blocks.append(("irrigation_features",
                       read(region.proc / "irrigation_features.csv"), ["fips5"]))
    else:
        blocks += [("soil_awc_features", read(region.proc / "soil_awc_features.csv"),
                    ["fips5"]),
                   ("irrigation_2017", brazil_irrigation(region), ["fips5"])]
    panel = base
    for name, block, on in blocks:
        panel = merge_block(panel, block, on, name, f"{region.key}/{name}",
                            catalog, region.key)
    return panel


def add_global(panel: pd.DataFrame, country: str) -> pd.DataFrame:
    co2 = pd.read_csv(GLOBAL_RAW / "co2_annual_mlo.csv")[["year", "co2_ppm"]]
    oni = pd.read_csv(GLOBAL_RAW / "oni_crop_year.csv")
    suffix = country.lower()
    oni = oni[["year", f"oni_{suffix}_season", f"enso_{suffix}"]].rename(
        columns={f"oni_{suffix}_season": "oni_season", f"enso_{suffix}": "enso_phase"})
    if country == "BR":      # ONI is keyed by planting year, the panel by harvest year
        oni = oni.assign(year=oni.year + BR_HARVEST_LAG)
        panel = panel.assign(planting_year=panel.year - BR_HARVEST_LAG)
    return panel.merge(co2, on="year", how="left").merge(oni, on="year", how="left")


def column_table(panel: pd.DataFrame, country: str, origin: dict) -> pd.DataFrame:
    rows = []
    for column in panel.columns:
        values = panel[column]
        present = panel.loc[values.notna(), "year"]
        rows.append(dict(
            country=country, column=column, block=origin.get(column, "production_clean"),
            non_null_pct=round(float(values.notna().mean() * 100), 1),
            first_year=int(present.min()) if len(present) else None,
            last_year=int(present.max()) if len(present) else None))
    return pd.DataFrame(rows)


def main() -> None:
    FINAL.mkdir(parents=True, exist_ok=True)
    catalog, tables, summary = [], [], {}
    for country in ("US", "BR"):
        parts = [build_region(r, catalog) for r in all_regions() if r.country == country]
        parts = [p for p in parts if p is not None]
        if not parts:
            continue
        panel = add_global(pd.concat(parts, ignore_index=True), country)
        panel = panel.sort_values(["region", "fips5", "year"]).reset_index(drop=True)
        out = FINAL / f"model_panel_{country.lower()}.csv.gz"
        panel.to_csv(out, index=False, compression="gzip", float_format="%.8g")
        origin = {c: e["block"] for e in catalog if e["region"].startswith(country)
                  and e["status"] == "ok" for c in e["column_names"]}
        origin.update(co2_ppm="co2_oni", oni_season="co2_oni", enso_phase="co2_oni")
        tables.append(column_table(panel, country, origin))
        summary[country] = dict(
            file=out.name, rows=len(panel), units=int(panel.fips5.nunique()),
            regions=sorted(panel.region.unique()), columns=panel.shape[1],
            years=[int(panel.year.min()), int(panel.year.max())],
            size_mb=round(out.stat().st_size / 1e6, 1))
        log(TAG, f"{country}: {summary[country]}")
    pd.concat(tables).to_csv(FINAL / "MODEL_PANEL_COLUMNS.csv", index=False)
    missing = [dict(region=e["region"], block=e["block"]) for e in catalog
               if e["status"] == "MISSING"]
    (ROOT / "results" / "47_model_panels_report.json").write_text(json.dumps(dict(
        built=time.strftime("%Y-%m-%d"), panels=summary, missing_blocks=missing),
        indent=2))
    if missing:
        log(TAG, f"{len(missing)} region x block inputs missing "
                 f"(see results/47_model_panels_report.json)")


if __name__ == "__main__":
    main()
