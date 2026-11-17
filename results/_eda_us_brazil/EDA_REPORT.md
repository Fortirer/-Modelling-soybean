# Soybean in the United States and Brazil: exploratory comparison

22 states (12 US, 10 Brazilian), 1980-2025. Built by `scripts/36_eda_tables.py` (tables, Flourish files) and
`scripts/37_eda_figures.py` (figures). Every number below is read from the CSVs in this folder.

> **Re-run on 16 November 2026.** Brazil's climate was previously matched to yield one season late: IBGE's PAM year is
> the harvest year, and `br_05` had treated it as the planting year. With the corrected alignment the Brazilian
> heat-sensitivity results in section 3 changed completely. The window was also extended from 1980-2023 to 1980-2025,
> with "recent" now meaning 2016-2025.
> See `docs/DADOS_FALTANTES.md`, section 8.

## 1. Scope and harmonisation

| | United States | Brazil |
| --- | --- | --- |
| Unit | county (1,029 units) | municipio (2,488 units) |
| Unit-years | 39,191 | 67,672 |
| Yield and area | USDA NASS county estimates | IBGE PAM municipal estimates |
| Climate | NOAA nClimDiv, degF and inches | MERRA-2 via NASA POWER, degC and mm |
| Peak-season ("critical") window | July-August | January-February |

What had to be fixed before the two panels could be compared:

1. **Units.** US climate was converted to degC and mm. Yield anomalies are re-expressed as % of each unit's own trend.
2. **Anomalies** are recomputed identically for both countries (deviation from each unit's own 1980-2025 mean).
3. **Window.** All cross-country statistics use 1980-2025. Brazilian climate (NASA POWER) starts in 1981, and its 1981
   harvest has a partial season (January-April only). The 2025 US county estimates are less complete than earlier years.
4. **The "balanced panel" was defined differently.** The repo's US rule requires at least 42 of 44 years (1980-2023), the Brazilian rule
   only 20. One common rule (at least 20 years) is used here: it keeps 911 of 1,029 US units (the repo rule keeps 689)
   and 1,673 of 2,488 Brazilian units.

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
- Raw files hold almost no NA (at most 0.5% of rows). Missing cells are **structural**, not suppression. In Brazil 62% of
  missing cells are late entry (soy had not reached the municipio yet), 28% internal gaps, 9% exit. In the US 50% are
  internal gaps, 36% exits, 14% late entry.
- The median share of the unit x year grid that is filled is 83% in the US and 56% in Brazil. Bahia (10 balanced units) and
  Maranhao (27) are thin samples.

**Potential and growth**
- Yield level, the P95 proxy for potential, mean-as-% of P95 (US 81%, Brazil 79%) and instability do not differ between
  countries (Holm-adjusted p = 1.0 for each).
- Brazil's yields rose faster: 1.94 %/yr against 1.25 %/yr (Holm p = 0.008), a gain of 93% against 63% from 1980-89 to
  2016-25 (Holm p = 0.027).
- Kansas has the largest gap to its own frontier (mean is 63% of P95); Iowa, Mato Grosso and Ohio the smallest (86-88%).

**Observed and projected climate**
- Observed critical-window warming is significant in 9 of 10 Brazilian states (+0.28 to +0.44 deg C per decade; only
  Parana is not significant at 5%) and in none of the 12 US states. The two added years matter: January-February of
  2024 and 2025 are among the hottest in this record in most Brazilian states (fig 5), and with the window ending in
  2023 only 6 states were significant. **This may reflect the data source** (station-based nClimDiv vs MERRA-2 reanalysis).
- Under SSP5-8.5, late century, projected warming of the critical window is larger in the US (median +5.5 deg C) than in
  Brazil (+3.4 deg C), Holm p = 0.001, and 94% of US unit-years would exceed the historical record against 53% in
  Brazil (Holm p = 0.002). Relative to each state's own interannual variability, warming is similar (4.1 vs 3.6 SD, not
  significant).
- Precipitation change is small and uncertain: 76 of 88 state-scenario-horizon projections have fewer than 80% of models
  agreeing on the sign.

**Sensitivity**
- Pooled over all units, heat lowers yield by 2.6% per deg C in the US and 5.2% per deg C in Brazil (no year effects). With
  year effects the effects are 4.1% and 5.8%.
- At state level, without year effects, heat lowers yield significantly in 8 of 12 US and 8 of 10 Brazilian states. With
  year effects it does so in all 12 US states and in 7 of 10 Brazilian ones. **No Brazilian state has a significant
  positive heat effect in either specification.** Goias and Bahia show no effect in either; Mato Grosso loses its effect
  once year effects are added.
- The largest Brazilian effects are in Rio Grande do Sul (-6.8% per deg C), Parana (-6.3%) and Mato Grosso do Sul
  (-5.7%), close to the largest US one, Kansas (-6.6%), without year effects.
- **The sign changes when year effects are added in 4 of 12 US states and in no Brazilian state.** The positive heat
  effects in Minnesota, Michigan and North Dakota are specification-dependent and should not be read as benefits (they
  turn clearly negative with year effects).
- Rainfall: +6.6% per 100 mm in the US, +0.6% in Brazil (+1.3% with year effects).
- In units running 2 deg C or more above normal, the median yield anomaly is -18% in the US and -13% in Brazil (raw, with
  no control for rainfall).
- The state-level median heat sensitivity is similar in the two countries (US -2.6, Brazil -2.2 %/deg C; Holm p = 1.0).

## 4. Data issues found along the way

- Climate units differ by country (degF/inches vs degC/mm).
- The balanced-panel rules differ (42 vs 20 years), which would have biased any cross-country comparison.
- The US `is_county_estimate` flag is 99-100% in every state, so it carries no information.
- IBGE yields are rounded to 100 kg/ha, so several Brazilian P95 values tie (3,900 kg/ha).
- Yield sources (NASS vs IBGE), climate sources and peak-season windows all differ between countries.
- Brazil's yield year was misread as the planting year until 16 November 2026, which offset climate by one season and
  hid the heat response. This was the largest data issue in the comparison.

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
