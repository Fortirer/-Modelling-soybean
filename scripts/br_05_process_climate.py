"""BR 05 - Aggregate NASA POWER daily weather into agronomic monthly/seasonal
features, analogue of US script 04 (which starts from NOAA nClimDiv monthly
data instead of daily, since the US branch has that source). No Palmer
drought indices (PDSI, Z-index) here -- CMIP6 does not supply them either
(see US script 12's caveats) and Brazil has no equivalent public monthly
county-level index this pipeline can pull without a separate water-balance
model; drought is represented here only by the precipitation-deficit
features actually computed from POWER (pcp_critical shortfall, dry-day
counts) -- weaker than Palmer, flagged rather than faked.

CROP-YEAR CONVENTION -- "ano" is the HARVEST year
  IBGE's PAM files a crop under the calendar year it is harvested in. Soy
  sown in Sep-Dec of ano-1 fills its pods in Jan-Feb of ano and is reported
  under ano. So ano=2022 means: growing season Sep 2021 through Apr 2022,
  critical pod-set/seed-fill window Jan-Feb 2022 -- the Brazilian-summer
  analogue of the US pipeline's July-August window.

  Until 2026-11-16 this script assumed the opposite (ano = planting year),
  on the strength of a test run on Mato Grosso alone, which paired each
  yield with the weather of the FOLLOWING season. Checked against all ten
  states with the SPEI-3 of script 42:
    - Rio Grande do Sul's yield collapses are in PAM 2005, 2012 and 2022,
      the harvests of the 2004/05, 2011/12 and 2021/22 droughts;
    - the correlation of yield anomaly with critical-window SPEI-3 is about
      zero under the old alignment and 0.45 (RS), 0.36 (PR), 0.36 (MS) under
      this one. Mato Grosso, where drought is rare, separates the two poorly
      (-0.02 either way), which is how the old test went wrong.
  See docs/DADOS_FALTANTES.md, section 8.
"""
import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _brcfg import RAW, PROC, RES, UF

CRITICAL_MONTHS = {1, 2}            # Jan-Feb of the harvest year
GROW_MONTHS_NEXT = {1, 2, 3, 4}     # Jan-Apr of the harvest year
GROW_MONTHS_CUR = {9, 10, 11, 12}   # Sep-Dec of the year before harvest


def main():
    d = pd.read_csv(RAW / "power_daily.csv.gz", dtype={"unit_id": str})
    d["month"] = pd.to_datetime(d.date).dt.month

    # crop_year: the HARVEST year (= IBGE's "ano") this day's weather counts
    # toward -- Sep-Dec belongs to the crop harvested NEXT calendar year,
    # Jan-Apr to the crop harvested THIS calendar year; May-Aug is the
    # Brazilian dry season/off-crop, excluded from every season feature
    # below (it still exists in the daily file).
    d["crop_year"] = np.where(d.month.isin(GROW_MONTHS_CUR), d.year + 1,
                      np.where(d.month.isin(GROW_MONTHS_NEXT), d.year, np.nan))

    grow = d.dropna(subset=["crop_year"]).copy()
    grow["crop_year"] = grow.crop_year.astype(int)
    grow["is_critical"] = grow.month.isin(CRITICAL_MONTHS)

    g = grow.groupby(["unit_id", "crop_year"])
    gc = grow[grow.is_critical].groupby(["unit_id", "crop_year"])

    feat = pd.DataFrame({
        "pcp_grow":       g.prcp_mm.sum(),
        "pcp_critical":   gc.prcp_mm.sum(),
        "tmp_grow":       g.tmean_c.mean(),
        "tmp_critical":   gc.tmean_c.mean(),
        "tmax_critical":  gc.tmax_c.mean(),
        "tmax_grow":      g.tmax_c.mean(),
        "tmin_grow":      g.tmin_c.mean(),
        "tmp_grow_sd":    g.tmean_c.std(),
        "n_days_grow":    g.size(),
        "n_days_critical": gc.size(),
    }).reset_index().rename(columns={"unit_id": "fips5", "crop_year": "year"})

    # dry/hot proxies, same spirit as US script 04's hot_month_count /
    # dry_month_count but at DAILY resolution (finer, since POWER is daily)
    hot = grow[grow.is_critical].groupby(["unit_id", "crop_year"]).apply(
        lambda x: (x.tmax_c >= 32).sum(), include_groups=False
    ).rename("hot_days_critical").reset_index().rename(
        columns={"unit_id": "fips5", "crop_year": "year"})
    dry = grow[grow.is_critical].groupby(["unit_id", "crop_year"]).apply(
        lambda x: (x.prcp_mm < 1).sum(), include_groups=False
    ).rename("dry_days_critical").reset_index().rename(
        columns={"unit_id": "fips5", "crop_year": "year"})
    feat = feat.merge(hot, on=["fips5", "year"]).merge(dry, on=["fips5", "year"])
    feat["heat_x_dry"] = feat.tmax_critical * feat.dry_days_critical

    # county-specific (municipio-specific) anomalies vs that municipio's own
    # climatology, same construction as US script 04
    ANOM = ["pcp_grow", "pcp_critical", "tmp_grow", "tmp_critical", "tmax_critical"]
    gg = feat.groupby("fips5")
    for v in ANOM:
        feat[f"{v}_anom"] = feat[v] - gg[v].transform("mean")
        sd = gg[v].transform("std")
        feat[f"{v}_z"] = feat[f"{v}_anom"] / sd.replace(0, np.nan)
    feat["climate_normal_pcp"] = gg["pcp_critical"].transform("mean")
    feat["climate_normal_tmax"] = gg["tmax_critical"].transform("mean")

    out = PROC / "climate_features.csv"
    feat.to_csv(out, index=False)
    rep = dict(
        daily_rows=len(d), crop_year_rows=len(grow), feature_rows=len(feat),
        municipalities=int(feat.fips5.nunique()),
        year_min=int(feat.year.min()), year_max=int(feat.year.max()),
        critical_window="Jan-Feb of the harvest year (year=ano=harvest year, "
                        "see docstring)",
        growing_season="Sep(year-1)-Apr(year)",
        nulls_total=int(feat.isna().sum().sum()),
        note="no Palmer drought indices available for Brazil in this pipeline; "
             "drought represented only via precipitation-deficit features",
    )
    (RES / "br05_climate_processing_report.json").write_text(json.dumps(rep, indent=2))
    for k, v in rep.items():
        print(f"[br05] {k:20} {v}")
    print(f"[br05] columns out   {feat.shape[1]}")
    print(f"[br05] -> data/processed/BR/{UF}/climate_features.csv")


if __name__ == "__main__":
    main()
