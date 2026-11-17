## 2 | MATERIALS AND METHODS

### 2.1 | Study regions and spatial units

We analysed soybean (*Glycine max* (L.) Merr.) production in the two largest producing countries at the finest administrative level for which yields are published. In the United States the units are counties of twelve Corn Belt and Northern Plains states (Illinois, Iowa, Indiana, Minnesota, Nebraska, Missouri, Ohio, North Dakota, South Dakota, Kansas, Michigan and Wisconsin; 1,029 counties with reported yield). In Brazil the units are municipalities of ten states spanning the South, the Cerrado and the Matopiba frontier (Rio Grande do Sul, Paraná, São Paulo, Mato Grosso do Sul, Mato Grosso, Goiás, Minas Gerais, Bahia, Tocantins and Maranhão; 2,520 municipalities with reported yield). All data sources are public and all processing is scripted (Section 2.11).

### 2.2 | Yield data and crop-year alignment

County soybean yield, harvested area and production for 1980-2025 were taken from the USDA National Agricultural Statistics Service survey estimates (USDA NASS, 2026). Municipal yield, harvested area and production were taken from the Brazilian Municipal Agricultural Production survey (PAM, table 1612; IBGE, 2026). US yields (bushels per acre) were converted to kg ha⁻¹ at 60 lb per bushel.

Because the Brazilian season crosses the calendar year, the year under which a harvest is filed determines which weather it must be paired with. PAM files each crop under its harvest year: soybean sown in September-December of year *t* − 1 is reported under year *t*. We verified this empirically. Yield collapses in Rio Grande do Sul occur in the PAM years 2005, 2012 and 2022, the harvests of the 2004/05, 2011/12 and 2021/22 droughts, and the correlation between detrended yield and the 3-month Standardised Precipitation-Evapotranspiration Index of January-February was 0.45, 0.36 and 0.36 in Rio Grande do Sul, Paraná and Mato Grosso do Sul under the harvest-year alignment against approximately zero under a planting-year alignment. All Brazilian weather variables were therefore assigned to the harvest year.

For state-level models, units were retained if they had at least 20 years of yield and weather (the balanced panel). The yield response variable was either the natural logarithm of yield or the yield anomaly, defined as the residual from a unit-specific linear time trend, which removes gains from technology and cultivar change.

### 2.3 | Weather data

Daily weather for US counties (1980-2025) was extracted from Daymet version 4 R1 at 1 km resolution (Thornton et al., 2022): maximum and minimum temperature, precipitation, shortwave radiation and vapour pressure. Daily weather for both countries (1981-2025) was extracted from NASA POWER (NASA Langley Research Center, 2026), which distributes the MERRA-2 reanalysis (Gelaro et al., 2017) at approximately 0.5° resolution: maximum, minimum and mean temperature, dew point, bias-corrected precipitation, relative humidity, and surface (0-5 cm) and root-zone (0-100 cm) soil wetness expressed as a fraction of saturation (Reichle et al., 2017). Each unit was assigned the value of the grid cell containing its polygon centroid. Daymet was used for the US heat variables because of its resolution; the same variables were also computed from NASA POWER for the US so that pooled two-country analyses rely on a single source. Monthly county-level Palmer Drought Severity Index and Palmer Z index for the US were taken from NOAA nClimDiv (Vose et al., 2014).

The growing season was defined as April-September in the US and September-April in Brazil. The critical window for pod set and seed filling was July-August in the US and January-February in Brazil.

### 2.4 | Derived climate variables

*Thermal time and heat.* Degree days were computed from daily maximum and minimum temperature by single-sine integration (Snyder, 1985). Following Schlenker and Roberts (2009), we separated beneficial growing degree days between 10 and 30 °C (GDD) from extreme degree days above 30 °C (EDD); EDD was also computed at 29, 32 and 34 °C. We further computed, for the growing season and for the critical window, the number of days with maximum temperature at or above 30, 32 and 35 °C, nights with minimum temperature at or above 20 and 24 °C, the absolute maximum and minimum temperature, and a warm-spell duration index: days in spells of at least six consecutive days with maximum temperature above the unit's own 90th percentile for that calendar month in 1981-2010. This follows the ETCCDI definition (Zhang et al., 2011) except that a monthly rather than a 5-day moving percentile was used.

*Precipitation extremes.* Total precipitation, number of dry days (< 1 mm), longest run of consecutive dry days, maximum 1-day and 5-day precipitation, and days with at least 20 mm were computed for the same two windows (Zhang et al., 2011).

*Atmospheric demand.* Daily vapour pressure deficit (VPD) was the difference between saturation vapour pressure, averaged over that at maximum and minimum temperature (Allen et al., 1998), and actual vapour pressure, taken from Daymet in the US and from dew-point temperature in NASA POWER.

*Drought indices.* Daily data were aggregated to months. Reference evapotranspiration was estimated with the Hargreaves-Samani equation (Hargreaves & Samani, 1985), which requires only temperature and latitude and is therefore available for the whole record. The Standardised Precipitation Index (SPI; McKee et al., 1993) was obtained by fitting a gamma distribution with a probability mass at zero (Stagge et al., 2015), and the Standardised Precipitation-Evapotranspiration Index (SPEI; Vicente-Serrano et al., 2010) by fitting a generalised logistic distribution by L-moments (Hosking, 1990) to the climatic water balance. Both were computed at 3- and 6-month scales, separately for each unit and calendar month, on the unit's 1981-2025 record. We retained the 3-month indices ending in the last month of the critical window, the 6-month indices at the end of the season, the lowest 3-month SPEI of the season and the number of season months with SPEI below −1.

*Soil moisture.* Root-zone soil wetness was averaged over the growing season and the critical window, and the critical-window value was also expressed as a standardised anomaly relative to each unit's own climatology.

### 2.5 | Soil, irrigation and ancillary data

US soil properties were taken from the SSURGO database (Soil Survey Staff, 2026), aggregated to counties by component percentage and area, including plant-available water in the top metre. Brazilian soil properties were sampled from SoilGrids 2.0 at 250 m (Poggio et al., 2021) at municipality centroids for five depth intervals to 100 cm: clay, sand, silt, organic carbon, pH, bulk density and cation exchange capacity. Plant-available water in the top metre was computed as the depth-integrated difference between volumetric water content at 33 and 1,500 kPa from the SoilGrids water-retention layers; the pedotransfer function of Saxton and Rawls (2006) applied to texture and organic matter served as a cross-check. Irrigated area came from the USDA Census of Agriculture and from the 2017 Brazilian Agricultural Census (IBGE, 2019). Planting dates were characterised from NASS Crop Progress reports in the US and, in Brazil, from two sources: the lowest-risk sowing decade of the official agricultural climate-risk zoning (ZARC; MAPA, 2026), per municipality, and the observed weekly share of soybean area sown and harvested in each state from the Conab crop-progress bulletins, 2020-2026 (Conab, 2026), from which we interpolated the day on which half the area was sown. For within-season prediction only, the MODIS Terra 16-day 250 m NDVI (MOD13Q1 v6.1; Didan, 2021) was retrieved at the centroids of the municipalities of Rio Grande do Sul, Paraná and Mato Grosso do Sul through the ORNL DAAC subsetting service (ORNL DAAC, 2018), and its maximum and mean over the January-February composites of each harvest year, 2001-2025, were computed. The Oceanic Niño Index (NOAA Climate Prediction Center, 2026), averaged over each country's season, and annual mean atmospheric CO₂ at Mauna Loa (Lan et al., 2026) completed the dataset.

### 2.6 | Panel regression models

We fitted, with identical code in both countries, five specifications drawn from the literature. In each, the response was log yield of unit *i* in state *s* and year *t*:

log(*Y*ᵢₜ) = **X**ᵢₜ**β** + αᵢ + λₛ*t* + κₛ*t*² + εᵢₜ

where αᵢ is a unit fixed effect that absorbs time-invariant soil, management and location, and λₛ and κₛ define a state-specific quadratic trend that absorbs technological change and the CO₂ trend. The vector **X** contained: (i) GDD, EDD above 30 °C, season precipitation and its square (Schlenker & Roberts, 2009); (ii) the same plus critical-window root-zone soil wetness and its square (Ortiz-Bobea et al., 2019); (iii) GDD, critical-window VPD, critical-window precipitation and its square (Lobell et al., 2014); (iv) season mean temperature, season precipitation and its square (Silva et al., 2023); and (v) critical-window SPEI-3, warm-spell days and their product, representing compound dry-hot events (Parisoto et al., 2026). Fixed effects and trends were removed by partialling out (Frisch & Waugh, 1933; Lovell, 1963) with a sparse least-squares solver. Units with fewer than 20 complete years were excluded. Standard errors were clustered by state and inference used a *t* distribution with *G* − 1 degrees of freedom; because there are only 12 (US) and 10 (Brazil) clusters, *p*-values are treated as indicative (Cameron & Miller, 2015).

Separately for each state, we fitted a model of the detrended yield anomaly on critical-window maximum temperature and precipitation, their squares and their interaction, with unit and year fixed effects and standard errors clustered by unit. From it we derived the marginal effect of temperature at the sample mean and at the 10th and 90th percentiles of precipitation, and the temperature that maximises yield where the quadratic term was negative and significant. To test whether the heat response varies within a state, the linear temperature coefficient was estimated by latitude tercile and equality of slopes was assessed with a Wald test.

To identify when in the season weather matters (Mourtzinis et al., 2015), we replaced the season aggregates in the pooled model by mean temperature and total precipitation of each of the five months from flowering to maturity (May-September in the US, October-February in Brazil), with the same fixed effects, trends and inference. To test the fixed critical window, the Brazilian state models were re-estimated with a window placed 60 to 105 days after sowing in each municipality, an assumed R3-R6 interval, using either the ZARC sowing date or the Conab observed date, and compared on identical observations by the within-municipality *R*².

### 2.7 | Machine-learning models and validation

To compare a flexible learner with the parametric specification (Leng & Hall, 2020), a random forest (Breiman, 2001; 200 trees, minimum leaf size 5, half of the predictors tried at each split) was trained on 26 predictors covering thermal time, heat and precipitation extremes, VPD, drought indices, soil wetness and the Oceanic Niño Index. The target was the yield anomaly net of unit effects and state trends. Skill was evaluated by five-fold cross-validation in which whole years were held out, so that no year contributes to both training and testing; unit effects and trends were re-estimated on the training years of each fold. The Schlenker-Roberts regression was evaluated under the same scheme. Predictor importance was measured by permutation on held-out years.

Following the input design of Khaki et al. (2020), we also gave the learners 26 weeks of in-season weather (weekly mean maximum and minimum temperature, total precipitation and mean VPD; 104 inputs) instead of season indices, and compared a random forest and a feed-forward neural network (two hidden layers of 64 and 32 units, early stopping) under the same year-held-out scheme. This tests whether weekly timing adds skill; it is not a reproduction of their convolutional-recurrent architecture. Finally, to assess within-season prediction with remote sensing (Schwalbert et al., 2020; von Bloh et al., 2023), the random forest was refitted with the January-February NDVI added to the weather and drought predictors, on identical rows.

Within states, gradient-boosted trees (200 trees, depth 3, learning rate 0.05) were evaluated with an expanding window (rolling origin from the midpoint of the record, no random splits) for climate predictors alone, climate plus process-based predictors, and both plus soil. Spatial transferability was assessed by leaving out one mesoregion at a time. Skill is reported as the percentage reduction in root-mean-square error relative to predicting a zero anomaly.

### 2.8 | Climate projections

Monthly near-surface air temperature, daily maximum temperature, precipitation and relative humidity were obtained from eight CMIP6 models (Eyring et al., 2016): ACCESS-ESM1-5, CanESM5, EC-Earth3, GFDL-ESM4, INM-CM5-0, MIROC6, MPI-ESM1-2-LR and MRI-ESM2-0, one realisation each, for the historical experiment and for SSP2-4.5 and SSP5-8.5 (O'Neill et al., 2016). Change factors relative to 1985-2014 were computed for 2040-2069 and 2070-2099 at each unit centroid, additive for temperature and multiplicative for precipitation, and applied to the observed critical-window series (delta-change method). Yield was re-predicted with the state-level quadratic model. We report the ensemble median, the range across models, the number of models agreeing on the sign of the change, and the share of projected unit-years lying outside the observed range of critical-window temperature, which identifies extrapolation. Projections hold cultivars, management and planted area constant and include no CO₂ fertilisation effect.

Monthly change factors shift every day of a month equally and cannot represent changes in the frequency of days above 30 °C. We therefore also extracted daily, bias-corrected maximum and minimum temperature and precipitation from NEX-GDDP-CMIP6 at 0.25° (Thrasher et al., 2022) at every unit centroid, for MPI-ESM1-2-LR under the historical experiment (2005-2014) and SSP5-8.5 (2051-2060). Season GDD, EDD above 30 °C and precipitation were computed exactly as for the observations, and their change between the two periods was translated into yield change with the pooled Schlenker-Roberts coefficients of each country. With one model and ten-year periods this demonstrates the daily method rather than providing a projection.

### 2.9 | Comparison between countries

For the cross-country comparison (1980-2025) climate variables were converted to common units and anomalies were recomputed identically for both countries as deviations from each unit's own mean. State-level summaries were compared with the Mann-Whitney *U* test (Mann & Whitney, 1947), with Cliff's delta as effect size (Cliff, 1993) and Holm's correction for multiple comparisons (Holm, 1979). Differences between countries are descriptive: yield sources, weather sources and the calendar position of the critical window all differ.

### 2.10 | Limitations of the data

Each unit is represented by the grid cell at its centroid rather than by a cropland-weighted mean, which misrepresents large municipalities. The US heat variables derive from a 1 km product and the Brazilian ones from an approximately 50 km reanalysis that smooths extremes, so coefficients on extreme degree days are not directly comparable between countries; pooled analyses therefore use the NASA POWER version for both. Soil wetness is a land-surface model estimate, not a measurement. The critical window was fixed by country; moving it with the sowing date changed the fit little (Section 2.6). The ZARC lowest-risk date is two to five weeks later than the date Conab observes in most states, so it should not be read as the sowing date. NASA POWER begins in January 1981, so the first Brazilian harvest year has a partial season and was flagged. The Saxton-Rawls function was calibrated on US soils and is not reliable for the oxidic clays of the Cerrado.

### 2.11 | Software and reproducibility

Analyses were run in Python 3.12 with pandas, NumPy, SciPy, statsmodels (Seabold & Perktold, 2010), scikit-learn (Pedregosa et al., 2011) and xarray. The random seed was fixed at 42. The index functions (degree days, evapotranspiration, SPI, SPEI, spell lengths and the pedotransfer function) are covered by unit tests, including a check against a worked example in Allen et al. (1998) and against the tabulated values of Saxton and Rawls (2006). Code, processed data and provenance records for every download are available at https://github.com/Fortirer/-Modelling-soybean.

## REFERENCES

Allen, R. G., Pereira, L. S., Raes, D., & Smith, M. (1998). *Crop evapotranspiration: Guidelines for computing crop water requirements* (FAO Irrigation and Drainage Paper 56). Food and Agriculture Organization of the United Nations.

von Bloh, M., Nóia Júnior, R. de S., Wangerpohl, X., Saltık, A. O., Haller, V., Kaiser, L., & Asseng, S. (2023). Machine learning for soybean yield forecasting in Brazil. *Agricultural and Forest Meteorology*, 341, 109670. https://doi.org/10.1016/j.agrformet.2023.109670

Breiman, L. (2001). Random forests. *Machine Learning*, 45(1), 5-32. https://doi.org/10.1023/A:1010933404324

Cameron, A. C., & Miller, D. L. (2015). A practitioner's guide to cluster-robust inference. *Journal of Human Resources*, 50(2), 317-372. https://doi.org/10.3368/jhr.50.2.317

Cliff, N. (1993). Dominance statistics: Ordinal analyses to answer ordinal questions. *Psychological Bulletin*, 114(3), 494-509. https://doi.org/10.1037/0033-2909.114.3.494

Conab. (2026). *Progresso de safra: Acompanhamento das lavouras* [Data set]. Companhia Nacional de Abastecimento. https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/safras/progresso-de-safra

Didan, K. (2021). *MODIS/Terra Vegetation Indices 16-Day L3 Global 250m SIN Grid V061* [Data set]. NASA EOSDIS Land Processes DAAC. https://doi.org/10.5067/MODIS/MOD13Q1.061

Eyring, V., Bony, S., Meehl, G. A., Senior, C. A., Stevens, B., Stouffer, R. J., & Taylor, K. E. (2016). Overview of the Coupled Model Intercomparison Project Phase 6 (CMIP6) experimental design and organization. *Geoscientific Model Development*, 9(5), 1937-1958. https://doi.org/10.5194/gmd-9-1937-2016

Frisch, R., & Waugh, F. V. (1933). Partial time regressions as compared with individual trends. *Econometrica*, 1(4), 387-401. https://doi.org/10.2307/1907330

Gelaro, R., McCarty, W., Suárez, M. J., Todling, R., Molod, A., Takacs, L., Randles, C. A., Darmenov, A., Bosilovich, M. G., Reichle, R., Wargan, K., Coy, L., Cullather, R., Draper, C., Akella, S., Buchard, V., Conaty, A., da Silva, A. M., Gu, W., ... Zhao, B. (2017). The Modern-Era Retrospective Analysis for Research and Applications, version 2 (MERRA-2). *Journal of Climate*, 30(14), 5419-5454. https://doi.org/10.1175/JCLI-D-16-0758.1

Hargreaves, G. H., & Samani, Z. A. (1985). Reference crop evapotranspiration from temperature. *Applied Engineering in Agriculture*, 1(2), 96-99. https://doi.org/10.13031/2013.26773

Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scandinavian Journal of Statistics*, 6(2), 65-70.

Hosking, J. R. M. (1990). L-moments: Analysis and estimation of distributions using linear combinations of order statistics. *Journal of the Royal Statistical Society: Series B*, 52(1), 105-124. https://doi.org/10.1111/j.2517-6161.1990.tb01775.x

IBGE. (2019). *Censo Agropecuário 2017: Resultados definitivos*. Instituto Brasileiro de Geografia e Estatística. https://sidra.ibge.gov.br/tabela/6859

IBGE. (2026). *Produção Agrícola Municipal, tabela 1612* [Data set]. Instituto Brasileiro de Geografia e Estatística. https://sidra.ibge.gov.br/tabela/1612

Khaki, S., Wang, L., & Archontoulis, S. V. (2020). A CNN-RNN framework for crop yield prediction. *Frontiers in Plant Science*, 10, 1750. https://doi.org/10.3389/fpls.2019.01750

Lan, X., Tans, P., & Thoning, K. W. (2026). *Trends in globally-averaged CO₂ determined from NOAA Global Monitoring Laboratory measurements* [Data set]. NOAA Global Monitoring Laboratory. https://gml.noaa.gov/ccgg/trends/

Leng, G., & Hall, J. W. (2020). Predicting spatial and temporal variability in crop yields: An inter-comparison of machine learning, regression and process-based models. *Environmental Research Letters*, 15(4), 044027. https://doi.org/10.1088/1748-9326/ab7b24

Lobell, D. B., Roberts, M. J., Schlenker, W., Braun, N., Little, B. B., Rejesus, R. M., & Hammer, G. L. (2014). Greater sensitivity to drought accompanies maize yield increase in the U.S. Midwest. *Science*, 344(6183), 516-519. https://doi.org/10.1126/science.1251423

Lovell, M. C. (1963). Seasonal adjustment of economic time series and multiple regression analysis. *Journal of the American Statistical Association*, 58(304), 993-1010. https://doi.org/10.1080/01621459.1963.10480682

Mann, H. B., & Whitney, D. R. (1947). On a test of whether one of two random variables is stochastically larger than the other. *The Annals of Mathematical Statistics*, 18(1), 50-60. https://doi.org/10.1214/aoms/1177730491

MAPA. (2026). *Zoneamento Agrícola de Risco Climático (ZARC): Soja* [Data set]. Ministério da Agricultura e Pecuária. https://www.gov.br/agricultura/pt-br/assuntos/riscos-seguro/programa-nacional-de-zoneamento-agricola-de-risco-climatico

McKee, T. B., Doesken, N. J., & Kleist, J. (1993). The relationship of drought frequency and duration to time scales. In *Proceedings of the 8th Conference on Applied Climatology* (pp. 179-184). American Meteorological Society.

Mourtzinis, S., Specht, J. E., Lindsey, L. E., Wiebold, W. J., Ross, J., Nafziger, E. D., Kandel, H. J., Mueller, N., Devillez, P. L., Arriaga, F. J., & Conley, S. P. (2015). Climate-induced reduction in US-wide soybean yields underpinned by region- and in-season-specific responses. *Nature Plants*, 1, 14026. https://doi.org/10.1038/nplants.2014.26

NASA Langley Research Center. (2026). *Prediction Of Worldwide Energy Resources (POWER) project, daily agroclimatology data* [Data set]. https://power.larc.nasa.gov/

NOAA Climate Prediction Center. (2026). *Oceanic Niño Index (ONI)* [Data set]. https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt

O'Neill, B. C., Tebaldi, C., van Vuuren, D. P., Eyring, V., Friedlingstein, P., Hurtt, G., Knutti, R., Kriegler, E., Lamarque, J.-F., Lowe, J., Meehl, G. A., Moss, R., Riahi, K., & Sanderson, B. M. (2016). The Scenario Model Intercomparison Project (ScenarioMIP) for CMIP6. *Geoscientific Model Development*, 9(9), 3461-3482. https://doi.org/10.5194/gmd-9-3461-2016

ORNL DAAC. (2018). *MODIS and VIIRS Land Products Global Subsetting and Visualization Tool* [Data set]. Oak Ridge National Laboratory Distributed Active Archive Center. https://doi.org/10.3334/ORNLDAAC/1379

Ortiz-Bobea, A., Wang, H., Carrillo, C. M., & Ault, T. R. (2019). Unpacking the climatic drivers of US agricultural yields. *Environmental Research Letters*, 14(6), 064003. https://doi.org/10.1088/1748-9326/ab1e75

Parisoto et al. (2026). [Preprint on compound drought and heat effects on Brazilian soybean, 1989-2020; not peer reviewed. COMPLETE AUTHORS, TITLE AND DOI FROM THE PREPRINT.]

Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O., Blondel, M., Prettenhofer, P., Weiss, R., Dubourg, V., Vanderplas, J., Passos, A., Cournapeau, D., Brucher, M., Perrot, M., & Duchesnay, É. (2011). Scikit-learn: Machine learning in Python. *Journal of Machine Learning Research*, 12, 2825-2830.

Poggio, L., de Sousa, L. M., Batjes, N. H., Heuvelink, G. B. M., Kempen, B., Ribeiro, E., & Rossiter, D. (2021). SoilGrids 2.0: Producing soil information for the globe with quantified spatial uncertainty. *SOIL*, 7(1), 217-240. https://doi.org/10.5194/soil-7-217-2021

Reichle, R. H., Draper, C. S., Liu, Q., Girotto, M., Mahanama, S. P. P., Koster, R. D., & De Lannoy, G. J. M. (2017). Assessment of MERRA-2 land surface hydrology estimates. *Journal of Climate*, 30(8), 2937-2960. https://doi.org/10.1175/JCLI-D-16-0720.1

Saxton, K. E., & Rawls, W. J. (2006). Soil water characteristic estimates by texture and organic matter for hydrologic solutions. *Soil Science Society of America Journal*, 70(5), 1569-1578. https://doi.org/10.2136/sssaj2005.0117

Schlenker, W., & Roberts, M. J. (2009). Nonlinear temperature effects indicate severe damages to U.S. crop yields under climate change. *Proceedings of the National Academy of Sciences*, 106(37), 15594-15598. https://doi.org/10.1073/pnas.0906865106

Schwalbert, R. A., Amado, T., Corassa, G., Pott, L. P., Prasad, P. V. V., & Ciampitti, I. A. (2020). Satellite-based soybean yield forecast: Integrating machine learning and weather data for improving crop yield prediction in southern Brazil. *Agricultural and Forest Meteorology*, 284, 107886. https://doi.org/10.1016/j.agrformet.2019.107886

Seabold, S., & Perktold, J. (2010). Statsmodels: Econometric and statistical modeling with Python. In *Proceedings of the 9th Python in Science Conference* (pp. 92-96). https://doi.org/10.25080/Majora-92bf1922-011

Silva et al. (2023). [Municipal panel of Brazilian soybean yield and climate, 1980-2016, with Matopiba interviews.] *International Journal of Agricultural Sustainability*. [COMPLETE AUTHORS, TITLE, VOLUME AND DOI FROM THE PUBLISHED ARTICLE.]

Snyder, R. L. (1985). Hand calculating degree days. *Agricultural and Forest Meteorology*, 35(1-4), 353-358. https://doi.org/10.1016/0168-1923(85)90095-4

Soil Survey Staff. (2026). *Soil Survey Geographic (SSURGO) Database* [Data set]. USDA Natural Resources Conservation Service. https://sdmdataaccess.sc.egov.usda.gov/

Stagge, J. H., Tallaksen, L. M., Gudmundsson, L., Van Loon, A. F., & Stahl, K. (2015). Candidate distributions for climatological drought indices (SPI and SPEI). *International Journal of Climatology*, 35(13), 4027-4040. https://doi.org/10.1002/joc.4267

Thornton, M. M., Shrestha, R., Wei, Y., Thornton, P. E., Kao, S.-C., & Wilson, B. E. (2022). *Daymet: Daily surface weather data on a 1-km grid for North America, version 4 R1* [Data set]. ORNL DAAC. https://doi.org/10.3334/ORNLDAAC/2129

Thrasher, B., Wang, W., Michaelis, A., Melton, F., Lee, T., & Nemani, R. (2022). NASA Global Daily Downscaled Projections, CMIP6. *Scientific Data*, 9, 262. https://doi.org/10.1038/s41597-022-01393-4

USDA NASS. (2026). *Quick Stats* [Data set]. USDA National Agricultural Statistics Service. https://quickstats.nass.usda.gov/

Vicente-Serrano, S. M., Beguería, S., & López-Moreno, J. I. (2010). A multiscalar drought index sensitive to global warming: The Standardized Precipitation Evapotranspiration Index. *Journal of Climate*, 23(7), 1696-1718. https://doi.org/10.1175/2009JCLI2909.1

Vose, R. S., Applequist, S., Squires, M., Durre, I., Menne, M. J., Williams, C. N., Fenimore, C., Gleason, K., & Arndt, D. (2014). Improved historical temperature and precipitation time series for U.S. climate divisions. *Journal of Applied Meteorology and Climatology*, 53(5), 1232-1251. https://doi.org/10.1175/JAMC-D-13-0248.1

Zhang, X., Alexander, L., Hegerl, G. C., Jones, P., Klein Tank, A., Peterson, T. C., Trewin, B., & Zwiers, F. W. (2011). Indices for monitoring changes in extremes based on daily temperature and precipitation data. *WIREs Climate Change*, 2(6), 851-870. https://doi.org/10.1002/wcc.147
