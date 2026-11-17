"""52 - Conab weekly soybean sowing and harvest progress, by state.

The Brazilian counterpart of NASS Crop Progress, which the README lists under
"Still open". Conab publishes a weekly "Acompanhamento das lavouras" with a
spreadsheet (plantio-e-colheita-*.xlsx) giving, for each crop and state, the
share of area sown and harvested up to that week, the same week one year
earlier, and the five-year mean for that week.

This script walks the listing, downloads every weekly spreadsheet it finds and
keeps the soybean block. Recent bulletins link the spreadsheet directly (with
or without the .xlsx extension); 2020-2024 are bundled in one zip per year on
the "acompanhamento-das-lavouras-2020-a-2024" page.

Outputs
  data/raw/BR/conab_soja_progress.csv
      operation (semeadura / colheita), state, week_ending, pct,
      pct_5yr_mean, source_file
      One row per state, operation and reported week. Each spreadsheet also
      reports the same week of the previous year, which extends the series one
      season back.
  data/processed/BR/conab_soja_progress_dates.csv
      state, operation, season, day50_from_sep1: day (after 1 September) on
      which 50% of the area was sown or harvested, interpolated linearly
      between weekly reports; and the same from the five-year mean curve.

Limits. State level only (the finest Conab publishes): it cannot place a
window per municipality the way ZARC does (script 49). The site keeps roughly
the last two seasons online, so the observed series is short; the five-year
mean column is what gives a climatological date. Conab covers the main
producing states, not all ten of this study in every week.

Usage:  python scripts/52_download_conab_progress.py
"""
import io
import json
import re
import time
import zipfile

import numpy as np
import pandas as pd
import requests

from _gap import ROOT, log

TAG = "52"
LISTING = ("https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/"
           "safras/progresso-de-safra")
PAGE_SIZE, MAX_PAGES = 20, 15
HEADERS = {"User-Agent": "Mozilla/5.0 (research script)"}
RETRIES, PAUSE_S, TIMEOUT_S = 5, 1.0, 90
RAW_OUT = ROOT / "data" / "raw" / "BR" / "conab_soja_progress.csv"
DATES_OUT = ROOT / "data" / "processed" / "BR" / "conab_soja_progress_dates.csv"
OPERATIONS = {"semeadura": "semeadura", "colheita": "colheita"}


def get(url: str) -> requests.Response:
    last_error = None
    for attempt in range(RETRIES):
        try:
            response = requests.get(url, headers=HEADERS, timeout=TIMEOUT_S)
            response.raise_for_status()
            time.sleep(PAUSE_S)
            return response
        except requests.RequestException as error:
            last_error = error
            time.sleep(6 * (attempt + 1))
    raise RuntimeError(f"{url}: {last_error}")


def weekly_pages() -> list[str]:
    """Every weekly bulletin page linked from the paginated listing."""
    pages = []
    for index in range(MAX_PAGES):
        url = LISTING if index == 0 else f"{LISTING}?b_start:int={index * PAGE_SIZE}"
        html = get(url).text
        found = re.findall(rf'href="({re.escape(LISTING)}/acompanhamento[^"/]+/[^"]+)"', html)
        new = [link for link in dict.fromkeys(found) if link not in pages]
        if not new:
            break
        pages += new
    return pages


def page_files(page_url: str) -> tuple[list[str], list[str]]:
    """(weekly spreadsheet links, yearly zip links) found on a bulletin page."""
    html = get(page_url).text
    sheets = re.findall(r'href="([^"]+/plantio-e-colheita[^"#]*)"', html)
    zips = re.findall(r'href="([^"]+progressodesafra/\d{4}\.zip)"', html)
    return list(dict.fromkeys(sheets)), list(dict.fromkeys(zips))


def zip_sheets(url: str) -> list[tuple[str, bytes]]:
    """Weekly planting-and-harvest spreadsheets inside one yearly archive."""
    archive = zipfile.ZipFile(io.BytesIO(get(url).content))
    return [(name.rsplit("/", 1)[-1], archive.read(name)) for name in archive.namelist()
            if name.lower().endswith(".xlsx") and "plantio" in name.lower()]


def harvest_year_of(safra_label: str) -> int | None:
    """'Soja - Safra 2026/27' -> 2027, the harvest year this repository uses."""
    found = re.search(r"(\d{4})\s*/\s*(\d{2,4})", safra_label)
    if not found:
        return None
    return int(found.group(1)) + 1


def parse_soybean(content: bytes, source: str) -> list[dict]:
    """Rows of the soybean block of one weekly spreadsheet.

    Each block is headed by its crop and season ("Soja - Safra 2026/27"); the
    season is taken from that label, never inferred from the date, because
    Conab keeps reporting a finished crop at 100% into September, after the
    next season has started. The date row holds the same week one year
    earlier (previous season) and the last two weeks of this season; a column
    whose date is about a year before the newest one is assigned to the
    previous season.
    """
    try:
        sheet = pd.read_excel(io.BytesIO(content), header=None)
    except Exception:                       # some older files have broken styles
        sheet = pd.read_excel(io.BytesIO(content), header=None, engine="calamine")
    rows, crop, season, operation, dates, mean_column = [], None, None, None, {}, None
    for _, line in sheet.iterrows():
        cells = list(line)
        label = next((str(c).strip() for c in cells if isinstance(c, str) and c.strip()), "")
        if re.search(r"safra\s+\d{4}", label, re.I):
            crop = label.split("-")[0].strip().lower()
            season, operation, dates, mean_column = harvest_year_of(label), None, {}, None
            continue
        key = label.lower().rstrip("*").strip()
        if key in OPERATIONS:
            operation, dates, mean_column = OPERATIONS[key], {}, None
            continue
        if crop != "soja" or operation is None or season is None:
            continue
        stamps = {i: c for i, c in enumerate(cells) if isinstance(c, pd.Timestamp)}
        if stamps:
            dates = stamps
            continue
        mean_header = [i for i, c in enumerate(cells)
                       if isinstance(c, str) and re.search(r"5\s*anos", c, re.I)]
        if mean_header:                                    # "Média 5 anos" header row
            mean_column = mean_header[0]
            continue
        if not dates or not label or re.search(r"\d+\s+estados", label, re.I):
            continue
        newest = max(dates.values())
        mean = cells[mean_column] if mean_column is not None else np.nan
        for column, stamp in dates.items():
            value = cells[column]
            if not isinstance(value, (int, float)) or pd.isna(value):
                continue
            years_back = int(round((newest - stamp).days / 365.25))
            is_current = stamp == newest
            rows.append(dict(
                operation=operation, state=label, season=season - years_back,
                week_ending=stamp.date().isoformat(), pct=round(float(value) * 100, 2),
                pct_5yr_mean=round(float(mean) * 100, 2)
                if is_current and isinstance(mean, (int, float)) and not pd.isna(mean)
                else np.nan,
                is_current_week=is_current, source_file=source))
    return rows


def deduplicate(table: pd.DataFrame) -> pd.DataFrame:
    """One row per state, operation, season and calendar week.

    The same week appears in several bulletins (as the current week, as the
    previous week, and a year later as the comparison column) with stamps a
    day or two apart and sometimes revised values. The value Conab reported in
    that week's own bulletin is kept.
    """
    when = pd.to_datetime(table.week_ending)
    week = when - pd.to_timedelta(when.dt.dayofweek, unit="D")     # Monday of the week
    table = table.assign(week_start=week.dt.date.astype(str))
    table = table.sort_values(["is_current_week", "pct_5yr_mean"], ascending=[False, True],
                              na_position="last")
    keys = ["operation", "state", "season", "week_start"]
    return table.drop_duplicates(keys, keep="first").sort_values(keys).drop(columns="week_start")


def day50(days: np.ndarray, pct: np.ndarray) -> float:
    """Day on which progress first reaches 50%, by linear interpolation.

    NaN unless the season's record starts below 50% and reaches it, so a
    season seen only after (or only before) its midpoint gives no date.
    """
    order = np.argsort(days)
    days, pct = days[order], pct[order]
    if len(pct) < 2 or pct[0] >= 50 or pct.max() < 50:
        return float("nan")
    first = int(np.argmax(pct >= 50))
    return float(np.interp(50, pct[first - 1:first + 1], days[first - 1:first + 1]))


def progress_dates(table: pd.DataFrame) -> pd.DataFrame:
    when = pd.to_datetime(table.week_ending)
    start = pd.to_datetime(dict(year=table.season - 1, month=9, day=1))
    table = table.assign(day=(when - start).dt.days)
    rows = []
    for (state, operation, year), group in table.groupby(["state", "operation", "season"]):
        latest = group.dropna(subset=["pct_5yr_mean"])
        rows.append(dict(
            state=state, operation=operation, season=int(year), weeks=len(group),
            first_pct=float(group.sort_values("day").pct.iloc[0]),
            last_pct=float(group.sort_values("day").pct.iloc[-1]),
            day50_from_sep1=day50(group.day.to_numpy(), group.pct.to_numpy()),
            day50_5yr_mean_from_sep1=day50(latest.day.to_numpy(),
                                           latest.pct_5yr_mean.to_numpy())
            if len(latest) > 1 else float("nan")))
    return pd.DataFrame(rows)


def main() -> None:
    pages = weekly_pages()
    log(TAG, f"{len(pages)} weekly bulletins listed")
    rows, without_file, failed, seen = [], 0, [], set()
    for i, page in enumerate(pages, 1):
        try:
            sheets, zips = page_files(page)
        except Exception as error:
            failed.append(dict(url=page, error=f"{type(error).__name__}: {error}"[:200]))
            continue
        if not sheets and not zips:
            without_file += 1
        for url in sheets + zips:
            if url in seen:
                continue
            seen.add(url)
            try:                            # one bad file must not stop the rest
                if url.endswith(".zip"):
                    for name, content in zip_sheets(url):
                        rows += parse_soybean(content, name)
                else:
                    rows += parse_soybean(get(url).content, url.rsplit("/", 1)[-1])
            except Exception as error:
                failed.append(dict(url=url, error=f"{type(error).__name__}: {error}"[:200]))
        if i % 20 == 0 or i == len(pages):
            log(TAG, f"{i}/{len(pages)} bulletins, {len(rows)} soybean rows")
    if not rows:
        raise SystemExit(f"[{TAG}] no soybean rows parsed")
    table = pd.DataFrame(rows)
    # Conab keeps only recent bulletins online: merge with what earlier runs
    # saved so re-running later never loses history
    if RAW_OUT.exists():
        previous = pd.read_csv(RAW_OUT)
        if {"season", "is_current_week"} <= set(previous.columns):
            table = pd.concat([table, previous], ignore_index=True)
    table = deduplicate(table)
    RAW_OUT.parent.mkdir(parents=True, exist_ok=True)
    DATES_OUT.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(RAW_OUT, index=False)
    dates = progress_dates(table)
    dates.to_csv(DATES_OUT, index=False, float_format="%.1f")
    (ROOT / "results" / "52_provenance_conab_progress.json").write_text(json.dumps(dict(
        source="Conab, Acompanhamento das lavouras (plantio e colheita)", url=LISTING,
        accessed=time.strftime("%Y-%m-%d"), bulletins_listed=len(pages),
        bulletins_without_spreadsheet=without_file, failed=failed, rows=len(table),
        states=sorted(table.state.unique()),
        weeks=[table.week_ending.min(), table.week_ending.max()]), indent=2,
        ensure_ascii=False), encoding="utf-8")
    log(TAG, f"{len(table)} rows, {table.state.nunique()} states, "
             f"{table.week_ending.min()} to {table.week_ending.max()}; "
             f"{without_file} bulletins without spreadsheet, {len(failed)} failed")


if __name__ == "__main__":
    main()
