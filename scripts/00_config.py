"""Shared configuration and provenance constants.

STATE-PARAMETERIZED (added when the pipeline was extended to Iowa). Set the
environment variable STATE to select which state's pipeline runs; it defaults
to IL so every existing Illinois script and result is untouched. Illinois
keeps its original flat data/results/figures/models layout for backward
compatibility with every path already hardcoded across scripts 06-30; any
other state gets its own namespaced subtree (data/raw/IA/, results/IA/, ...)
so the two pipelines never collide and both stay independently reproducible
from the same codebase. Add a new state by adding one entry to STATE_REGISTRY
below -- nothing else in this file changes.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STATE = os.environ.get("STATE", "IL").upper()

# climdiv_code: NOAA nClimDiv 2-digit state code (county-readme.txt STATE CODE
# TABLE) -- NOT the Census/FIPS state code used everywhere else in this repo.
STATE_REGISTRY = {
    "IL": dict(name="ILLINOIS", fips="17", climdiv_code="11",
               focal_county="CHAMPAIGN", focal_fips="17019"),
    "IA": dict(name="IOWA", fips="19", climdiv_code="13",
               focal_county="STORY", focal_fips="19169"),
    "IN": dict(name="INDIANA", fips="18", climdiv_code="12",
               focal_county="TIPPECANOE", focal_fips="18157"),
}
if STATE not in STATE_REGISTRY:
    raise SystemExit(f"Unknown STATE={STATE!r}. Add it to STATE_REGISTRY in "
                     f"00_config.py (name, Census fips, NOAA climdiv_code, a focal "
                     f"county). Known: {sorted(STATE_REGISTRY)}")
_SC = STATE_REGISTRY[STATE]
STATE_NAME, STATE_FIPS, CLIMDIV_CODE = _SC["name"], _SC["fips"], _SC["climdiv_code"]
FOCAL_COUNTY, FOCAL_FIPS = _SC["focal_county"], _SC["focal_fips"]

_seg = "" if STATE == "IL" else f"/{STATE}"
RAW, PROC, FINAL = ROOT/f"data/raw{_seg}", ROOT/f"data/processed{_seg}", ROOT/f"data/final{_seg}"
FIG, RES, MOD = ROOT/f"figures{_seg}", ROOT/f"results{_seg}", ROOT/f"models{_seg}"
for d in (RAW,PROC,FINAL,FIG,RES,MOD): d.mkdir(parents=True,exist_ok=True)

# legacy filename, kept identical across states (every downstream script from
# 06 onward hardcodes this literal); harmless once RAW/PROC/FINAL are
# state-namespaced, since IL and IA never share a directory
PANEL_FILE = "soybean_illinois_climate_1980_2025.csv"

SEED = 42

# ---- Growing season (agronomic justification, see README Methodology) -------
# Soybean growing season is the same across the Corn Belt: planted
# early-to-mid May, emergence late May, vegetative June, flowering (R1-R2)
# late June-July, pod set (R3-R4) late July, seed fill (R5-R6) August,
# maturity (R7-R8) September, harvest October.
# Yield is set primarily during R3-R6, i.e. late July through August.
GROW_MONTHS    = [4,5,6,7,8,9]      # April-September, planting through maturity
CRITICAL_MONTHS= [7,8]              # July-August, pod set and seed fill
SUMMER_MONTHS  = [6,7,8]            # meteorological summer

# ---- Provenance -------------------------------------------------------------
PROVENANCE = {
 "production": dict(
   source="USDA NASS Quick Stats",
   url="https://quickstats.nass.usda.gov/",
   accessed="2026-08-31" if STATE == "IL" else None,
   params=f"source_desc=SURVEY; sector_desc=CROPS; commodity_desc=SOYBEANS; "
          f"agg_level_desc=COUNTY; state_name={STATE_NAME}; domain_desc=TOTAL; "
          f"period=YEAR; year=1980..2025",
   note="Illinois: query-tool CSV export, no API key. Other states: the same "
        "public bulk file used by script 23 (qs.crops_<date>.txt.gz), streamed "
        "and filtered -- see script 01."),
 "climate": dict(
   source="NOAA NCEI nClimDiv, county-level monthly",
   url="https://www.ncei.noaa.gov/pub/data/cirs/climdiv/",
   accessed="2026-08-31" if STATE == "IL" else None,
   files=["climdiv-pcpncy","climdiv-tmpccy","climdiv-tmaxcy","climdiv-tmincy",
          "climdiv-pdsicy","climdiv-zndxcy"],
   spatial_resolution="county polygon (pre-aggregated by NCEI from station network)",
   temporal_resolution="monthly",
   units="precipitation inches; temperature degrees Fahrenheit; Palmer indices dimensionless",
   note="ERA5 analogue. NCEI performs the gridding and polygon aggregation "
        "upstream, so no area-weighting step is executed in this pipeline. "
        "See README Limitations."),
 "geography": dict(
   source="USDA NASS county ANSI (FIPS) codes and Agricultural Statistics Districts",
   note=f"fips5 = '{STATE_FIPS}' + county_ansi. Joins to Census TIGER."),
}
