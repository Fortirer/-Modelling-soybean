"""Shared helpers for the gap-filling scripts (38 onward).

Scripts 01-37 and br_01-br_20 run one state at a time, selected by the STATE
or UF environment variable. The gap-filling scripts added after the
literature review (docs/DADOS_FALTANTES.md) work across BOTH countries, so
they take regions on the command line instead:

    python scripts/39_download_power_daily_all.py            # everything
    python scripts/39_download_power_daily_all.py US:IA BR:MT

This module resolves a region code to its folders without importing
00_config.py / br_00_config.py the normal way (both read an environment
variable and create a directory tree as a side effect).
"""
from __future__ import annotations

import importlib.util
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GLOBAL_RAW = ROOT / "data" / "raw" / "global"

US_GROW_MONTHS = (4, 5, 6, 7, 8, 9)
US_CRITICAL_MONTHS = (7, 8)
BR_GROW_MONTHS_CUR = (9, 10, 11, 12)
BR_GROW_MONTHS_NEXT = (1, 2, 3, 4)
BR_CRITICAL_MONTHS = (1, 2)


@dataclass(frozen=True)
class Region:
    """One US state or one Brazilian UF and where its files live."""
    country: str          # "US" or "BR"
    code: str             # "IA", "MT", ...
    raw: Path
    proc: Path
    res: Path
    boundaries: Path

    @property
    def key(self) -> str:
        return f"{self.country}:{self.code}"


def _load_registry(filename: str, attr: str, env: str, default: str) -> dict:
    previous = os.environ.get(env)
    os.environ[env] = default
    try:
        spec = importlib.util.spec_from_file_location(
            f"probe_{attr}", Path(__file__).with_name(filename))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return dict(getattr(module, attr))
    finally:
        if previous is None:
            os.environ.pop(env, None)
        else:
            os.environ[env] = previous


def all_regions() -> list[Region]:
    """Every region registered in 00_config.py and br_00_config.py."""
    regions = []
    for code in _load_registry("00_config.py", "STATE_REGISTRY", "STATE", "IL"):
        seg = "" if code == "IL" else code
        raw = ROOT / "data" / "raw" / seg
        regions.append(Region(
            "US", code, raw, ROOT / "data" / "processed" / seg,
            ROOT / "results" / seg, raw / f"{code.lower()}_county_boundaries.txt"))
    for code in _load_registry("br_00_config.py", "UF_REGISTRY", "UF", "MT"):
        raw = ROOT / "data" / "raw" / "BR" / code
        regions.append(Region(
            "BR", code, raw, ROOT / "data" / "processed" / "BR" / code,
            ROOT / "results" / "BR" / code, raw / "mt_municipio_boundaries.txt"))
    return regions


def select_regions(args: list[str]) -> list[Region]:
    """Regions named on the command line ("US:IA", "BR", "MT"); all if empty."""
    regions = all_regions()
    if not args:
        return regions
    wanted = {a.upper() for a in args}
    chosen = [r for r in regions
              if r.key in wanted or r.country in wanted or r.code in wanted]
    known = {r.key for r in regions} | {"US", "BR"} | {r.code for r in regions}
    unknown = wanted - known
    if unknown:
        raise SystemExit(f"Unknown region(s): {sorted(unknown)}. "
                         f"Use e.g. US, BR, US:IA, BR:MT.")
    return chosen


def centroids(region: Region, producing_only: bool = True) -> pd.DataFrame:
    """Unit centroids (unit_id, lon, lat) from the staged boundary file.

    Same vertex-mean centroid as scripts 17 and br_04, so points match the
    ones every existing feature was computed at. For Brazil only
    municipalities with recorded soybean production are kept (see br_04).
    """
    if not region.boundaries.exists():
        raise FileNotFoundError(f"{region.key}: missing {region.boundaries}")
    rows = []
    for line in region.boundaries.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        unit, coords = line.split("|", 1)
        pts = np.array([[float(x) for x in p.split(",")] for p in coords.split()])
        if len(pts) > 1 and np.allclose(pts[0], pts[-1]):
            pts = pts[:-1]
        rows.append(dict(unit_id=unit.strip(), lon=float(pts[:, 0].mean()),
                         lat=float(pts[:, 1].mean())))
    df = pd.DataFrame(rows)
    prod = region.proc / "production_clean.csv"
    if producing_only and region.country == "BR" and prod.exists():
        producing = set(pd.read_csv(prod, dtype={"fips5": str}).fips5)
        df = df[df.unit_id.isin(producing)].reset_index(drop=True)
    return df


def add_crop_year(daily: pd.DataFrame, country: str) -> pd.DataFrame:
    """New frame with crop_year, in_grow and in_critical columns added.

    US: crop_year is the calendar year; season April-September, critical
    July-August (00_config.py). Brazil: crop_year is the PLANTING year; season
    September-April, critical January-February of the following calendar
    year. IBGE reports that crop under crop_year + 1 (the harvest year);
    script 47 applies the shift. Days outside the season get NaN.
    """
    month = pd.to_datetime(daily["date"]).dt.month
    year = pd.to_datetime(daily["date"]).dt.year
    if country == "US":
        in_grow = month.isin(US_GROW_MONTHS)
        crop_year = year.where(in_grow)
        in_critical = month.isin(US_CRITICAL_MONTHS)
    else:
        cur, nxt = month.isin(BR_GROW_MONTHS_CUR), month.isin(BR_GROW_MONTHS_NEXT)
        in_grow = cur | nxt
        crop_year = year.where(cur, (year - 1).where(nxt))
        in_critical = month.isin(BR_CRITICAL_MONTHS)
    return daily.assign(crop_year=crop_year, in_grow=in_grow,
                        in_critical=in_critical, month=month)


def log(tag: str, message: str) -> None:
    print(f"[{tag}] {time.strftime('%H:%M:%S')} {message}", flush=True)


def scripts_on_path() -> None:
    here = str(Path(__file__).parent)
    if here not in sys.path:
        sys.path.insert(0, here)
