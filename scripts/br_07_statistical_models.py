"""BR 07 - Panel statistical models for Mato Grosso soybean yield, same
escalating-specification design as US script 07 (naive pooled OLS through
two-way fixed effects with municipality-clustered SEs). Units are metric
throughout (mm, degrees C) rather than converted to inches/degrees F, since
this branch has no US-comparison reason to convert. No Palmer-Z
specification (M5 in the US version) -- no Palmer index exists for this
branch, see br_05's docstring.
"""
import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import statsmodels.formula.api as smf
import statsmodels.api as sm
from statsmodels.stats.diagnostic import het_breuschpagan
from _brcfg import FINAL, RES, MOD, FOCAL_CODE

d = pd.read_csv(FINAL / "soja_mt_climate_1981_2024.csv", dtype={"fips5": str})
d = d[d.in_balanced_panel == 1].copy()
d["PCP"] = d.pcp_critical
d["TMX"] = d.tmax_critical
d["PCP2"] = d.PCP ** 2
d["TMX2"] = d.TMX ** 2
d["PT"] = d.PCP * d.TMX
d["muni"] = d.fips5.astype("category")
d["yr"] = d.year.astype("category")
print(f"[br07] estimation sample: {len(d):,} rows, {d.fips5.nunique()} municipalities, "
      f"{d.year.nunique()} years")

SPECS = {
    "M1 Baseline pooled OLS": "yield_anom ~ PCP + TMX",
    "M2 Quadratic + interaction": "yield_anom ~ PCP + PCP2 + TMX + TMX2 + PT",
    "M3 M2 + municipio FE": "yield_anom ~ PCP + PCP2 + TMX + TMX2 + PT + C(muni)",
    "M4 Two-way FE (municipio + year)":
        "yield_anom ~ PCP + PCP2 + TMX + TMX2 + PT + C(muni) + C(yr)",
    "M5 Raw yield, two-way FE": "yield_bu_ac ~ PCP + PCP2 + TMX + TMX2 + PT + year + C(muni)",
    "M6 Log yield, municipio FE": "log_yield ~ PCP + PCP2 + TMX + TMX2 + PT + year + C(muni)",
}
rows, coefs = [], []
for name, f in SPECS.items():
    m = smf.ols(f, data=d).fit(cov_type="cluster", cov_kwds={"groups": d.fips5})
    resid = m.resid
    rmse = float(np.sqrt(np.mean(resid ** 2)))
    mae = float(np.mean(np.abs(resid)))
    try:
        bp = het_breuschpagan(resid, m.model.exog)[1]
    except Exception:
        bp = np.nan
    dw = float(sm.stats.durbin_watson(resid))
    rows.append(dict(model=name, n=int(m.nobs), k=int(m.df_model), r2=m.rsquared,
                     adj_r2=m.rsquared_adj, RMSE=rmse, MAE=mae, aic=m.aic, bic=m.bic,
                     F_pvalue=float(m.f_pvalue), breusch_pagan_p=bp, durbin_watson=dw,
                     se_type="cluster(municipio)"))
    for term in [t for t in m.params.index if not t.startswith("C(")]:
        ci = m.conf_int().loc[term]
        coefs.append(dict(model=name, term=term, coef=m.params[term], se=m.bse[term],
                          t=m.tvalues[term], p=m.pvalues[term], ci_low=ci[0], ci_high=ci[1]))
    if name.startswith("M4"):
        m.save(str(MOD / "m4_twoway_fe.pkl"))

t4 = pd.DataFrame(rows).round(5)
t4.to_csv(RES / "table4_regression_models.csv", index=False)
cf = pd.DataFrame(coefs).round(5)
cf.to_csv(RES / "table4b_regression_coefficients.csv", index=False)
print("\n[br07] MODEL COMPARISON")
print(t4[["model", "n", "k", "r2", "adj_r2", "RMSE", "breusch_pagan_p", "durbin_watson"]]
      .to_string(index=False))

m4 = smf.ols(SPECS["M4 Two-way FE (municipio + year)"], data=d).fit(
    cov_type="cluster", cov_kwds={"groups": d.fips5})
print("\n[br07] M4 climate coefficients (municipio-clustered SE)")
print(cf[cf.model.str.startswith("M4")][["term", "coef", "se", "p", "ci_low", "ci_high"]]
      .to_string(index=False))
Pb, P2b = m4.params["PCP"], m4.params["PCP2"]
Tb, T2b = m4.params["TMX"], m4.params["TMX2"]
PTb = m4.params["PT"]
Pbar, Tbar = d["PCP"].mean(), d["TMX"].mean()
P_opt = -(Pb + PTb * Tbar) / (2 * P2b)
T_opt = -(Tb + PTb * Pbar) / (2 * T2b)
me_T = Tb + 2 * T2b * Tbar + PTb * Pbar
me_P = Pb + 2 * P2b * Pbar + PTb * Tbar
print(f"\n[br07] sample means           : Jan-Feb precip {Pbar:.1f} mm, Jan-Feb tmax {Tbar:.2f} degC")
print(f"[br07] precip optimum | T=mean: {P_opt:.1f} mm")
print(f"[br07] temp optimum   | P=mean: {T_opt:.2f} degC")
print(f"[br07] dYield/dT at means     : {me_T:+.4f} bu/acre per degC")
print(f"[br07] dYield/dP at means     : {me_P:+.4f} bu/acre per mm")
for q, lab in [(.1, "dry (P10)"), (.9, "wet (P90)")]:
    Pq = d["PCP"].quantile(q)
    print(f"[br07] dYield/dT at {lab:10}: {Tb+2*T2b*Tbar+PTb*Pq:+.4f} bu/acre per degC  (P={Pq:.0f} mm)")

json.dump(dict(
    precip_optimum_mm_at_mean_T=float(P_opt), temp_optimum_C_at_mean_P=float(T_opt),
    dY_dT_at_means=float(me_T), dY_dP_at_means=float(me_P),
    dY_dT_dry_P10=float(Tb + 2*T2b*Tbar + PTb*d["PCP"].quantile(.1)),
    dY_dT_wet_P90=float(Tb + 2*T2b*Tbar + PTb*d["PCP"].quantile(.9)),
    mean_precip_mm=float(Pbar), mean_tmax_C=float(Tbar), n=int(m4.nobs),
    r2_M4=float(m4.rsquared),
), open(RES / "br07_key_estimates.json", "w"), indent=2)
print(f"\n[br07] -> results/BR/MT/br07_key_estimates.json")
