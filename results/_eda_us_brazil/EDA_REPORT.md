# Soybean in the United States and Brazil: exploratory comparison

22 states (12 US, 10 Brazilian), 1980-2023. Built by `scripts/36_eda_tables.py` (tables, Flourish files) and
`scripts/37_eda_figures.py` (figures). Every number below is read from the CSVs in this folder.

## 1. Scope and harmonisation

| | United States | Brazil |
| --- | --- | --- |
| Unit | county (1,028 units) | municipio (2,452 units) |
| Unit-years | 37,918 | 64,076 |
| Yield and area | USDA NASS county estimates | IBGE PAM municipal estimates |
| Climate | NOAA nClimDiv, degF and inches | MERRA-2 via NASA POWER, degC and mm |
| Peak-season ("critical") window | July-August | January-February |

What had to be fixed before the two panels could be compared:

1. **Units.** US climate was converted to degC and mm. Yield anomalies are re-expressed as % of each unit's own trend.
2. **Anomalies** are recomputed identically for both countries (deviation from each unit's own 1980-2023 mean).
3. **Window.** Brazilian climate stops at 2023, so all cross-country statistics use 1980-2023.
4. **The "balanced panel" was defined differently.** The repo's US rule requires at least 42 of 44 years, the Brazilian rule
   only 20. One common rule (at least 20 years) is used here: it keeps 910 of 1,028 US units (the repo rule keeps 689)
   and 1,593 of 2,452 Brazilian units (unchanged).

## 2. Types of analysis

| Question | Method | Output |
| --- | --- | --- |
| What data do we have, and how complete? | coverage, panel balance, fill rate | fig 1, `audit_balance.csv` |
| Where are the NAs and why? | attrition funnel, missingness mechanism (late entry, exit, internal gap) | fig 2, `audit_funnel_na.csv` |
| How do levels and spread compare? | distributions, percentiles, skew, robust outliers | fig 3, `state_summary.csv` |
| Potential and its gap | P95 of unit-year yields as an attainable-yield proxy, mean as % of P95 | figs 3-4 |
| How fast are yields rising? | OLS trend on balanced-panel unit means | fig 4 |
| What has climate done? | critical-window warming stripes, trends | fig 5 |
| What do CMIP6 models project? | 8-model ensemble, median and range, sign agreement (AR6 conventions) | figs 6-7 |
| Hazard, exposure, vulnerability | AR6 risk framing; share of unit-years above the historical record | fig 8 |
| Yield response to heat and rain | one regression specification in all 22 states, unit-clustered CI, with and without year effects | fig 9 |
| Raw climate-yield shape | binned medians with IQR | fig 10 |
| Differences between countries | Mann-Whitney U, Cliff's delta, Holm correction (n = 12 vs 10) | `country_tests.csv` |
| Structure | PCA of 10 standardised state features, Spearman correlation | fig 11 |

## 3. Findings

**Data and missingness**
- Raw files hold almost no NA (at most 0.5% of rows). Missing cells are **structural**, not suppression. In Brazil 60% of
  missing cells are late entry (soy had not reached the municipio yet), 30% internal gaps, 10% exit. In the US 50% are
  internal gaps, 34% exits, 16% late entry.
- The median share of the unit x year grid that is filled is 85% in the US and 56% in Brazil. Bahia (9 balanced units) and
  Maranhao (24) are thin samples.

**Potential and growth**
- Yield level, the P95 proxy for potential, mean-as-% of P95 (US 82%, Brazil 80%) and instability do not differ between
  countries (Holm-adjusted p = 1.0 for each).
- Brazil's yields rose faster: 1.97 %/yr against 1.26 %/yr (Holm p = 0.005), a gain of 87% against 60% from the 1980s to the
  2010s (p = 0.027).
- Kansas has the largest gap to its own frontier (mean is 63% of P95); Mato Grosso, Iowa and Ohio the smallest (85-87%).

**Observed and projected climate**
- Observed critical-window warming is significant in 8 of 10 Brazilian states (+0.29 to +0.37 deg C per decade; Parana and
  Rio Grande do Sul are not significant) and in none of the 12 US states. **This may reflect the data source** (station-based nClimDiv vs MERRA-2 reanalysis).
- Under SSP5-8.5, late century, projected warming of the critical window is larger in the US (median +5.5 deg C) than in
  Brazil (+3.4 deg C), Holm p = 0.001, and 94% of US unit-years would exceed the historical record against 53% in
  Brazil. Relative to each state's own interannual variability, warming is similar (4.1 vs 3.7 SD, not significant).
- Precipitation change is small and uncertain: 76 of 88 state-scenario-horizon projections have fewer than 80% of models
  agreeing on the sign.

**Sensitivity**
- Pooled over all units, heat lowers yield by 2.6% per deg C in the US and 0.5% per deg C in Brazil (no year effects). With
  year effects the US effect is larger (4.0%) and Brazil's smaller (0.3%).
- At state level, heat lowers yield significantly in 8 of 12 US and 3 of 10 Brazilian states. **The sign changes when year
  effects are added in 4 of 12 US and 6 of 10 Brazilian states**, so positive heat effects in Minnesota, Michigan and North
  Dakota are specification-dependent and should not be read as benefits (they turn clearly negative with year effects).
  Most Brazilian flips are among coefficients close to zero. Mato Grosso do Sul keeps a positive effect in both
  specifications.
- Rainfall: +6.6% per 100 mm in the US, slightly negative (-0.2%) in Brazil.
- In units running 2 deg C or more above normal, the median yield anomaly is -18% in the US and +5% in Brazil (raw, with no control
  for rainfall).
- The state-level median heat sensitivity differs (US -2.6, Brazil -0.2 %/deg C) but not significantly after Holm
  correction (p = 0.64), because Brazilian states disagree in sign.

## 4. Data issues found along the way

- Climate units differ by country (degF/inches vs degC/mm).
- The balanced-panel rules differ (42 vs 20 years), which would have biased any cross-country comparison.
- The US `is_county_estimate` flag is 99-100% in every state, so it carries no information.
- IBGE yields are rounded to 100 kg/ha, so several Brazilian P95 values tie (3,900 kg/ha).
- Yield sources (NASS vs IBGE), climate sources and peak-season windows all differ between countries.

## 5. What not to conclude

- Differences between countries are **descriptive**, not a controlled experiment.
- P95 is a statistical frontier, not an agronomic yield potential.
- The projections are the historical yield-climate relationship under a changed climate: delta-change method, one run per
  model, no adaptation, cultivar change or CO2 effect. The min-max of 8 models is not an IPCC "likely" range.
- PCA on 22 states and 10 features is exploratory; some features are mechanically linked.
- Figures follow IPCC AR6 conventions (SSP colours, model range with median, 80% sign-agreement rule); they are not
  reproductions of AR6 figures.

## 6. Flourish

The Flourish web app needs your own account, so I could not build the visuals there. `flourish/` holds one CSV per
template, with column mappings in `flourish/README_flourish.md`: scatter/bubble (potential vs instability), line chart or
bar-chart race (yield by year), heatmap (warming stripes; projected warming), range/dot plot (model ranges) and Sankey
(data attrition, one file per country).

## 7. Reproduce

```bash
python scripts/36_eda_tables.py
python scripts/37_eda_figures.py
```
