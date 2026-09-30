"""Shared configuration for the BRAZIL branch of this pipeline.

WHY A SEPARATE BRANCH, NOT ANOTHER STATE_REGISTRY ENTRY
  00_config.py's STATE_REGISTRY and every script built on it (01-30) is
  wired to US-only sources: USDA NASS county ANSI codes, NOAA nClimDiv
  state codes, Census TIGER cartographic boundaries, EPA AQS monitors,
  USDA-NRCS SSURGO soil. None of those exist for Brazil. Rather than
  bend those scripts with country branches throughout, Brazil gets its
  own small parameterized config (this file) and its own br_NN_*.py
  scripts, reusing exactly the one source that was ALREADY chosen to be
  country-agnostic: NASA POWER (see script 17's own docstring -- it says
  outright that POWER was picked so Illinois and Brazil could share one
  consistent daily-weather source for cross-scale transfer learning; this
  branch is that transfer finally being built).

GEOGRAPHIC UNIT
  Brazil's municipality (município) is the direct analogue of a US
  county: the finest level IBGE publishes agricultural statistics at,
  and there are ~5,570 of them nationally, ~141 in Mato Grosso alone.

DATA SOURCES, one per US-pipeline step they replace
  production   IBGE SIDRA, table 1612 (PAM - Produção Agrícola Municipal),
               municipality level, product 2713 "Soja (em grão)". Public
               REST API, no key. Replaces USDA NASS (scripts 01-02).
  climate      NASA POWER daily point API, same as US script 17 --
               already global, no change needed except which centroids
               are queried. Replaces NOAA nClimDiv (US scripts 03-04).
  geography    IBGE malha municipal (municipality boundary) service,
               public, no key. Replaces Census TIGER (US script 10).
  soil, CMIP6, ozone, phenology calibration: not yet built for this
  branch -- see the Brazil README section once this exists. CMIP6 (US
  script 12) is coordinate-based already and should port with no change
  in principle; it has not been tried here yet.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

UF = os.environ.get("UF", "MT").upper()

# ibge_uf: 2-digit IBGE Unidade da Federação code (used to filter SIDRA's
# n6/"in n3 <code>" municipality-in-state query and to prefix municipality
# codes, which are IBGE_UF + 5 more digits).
UF_REGISTRY = {
    "MT": dict(name="MATO GROSSO", ibge_uf="51",
               focal_municipio="SORRISO", focal_code="5107925"),
    "PR": dict(name="PARANA", ibge_uf="41",
               focal_municipio="CASCAVEL", focal_code="4104808"),
    "GO": dict(name="GOIAS", ibge_uf="52",
               focal_municipio="RIO VERDE", focal_code="5218805"),
}
if UF not in UF_REGISTRY:
    raise SystemExit(f"Unknown UF={UF!r}. Add it to UF_REGISTRY in "
                     f"br_00_config.py (name, IBGE UF code, a focal "
                     f"municipality). Known: {sorted(UF_REGISTRY)}")
_UC = UF_REGISTRY[UF]
UF_NAME, IBGE_UF = _UC["name"], _UC["ibge_uf"]
FOCAL_MUNICIPIO, FOCAL_CODE = _UC["focal_municipio"], _UC["focal_code"]

RAW = ROOT / f"data/raw/BR/{UF}"
PROC = ROOT / f"data/processed/BR/{UF}"
FINAL = ROOT / f"data/final/BR/{UF}"
FIG = ROOT / f"figures/BR/{UF}"
RES = ROOT / f"results/BR/{UF}"
MOD = ROOT / f"models/BR/{UF}"
for d in (RAW, PROC, FINAL, FIG, RES, MOD):
    d.mkdir(parents=True, exist_ok=True)

SEED = 42

# ---- Growing season -----------------------------------------------------
# Southern-hemisphere soybean calendar, inverted from the US Corn Belt:
# planted Sep-Nov, flowering Dec-Jan, pod set/seed fill Jan-Feb (the local
# summer), harvest Feb-Apr. The critical yield-setting window (US July-
# August) maps to Brazilian January-February.
GROW_MONTHS     = [9, 10, 11, 12, 1, 2, 3, 4]   # Sep(prior yr)-Apr, planting through harvest
CRITICAL_MONTHS = [1, 2]                         # Jan-Feb, pod set and seed fill
SUMMER_MONTHS   = [12, 1, 2]                     # local meteorological summer (DJF)

PROVENANCE = {
    "production": dict(
        source="IBGE SIDRA, tabela 1612 (Producao Agricola Municipal)",
        url="https://sidra.ibge.gov.br/tabela/1612",
        api="https://apisidra.ibge.gov.br/values/t/1612/n6/in%20n3%20{ibge_uf}/"
            "v/109,216,214,112/p/all/c81/2713",
        note="area plantada (ha), area colhida (ha), quantidade produzida (t), "
             "rendimento medio (kg/ha); produto=2713 Soja (em grao); "
             "municipio level (n6), all municipalities in the state (n3 filter). "
             "Public REST API, no key."),
    "climate": dict(
        source="NASA POWER daily point API (MERRA-2 reanalysis)",
        url="https://power.larc.nasa.gov/",
        note="same source and script logic as the US pipeline's script 17, "
             "global coverage by design -- see that script's docstring."),
    "geography": dict(
        source="IBGE Malhas Territoriais (municipality boundaries)",
        url="https://servicodados.ibge.gov.br/api/docs/malhas",
        note=f"municipio codigo = IBGE_UF '{IBGE_UF}' + 5 more digits."),
}
