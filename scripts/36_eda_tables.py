"""36 - Exploratory data analysis, US vs Brazil soybean: harmonised panel and tables.

WHAT THIS DOES
  Puts the 12 US states (county level) and 10 Brazilian states (municipio level)
  on one footing and builds every table the EDA figures (script 37) and the
  Flourish exports are made from. Nothing here re-runs a pipeline: it only reads
  what scripts 01-35 and br_01-br_20 already wrote.

HARMONISATION (what had to be fixed before the two countries can be compared)
  * Units. US climate columns are degF and inches (NOAA nClimDiv), Brazil's are
    degC and mm (NASA POWER). Everything is converted to degC and mm. Yield is
    kg/ha in both panels already; yield anomalies are re-expressed in percent of
    each unit's own trend so they are unit-free.
  * Anomalies. Recomputed here as deviation from each unit's own 1980-2025 mean,
    identically for both countries, rather than trusting two differently built
    *_anom columns.
  * Window. Every cross-country statistic uses 1980-2025 (WIN below). Brazilian
    climate (NASA POWER) starts in 1981, keyed by harvest year (br_05); the
    1981 harvest has a partial season. "Recent" is the last ten years, 2016-2025.
  * Peak-season window. The repo's yield-setting window is July-August in the US
    and January-February in Brazil (southern-hemisphere summer). Both are called
    the "critical window" and compared as like-for-like local peak season.

WHAT THE TABLES CONTAIN
  A. data audit     attrition funnel, missingness (NA), panel balance
  B. descriptives   level, spread, shape, trend, outliers
  C. potential      attainable-yield proxy (95th percentile) and the gap to it
  D. hazard         observed critical-window warming; CMIP6 projections in the
                    AR6 style (median, model range, model agreement)
  E. exposure       how often projected warming leaves the historical envelope
  F. sensitivity    one regression specification, both countries
  G. structure      state-level tests, correlations, PCA

READ THIS BEFORE USING THE NUMBERS
  Yield sources differ (NASS county surveys vs IBGE municipal estimates), climate
  sources differ (nClimDiv vs MERRA-2 via POWER), and the two peak-season windows
  fall in different months. Differences between countries are descriptive. They
  are not a controlled experiment.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
RAW, PROC, FINAL = ROOT / "data/raw", ROOT / "data/processed", ROOT / "data/final"
OUT = ROOT / "results" / "_eda_us_brazil"
FL = OUT / "flourish"
OUT.mkdir(parents=True, exist_ok=True)
FL.mkdir(parents=True, exist_ok=True)

US = ["IL", "IA", "IN", "KS", "MI", "MN", "MO", "ND", "NE", "OH", "SD", "WI"]
BR = ["MT", "PR", "GO", "RS", "MS", "MG", "BA", "TO", "SP", "MA"]
NAME = {"IL": "Illinois", "IA": "Iowa", "IN": "Indiana", "KS": "Kansas", "MI": "Michigan",
        "MN": "Minnesota", "MO": "Missouri", "ND": "North Dakota", "NE": "Nebraska",
        "OH": "Ohio", "SD": "South Dakota", "WI": "Wisconsin",
        "MT": "Mato Grosso", "PR": "Paraná", "GO": "Goiás", "RS": "Rio Grande do Sul",
        "MS": "Mato Grosso do Sul", "MG": "Minas Gerais", "BA": "Bahia", "TO": "Tocantins",
        "SP": "São Paulo", "MA": "Maranhão"}
CRIT = {"US": [7, 8], "BR": [1, 2]}
WIN = (1980, 2025)
RECENT, EARLY = (2016, 2025), (1980, 1989)
AREA_RECENT = (2021, 2025)      # years averaged for the harvested-area weights
BU_AC_TO_KG_HA = 67.25
MIN_YEARS = 20     # common balanced-panel rule; the repo's own US rule needs 42 of 44 (1980-2023), Brazil's 20
SEED = 42


def key(c, s):
    return f"{c}-{s}"


def final_path(c, s):
    if c == "US":
        return FINAL / ("" if s == "IL" else s) / "soybean_illinois_climate_1980_2025.csv"
    return FINAL / "BR" / s / "soja_mt_climate_1981_2024.csv"


def raw_path(c, s):
    if c == "US":
        return RAW / ("" if s == "IL" else s) / "nass_il_soybeans_county_raw.csv"
    return RAW / "BR" / s / "ibge_pam_soja_municipios.csv"


def cmip_path(c, s):
    if c == "US":
        return PROC / ("" if s == "IL" else s) / "cmip6_deltas.csv"
    return PROC / "BR" / s / "cmip6_deltas.csv"


# ------------------------------------------------------------------ A. panel
def load_panel(c, s):
    d = pd.read_csv(final_path(c, s), low_memory=False, dtype={"fips5": str})
    if c == "US":
        d["fips5"] = d.fips5.str.zfill(5)
        assert 60 < d.tmax_critical.mean() < 110, f"{s}: expected degF"
        d["tmax_c"] = (d.tmax_critical - 32) / 1.8
        d["pcp_crit_mm"] = d.pcp_critical * 25.4
        d["pcp_grow_mm"] = d.pcp_grow * 25.4
        ycol = "n_years_county"
    else:
        assert d.tmax_critical.mean() < 50, f"{s}: expected degC"
        d["tmax_c"] = d.tmax_critical
        d["pcp_crit_mm"] = d.pcp_critical
        d["pcp_grow_mm"] = d.pcp_grow
        ycol = "n_years_muni"
    d = d[(d.year >= WIN[0]) & (d.year <= WIN[1])].copy()
    d["country"], d["state"] = c, s
    d["uid"] = c + "-" + d.fips5
    d["n_years"] = d[ycol]
    d["balanced_repo"] = d.in_balanced_panel.astype(int)
    d["n_years_win"] = d.groupby("uid").year.transform("size")
    d["balanced"] = (d.n_years_win >= MIN_YEARS).astype(int)
    ok = d.yield_trend > 0
    d["yield_anom_pct"] = np.where(ok, 100 * d.yield_anom / d.yield_trend, np.nan)
    g = d.groupby("uid")
    d["tmax_anom_c"] = d.tmax_c - g.tmax_c.transform("mean")
    d["pcp_anom_mm"] = d.pcp_crit_mm - g.pcp_crit_mm.transform("mean")
    d["pcp_anom_pct"] = 100 * d.pcp_anom_mm / g.pcp_crit_mm.transform("mean")
    d["unit_tmax_max"] = g.tmax_c.transform("max")
    d["unit_area_mean_ha"] = g.area_harvested_ha.transform("mean")
    cols = ["country", "state", "uid", "year", "yield_kg_ha", "area_harvested_ha", "production_tonnes",
            "tmax_c", "pcp_crit_mm", "pcp_grow_mm", "tmax_anom_c", "pcp_anom_mm", "pcp_anom_pct",
            "yield_trend", "yield_anom", "yield_anom_pct", "balanced", "balanced_repo", "n_years_win",
            "unit_tmax_max", "unit_area_mean_ha"]
    return d[cols]


def funnel_row(c, s, panel_s):
    raw = pd.read_csv(raw_path(c, s), low_memory=False)
    if c == "US":
        r = raw.rename(columns={"acres_planted": "area_planted", "acres_harvested": "area_harvested",
                                "production_bu": "production", "yield_bu_ac": "yield_"})
        yr = "year"
        est = None
        if "is_county_estimate" in r:
            est = r.is_county_estimate.map({True: 1, False: 0, "True": 1, "False": 0, 1: 1, 0: 0})
    else:
        r = raw.rename(columns={"area_plantada_ha": "area_planted", "area_colhida_ha": "area_harvested",
                                "producao_t": "production", "rendimento_kg_ha": "yield_", "ano": "year"})
        yr, est = "year", None
    r = r[(r[yr] >= WIN[0]) & (r[yr] <= WIN[1])].copy()
    for k in ["area_planted", "area_harvested", "production", "yield_"]:
        r[k] = pd.to_numeric(r[k], errors="coerce")
    usable = r.yield_.notna() & r.area_harvested.notna() & (r.area_harvested > 0)
    out = dict(country=c, state=s, raw_rows=len(r), usable_rows=int(usable.sum()),
               climate_matched_rows=len(panel_s), balanced_rows=int(panel_s.balanced.sum()),
               balanced_repo_rows=int(panel_s.balanced_repo.sum()),
               na_area_planted=r.area_planted.isna().mean() * 100,
               na_area_harvested=r.area_harvested.isna().mean() * 100,
               na_production=r.production.isna().mean() * 100,
               na_yield=r.yield_.isna().mean() * 100,
               county_estimate_pct=(est.mean() * 100 if est is not None and est.notna().any() else np.nan))
    return out


def audit(panel):
    fun, bal = [], []
    for (c, s), p in panel.groupby(["country", "state"]):
        fun.append(funnel_row(c, s, p))
        span = WIN[1] - WIN[0] + 1
        u = p.groupby("uid").size()
        ub = p[p.balanced == 1].groupby("uid").size()
        ur = p[p.balanced_repo == 1].groupby("uid").size()
        g = p.groupby("uid").year.agg(["min", "max", "size"])
        missing = span * len(g) - g["size"].sum()
        lead = (g["min"] - WIN[0]).sum()
        trail = (WIN[1] - g["max"]).sum()
        gaps = ((g["max"] - g["min"] + 1) - g["size"]).sum()
        bal.append(dict(country=c, state=s, units_total=p.uid.nunique(), units_balanced=ub.size,
                        share_units_balanced=100 * ub.size / p.uid.nunique(),
                        units_balanced_repo_rule=ur.size,
                        rows_total=len(p), rows_balanced=int(p.balanced.sum()),
                        years_per_unit_median=float(u.median()), years_per_unit_mean=float(u.mean()),
                        fill_rate_all=100 * len(p) / (p.uid.nunique() * span),
                        fill_rate_balanced=100 * p.balanced.sum() / (max(ub.size, 1) * span),
                        missing_cells=int(missing), miss_late_entry_pct=100 * lead / missing,
                        miss_exit_pct=100 * trail / missing, miss_internal_gap_pct=100 * gaps / missing,
                        na_yield_anom=p.yield_anom_pct.isna().mean() * 100))
    f, b = pd.DataFrame(fun), pd.DataFrame(bal)
    f["lost_na_or_suppressed"] = f.raw_rows - f.usable_rows
    f["lost_no_climate_match"] = (f.usable_rows - f.climate_matched_rows).clip(lower=0)
    f["lost_unbalanced"] = f.climate_matched_rows - f.balanced_rows
    f["retained_pct"] = 100 * f.balanced_rows / f.raw_rows
    return f, b


# ------------------------------------------------------------- B/C. levels
def pct_stats(x, q):
    return float(np.nanpercentile(x, q)) if len(x) else np.nan


def trend_ols(years, vals):
    m = np.isfinite(vals)
    if m.sum() < 8:
        return np.nan, np.nan, np.nan
    r = stats.linregress(np.asarray(years)[m], np.asarray(vals)[m])
    return r.slope, r.stderr, r.pvalue


def describe(panel):
    rows = []
    for (c, s), p in panel.groupby(["country", "state"]):
        rec = p[(p.year >= RECENT[0]) & (p.year <= RECENT[1])]
        ear = p[(p.year >= EARLY[0]) & (p.year <= EARLY[1])]
        b = p[p.balanced == 1]
        ser = b.groupby("year").yield_kg_ha.mean()
        slope, se, pv = trend_ols(ser.index.values, ser.values)
        a = p.yield_anom_pct.dropna()
        mad = np.median(np.abs(a - a.median()))
        robust_z = 0.6745 * (a - a.median()) / mad if mad > 0 else a * 0
        area_recent = p[(p.year >= AREA_RECENT[0]) & (p.year <= AREA_RECENT[1])].groupby("year").area_harvested_ha.sum().mean()
        rows.append(dict(
            country=c, state=s, name=NAME[s], n_units=p.uid.nunique(),
            n_units_balanced=b.uid.nunique(), n_unit_years=len(p),
            yield_recent_mean=rec.yield_kg_ha.mean(), yield_recent_median=rec.yield_kg_ha.median(),
            yield_recent_p10=pct_stats(rec.yield_kg_ha, 10), yield_recent_p90=pct_stats(rec.yield_kg_ha, 90),
            yield_recent_p95=pct_stats(rec.yield_kg_ha, 95),
            yield_recent_cv=100 * rec.yield_kg_ha.std() / rec.yield_kg_ha.mean(),
            yield_recent_skew=float(stats.skew(rec.yield_kg_ha.dropna())),
            yield_recent_kurt=float(stats.kurtosis(rec.yield_kg_ha.dropna())),
            yield_early_mean=ear.yield_kg_ha.mean(),
            yield_gain_pct=100 * (rec.yield_kg_ha.mean() / ear.yield_kg_ha.mean() - 1),
            trend_kg_ha_yr=slope, trend_se=se, trend_p=pv,
            trend_rel_pct_yr=100 * slope / ser.mean() if np.isfinite(slope) else np.nan,
            anom_sd_pct=float(a.std()), anom_skew=float(stats.skew(a)),
            outlier_share_pct=float((np.abs(robust_z) > 3.5).mean() * 100),
            area_recent_kha=area_recent / 1000.0,
            tmax_mean_c=p.tmax_c.mean(), pcp_crit_mean_mm=p.pcp_crit_mm.mean(),
            pcp_grow_mean_mm=p.pcp_grow_mm.mean()))
    t = pd.DataFrame(rows)
    t["gap_kg_ha"] = t.yield_recent_p95 - t.yield_recent_mean
    t["efficiency_pct"] = 100 * t.yield_recent_mean / t.yield_recent_p95
    fr = {c: t[t.country == c].yield_recent_p95.max() for c in ("US", "BR")}
    t["mean_vs_us_frontier_pct"] = 100 * t.yield_recent_mean / fr["US"]
    t["mean_vs_own_frontier_pct"] = [100 * m / fr[c] for m, c in zip(t.yield_recent_mean, t.country)]
    return t


# ----------------------------------------------------- D. observed warming
def observed_climate(panel):
    ya = (panel.groupby(["country", "state", "year"])
          .agg(tmax_anom_c=("tmax_anom_c", "mean"), pcp_anom_pct=("pcp_anom_pct", "mean"),
               yield_anom_pct=("yield_anom_pct", "mean"), n=("uid", "size")).reset_index())
    rows = []
    for (c, s), g in ya.groupby(["country", "state"]):
        sl, se, p = trend_ols(g.year.values, g.tmax_anom_c.values)
        slp, sep, pp = trend_ols(g.year.values, g.pcp_anom_pct.values)
        det = g.tmax_anom_c - np.polyval(np.polyfit(g.year, g.tmax_anom_c, 1), g.year)
        rows.append(dict(country=c, state=s, tmax_trend_c_decade=10 * sl, tmax_trend_se=10 * se,
                         tmax_trend_p=p, tmax_sd_detrended_c=float(det.std()),
                         pcp_trend_pct_decade=10 * slp, pcp_trend_p=pp))
    return ya, pd.DataFrame(rows)


# ---------------------------------------------------- D/E. CMIP6 projections
def projections(panel):
    st_rows, oor_rows = [], []
    for (c, s), p in panel.groupby(["country", "state"]):
        d = pd.read_csv(cmip_path(c, s), dtype={"fips5": str})
        if c == "US":
            d["fips5"] = d.fips5.str.zfill(5)
        d = d[d.month.isin(CRIT[c])]
        d["uid"] = c + "-" + d.fips5
        d = d.groupby(["uid", "model", "scenario", "horizon"], as_index=False).agg(
            dT=("d_tasmax_C", "mean"), pr=("pr_ratio", "mean"), dRH=("d_hurs_pct", "mean"))
        w = p.groupby("uid").unit_area_mean_ha.first().rename("w")
        dd = d.merge(w, left_on="uid", right_index=True)
        dd = dd[dd.w > 0]
        wm = (dd.assign(a=dd.dT * dd.w, b=(dd.pr - 1) * 100 * dd.w, c_=dd.dRH * dd.w)
              .groupby(["model", "scenario", "horizon"])
              .agg(a=("a", "sum"), b=("b", "sum"), c_=("c_", "sum"), w=("w", "sum")).reset_index())
        wm["dT"], wm["pr_pct"], wm["dRH"] = wm.a / wm.w, wm.b / wm.w, wm.c_ / wm.w
        for (sc, hz), g in wm.groupby(["scenario", "horizon"]):
            med_pr, med_rh = g.pr_pct.median(), g.dRH.median()
            st_rows.append(dict(
                country=c, state=s, scenario=sc, horizon=hz, n_models=len(g),
                dT_med=g.dT.median(), dT_min=g.dT.min(), dT_max=g.dT.max(),
                pr_med=med_pr, pr_min=g.pr_pct.min(), pr_max=g.pr_pct.max(),
                pr_agree_pct=100 * (np.sign(g.pr_pct) == np.sign(med_pr)).mean() if med_pr != 0 else np.nan,
                rh_med=med_rh, rh_agree_pct=100 * (np.sign(g.dRH) == np.sign(med_rh)).mean() if med_rh != 0 else np.nan))
        x = p[["uid", "year", "tmax_c", "unit_tmax_max"]].merge(d[["uid", "model", "scenario", "horizon", "dT"]], on="uid")
        x["out"] = (x.tmax_c + x.dT) > x.unit_tmax_max
        oo = x.groupby(["scenario", "horizon", "model"]).out.mean().mul(100).reset_index()
        for (sc, hz), g in oo.groupby(["scenario", "horizon"]):
            oor_rows.append(dict(country=c, state=s, scenario=sc, horizon=hz,
                                 out_of_range_pct_med=g.out.median(), out_of_range_pct_min=g.out.min(),
                                 out_of_range_pct_max=g.out.max()))
    return pd.DataFrame(st_rows), pd.DataFrame(oor_rows)


# ------------------------------------------------------ F. sensitivity
def sensitivity(panel):
    b = panel[(panel.balanced == 1)].dropna(subset=["yield_anom_pct", "tmax_anom_c", "pcp_anom_mm"]).copy()
    b["pcp_anom_100mm"] = b.pcp_anom_mm / 100.0
    rows = []

    def fit(df, label, c, s, fe_year):
        f = "yield_anom_pct ~ tmax_anom_c + pcp_anom_100mm" + (" + C(year)" if fe_year else "")
        m = smf.ols(f, df).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(df.uid)[0]})
        out = []
        for term, nm in (("tmax_anom_c", "heat_pct_per_c"), ("pcp_anom_100mm", "rain_pct_per_100mm")):
            ci = m.conf_int().loc[term]
            out.append(dict(country=c, state=s, spec="year_FE" if fe_year else "no_FE", term=nm,
                            coef=m.params[term], se=m.bse[term], lo=ci[0], hi=ci[1], p=m.pvalues[term],
                            n=int(m.nobs), n_units=df.uid.nunique()))
        return out
    for (c, s), g in b.groupby(["country", "state"]):
        for fe in (False, True):
            rows += fit(g, s, c, s, fe)
    for c, g in b.groupby("country"):
        for fe in (False, True):
            rows += fit(g, "ALL", c, "ALL", fe)
    return pd.DataFrame(rows)


# ---------------------------------------------------------- G. structure
def cliffs_delta(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    gt = sum((x > b).sum() for x in a)
    lt = sum((x < b).sum() for x in a)
    return (gt - lt) / (len(a) * len(b))


def group_tests(state_tab):
    rows = []
    for k, lab in [("yield_recent_mean", f"Mean yield {RECENT[0]}-{RECENT[1] % 100} (kg/ha)"), ("yield_recent_p95", "Yield proxy for potential, P95 (kg/ha)"),
                   ("efficiency_pct", "Mean as % of P95"), ("yield_gain_pct", f"Yield gain {EARLY[0]}-{EARLY[1] % 100} to {RECENT[0]}-{RECENT[1] % 100} (%)"),
                   ("trend_rel_pct_yr", "Relative yield trend (%/yr)"), ("anom_sd_pct", "Yield anomaly SD (% of trend)"),
                   ("heat_pct_per_c", "Heat sensitivity (% yield per C)"), ("dT_ssp585_late", "Projected warming SSP5-8.5 late (C)"),
                   ("snr_ssp585_late", "Warming / interannual SD (SSP5-8.5 late)"),
                   ("oor_ssp585_late", "Out-of-range share SSP5-8.5 late (%)"), ("share_units_balanced", "Units in balanced panel (%)")]:
        us = state_tab[state_tab.country == "US"][k].dropna()
        br = state_tab[state_tab.country == "BR"][k].dropna()
        if len(us) < 3 or len(br) < 3:
            continue
        u = stats.mannwhitneyu(us, br, alternative="two-sided")
        rows.append(dict(metric=lab, key=k, us_median=us.median(), br_median=br.median(), n_us=len(us), n_br=len(br),
                         mann_whitney_U=u.statistic, p=u.pvalue, cliffs_delta=cliffs_delta(us, br)))
    t = pd.DataFrame(rows)
    idx = np.argsort(t.p.values)                           # Holm step-down
    stepped = np.maximum.accumulate((len(t) - np.arange(len(t))) * t.p.values[idx])
    adj = np.empty(len(t))
    adj[idx] = np.minimum(stepped, 1.0)
    t["p_holm"] = adj
    return t


def pca(state_tab, feats):
    X = state_tab[feats].astype(float)
    X = X.fillna(X.median())
    Z = (X - X.mean()) / X.std(ddof=0)
    U, S, Vt = np.linalg.svd(Z.values, full_matrices=False)
    ev = S ** 2 / (S ** 2).sum()
    scores = pd.DataFrame(U * S, columns=[f"PC{i + 1}" for i in range(len(S))], index=state_tab.state)
    load = pd.DataFrame(Vt.T, index=feats, columns=[f"PC{i + 1}" for i in range(len(S))])
    corr = X.corr(method="spearman")
    return scores, load, ev, corr


def binned(panel):
    rows = []
    for c, g in panel[panel.balanced == 1].groupby("country"):
        for var, width, nm in (("tmax_anom_c", 0.5, "heat"), ("pcp_anom_pct", 10, "rain")):
            x = g.dropna(subset=[var, "yield_anom_pct"]).copy()
            x["bin"] = (np.floor(x[var] / width) + 0.5) * width
            for bn, h in x.groupby("bin"):
                if len(h) < 30:
                    continue
                rows.append(dict(country=c, driver=nm, bin=bn, n=len(h), median=h.yield_anom_pct.median(),
                                 q25=h.yield_anom_pct.quantile(0.25), q75=h.yield_anom_pct.quantile(0.75)))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ main
def main():
    panels = []
    for c, lst in (("US", US), ("BR", BR)):
        for s in lst:
            panels.append(load_panel(c, s))
    panel = pd.concat(panels, ignore_index=True)
    panel.drop(columns=["unit_tmax_max", "unit_area_mean_ha"]).to_csv(
        OUT / "harmonised_panel.csv.gz", index=False, float_format="%.4f", compression="gzip")
    print(f"[36] harmonised panel: {len(panel):,} unit-years, {panel.uid.nunique():,} units, "
          f"{panel.state.nunique()} states, {WIN[0]}-{WIN[1]}")

    funnel, balance = audit(panel)
    funnel.to_csv(OUT / "audit_funnel_na.csv", index=False)
    balance.to_csv(OUT / "audit_balance.csv", index=False)
    print(f"[36] common balanced rule: >= {MIN_YEARS} of {WIN[1] - WIN[0] + 1} years. Repo rule keeps "
          f"{int(balance[balance.country == 'US'].units_balanced_repo_rule.sum())} of "
          f"{int(balance[balance.country == 'US'].units_total.sum())} US units; the common rule keeps "
          f"{int(balance[balance.country == 'US'].units_balanced.sum())}")
    act = panel.groupby(["state", "year"]).size().unstack(fill_value=0)
    act.to_csv(OUT / "audit_active_units_by_year.csv")

    desc = describe(panel)
    ya, obs = observed_climate(panel)
    ya.to_csv(OUT / "observed_state_year_anomalies.csv", index=False)
    obs.to_csv(OUT / "observed_trends.csv", index=False)

    proj, oor = projections(panel)
    proj.to_csv(OUT / "projections_state.csv", index=False)
    oor.to_csv(OUT / "exposure_out_of_range.csv", index=False)

    sens = sensitivity(panel)
    sens.to_csv(OUT / "sensitivity_heat_rain.csv", index=False)

    t = desc.merge(obs, on=["country", "state"])
    heat = sens[(sens.state != "ALL") & (sens.spec == "no_FE") & (sens.term == "heat_pct_per_c")]
    t = t.merge(heat[["state", "coef", "lo", "hi", "p"]].rename(
        columns={"coef": "heat_pct_per_c", "lo": "heat_lo", "hi": "heat_hi", "p": "heat_p"}), on="state")
    k = proj[(proj.scenario == "ssp585") & (proj.horizon == "late_century")]
    t = t.merge(k[["state", "dT_med", "pr_med", "pr_agree_pct"]].rename(
        columns={"dT_med": "dT_ssp585_late", "pr_med": "pr_ssp585_late", "pr_agree_pct": "pr_agree_ssp585_late"}), on="state")
    t["snr_ssp585_late"] = t.dT_ssp585_late / t.tmax_sd_detrended_c
    o = oor[(oor.scenario == "ssp585") & (oor.horizon == "late_century")]
    t = t.merge(o[["state", "out_of_range_pct_med"]].rename(columns={"out_of_range_pct_med": "oor_ssp585_late"}), on="state")
    t = t.merge(balance[["state", "share_units_balanced", "fill_rate_all"]], on="state")
    t.to_csv(OUT / "state_summary.csv", index=False)

    tests = group_tests(t)
    tests.to_csv(OUT / "country_tests.csv", index=False)

    feats = ["yield_recent_mean", "yield_recent_p95", "efficiency_pct", "anom_sd_pct", "trend_rel_pct_yr",
             "tmax_mean_c", "pcp_crit_mean_mm", "heat_pct_per_c", "dT_ssp585_late", "share_units_balanced"]
    scores, load, ev, corr = pca(t, feats)
    scores.to_csv(OUT / "pca_scores.csv")
    load.to_csv(OUT / "pca_loadings.csv")
    corr.to_csv(OUT / "feature_spearman.csv")
    pd.Series(ev, index=[f"PC{i + 1}" for i in range(len(ev))]).to_csv(OUT / "pca_explained.csv", header=["share"])
    binned(panel).to_csv(OUT / "binned_climate_yield.csv", index=False)

    export_flourish(panel, t, funnel, proj, oor, ya)

    pd.set_option("display.width", 220, "display.max_columns", 40)
    print("\n[36] BALANCE (common >=20-year rule) and WHY cells are missing")
    print(balance[["state", "units_total", "units_balanced", "units_balanced_repo_rule", "fill_rate_all",
                   "fill_rate_balanced", "miss_late_entry_pct", "miss_exit_pct",
                   "miss_internal_gap_pct"]].round(1).to_string(index=False))
    print("\n[36] FUNNEL (rows " + f"{WIN[0]}-{WIN[1]})")
    print(funnel[["state", "raw_rows", "usable_rows", "climate_matched_rows", "balanced_rows", "retained_pct",
                  "na_yield", "county_estimate_pct"]].round(1).to_string(index=False))
    print("\n[36] POTENTIAL / LEVELS (" + f"{RECENT[0]}-{RECENT[1]})")
    print(t[["state", "yield_recent_mean", "yield_recent_p95", "efficiency_pct", "yield_gain_pct",
             "trend_rel_pct_yr", "anom_sd_pct", "outlier_share_pct"]].round(1).to_string(index=False))
    print("\n[36] HAZARD / SENSITIVITY")
    print(t[["state", "tmax_trend_c_decade", "tmax_trend_p", "dT_ssp585_late", "snr_ssp585_late", "oor_ssp585_late",
             "heat_pct_per_c", "heat_p"]].round(3).to_string(index=False))
    print("\n[36] COUNTRY TESTS (Mann-Whitney, US n=12 vs BR n=10)")
    print(tests.round(3).to_string(index=False))
    print("\n[36] PCA explained variance:", np.round(ev[:4], 3))

    (OUT / "config.json").write_text(json.dumps(dict(
        window=WIN, recent=RECENT, early=EARLY, area_recent=AREA_RECENT, critical_months=CRIT, seed=SEED,
        states=dict(US=US, BR=BR),
        notes=["US climate converted degF->degC and inches->mm", f"anomalies recomputed vs each unit's own {WIN[0]}-{WIN[1]} mean",
               "CMIP6: 8 models, baseline 1985-2014, horizons 2040-69 / 2070-99, SSP2-4.5 and SSP5-8.5, area-weighted by mean harvested area",
               "heat sensitivity: yield anomaly (% of unit trend) on critical-window Tmax and rainfall anomalies, balanced panel, unit-clustered SE",
               "yield/climate sources differ between countries: differences are descriptive"]), indent=2))
    print(f"\n[36] -> {OUT.relative_to(ROOT)}")


def export_flourish(panel, t, funnel, proj, oor, ya):
    s = t.copy()
    s["country_name"] = s.country.map({"US": "United States", "BR": "Brazil"})
    s[["name", "state", "country_name", "yield_recent_mean", "yield_recent_p95", "efficiency_pct", "gap_kg_ha",
       "anom_sd_pct", "trend_rel_pct_yr", "yield_gain_pct", "area_recent_kha", "heat_pct_per_c",
       "dT_ssp585_late", "snr_ssp585_late", "oor_ssp585_late", "share_units_balanced"]].round(2).to_csv(
        FL / "flourish_state_scatter.csv", index=False)

    b = panel[panel.balanced == 1].groupby(["state", "year"]).yield_kg_ha.mean().unstack().round(0)
    b.insert(0, "Country", [("United States" if x in US else "Brazil") for x in b.index])
    b.insert(0, "Name", [NAME[x] for x in b.index])
    b.reset_index().to_csv(FL / "flourish_yield_by_year_rows_are_states.csv", index=False)

    w = ya.pivot(index="state", columns="year", values="tmax_anom_c").round(2)
    w.insert(0, "Country", [("United States" if x in US else "Brazil") for x in w.index])
    w.insert(0, "Name", [NAME[x] for x in w.index])
    w.reset_index().to_csv(FL / "flourish_warming_stripes_tmax_anomaly.csv", index=False)

    p = proj.copy()
    p["scenario_horizon"] = p.scenario.map({"ssp245": "SSP2-4.5", "ssp585": "SSP5-8.5"}) + " " + p.horizon.map(
        {"mid_century": "2040-69", "late_century": "2070-99"})
    p["name"] = p.state.map(NAME)
    p["country_name"] = p.country.map({"US": "United States", "BR": "Brazil"})
    p[["name", "state", "country_name", "scenario_horizon", "dT_med", "dT_min", "dT_max", "pr_med", "pr_min",
       "pr_max", "pr_agree_pct"]].round(2).to_csv(FL / "flourish_projection_ranges_long.csv", index=False)
    hm = p.pivot(index="name", columns="scenario_horizon", values="dT_med").round(2)
    hm.insert(0, "Country", [("United States" if NAME_INV[x] in US else "Brazil") for x in hm.index])
    hm.reset_index().to_csv(FL / "flourish_projection_heatmap_dT.csv", index=False)

    for c, lab in (("US", "United States"), ("BR", "Brazil")):
        f = funnel[funnel.country == c][["raw_rows", "usable_rows", "climate_matched_rows", "balanced_rows"]].sum()
        rows = [("Reported unit-years", "Usable yield and area", f.usable_rows),
                ("Reported unit-years", "Lost: NA or suppressed", f.raw_rows - f.usable_rows),
                ("Usable yield and area", "Matched to climate", f.climate_matched_rows),
                ("Usable yield and area", "Lost: no climate match", max(f.usable_rows - f.climate_matched_rows, 0)),
                ("Matched to climate", "Balanced panel", f.balanced_rows),
                ("Matched to climate", "Lost: unbalanced unit", f.climate_matched_rows - f.balanced_rows)]
        pd.DataFrame(rows, columns=["Source", "Target", "Value"]).astype({"Value": int}).to_csv(
            FL / f"flourish_sankey_funnel_{c}.csv", index=False)
    (FL / "README_flourish.md").write_text(FLOURISH_README, encoding="utf-8")


NAME_INV = {v: k for k, v in NAME.items()}

FLOURISH_README = """# Flourish-ready files

I could not drive Flourish itself (it needs your account), so these files are shaped for its templates.
In Flourish: New visualisation -> choose the template -> Data tab -> upload the CSV -> map the columns as below.

| File | Flourish template | Column mapping |
| --- | --- | --- |
| flourish_state_scatter.csv | Scatter / Bubble | X = yield_recent_p95 (potential proxy), Y = anom_sd_pct (instability), Size = area_recent_kha, Colour = country_name, Label = name |
| flourish_yield_by_year_rows_are_states.csv | Line chart, or Bar chart race | Rows are states, year columns are the series/time steps. Colour/category = Country, label = Name |
| flourish_warming_stripes_tmax_anomaly.csv | Heatmap (matrix) | Rows = Name, columns = years, diverging blue-grey-red scale centred on 0 |
| flourish_projection_ranges_long.csv | Scatter, or Dot/Range plot | Y = name, X = dT_med, with dT_min and dT_max as range ends, filter or facet by scenario_horizon |
| flourish_projection_heatmap_dT.csv | Heatmap (matrix) | Rows = Name, columns = scenario/horizon, sequential one-hue scale |
| flourish_sankey_funnel_US.csv / _BR.csv | Sankey | Source, Target, Value |

Conventions kept from the static figures: US = blue, Brazil = orange; SSP2-4.5 = AR6 yellow (#eadd3d), SSP5-8.5 = AR6 dark red (#840b22).
"""

if __name__ == "__main__":
    main()
