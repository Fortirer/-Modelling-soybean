# Soybean Yield and Climate Variability in Illinois, 1980 to 2025

### A county-level panel analysis with Champaign County as the focal unit

Version 2.0 | 2026-09-20 | Part I: original study, v1.0 of 2026-08-31 (github.com/osperry/soybean-climate-illinois). Part II: extensions, scripts 12 to 27. Data: USDA NASS Quick Stats and Crop Progress, NOAA NCEI nClimDiv, NASA POWER, USDA-NRCS SSURGO, CMIP6 via AWS Open Data, EPA AirData.

> **How to read this version.** Part I is the original study and its analysis has not changed. Part II tests it against independent data and extends it, and in several places corrects it. Where Part II supersedes something in Part I, the sentence says so. The v1.0 report is preserved unchanged in `results/archive/`.

---

## Abstract

**Objective.** Quantify how historical climate variability has been associated with soybean yield across Illinois counties, test whether climate information improves out-of-sample prediction, and, in Part II, test whether the analysis survives being checked against observed crop phenology, soil, daily weather, ozone and CMIP6 scenarios.

### Part I: the original study

### Part II: extensions and independent checks

**Data added.** NASA POWER daily weather (1,639,242 records, 1981-2024); SSURGO soil (83,063 horizon records); CMIP6 monthly output for eight models under SSP2-4.5 and SSP5-8.5; NASS weekly crop progress and condition; EPA ground-level ozone, 1980-2024.

**Main findings.**

- **Soil explains where the good ground is, not what happens in a given year.** Soil explains 82% of the variance in county mean yield and 55% of county climate sensitivity, but adds +0.3% to prediction of the detrended anomaly, which by construction has no county mean left to explain.
- **The crop calendar is not the calendar.** A phenological window replaces July and August. The first version of it, calibrated to dates written from memory, was wrong: modelled planting ran 15.2 days early and thermal-time maturity predicted leaf drop worse than the plain average date. It was recalibrated against the observed NASS record.
- **Observed leaf drop has not advanced, and the model says it should have.** Trend +0.61 ± 0.64 days per decade observed, against −0.78 modelled. Adaptation is already in the record.
- **CMIP6 scenarios give a bracketed, not a pinned-down, answer.** The median climate effect at SSP5-8.5 late century is −8.6 bu/acre, but the eight models span −24.9 to −6.1, and 49% of county-years exceed the observed heat maximum. The CO₂ assumption alone moves the net answer from −8.6 to +6.5 bu/acre.
- **Ozone survives detrending and cannot be separated from heat.** Detrended ozone correlates −0.52 to −0.41 with the yield anomaly but +0.62 to +0.74 with extreme degree days.
- **The model transfers to unseen districts with no measurable loss, and the heat penalty does not differ north to south.** County-level validation of the phenology itself is not possible, because NASS publishes state-level progress only.

**Implications.** Part I stands as an association study. Part II shows that its central variables (extreme heat and soil water) are corroborated by independent farmer condition ratings, that projections built on them are wide and depend on assumptions the data cannot settle (CO₂, adaptation, extrapolation beyond the observed heat range), and that several early results of the extension were wrong and are documented in Appendix A. None of the projections is a forecast.

---

## 1. Introduction

Illinois is consistently among the two largest soybean-producing states in the United States, harvesting roughly 10 million acres annually and producing 600 to 690 million bushels in recent years. Soybean is a rainfed crop across nearly the entire state, which makes yield unusually exposed to growing-season weather and makes Illinois a useful natural laboratory for climate-yield relationships.

The central analytical difficulty is that observed yield is dominated by a technology trend. Illinois state yield rose from 33.5 bu/acre in 1980 to 62.5 in 2025, an increase of roughly 0.65 bu/acre per year driven by cultivar improvement, seed treatment, planting equipment, and agronomic practice. That trend is an order of magnitude larger than any plausible climate signal within the sample, and because temperature also trended over the same period, a model that fails to remove it will attribute technology gains to warming and can return a positive temperature coefficient. Recovering the climate signal therefore requires the trend to be removed first, at the county level, because county trends themselves range from 0.29 to 0.85 bu/acre per year.

### Research questions

1. How has historical climate variability been associated with soybean yield across Illinois counties from 1980 to 2025?
2. Which climate variables have the strongest relationship with yield?
3. Are temperature and precipitation effects linear or nonlinear?
4. Are some counties more climate-sensitive than others?
5. Are extreme and anomaly-based indicators more informative than seasonal averages?
6. Does machine learning improve prediction relative to conventional statistical models and to a trend-only baseline?
7. How does simulated yield respond to warmer and drier conditions?

---

## 2. Data

### 2.1 Production

| Attribute | Value |
|---|---|
| Source | USDA NASS Quick Stats |
| Program | `source_desc = SURVEY`, `Period = YEAR` |
| Geography | `agg_level_desc = COUNTY`, Illinois |
| Domain | `domain_desc = TOTAL` (the only value available at county level) |
| Coverage | 1980 to 2025, 46 years |
| Variables | acres planted, acres harvested, production (bu), yield (bu/acre) |
| Access | Query-tool CSV export, no API key |

Only four variables exist at county level. Value of production and the irrigated versus non-irrigated splits are published at state level and above only.

**A key structural detail.** NASS reports counties suppressed for disclosure in an `OTHER (COMBINED) COUNTIES` bucket, and it publishes **one such bucket per Agricultural Statistics District, not one per state**. In 2019 there are nine, all carrying a blank county ANSI code. The primary key on the raw export is therefore `county_ansi + ag_district_code + year`. Keying on county and year alone silently collapses those rows. The cleaning script asserts uniqueness and drops the 48 aggregate rows.

### 2.2 Climate

| Attribute | Value |
|---|---|
| Source | NOAA NCEI nClimDiv, county-level monthly |
| Files | `climdiv-{pcpn,tmpc,tmax,tmin,pdsi,zndx}cy-v1.0.0-20260806` |
| Layout | Fixed width: state code (cols 1-2, Illinois = 11), county FIPS (3-5), element (6-7), year (8-11), then twelve 7-character monthly values |
| Units | Precipitation inches, temperature °F, Palmer indices dimensionless |
| Coverage | 1980 to 2025, all 102 Illinois counties |

nClimDiv is the ERA5 analogue in this design: an operational reanalysis-style product providing consistent long-record gridded-to-polygon climate. One structural difference matters and is stated plainly here and again in Limitations. **NCEI performs the gridding and polygon aggregation upstream**, so this pipeline executes no area-weighting step of its own. That removes a source of analyst error but also removes a documented methodological choice, and it fixes the temporal resolution at monthly.

County values are genuinely county-specific rather than climate-division clones. In 2012, 96 counties produced 82 distinct August precipitation values and 86 distinct August PDSI values, and within every Agricultural Statistics District the member counties differ. Temperature fields are smoother: the same 96 counties produced only 55 distinct August maximum-temperature values.

### 2.3 Geography

`fips5 = "17" + county_ansi`, joining to Census TIGER. County names in NASS do not match Census spelling (`DU PAGE`, `ST CLAIR`, `JO DAVIESS` against `DuPage`, `St. Clair`, `Jo Daviess`), so all joins use FIPS. County boundary geometry for the choropleth was taken from a public county GeoJSON keyed on the same FIPS codes.

### 2.4 Data quality report

| Check | Result |
|---|---|
| Raw production rows | 4,507 |
| Aggregate (non-county) rows dropped | 48 |
| Duplicate county-year keys after cleaning | 0 |
| Sentinel or unparsed cells | 0 |
| Identity `production_bu / acres_harvested == yield_bu_ac` | 4,459 of 4,459, max residual 0.25 bu/acre |
| `acres_harvested <= acres_planted` violations | 0 |
| Zero-production rows (distinguished from missing) | 0 |
| Climate join completeness | 4,459 of 4,459, zero nulls |
| Panel county totals reconcile to published state totals | Exact, 0.000% error, all 46 years, three measures |

The final reconciliation check is the one that matters most. Internal consistency checks pass even on a file that has silently lost rows; only comparison against an independently published aggregate detects that failure mode.

---

## 3. Methodology

### 3.1 Growing season definition

Illinois soybeans are planted in early to mid May, emerge in late May, are vegetative through June, flower (R1-R2) from late June into July, set pods (R3-R4) in late July, fill seed (R5-R6) through August, mature (R7-R8) in September and are harvested in October.

Yield is determined principally during R3 through R6. The pipeline therefore defines:

- **Growing season**: April through September, planting through maturity
- **Critical window**: July and August, pod set and seed fill

This is an agronomic choice, not a statistical one, and it was fixed before any model was estimated. The empirical results support it: July and August precipitation correlate 0.32 and 0.34 with the yield anomaly while June correlates 0.08 and September 0.02. Part II tests this calendar window against observed crop progress and replaces it with a phenological one (Sections 5.3 and 5.4).

### 3.2 Target variable

```
yield_anom = yield_bu_ac - (a_county + b_county * year)
```

fitted separately within each county by ordinary least squares. County trend slopes range from 0.290 (DuPage) to 0.846 (Piatt) bu/acre per year, so a single pooled detrend would be misspecified.

### 3.3 Feature engineering

Thirty-eight engineered features across five families: seasonal precipitation and temperature aggregates, within-season variability, Palmer drought indices, heat and dry stress proxies, and county-specific anomalies expressed both in natural units and as z-scores against each county's own 1980-2025 climatology. Anomaly standardisation matters because baseline yield spans 18 bu/acre across the state's north-south gradient.

### 3.4 Panel specification

The panel is repeated observations of counties over years, so observations are not independent. Standard errors are clustered on county throughout. Seven specifications were estimated, escalating from pooled OLS to two-way fixed effects, plus alternative targets in logs and raw levels.

### 3.5 Machine learning and leakage control

No random splits are used anywhere. Two validation regimes:

- **Fixed temporal split**: train 1980-2013 (3,089 rows), validate 2014-2018 (437), test 2019-2025 (525)
- **Expanding-window rolling origin**: for each year from 2001 to 2025, train on all prior years and predict that year (2,317 test observations in total)

Random splits are inadmissible here for two reasons. Temporally, they let future information into training. Spatially, counties within a year are strongly correlated through shared weather, so a random split places near-duplicates of test observations into the training set. Blocking on year addresses both.

The comparison of scientific interest is not between algorithms but between **a trend-only baseline** (predict the county trend, that is, anomaly = 0) and **models that use climate**. That contrast tests whether climate information has predictive content at all.

### 3.6 Scenarios

Six perturbation experiments apply uniform shifts to observed climate and re-predict with the fitted model. **These are sensitivity experiments, not climate projections.** They apply no CMIP6 or IPCC pattern, carry no probability information, and hold constant the agronomic adaptation, cultivar change, and planting-date shifts that would accompany any real climate change.

> **Part II replaces these perturbation experiments** with scenarios built from CMIP6 change factors (Section 5.5). The experiments above are retained as sensitivity analyses.

---

## 4. Results

### 4.1 Descriptive and exploratory

Illinois state yield rose from 33.5 bu/acre in 1980 to 62.5 in 2025. The detrended state anomaly has a standard deviation of about 4.2 bu/acre, so roughly 85% of raw yield variation is technology rather than weather.

The three worst years are 2012 (-9.6), 1988 (-8.7) and 2003 (-8.5). The three best are 2018 (+6.8), 2021 (+6.3) and 1985 (+6.1). The downside tail is deeper than the upside, which matters for how the response is specified.

Abandonment carries no signal in Illinois: the gap between acres planted and acres harvested has a median of 0.54% and a maximum of 3.23%. This is a useful null result and distinguishes Illinois from the Plains states.

### 4.2 Climate-yield correlations (Table 3)

Ranked by correlation with the detrended anomaly across all 4,459 county-years:

| Variable | r (detrended) | r (raw yield) | r (Champaign only) |
|---|---|---|---|
| Palmer Z-index, Jul-Aug | **0.490** | 0.311 | 0.453 |
| Jul-Aug precipitation (z-score) | 0.476 | 0.279 | 0.394 |
| August max temperature (anomaly) | **-0.469** | -0.286 | -0.426 |
| August Palmer Z-index (z-score) | 0.468 | 0.236 | 0.444 |
| Jul-Aug precipitation | 0.464 | 0.296 | 0.394 |
| Heat by dryness interaction | -0.463 | -0.265 | -0.448 |

Three findings.

**Detrending roughly doubles every correlation.** The Palmer Z-index moves from 0.311 against raw yield to 0.490 against the anomaly. Climate has no trend and yield does, so the trend acts as pure noise in the raw correlation.

**The Palmer Z-index outperforms raw precipitation.** Z-index is the current-month moisture departure accounting for antecedent soil water. PDSI, which has longer memory, performs worse (0.349 for August) because it carries drought signal from months that no longer affect the crop.

**Anomaly and z-score forms outperform natural units**, confirming that county-relative departures carry more information than absolute levels in a panel spanning a large climatic gradient.

### 4.3 Panel regression (Table 4)

| Specification | n | R² | Adj. R² | RMSE |
|---|---|---|---|---|
| M1 Baseline pooled OLS | 4,051 | 0.254 | 0.253 | 4.63 |
| M2 Quadratic + interaction | 4,051 | 0.361 | 0.360 | 4.28 |
| M3 M2 + county FE | 4,051 | 0.379 | 0.365 | 4.22 |
| **M4 Two-way FE (county + year)** | 4,051 | **0.668** | **0.656** | **3.09** |
| M5 Palmer Z specification | 4,051 | 0.353 | 0.337 | 4.31 |
| M6 Raw yield, two-way FE | 4,051 | 0.857 | 0.853 | 4.32 |
| M7 Log yield, county FE | 4,051 | 0.859 | 0.856 | 0.10 |

Adding the quadratic terms and the interaction lifts R² from 0.254 to 0.361, which is the single largest specification gain and establishes that the relationship is nonlinear. Year fixed effects add a further 0.29, confirming that a large share of yield variation is common statewide shocks.

**M4 climate coefficients, county-clustered standard errors:**

| Term | Coefficient | SE | p | 95% CI |
|---|---|---|---|---|
| Precipitation | -3.978 | 1.322 | 0.003 | [-6.570, -1.387] |
| Precipitation² | -0.0625 | 0.0070 | <0.001 | [-0.0761, -0.0488] |
| Max temperature | 8.770 | 1.390 | <0.001 | [6.045, 11.495] |
| Max temperature² | -0.0581 | 0.0076 | <0.001 | [-0.0729, -0.0433] |
| Precipitation × temperature | 0.0648 | 0.0145 | <0.001 | [0.0364, 0.0931] |

Because the model contains an interaction, individual coefficients are not directly interpretable. Evaluated at sample means (7.73 inches July-August precipitation, 85.5 °F July-August maximum temperature):

| Quantity | Estimate |
|---|---|
| Marginal effect of temperature | **-0.664 bu/acre per °F** |
| Marginal effect of precipitation | **+0.591 bu/acre per inch** |
| Precipitation optimum, at mean temperature | 12.46 inches |
| Temperature optimum, at mean precipitation | 79.78 °F |

**The interaction is the substantive result.** The temperature effect is conditional on moisture:

| Moisture condition | dYield/dTemperature |
|---|---|
| Dry (10th percentile, 4.3 in) | **-0.887 bu/acre per °F** |
| At the mean (7.7 in) | -0.664 |
| Wet (90th percentile, 11.4 in) | **-0.429** |

Warming costs roughly twice as much in dry conditions as in wet. An additive model would systematically understate warming risk. The same pattern appears non-parametrically: mean yield anomaly is +1.44 in cool and wet conditions, +1.45 in hot and wet, -1.17 in cool and dry, and -5.26 in hot and dry. Heat alone is nearly costless; heat with drought is not.

The precipitation response has an interior optimum near 12.5 inches and turns down beyond it. Binned means confirm the shape: the anomaly rises from -6.4 bu/acre in the driest decile to +2.1 at 16 inches, then falls to +1.7 in the wettest decile. The drought penalty is roughly three times the wet-year bonus.

Diagnostics: Breusch-Pagan rejects homoskedasticity for most specifications, which is why all standard errors are clustered. Durbin-Watson for M4 is 1.97, close to the null of no residual autocorrelation.

![Figure 7. Yield anomaly against July-August precipitation](figures/fig07_precipitation_yield.png)

### 4.4 Machine learning (Table 5)

**Expanding-window rolling origin, 2001-2025, 2,317 test observations:**

| Model | RMSE | MAE | R² | Skill vs baseline |
|---|---|---|---|---|
| **Gradient Boosting** | **4.844** | 3.680 | **0.284** | **+15.7%** |
| HistGBM | 4.870 | 3.706 | 0.276 | +15.3% |
| Random Forest | 4.895 | 3.723 | 0.269 | +14.8% |
| Linear Regression | 5.090 | 3.892 | 0.209 | +11.5% |
| Ridge | 5.095 | 3.896 | 0.208 | +11.4% |
| Baseline: trend only | 5.748 | 4.424 | -0.008 | 0.0 |

**Fixed split, test 2019-2025:**

| Model | RMSE | MAE | R² |
|---|---|---|---|
| HistGBM | **3.925** | 3.166 | 0.122 |
| Gradient Boosting | 3.990 | 3.265 | 0.092 |
| Ridge | 4.124 | 3.337 | 0.030 |
| Random Forest | 4.137 | 3.399 | 0.024 |
| Baseline: trend only | 4.895 | 4.119 | **-0.366** |

Two conclusions, and the second is more important than the first.

**Climate information genuinely improves prediction.** Every climate model beats the trend-only baseline in both validation regimes, by 11 to 16% in RMSE. The baseline's negative out-of-sample R² confirms it carries no information about deviations from trend, which is what it should do by construction.

**The gain from algorithm sophistication is modest.** Gradient boosting beats ridge regression by 4.9% in RMSE. Most of the available signal is captured by a penalised linear model. The nonlinearity and interaction that matter are the ones already written into the parametric specification.

![Figure 10. Model performance under expanding-window validation](figures/fig10_model_performance.png)

### 4.5 Feature importance (Table 6)

Permutation importance for gradient boosting, evaluated on held-out years 2019-2025:

| Feature | Importance | SD |
|---|---|---|
| Jul-Aug precipitation | **0.106** | 0.013 |
| Growing-season precipitation | 0.078 | 0.008 |
| August maximum temperature | 0.067 | 0.013 |
| Jul-Aug PDSI | 0.059 | 0.006 |
| Heat by dryness interaction | 0.052 | 0.011 |
| Within-season precipitation variability | 0.035 | 0.004 |
| Within-season temperature variability | 0.029 | 0.011 |
| Jul-Aug maximum temperature | 0.026 | 0.004 |

Moisture terms occupy four of the top five positions. The engineered heat-by-dryness interaction ranks fifth on its own, independent evidence for the interaction found parametrically. Within-season variability terms rank above several seasonal means, indicating that the distribution of weather within the season carries information beyond its total.

These are associational rankings from a predictive model and should not be read as causal effect sizes.

### 4.6 County climate sensitivity (Table 7)

Sensitivity was estimated county by county as the yield-anomaly response to a one-standard-deviation August moisture anomaly.

**Most sensitive:**

| County | District | r (moisture) | β (bu/acre per SD) |
|---|---|---|---|
| CLAY | East Southeast | 0.679 | **3.596** |
| RICHLAND | East Southeast | 0.687 | 3.223 |
| WAYNE | Southeast | **0.693** | 2.987 |
| EDWARDS | Southeast | 0.618 | 2.254 |
| FRANKLIN | Southeast | 0.604 | 2.162 |

**Least sensitive:**

| County | District | r (moisture) | β (bu/acre per SD) |
|---|---|---|---|
| MERCER | Northwest | 0.174 | **0.556** |
| KNOX | West | 0.186 | 0.468 |
| ROCK ISLAND | Northwest | 0.233 | 0.864 |
| BUREAU | Northwest | 0.230 | 1.002 |

**Sensitivity varies more than sevenfold in β and by a factor of four in correlation.** A pooled climate coefficient averages a county where August moisture explains 48% of anomaly variance with one where it explains 3%.

The pattern is geographic and systematic. Southern and southeastern counties on thinner, less water-retentive soils are far more exposed; northern and western counties on deep glacial soils buffer moisture deficits. Two cross-sectional relationships confirm this:

- `r(mean Aug max temperature, moisture sensitivity) = +0.606`. Structurally hotter counties respond more sharply to moisture.
- `r(recent yield level, moisture sensitivity) = -0.512`. **Higher-yielding counties are less climate-exposed.** Advantage compounds: the best ground both yields more and varies less.

![Figure 13. County climate sensitivity to August moisture](figures/fig13_county_climate_sensitivity.png)

### 4.7 Champaign County, the focal unit

| Metric | Champaign | State panel |
|---|---|---|
| Observations | 44 (1980-2023) | 4,459 |
| Mean yield 2015-2025 | 64.3 bu/acre | 58.7 |
| Technology trend | 0.660 bu/acre/yr | 0.627 mean |
| Moisture sensitivity β | +1.740 bu/acre per SD | 0.47 to 3.60 range |
| Sensitivity rank | 53rd of 91 (42nd percentile) | |
| r with Jul-Aug Palmer Z | 0.453 | 0.490 pooled |
| Simulated change under +1 °C, -10% precip | **-0.24 bu/acre (-0.47%)** | -0.73 (-1.62%) mean |

Champaign is a high-yielding, near-median-sensitivity county that is **less exposed than the state average** under the perturbation experiments. Its worst recorded year is 2003 at -13.99 bu/acre below trend, followed by 1988 at -12.25 and 2012 at -11.34.

**Champaign has no 2024 or 2025 observation.** It was suppressed under the recent collapse in NASS county coverage, described in Limitations.

### 4.8 Scenario results (Tables 8a, 8b)

Sensitivity experiments, not projections. Section 5.5 supersedes them for projection purposes.

| Scenario | ΔT | ΔP | Mean Δyield | % of mean yield | P10 | P90 | Counties worse |
|---|---|---|---|---|---|---|---|
| S1 Baseline | 0 | 0 | 0.00 | 0.0% | 0.00 | 0.00 | 0 |
| S2 | +1 °C | 0 | -0.31 | -0.68% | -1.73 | +0.78 | 89 of 91 |
| S3 | 0 | -10% | -0.27 | -0.59% | -1.12 | +0.51 | 88 of 91 |
| **S4** | **+1 °C** | **-10%** | **-0.73** | **-1.62%** | -2.55 | +0.82 | **91 of 91** |
| S5 | +2 °C | 0 | -0.64 | -1.42% | -2.82 | +1.11 | 91 of 91 |
| S6 | +2 °C | -20% | **-2.03** | **-4.48%** | -4.98 | +0.62 | 91 of 91 |

**The combination exceeds the sum of its parts.** S2 alone costs 0.31 bu/acre and S3 alone costs 0.27, summing to 0.58, but S4 costs 0.73. The excess is the interaction, and it is the same mechanism identified in the regression and the feature importance.

Impacts are geographically heterogeneous. Under S4:

| Largest losses | Δ bu/acre | Δ % | | Smallest / positive | Δ bu/acre |
|---|---|---|---|---|---|
| JACKSON (SW) | -1.92 | -5.26% | | LAKE (NE) | +0.20 |
| GREENE (WSW) | -1.68 | -3.52% | | KANE (NE) | +0.19 |
| PULASKI (SW) | -1.62 | -4.31% | | VERMILION (E) | +0.09 |
| WASHINGTON (SW) | -1.53 | -4.17% | | EDGAR (ESE) | +0.07 |

Losses concentrate in the southwest, where baseline yields are already the lowest in the state. The few counties showing small positive responses are in the cool northeast, consistent with those locations sitting below the estimated temperature optimum.

![Figure 17. Simulated yield change under +1 C and -10% precipitation](figures/fig17_scenario_map.png)

### 4.9 Robustness (Table 9)

Thirteen specifications. The estimated marginal effect of temperature at means:

| Check | dY/dT | p (temperature) |
|---|---|---|
| Reference: balanced panel, two-way FE | -0.664 | <0.001 |
| All 102 counties, no balance rule | -0.625 | <0.001 |
| Fully balanced only (28 counties) | -0.552 | <0.001 |
| Trim 1% extreme yield years | -0.519 | <0.001 |
| Trim 2% extreme precipitation years | -0.629 | <0.001 |
| Drop 1988, 2003, 2012 | **-0.334** | <0.001 |
| Early period only (1980-2002) | -0.591 | 0.003 |
| Late period only (2003-2025) | **-0.838** | <0.001 |
| County FE only, no year FE | -0.404 | <0.001 |
| Alternative indicator: growing-season precipitation | -0.658 | <0.001 |
| Target: log yield | -0.019 | <0.001 |
| Target: raw yield | -0.698 | <0.001 |
| Target: yield growth (%) | -2.534 | <0.001 |

**The temperature effect is negative and significant at 5% in all thirteen specifications.** The magnitude is stable between -0.52 and -0.70 across most checks.

Two departures are informative rather than concerning. Dropping the three drought years halves the effect to -0.334, confirming that a substantial share of the estimated relationship is carried by extreme years, which is expected for a nonlinear damage function. And the late period (2003-2025) shows a larger effect (-0.838) than the early period (-0.591), consistent with either increased exposure or the changing county composition of the recent panel; the design cannot separate those.

---

## 5. Extensions and independent checks (Part II)

Every number in this part is read from the results files at build time. The scripts are numbered 12 to 27 and listed in Appendix B.

### 5.1 Data added

| Source | Used for | Script | Access | Coverage |
|---|---|---|---|---|
| NASA POWER daily point API (MERRA-2) | Daily temperature, dewpoint, precipitation, solar radiation | 17 | Free, no key | 1981-2024, 102 county centroids, 1,639,242 records |
| USDA-NRCS SSURGO via Soil Data Access | County soil properties, available water | 14, 15 | Free, no key | 83,063 horizon records, 10,200 map units |
| CMIP6 monthly output, AWS Open Data | Scenario change factors incl. relative humidity | 12 | Anonymous | 8 models, SSP2-4.5 and SSP5-8.5, baseline 1985-2014, horizons 2040-69 and 2070-99 |
| USDA NASS Quick Stats bulk file | Weekly crop progress and condition | 23 | Key-free bulk file, 1.05 GB streamed | Illinois soybean, state level only, 1980-2026 |
| EPA AirData annual concentration by monitor | Ground-level ozone | 22 | Free | 1980-2024, 45 annual files, 18-23 counties with a monitor |

No source needed an API key or a login. The choice of NASA POWER for daily weather was deliberate: it is global, and this analysis is meant to serve as a source domain for Brazilian soybean, where features must be computed identically in both countries.

### 5.2 Soil

Script 14 pulls SSURGO through the public Soil Data Access service: 83,063 horizon records across 10,200 map units and all 102 counties. Script 15 aggregates them to 25 county features over 0-30 cm and 30-100 cm, weighted by horizon overlap, then component percentage, then map-unit acreage. The first version contained an error: horizon water contributions were averaged across rows instead of summed down each profile and then weighted, which made available water 4.35 times too small (Champaign read 39 mm against about 170 mm). It is corrected, and the county mean is now 176 mm.

Soil answers three different questions with three different answers, and reporting them separately matters.

| Question | Outcome explained | R² |
|---|---|---|
| Does soil explain the **level** of county yield? | County mean yield, 1980-2025 | 0.82 |
| Does soil explain **climate sensitivity**? | Composite sensitivity index from script 09 | 0.55 |
|  | Yield response to heat | 0.51 |
| Does soil improve **prediction** of the anomaly? | Expanding-window RMSE, 2001-2025 | +0.3% vs climate alone |

![Figure 22. Soil against county yield level](figures/fig22_soil_vs_yield_level.png)

The last row is arithmetic, not disappointment. The modelling target is the residual of each county's own trend, so its county mean is zero by construction, and a static county attribute has no main effect left to explain. Soil does not say what this year's anomaly will be. It says which counties suffer most when a bad year arrives, which is what a projection needs. Soil alone predicts worse than assuming no anomaly (−2.2% skill).

#### Irrigation

A second static county attribute, checked the same way. Illinois soybean is overwhelmingly rainfed: script 29 pulls county irrigated-acreage from the NASS Census of Agriculture (2017 and 2022, the only two years it is published), and the statewide mean is 1.9% of harvested acres. It is not spread evenly — the irrigated share concentrates on the Illinois River sand-plain counties, up to 43% in the highest county — which makes it a plausible candidate to explain part of the county-level heterogeneity Section 5.8 could not attribute to soil.

It does, a little. Regressed against the script 09 sensitivity coefficients (log of irrigated percentage, 91 counties):

| County sensitivity coefficient | R² | Coefficient | p |
|---|---|---|---|
| yield response to moisture (bu/SD) | 0.067 | −0.265 | 0.013 |
| yield response to heat (bu/SD) | 0.007 | −0.079 | 0.415 |
| composite sensitivity index | 0.003 | −0.016 | 0.631 |

More irrigated counties respond **less** to natural moisture variation (−0.265 per log-point, p = 0.013), which is the expected sign: irrigation buffers a dry August. It says nothing about heat response or the yield level, both statistically indistinguishable from zero. The R² is small (0.067), and the result survives the obvious check: restricted to the 59 counties whose irrigated-acreage figure was never disclosure-suppressed (suppressed values are coded 0 rather than dropped, which could otherwise manufacture the correlation), the coefficient holds (−0.279, p = 0.011). Not built into the scenarios: script 20 applies one pooled moisture response to every county, irrigated or not, so the SSP5-8.5 losses are if anything slightly overstated for the small share of acreage that is irrigated today.

### 5.3 Daily weather and process variables

Monthly means erase the extremes that do the damage. Schlenker and Roberts (2009) show soybean yield rising with temperature to about 30 °C and then falling steeply, with damage tracking the distribution of daily temperature. Script 17 pulls daily NASA POWER for every county centroid. Script 18 derives degree days by single-sine integration (Snyder, 1985), giving GDD between 10 and 30 °C and extreme degree days (EDD) above 30 °C separately, plus vapour pressure deficit and a daily soil water balance. Evapotranspiration is FAO-56 Penman-Monteith, not Hargreaves: Hargreaves uses temperature alone and cannot respond to the humidity change that CMIP6 projects, so an early version that perturbed humidity changed nothing downstream. The water-balance bucket is the SSURGO available water of Section 5.2.

VPD was tried as a regressor and rejected. Entered alongside EDD it took a positive coefficient, which is physiologically backwards, because the two correlate at about +0.9 and cannot be separated. Humidity enters through evapotranspiration and the water balance instead.

**Do the process variables predict better? Mostly no.** Expanding window, rolling origin, 2001-2024, 2,082 test observations:

| Feature set | Features | RMSE | R² | vs calendar |
|---|---|---|---|---|
| Both | 38 | 4.857 | 0.279 | +0.14% |
| Calendar (script 08) | 20 | 4.863 | 0.277 |  |
| Process (script 18) | 18 | 5.273 | 0.150 | −8.43% |

They supply the strongest single predictors, by correlation with the yield anomaly: win hot days −0.496, wb season deficit mm −0.496, win edd −0.487, win vpd max −0.471, against +0.467 for the best calendar variable (pcp critical). **This comparison is confounded.** The process features come from NASA POWER at about half a degree; the calendar features come from nClimDiv county polygons, so part of the gap is data source and not formulation. A clean test needs the calendar features rebuilt from POWER, which has not been done. The case for the phenological window was never hindcast accuracy. It is that it can represent a moving window and a threshold heat response, and a calendar window structurally cannot.

### 5.4 The phenology checked against observation

Script 23 pulls the weekly Illinois soybean progress and condition series from NASS Quick Stats. The Quick Stats API needs a key, so the key-free bulk file (1.05 GB, the whole national crops database) was streamed and filtered from 23.9 million rows to 11,350. **The series are state-level only**: the file holds no district or county progress for Illinois soybean. Planting runs from 1980, blooming, pod setting, leaf drop and harvest from 1981, condition from 1986.

#### What the first check found

The thermal-time thresholds in the first version of the phenology were described as calibrated to NASS norms. They were not: the dates were written from memory and never downloaded, so the stage dates agreed with them by construction and proved nothing. Against the real series (mean day of year, 1981-2024):

| Stage | Written from memory | Observed | Error |
|---|---|---|---|
| Planted (50%) | 20 May | 22 May | −1.7 d |
| Blooming (50%) | 10 July | 16 July | −6.4 d |
| Setting pods (50%) | 28 July | 2 August | −4.6 d |
| Dropping leaves (50%) | about 20 September, called maturity | 20 September | +0.5 d |

NASS has no maturity or full-seed stage. Leaf drop corresponds to roughly R7, and the full-seed date had no source. The thresholds themselves were within about 5% of the observed thermal requirement (GDD from each year's observed planting date: blooming 651, setting pods 883, leaf drop 1504, with a cross-year coefficient of variation of 7.6% to 8.8%). The real faults were elsewhere:

- **Modelled planting ran 15.2 days early** and tracked real planting at r = 0.18, because farmers plant when fields are workable, not when a running temperature mean crosses a threshold.
- **Thermal time predicts late-season timing worse than the average date.** Given observed planting it predicts flowering (r = 0.86, RMSE 4.1 days) and pod set (r = 0.83, RMSE 4.6) well, but leaf drop with an RMSE of **19.5 days against an observed sd of 4.8**, a skill of −305% against guessing the mean date. Soybean is a photoperiod-sensitive short-day plant, so maturity is set partly by day length, which a thermal-time model lacks. That is agronomic background rather than something tested here, but it fits the data.
- **The observed yield window barely varies.** The interval from pod setting to leaf drop has a standard deviation of only 3.5 days.

#### What was changed

Planting is anchored to the observed mean: a 19 °C seven-day-mean threshold gives a bias of −1.4 days where the old 15 °C gave −15.2, and improves year-to-year skill (r = 0.45 against 0.26). It is a statistical device, not a physiological threshold. The R1, R3 and R7 thresholds are the observed medians above. Both ends of the yield window are regressions on the observed pod-setting and leaf-drop dates, moved by a county-relative anomaly.

Thermal-time R7 was tried first and abandoned. Under the corrected, later planting it was never reached in 15.3% of county-years, and dropping them was not random: it skewed the surviving planting mean four days early. Four always-defined drivers were compared for predicting observed leaf drop, leave-one-out over 44 years:

| Driver | RMSE (days) | Skill vs the mean date |
|---|---|---|
| 0 climatology | 5.42 | −2% |
| D1 thermal R7 anomaly (imputed) | 4.72 | 11% |
| D2 thermal R3 anomaly  [default] | 4.77 | 10% |
| D3 GDD planting -> day 250 | 4.77 | 10% |
| D4 GDD 1 May -> 15 Sep [alternative] | 4.71 | 11% |

Every driver beats the plain average by about the same modest margin, so **the record cannot choose between them**, and the scenarios run two. They agree on the sign of the window-length response, which is the opposite of what the first version reported: warm seasons advance pod setting more than they advance maturity, so the window gets slightly **longer**.

| Driver | Pod-set slope | Leaf-drop slope | Window-length slope | Out-of-sample skill |
|---|---|---|---|---|
| R3 anomaly (days) | +0.49 ± 0.09 | +0.27 ± 0.09 | **−0.22 ± 0.06**, p < 0.001 | 10% |
| GDD, 1 May to 15 Sept | −0.030 ± 0.007 | −0.021 ± 0.006 | **+0.0097 ± 0.0049**, p = 0.055 | 0% |

Read this as small and weakly supported: only the R3 driver has real out-of-sample skill for window length.

#### Where it stands after recalibration

| Observed | Model | Bias | RMSE | Year-to-year r | Trend observed | Trend model | Gap |
|---|---|---|---|---|---|---|---|
| planted | temperature rule | −1.4 d | 9.6 d | 0.45 | −1.69 ± 1.15 | −2.24 | 0.4 SE |
| blooming | thermal R1 | −1.6 d | 6.4 d | 0.62 | −0.54 ± 0.87 | −3.17 | 2.3 SE |
| pods | thermal R3 | −0.8 d | 6.0 d | 0.66 | −0.98 ± 0.72 | −3.53 | 2.3 SE |
| pods | window start* | 0.0 d | 4.4 d | 0.66 | −0.98 ± 0.72 | −1.73 | 0.9 SE |
| leaves | window end* | 0.0 d | 4.6 d | 0.49 | 0.61 ± 0.64 | −0.78 | 2.1 SE |

Trends in days per decade, 1981-2024. *These two are fitted to the same observations, so their bias and RMSE are in-sample and agreement on mean dates is by construction. What is not by construction is the year-to-year correlation and the trends. **The planting trend is reproduced without being fitted. The flowering and pod-set trends are not**: the model advances them about 2.3 standard errors faster than observed, and even the empirical window end trends earlier (−0.8) where leaf drop actually moved slightly later (+0.6 ± 0.6). Interannual slopes overstate the response over decades. The real system adapted through planting date and variety, and a fixed rule contains none of that.

![Figure 32. The phenology against what NASS observed](figures/fig32_phenology_validation.png)

**Farmers' assessment corroborates the stress variables.** August good-plus-excellent condition ratings (39 years) correlate +0.66 with the state yield anomaly, −0.69 with extreme degree days, +0.51 with minimum soil water fraction and +0.28 with window precipitation.

### 5.5 CMIP6 scenarios on the calibrated window

Script 12 pulls CMIP6 monthly output from the AWS Open Data registry for eight models (ACCESS-ESM1-5, CanESM5, EC-Earth3, GFDL-ESM4, INM-CM5-0, MIROC6, MPI-ESM1-2-LR, MRI-ESM2-0) under SSP2-4.5 and SSP5-8.5. Raw model output is never fed to the yield model, because it carries systematic bias. Instead each model's change between a 1985-2014 baseline and the target horizon is applied to the observed record: additively for temperature and relative humidity, multiplicatively for precipitation, interpolated to all county centroids. Script 20 applies the deltas to the daily record and recomputes the whole phenology through the same module script 18 uses on observed weather. Scenario windows are measured against the observed-climate baseline, otherwise warming would cancel itself out of the anomaly.

The parametric estimator is the Schlenker-Roberts specification with EDD entering linearly, so the nonlinearity lives in the degree-day accounting and extrapolation is a straight line in a variable with a physical threshold, not a fitted curve in raw temperature. The two-estimator design exists because boosted trees predict a constant outside their training range: the first scenario script (script 13, retained in Part I's lineage) returned its **smallest** loss (−0.17 bu/acre) for its **hottest** scenario, an artefact of that saturation, and a quadratic estimator gave −8.70.

#### What warming does to the calendar

| Scenario | Horizon | Δ Tmax Jul-Aug | Planting | R3 | Window end | Window length | Extreme degree days | Beyond record |
|---|---|---|---|---|---|---|---|---|
| SSP2-4.5 | 2040-69 | +2.54 °C | −7.7 d | −13.8 d | −3.7 d | +3.1 d | ×2.9 | 9% |
| SSP2-4.5 | 2070-99 | +3.08 °C | −10.2 d | −17.7 d | −4.7 d | +4.0 d | ×3.5 | 13% |
| SSP5-8.5 | 2040-69 | +3.04 °C | −10.1 d | −17.5 d | −4.7 d | +3.9 d | ×3.6 | 14% |
| SSP5-8.5 | 2070-99 | +5.44 °C | −14.6 d | −26.1 d | −7.0 d | +5.9 d | ×7.3 | 49% |

Pod setting advances up to 26 days and maturity up to 7, so the window lengthens by 3 to 6 days and accumulates more hot days. "Beyond record" is the share of county-years whose season EDD exceeds the observed maximum.

![Figure 26. What warming does to the calibrated window](figures/fig26_window_response.png)

#### The climate effect, and the range behind it

| Scenario | Horizon | Median, R3 driver | Range across 8 models | Median, GDD driver | Boosted trees |
|---|---|---|---|---|---|
| SSP2-4.5 | 2040-69 | −1.48 | −8.17 to −0.48 | −1.38 | +0.34 |
| SSP2-4.5 | 2070-99 | −2.04 | −8.91 to −0.94 | −1.95 | +0.79 |
| SSP5-8.5 | 2040-69 | −2.39 | −10.40 to −0.71 | −2.25 | +0.84 |
| SSP5-8.5 | 2070-99 | −8.56 | −24.89 to −6.07 | −7.99 | −0.36 |

Bu/acre. **The median alone should not be quoted.** Under SSP5-8.5 late century the eight models span a fourfold range (−24.9 to −6.1), and the worst comes with extreme degree days far outside anything in the 1981-2024 record. The two window drivers give medians within 0.6 bu/acre of each other in every scenario, so the choice the record could not make does not matter for yield. The losses are larger than in the earlier version that let thermal time end the window, because with the window no longer shortening, warming buys more hot days inside it.

#### CO₂ changes the sign

Soybean is a C3 legume and the most CO₂-responsive major crop; SoyFACE sits in Champaign County. The response is applied as an explicit layer with three variants (none; a logarithmic curve scaled to about +15% seed yield at 550 ppm; the same curve capped at 550 ppm), calibrated against the FACE meta-analysis of Ainsworth and Long (2005), and it is an assumption, not a result.

| Scenario | Horizon | Climate | No CO₂ | Saturating | FACE |
|---|---|---|---|---|---|
| SSP2-4.5 | 2040-69 | −1.48 | −1.48 | +4.02 | +4.02 |
| SSP2-4.5 | 2070-99 | −2.04 | −2.04 | +4.76 | +5.67 |
| SSP5-8.5 | 2040-69 | −2.39 | −2.39 | +4.41 | +5.32 |
| SSP5-8.5 | 2070-99 | −8.56 | −8.56 | −1.76 | +6.50 |

![Figure 28. Three CO₂ assumptions](figures/fig28_co2_assumption_range.png)

Under SSP5-8.5 late century the net answer runs from −8.6 to +6.5 bu/acre on the CO₂ assumption alone. The saturating variant, the more defensible non-zero option because the FACE curve is extrapolated to 890 ppm far beyond its data, gives a **net loss** (−1.8). Whether climate change is bad for Illinois soybean cannot be answered from this pipeline without committing to a CO₂ response, and it does not know one.

#### What the scenarios do not include

- **Adaptation.** The observed record shows earlier planting and no advance in maturity. The window slopes are interannual estimates at today's level of adaptation, extrapolated far beyond it, and the model's flowering and pod-set trends already overshoot observation by about 2.3 standard errors. **The losses above are probably too large for that reason.**
- **Extrapolation of EDD.** In the hottest scenario about 49% of county-years lie beyond the observed maximum, where the linear term is an assumption.
- **The CO₂ response is a flat multiplier**, though FACE shows it shrinks under heat and interacts with drought, and the concentrations used are round numbers, not the published CMIP6 series.
- **Ozone**, whose confounding with heat cannot be separated here (Section 5.7).
- **The scenario set.** Two pathways were run. SSP5-8.5 is now widely contested as a plausible baseline, and the full ScenarioMIP set adds SSP1-2.6 and SSP3-7.0, which were not run.

### 5.6 Adaptation: what the grower can do, and what this model cannot say

Every scenario assumes a grower changes nothing. Script 21 asks what a longer maturity group does. It runs on thermal-time maturity on purpose, because its frost arithmetic needs a thermal-time R8, and that is the quantity Section 5.4 showed to be unreliable for late-season timing, so **its conclusions inherit that weakness**.

| Climate | Longest viable MG | Frost margin at MG 3.5 | Mature before frost at MG 3.5 | Seed fill at MG 3.5 | at longest |
|---|---|---|---|---|---|
| Today | 2.5 | 45 d | 84% | 24.5 d | 21.4 d |
| SSP2-4.5 | 2040-69 | 5.0+ | 74 d | 99% | 19.4 d | 22.4 d |
| SSP2-4.5 | 2070-99 | 5.0+ | 81 d | 100% | 18.8 d | 21.3 d |
| SSP5-8.5 | 2040-69 | 5.0+ | 81 d | 100% | 18.6 d | 21.1 d |
| SSP5-8.5 | 2070-99 | 5.0+ | 107 d | 99% | 17.0 d | 19.0 d |

"Longest viable" is the longest group maturing before the killing frost in 90% of years; values of 5.0 are censored at the top of the tested range. The qualitative conclusion holds: under any scenario frost stops binding and even MG 5.0 matures in almost every year. **A result reported earlier does not survive**: with corrected planting the frost constraint binds at MG 2.5 today, not 3.5, so the earlier claim that it matched what Illinois growers plant, which was never sourced, is withdrawn.

**No maturity group is recommended, and the reason has been corrected.** Predicted yield across MG 2.0 to 5.0 at today's climate is +0.08, +0.04, +0.02, −0.04, −0.08, −0.13, −0.24: nearly flat. It used to rise a clean 1.7 bu/acre per half group. Both were artefacts of one defect. Under the thermal end rule the season length is defined by the R6 threshold, so `season_gdd` was constant by construction (sd 4.25 GDD around 1,396), the coefficient was fitted to discretisation noise, and the earlier explanation, that it was identified from seasons varying at one maturity group, was wrong. The phenological consequences of a variety choice are computable. Converting them into a yield optimum needs a model that carries yield potential, which is the argument Peng et al. (2020) make for process-based crop models.

### 5.7 Ozone

Midwest soybean is suppressed by roughly 10% under current tropospheric ozone, and at SoyFACE elevated ozone cost 10 ± 11% at 370 ppm CO₂ but only 5 ± 4% at 550 ppm, so CO₂ partly protects the crop. Before building anything, the question that ended the soil work was asked: does ozone survive detrending? The modelling target is the residual of a county trend, so a monotone ozone decline is absorbed. Script 22 uses the EPA annual monitor summaries for Illinois, 1980-2024, covering 18 to 23 of 102 counties.

| Metric | Trend explains | Detrended sd | r with anomaly (44 yr) | Coefficient, bu/acre per ppb | p | ΔR² |
|---|---|---|---|---|---|---|
| 4th-highest 8-h value | 38% | 6.0 ppb | −0.41 | −0.046 | 0.64 | 0.002 |
| 90th-percentile 8-h value | 34% | 4.3 ppb | −0.52 | −0.156 | 0.24 | 0.008 |
| annual mean 8-h value | 0% | 2.4 ppb | −0.48 | −0.139 | 0.57 | 0.002 |

**It does survive detrending, unlike soil**: the trend explains only about a third of the peak metrics, and the correlation with the yield anomaly strengthens once the trend is removed. **But it is not separable from heat and water.** Detrended ozone correlates +0.62 to +0.74 with extreme degree days and −0.57 to −0.46 with the water balance, and adds at most 0.008 to R². A year-level regression with no county replication gives p between 0.67 and 0.98.

![Figure 31. Ozone screen](figures/fig31_ozone_screen.png)

**A null here does not mean ozone does nothing.** The detectable-effect floor is about 0.21 bu/acre per ppb, and the literature implies roughly 0.13 to 0.38 from two rough anchors, so the range straddles the floor. The consequence runs the other way: because ozone tracks heat and drought, part of what the fitted EDD and water coefficients measure may be ozone damage, and part of the measured FACE benefit is ozone protection and not fertilisation. This cannot be tested with annual state-level data. It would take county-varying growing-season exposure (AOT40 or W126) from the hourly files, and an ozone-explicit process crop model.

### 5.8 County-level validation, as far as the data allow

**What cannot be done.** County-level validation of the phenology is not possible. NASS publishes Illinois soybean progress at state level only, and every finer source that could stand in for it needs an Earthdata login or tens of gigabytes. The county dimension of the phenology therefore rests on an assumption nothing here can confirm: that every county's yield window sits on the same dates, with only year-to-year anomalies varying by county.

**What can be done.** Counties do have observed yields, so everything downstream of the phenology can be validated at county level, and the exposed assumption can be tested indirectly through yield. Script 26 does four things.

#### A. Transfer to unseen districts

Each of the nine crop-reporting districts is predicted from a model trained on the other eight and only earlier years. This is strictly harder than the expanding-window test, where the county being predicted was in the training set in every earlier year. Leaving a district out while keeping the same years elsewhere would leak the year's shared weather shock, so the temporal restriction is kept.

| Features | Holdout | RMSE | Skill vs no anomaly |
|---|---|---|---|
| calendar | none (script 19) | 4.863 | 15.4% |
| calendar | district held out | 4.864 | 15.4% |
| process | none (script 19) | 5.273 | 8.2% |
| process | district held out | 5.328 | 7.3% |
| both | none (script 19) | 4.856 | 15.5% |
| both | district held out | 4.878 | 15.1% |

**The calendar model loses nothing** (4.863 against 4.864), the process model loses 1.0%, and district-by-district the change runs from −1.9% to +2.2%. The yield-climate relationship transfers across Illinois. Two caveats bound this: adjacent districts share weather, so a held-out district is never far from training data, and nine spatial units is a small number.

#### B. Do the errors line up north to south?

County-mean residuals fall with latitude: slope −0.143 bu/acre per degree (r = −0.40, p < 0.01) under the expanding window and −0.184 under district holdout, across 91 counties. Over the 5.3-degree span that is about 0.8 bu/acre against a typical RMSE near 5, so the structure is statistically clear and small. Mean residual by tercile: south −0.83, central −0.68, north −1.19. The model over-predicts everywhere in 2001-2024, probably a property of the linear detrend, and over-predicts most in the north.

#### C. The uniform-window assumption

The windows were rebuilt with the north-south gradient in thermal time retained (state-relative anomalies), which moves the northern window 8.6 days later at the start and 4.6 at the end, and county yield prediction was compared.

| Windows | RMSE | Skill | Start, north minus south | End, north minus south |
|---|---|---|---|---|
| county-relative (uniform window, default) | 5.273 | 8.2% | 0.0 d | 0.0 d |
| county-relative + latitude as a feature (control) | 5.321 | 7.4% | 0.0 d | 0.0 d |
| state-relative (north-south gradient retained) | 5.194 | 9.6% | 8.6 d | 4.6 d |

Retaining the gradient improves RMSE by 1.44%, but the paired comparison does not establish it: it is better in 14 of 24 test years, with a bootstrap 95% interval over years of −4.6% to +1.5%, which **includes zero**. **Yield cannot reliably discriminate between the two window designs.** A control shows the difference is not simply latitude leaking into the features: adding latitude to the uniform-window features makes prediction slightly worse (+0.9%), not better. The uniform-window assumption is therefore neither confirmed nor refuted; its error, if any, is below what county yields can detect.

#### D. Does the heat penalty differ by latitude?

The scenarios apply one pooled coefficient to every county. Estimated together in one model, with county fixed effects and errors clustered by county, the three tercile heat slopes are indistinguishable (Wald p = 0.35):

| Latitude tercile | Counties | Mean season EDD | Heat slope, one model | Heat slope, fitted separately | Water coefficient, fitted separately |
|---|---|---|---|---|---|
| south | 31 | 29 | −0.121 ± 0.006 | −0.090 | 11.7 |
| central | 30 | 25 | −0.110 ± 0.005 | −0.119 | 3.6 |
| north | 30 | 16 | −0.120 ± 0.010 | −0.127 | 3.0 |

The separately fitted heat slopes look different, but that difference is produced by the water and precipitation terms, whose coefficients vary by a factor of about four across terciles. Fitted together with shared terms the heat slopes agree, so separate fits **overstated** heterogeneity in the heat penalty. The water response, by contrast, is stronger in the south, consistent with the soil result of Section 5.2. The pooled heat coefficient the scenarios use is supported.

![Figure 33. County-level validation](figures/fig33_county_validation.png)

### 5.9 What the literature audit changed

The analysis was checked against published work, not recollection. Four things held: the 30 °C soybean threshold is Schlenker and Roberts' own figure; the CO₂ curve reproduces both the SoyFACE measurement (2.5 kg/ha/ppm from 373 to 550 ppm) and the Ainsworth and Long meta-analytic +24% at 689 ppm; warming losses arise mainly through a shortened growing season in the published attribution work; and the recommendation to model maturity-group adaptation with a process-based crop model is the standard one. Three things changed.

- **Humidity had been assumed away.** At 2 °C of warming the yield loss attributable to the associated VPD rise exceeds the loss from warming itself in published attribution work, and CMIP6 projects relative humidity declining over North America. Script 12 now pulls it: July-August RH falls by roughly 3 to 5 percentage points across the scenarios.
- **Evapotranspiration could not see humidity**, so projecting it changed nothing downstream. FAO-56 Penman-Monteith replaced Hargreaves.
- **The water balance was missing from the specification.** The first humidity fix returned a climate effect identical to four decimal places, because the specification read no water-balance variable. It was caught only by comparing against the previous run.

The one item this audit found and this analysis cannot resolve is ozone (Section 5.7).

---

## 6. Discussion

### 6.1 Mechanism

The results describe a coherent agronomic mechanism. Damage concentrates in July and August, the pod set and seed fill window, and is essentially absent in June and September. It operates through moisture more than heat, and heat matters mainly by amplifying moisture stress, which is consistent with the physiology of pod abortion and reduced seed fill under combined high vapour pressure deficit and low soil water. The precipitation response saturates and reverses, consistent with waterlogging, disease pressure and nitrogen loss at the wet extreme.

The county-level sensitivity gradient tracks soil water-holding capacity rather than climate exposure per se (Part II tests this directly in Section 5.2). Southern Illinois receives comparable rainfall to the north but has thinner, less retentive soils, so the same deficit translates into more stress.

### 6.2 What the evidence supports and what it does not

The design is observational panel data. County and year fixed effects absorb time-invariant county characteristics and statewide annual shocks, which removes large classes of confounding, but they do not remove county-specific time-varying factors: differential technology adoption, drainage tile installation, cultivar turnover, pest and disease pressure, or local land-use change.

The correct statement of the finding is therefore: **higher July-August temperatures and lower July-August moisture were statistically associated with lower soybean yield after controlling for county and year fixed effects, and this association is robust across thirteen specifications.** It is not: temperature caused yield to decline.

### 6.3 The 2003 anomaly, and a hypothesis that fails its test

One year resists climate explanation entirely. Decomposing the climate model's predictions by year, 1988 is explained to 88% and 2012 to 41%, but **2003 is explained to only 15%**. At a mean residual of **-3.43 bu/acre it is the largest unexplained shortfall in the record, rank 1 of 46 years.** Statewide August PDSI in 2003 was slightly positive and precipitation near normal, yet yield fell 8.5 bu/acre below trend. 2003 contributed 14 of the 39 observations exceeding three standard deviations in the entire panel.

The damage was regionally concentrated: Northwest Illinois lost 18.3 bu/acre while East district lost 15.1 with a positive Palmer Z-index.

**The obvious explanation was tested and does not hold.** 2003 is a documented severe soybean aphid outbreak year in the North Central region, with populations exceeding 1,000 per plant and 40% yield loss recorded at those densities (Ragsdale et al., *Journal of Integrated Pest Management*, 2012). The soybean aphid overwinters as eggs on common buckthorn, *Rhamnus cathartica*, which is concentrated **north of 41 degrees latitude** at densities above 10,000 per acre (Tilmon et al., *Journal of Integrated Pest Management*, 2011). Illinois straddles that line, spanning 37.2 to 42.5 degrees, which makes the hypothesis falsifiable against this panel. Five tests were run.

| Test | Result | Interpretation |
|---|---|---|
| Raw 2003 anomaly against county latitude | r = -0.775 | Strong northern concentration, consistent with the hypothesis |
| Model **residual** against latitude, 2003 | r = -0.124 | The gradient is climate, not the unexplained part |
| Rank of 2003 among 46 years by absolute latitude-residual correlation | **33 of 46** | Unremarkable |
| North (>= 41 N) minus South residual gap, 2003 | **+1.72** | **Wrong sign.** The north performed better once climate is removed |
| Same raw gradient in 1988, before the aphid existed in North America | r = -0.655 | A northern gradient in a bad year is not diagnostic |
| Aphid-era shift in the north-south residual gap, pre- versus post-2000 | Welch t = 0.205, **p = 0.84** | No detectable effect |

The northern concentration in 2003 is real, but it is **fully accounted for by climate**. Northwestern Illinois recorded a genuine August moisture deficit that year (district mean Palmer Z-index -2.60). What remains unexplained after the climate model is spatially uniform, which is the opposite of the signature a northern-origin pest would leave. The two other documented outbreak years behave inconsistently as well: 2005 shows a northern residual skew of -1.77, which is in the predicted direction, while 2001 shows -0.82 and 2003 shows the wrong sign entirely. None of the three ranks among the five most northern-skewed years on record, which are 1996, 2000, 2002, 2007 and 1982.

The finding is therefore narrower than a pest attribution and, in a way, more useful: **2003 is the largest unexplained shortfall in 46 years, and the most plausible candidate explanation does not match its geography.** The cause remains open. A definitive test would require county-level aphid scouting records or insecticide application data from the 2003 season, neither of which is in this dataset.

This is also a caution about the class of explanation. A documented event that coincides in time with an anomaly, and appears to match its geography, can still fail once the climate signal is removed from that geography. The raw spatial pattern looked like confirmation. It was not.

Supporting output: `results/table10_aphid_hypothesis_test.csv` and `results/12_aphid_hypothesis_test.json`.

### 6.4 Comparison with expectations from the literature

The estimated marginal effect of -0.66 bu/acre per °F, the nonlinear precipitation optimum, the dominance of the reproductive window, and the heat-moisture interaction are all qualitatively consistent with the published US crop-climate literature. The finding that penalised linear regression captures most of the signal available to gradient boosting is also consistent with work reporting that well-specified parametric damage functions are hard to beat when the functional form is known.

---

## 7. Limitations

**Some limitations of Part I were addressed by Part II; the rest stand.** Monthly resolution (which could not resolve frost or daily extremes) and the absence of vapour pressure deficit were the largest gaps of v1.0, and Section 5.3 addresses both, at the cost of a coarser 0.5-degree source. The statement that scenarios use no CMIP6 pattern is superseded by Section 5.5, whose own limitations follow.

**Limitations of the extension**

- **Phenology is validated at state level only.** NASS publishes nothing finer, and the county-relative anomaly design means every county's average window sits on the same dates, surely wrong for a state spanning five degrees of latitude. County yield cannot discriminate between a uniform and a gradient window (Section 5.8), so the assumption is unresolved, not confirmed.
- **The trends are overstated.** The model's flowering and pod-set trends run about 2.3 standard errors steeper than observed, because interannual slopes fitted at today's level of adaptation are extrapolated over decades in which the real crop adapted. The scenario losses are probably too large for that reason.
- **No adaptation is modelled.** Earlier planting and variety change are visible in the observed record and absent from the scenarios. The maturity-group analysis of Section 5.6 rests on thermal-time maturity, which does not predict late-season timing, and cannot yield an optimum without a crop model carrying yield potential.
- **Extrapolation beyond the observed heat range.** Up to 49% of county-years in the hottest scenario lie beyond the observed maximum EDD, where the linear term is an assumption and the eight models span a fourfold range.
- **The CO₂ layer is an assumption.** It is a flat multiplier calibrated to FACE, applied with rounded concentrations, and it does not shrink under heat or interact with drought as the experimental record shows it does.
- **Ozone cannot be separated from heat.** Part of the fitted heat and water response may be ozone damage, and part of the FACE benefit ozone protection. The screen used annual state-level data from urban-biased monitors covering under a quarter of counties.
- **Two scenarios only.** SSP2-4.5 and SSP5-8.5. SSP5-8.5 is contested as a plausible baseline, and SSP1-2.6 and SSP3-7.0 were not run.
- **Eight models, one realisation each.** Internal variability is not sampled, and monthly means cannot change within-month extremes or wet-day frequency.
- **The process-versus-calendar comparison is confounded** by data source (POWER against nClimDiv).
- **Soil is static and aggregated** to county means, and explains where the good ground is, not the timing of a bad year.

**Limitations of Part I that stand**

- **No spatial aggregation step is executed** in the original climate data: NCEI performs the gridding upstream, so the pipeline inherits the weighting method.
- **Snow is not available** in nClimDiv.
- **County coverage collapses after 2018**, from 102 counties reporting in 2000 to 62 in 2025, with survival not random.
- **Confounders are not controlled**: cultivar turnover, drainage, fertiliser, pest pressure, machinery, price and policy.
- **No causal identification.** All estimates are associations.
- **Machine-learning importance is not causal.**
- **Champaign is one county in a panel**, and its 44 observations do not support independent estimation.

---

## 8. Conclusions

**1. Is climate variability associated with soybean yield?** Yes, robustly. The two-way fixed-effects model explains 66.8% of detrended yield variance, and the temperature effect is negative and significant at 5% in all thirteen robustness specifications, with a stable magnitude near -0.6 bu/acre per °F.

**2. Which variables matter most?** July-August moisture, best measured by the Palmer Z-index (r = 0.490) rather than raw precipitation (0.464) or PDSI (0.349). August maximum temperature follows (-0.469). Timing dominates magnitude: June precipitation correlates 0.08 and September 0.02, while August correlates 0.34. Anomaly and z-score forms beat natural units.

**3. Are relationships nonlinear?** Yes, decisively. Adding quadratic terms and an interaction raises R² from 0.254 to 0.361, the largest single specification gain. Precipitation has an interior optimum near 12.5 inches over July-August with the response reversing beyond it, and the drought penalty is roughly three times the wet-year bonus. Crucially, the temperature effect is conditional on moisture, at -0.89 bu/acre per °F in dry conditions against -0.43 in wet.

**4. Which counties are most vulnerable?** Sensitivity varies more than sevenfold, from 0.47 bu/acre per standard deviation of moisture in Mercer County to 3.60 in Clay County. Vulnerability concentrates in the southern and southeastern districts and correlates negatively with baseline yield (-0.512), so exposure is highest where the buffer is thinnest. Champaign sits at the 42nd percentile, less exposed than the state average.

**5. Does climate improve prediction?** Yes. Climate models beat a trend-only baseline by 15.7% in RMSE under expanding-window validation and by 19.8% under the fixed 2019-2025 test split. But the increment from algorithm sophistication is small: gradient boosting beats ridge regression by only 4.9%, so most of the signal is linear once the correct nonlinear terms are specified.

**5b. Can the largest anomaly be attributed?** No. 2003 is the largest unexplained shortfall in the record at -3.43 bu/acre, rank 1 of 46. The documented 2003 soybean aphid outbreak was tested as a candidate using the buckthorn 41-degree-latitude threshold and **rejected**: the northern concentration is fully explained by climate, the residual carries no latitude gradient (r = -0.124), the north-south residual gap has the wrong sign (+1.72), and there is no aphid-era shift (p = 0.84). The cause remains open.

**6. Are results robust?** Yes. The sign and significance of the temperature effect survive all thirteen checks, including dropping the balance rule, trimming extreme years, splitting the sample by period, changing the target to logs, levels and growth rates, and substituting alternative climate indicators. Removing 1988, 2003 and 2012 halves the magnitude, which confirms that extreme years carry a disproportionate share of a nonlinear damage function.

**7. What do the scenarios imply?** Under +1 °C with a 10% precipitation reduction, mean simulated yield falls 0.73 bu/acre (1.6%) and all 91 panel counties decline. Under +2 °C with a 20% reduction, the loss is 2.03 bu/acre (4.5%). The combination consistently exceeds the sum of the separate perturbations, which is the interaction expressing itself. Losses concentrate in the already-lowest-yielding southwest. **These are sensitivity experiments and carry no information about the likelihood of any future climate state.**

**Part II conclusions**

**8. Does the analysis survive independent checks?** In part. The heat and water variables at its centre are corroborated by farmers' own condition ratings, and the planting trend is reproduced without being fitted. The flowering and pod-set trends are not, and observed leaf drop has not advanced as the model implies. Adaptation is in the record and not in the model.

**9. What do CMIP6-based projections say?** They bracket the answer without pinning it down. The median climate effect at SSP5-8.5 late century is −8.6 bu/acre, the eight models span −24.9 to −6.1, and the CO₂ assumption moves the net from −8.6 to +6.5. They are not forecasts, and the losses are probably overstated for want of adaptation.

**10. Does soil matter?** For where the good ground is and how counties respond to a bad year, yes; for predicting a given year's anomaly, no, and for a reason that follows from the detrending.

**11. Can ozone be separated from heat?** Not with these data. It survives detrending, tracks extreme degree days at about +0.6 to +0.7, and the design cannot detect effects of the size the literature implies.

**12. Does the model transfer to places it has not seen?** Across Illinois districts, yes, with no measurable loss, and the heat penalty does not differ by latitude. Whether the window's spatial structure is right cannot be established, because NASS phenology is state-level only.

### Direct answer to the central question

Between 1980 and 2025, Illinois soybean yield was strongly and negatively associated with July-August heat and moisture deficit, once the county-specific technology trend of roughly 0.65 bu/acre per year was removed. Moisture matters more than heat, and heat matters mainly by amplifying moisture stress. The relationship is nonlinear with an interior precipitation optimum, and it is highly heterogeneous across counties, with sensitivity varying more than sevenfold and concentrating where baseline productivity is lowest. Climate information carries genuine out-of-sample predictive value, improving on a trend-only baseline by 15 to 20%. Simulated warming and drying reduce yield in essentially every county, with combined perturbations doing more damage than their separate effects would suggest. All of this is association under a fixed-effects design, not causal identification, and the perturbation experiments are sensitivity analyses rather than climate projections.

**Part II adds** that the projection of this relationship under CMIP6 scenarios is wide and depends on assumptions the data cannot settle, chiefly the response to CO₂, the absence of adaptation, and extrapolation beyond the observed heat range. The direction of the near-term effect is a loss under any assumption about CO₂ up to 550 ppm; at the highest concentrations it depends on a CO₂ response this analysis cannot supply.

## Appendix A. Errors found and corrected during the extension

An audit trail, because several early results of Part II were wrong and the corrections change conclusions.

| # | What was wrong | Consequence | Where corrected |
|---|---|---|---|
| 1 | Soil available water averaged across horizon rows instead of summed down each profile | Bucket 4.35 times too small; the water balance drained to empty every year | Script 15 |
| 2 | Phenology thresholds and stage dates written from memory and described as calibrated to NASS | Stage dates agreed with the thresholds by construction and proved nothing | Scripts 23-25 |
| 3 | Temperature-rule planting 15.2 days early, described at the time as close to Illinois norms | Every modelled stage 10 to 19 days early | Script 25 |
| 4 | Thermal time used to end the yield window | Predicts leaf drop worse than the average date (RMSE 19.5 against sd 4.8 days) | Script 25 |
| 5 | `season_gdd` constant by construction under the thermal end rule (sd 4.25 GDD) | Its coefficient was fitted to discretisation noise; the earlier explanation of the maturity-group result was wrong | Scripts 20, 21 |
| 6 | Maturity-group offset added a constant, so seed fill was identical for every group | The exercise was voided | `_pheno.py` |
| 7 | Claim that thermal maturity matched what Illinois growers plant | Figure never sourced; withdrawn when corrected planting moved the frost constraint to MG 2.5 | Script 21 |
| 8 | Humidity assumed constant; then perturbed but not read by the specification | First fix returned a climate effect identical to four decimals | Scripts 12, 20 |
| 9 | VPD entered as a regressor | Wrong sign, collinear with EDD at about +0.9 | Script 20 |
| 10 | Ozone screen: units off by 10⁶, and a power comment that spread a whole-atmosphere effect over a 5 ppb range | Test looked able to detect an effect it could not | Script 22 |
| 11 | Retained-gradient window test judged by a naive 1% threshold | Paired year-by-year comparison shows the difference is not established | Script 26 |
| 12 | Heat-penalty heterogeneity inferred from separately fitted terciles | Separate fits overstated it; the pooled test finds none | Script 26 |
| 13 | Original report said county sensitivity varied by both tenfold and sevenfold | The same quantity, and neither ratio is defined because some counties have negative sensitivity | Part I text retained as written; see Section 4.6 |

---

## Appendix B. Reproduction

Scripts 01 to 11 reproduce Part I. The extensions add public downloads, none of which needs a key. Run order is slightly circular: script 24 runs once before calibration and once after, and script 25 checks that the constants in `scripts/_pheno.py` agree with what it recomputes.

| Script | Purpose | Main outputs |
|---|---|---|
| 12 | CMIP6 change factors (temperature, precipitation, relative humidity) | cmip6_deltas.csv |
| 13 | First-generation scenarios on monthly aggregates, superseded by 20 | tables 11-13 |
| 14-16 | SSURGO soil download, county features, three soil tests | tables 14-17 |
| 17 | NASA POWER daily weather | power_daily.csv.gz (not committed) |
| 18 | Phenology, VPD, water balance on observed weather | phenology_features.csv |
| 19 | Process versus calendar features | tables 18-20 |
| 20 | CMIP6 scenarios on the calibrated window, two window drivers | tables 21-22 |
| 21 | Maturity-group adaptation, thermal-time maturity | tables 23-24 |
| 22 | Ozone screen | tables 26-27 |
| 23 | NASS crop progress and condition download | nass_il_soybean_progress.csv |
| 24 | Phenology validated against NASS | tables 28-31 |
| 25 | Calibration of planting and yield window | tables 32-34 |
| 26 | County-level validation | tables 35-38 |
| 27 | This report | FINAL_REPORT.md, Illinois_Soybean_Climate_Report.docx |
| 28 | IPCC AR6 SPM-style summary figure | fig34 |
| 29 | County irrigated-acreage download, NASS Census of Agriculture | irrigation_features.csv |
| 30 | Irrigation vs climate sensitivity | tables 39-40b |

Random seed 42 throughout. Every figure is 200 dpi PNG in `figures/`, and every table is a CSV in `results/`.

---

## References

Ainsworth, E. A., and Long, S. P. (2005). What have we learned from 15 years of free-air CO₂ enrichment (FACE)? A meta-analytic review of the responses of photosynthesis, canopy properties and plant production to rising CO₂. *New Phytologist*.

Allen, R. G., Pereira, L. S., Raes, D., and Smith, M. (1998). *Crop evapotranspiration: guidelines for computing crop water requirements.* FAO Irrigation and Drainage Paper 56.

Khaki, S., Wang, L., and Archontoulis, S. V. (2020). A CNN-RNN framework for crop yield prediction. *Frontiers in Plant Science*, 10, 1750.

Peng, B., Guan, K., Tang, J., et al. (2020). Towards a multiscale crop modelling framework for climate change adaptation assessment. *Nature Plants*. doi:10.1038/s41477-020-0625-3

Ragsdale, D. W., et al. (2012). *Journal of Integrated Pest Management*, as cited in Section 6.3.

Schlenker, W., and Roberts, M. J. (2009). Nonlinear temperature effects indicate severe damages to U.S. crop yields under climate change. *Proceedings of the National Academy of Sciences*, 106.

Snyder, R. L. (1985). Hand calculating degree days. *Agricultural and Forest Meteorology*, 35.

Sun, J., Di, L., Sun, Z., Shen, Y., and Lai, Z. (2019). County-level soybean yield prediction using deep CNN-LSTM model. *Sensors*, 19, 4363.

Tian, H., Wang, P., Tansey, K., et al. (2021). An LSTM neural network for improving wheat yield estimates by integrating remote sensing data and meteorological data in the Guanzhong Plain, PR China. *Agricultural and Forest Meteorology*, 310, 108629.

Tilmon, K. J., et al. (2011). *Journal of Integrated Pest Management*, as cited in Section 6.3.

Zhang, J., Guan, K., Chen, Z., et al. (2025). Transfer learning for improved crop yield predictions in a cross-scale pathway: a case study for Brazilian national soybean. *International Journal of Applied Earth Observation and Geoinformation*, 145, 104981.

Cited by title from publisher pages: Morgan et al. (2006), season-long elevation of ozone concentration to projected 2050 levels under fully open-air conditions substantially decreases the growth and production of soybean, *New Phytologist*; and the published work on the role of vapour pressure deficit in maize and soybean yield loss under warming, including "Maize yield under a changing climate: The hidden role of vapor pressure deficit", *Agricultural and Forest Meteorology*.
