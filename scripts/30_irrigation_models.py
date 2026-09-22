"""30 - Does irrigation status explain county climate sensitivity? Table 39-40.

Same design as script 16's soil questions, on a different county attribute.
Illinois soybean is overwhelmingly rainfed (statewide, script 29 puts irrigated
share at under 2%), but it is not zero, and it is not spread evenly: the
irrigated acreage concentrates on the Illinois River sand-plain counties. That
is exactly the kind of static county attribute that could explain part of the
county-level residual heterogeneity Section 5.2/5.8 flagged as unaccounted for
by soil alone.

Two questions, not one, for the same reason script 16 kept its three separate:

  Q1  Does irrigation explain the LEVEL of county yield?
      Plausible: irrigated ground is a selection effect (better land gets
      irrigated) as much as a causal one.

  Q2  Does irrigation explain each county's SENSITIVITY to heat and moisture?
      The interaction story this script actually exists to test: an irrigated
      county's yield should respond less to a dry August than a rainfed one's.
      Tested against the county sensitivity coefficients from script 09.

Coverage caveat up front: irrigated_frac_avg comes from only 2 Census years
(2017, 2022) per county, is disclosure-suppressed in 36 of 102 counties (those
rows are coded as 0 rather than missing -- see script 29), and only 102 of the
122 counties script 09 reports on have a value at all. Small numbers throughout.
"""
import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import statsmodels.formula.api as smf
from _cfg import PROC, RES

irr = pd.read_csv(PROC / "irrigation_features.csv", dtype={"fips5": str})
t7 = pd.read_csv(RES / "table7_county_climate_sensitivity.csv", dtype={"fips5": str})

print(f"[30] irrigation covariate: {len(irr)} counties "
      f"({irr.any_suppressed.sum()} with a suppressed irrigated-acreage value in at "
      f"least one census year)")
print(f"[30] statewide (unweighted county mean) irrigated fraction: "
      f"{irr.irrigated_frac_avg.mean()*100:.2f}%")

m = irr.merge(t7, on="fips5", how="inner")
print(f"[30] matched to {len(m)} of {len(t7)} counties in table7 "
      f"({len(t7) - len(m)} have no Census irrigation record at all)")

irr_log = np.log1p(m.irrigated_frac_avg * 100)   # heavy right skew: a handful of
m = m.assign(irrigated_log=irr_log)               # sand-plain counties dominate
m["irrigated_any"] = (m.irrigated_frac_avg > 0).astype(int)

KEY = ["irrigated_log"]


def fit_ols(df, y, X):
    return smf.ols(y + " ~ " + " + ".join(X), data=df).fit()


# ===== Q1: irrigation vs the LEVEL of county yield ============================
q1 = []
for y, lab in [("yield_recent", "county recent-years mean yield (bu/acre)")]:
    if y not in m.columns:
        continue
    mdl = fit_ols(m, y, KEY)
    q1.append(dict(target=lab, n=int(mdl.nobs), r2=float(mdl.rsquared),
                   coef_irrigated_log=float(mdl.params["irrigated_log"]),
                   p_value=float(mdl.pvalues["irrigated_log"])))
if not q1:
    print("\n[30] Q1 skipped: table7 has no yield-level column to test "
          "(this repo carries that test in script 16 instead)")
    Q1 = pd.DataFrame()
else:
    Q1 = pd.DataFrame(q1)
    print("\n[30] Q1  IRRIGATION vs THE LEVEL OF COUNTY YIELD")
    print(Q1.round(4).to_string(index=False))

# ===== Q2: irrigation vs climate SENSITIVITY ===================================
q2 = []
for y, lab in [("beta_moisture_bu_per_sd", "yield response to moisture (bu/SD)"),
               ("beta_heat_bu_per_sd", "yield response to heat (bu/SD)"),
               ("sensitivity_index", "composite sensitivity index")]:
    mdl = fit_ols(m, y, KEY)
    q2.append(dict(target=lab, n=int(mdl.nobs), r2=float(mdl.rsquared),
                   coef_irrigated_log=float(mdl.params["irrigated_log"]),
                   se=float(mdl.bse["irrigated_log"]),
                   p_value=float(mdl.pvalues["irrigated_log"])))
Q2 = pd.DataFrame(q2)
print("\n[30] Q2  IRRIGATION vs CLIMATE SENSITIVITY  (OLS, log1p(irrigated %) )")
print(Q2.round(4).to_string(index=False))

# binary check: does simply having ANY irrigated acreage (vs none reported) move
# the moisture-sensitivity coefficient, independent of how much?
mdl_bin = fit_ols(m, "beta_moisture_bu_per_sd", ["irrigated_any"])
print(f"\n[30] binary check: beta_moisture ~ irrigated_any  "
      f"coef={mdl_bin.params['irrigated_any']:+.4f}  p={mdl_bin.pvalues['irrigated_any']:.4f}  "
      f"({int(m.irrigated_any.sum())} of {len(m)} counties report any irrigated soybean acreage)")

# restricted to counties with a genuinely reported (not suppressed-as-zero) value,
# since the suppression coding could be manufacturing the correlation
clean = m[~m.any_suppressed]
mdl_clean = fit_ols(clean, "beta_moisture_bu_per_sd", KEY)
print(f"\n[30] robustness: same test, counties with NO suppressed irrigated-acreage "
      f"value only ({len(clean)} of {len(m)} counties)  "
      f"coef={mdl_clean.params['irrigated_log']:+.4f}  p={mdl_clean.pvalues['irrigated_log']:.4f}")

if not Q1.empty:
    Q1.round(5).to_csv(RES / "table39_irrigation_explains_level.csv", index=False)
Q2.round(5).to_csv(RES / "table40_irrigation_explains_sensitivity.csv", index=False)
pd.DataFrame([dict(test="binary irrigated_any vs moisture sensitivity",
                   coef=float(mdl_bin.params["irrigated_any"]), p=float(mdl_bin.pvalues["irrigated_any"]),
                   n=int(mdl_bin.nobs)),
              dict(test="log irrigated pct vs moisture sensitivity, unsuppressed counties only",
                   coef=float(mdl_clean.params["irrigated_log"]), p=float(mdl_clean.pvalues["irrigated_log"]),
                   n=int(mdl_clean.nobs))]).to_csv(RES / "table40b_irrigation_robustness.csv", index=False)

json.dump(dict(
    source="results/29_provenance_irrigation.json (NASS Census of Agriculture 2017, 2022)",
    counties_with_irrigation_record=int(len(irr)),
    counties_matched_to_table7=int(len(m)),
    counties_with_any_suppressed_value=int(m.any_suppressed.sum()),
    counties_reporting_any_irrigated_acreage=int(m.irrigated_any.sum()),
    statewide_irrigated_fraction_pct=float(irr.irrigated_frac_avg.mean() * 100),
    q2_note="log1p(irrigated pct) against county climate-sensitivity coefficients from script 09; "
            "heavy right skew handled with a log transform, not because a linear response is expected",
    caveat="irrigated_frac_avg is coded 0, not missing, for counties whose irrigated-acreage line was "
          "disclosure-suppressed; the robustness check drops those counties entirely",
), open(RES / "30_irrigation_config.json", "w"), indent=2)
print("\n[30] wrote table39 (if applicable), table40, table40b, 30_irrigation_config.json")
