# Flourish-ready files

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
