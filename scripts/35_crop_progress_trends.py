"""35 - Soybean planting and phenology trends from NASS crop progress, 12 states.

Follows the crop-progress half of Sacks & Kucharik (2011), Agricultural and
Forest Meteorology 151:882-894, applied to soybean only and extended from their
1981-2005 window to every year in the repo (1980-2025).

METHOD (their Section 2.1)
  1. Weekly state-level NASS progress (planted, blooming = R1, dropping leaves =
     maturity, harvested), interpolated with PCHIP (monotone, no extrapolation).
  2. 50% completion date per state-year-stage. When collection ended before 50%
     or began after it, estimate it from the 25% or 75% date (then 10% or 90%)
     plus the state's mean gap between that level and 50%.
  3. Linear trend (days per year) and its slope p-value for each date and for the
     intervals between them: planted-R1 (vegetative), R1-maturity (reproductive),
     planted-maturity (growth), maturity-harvest (dry-down).
  4. A US average with FIXED area weights (each state's mean harvested area), so
     shifts in where soybeans are grown do not masquerade as a phenology trend.

WHAT IS NOT DONE, AND WHY
  The paper restricts GDD between stages and all Agro-IBIS modelling to corn
  because soybean development depends on photoperiod as well as temperature. This
  script follows that: soybean gets dates, intervals and trends only.

DIFFERENCES FROM THE PAPER
  States. The paper's 13 soybean states include AR, KY, LA and TN; the repo holds
  progress files for IL, IA, IN, KS, MI, MN, MO, ND, NE, OH, SD, WI. Nine overlap.
  ND (from 1998), SD (1985) and WI (2000) start later, so they get shorter trend
  windows and are excluded from the long US average (see SETS).
  Years. 1980-2025 here against 1981-2005 there. 2026 is dropped, as that season
  is incomplete. The 1981-2005 window is re-run for the nine shared states and
  compared with the paper's Tables 2 and 3 as a check on this implementation.
  Weights. County acres_harvested summed to the state, since the repo holds no
  state totals for most states. Suppressed counties make this slightly low, but
  weights only need the relative size of states.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from scipy.interpolate import PchipInterpolator
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RES = ROOT / "results" / "_crop_progress"
FIG = ROOT / "figures" / "_crop_progress"
RES.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

STATES = ["IL", "IA", "IN", "KS", "MI", "MN", "MO", "ND", "NE", "OH", "SD", "WI"]
CORE9 = ["IA", "IL", "IN", "KS", "MI", "MN", "MO", "NE", "OH"]
SETS = {"core9": CORE9, "all12": STATES}
UNIT = {"planted": "PCT PLANTED", "r1": "PCT BLOOMING",
        "maturity": "PCT DROPPING LEAVES", "harvested": "PCT HARVESTED"}
STAGES = list(UNIT)
INTERVALS = {"veg": ("planted", "r1"), "repro": ("r1", "maturity"),
             "growth": ("planted", "maturity"), "dry": ("maturity", "harvested")}
Y0, Y1 = 1980, 2025
FALLBACK = [25, 75, 10, 90]
MIN_YEARS = 8
WINDOWS = {"full": (Y0, Y1), "paper": (1981, 2005), "post": (2006, Y1)}

# Sacks & Kucharik (2011) Tables 2 and 3, soybean columns, 1981-2005, days/yr.
# Order: planted, R1, maturity, harvested | planted-R1, R1-maturity,
# planted-maturity, maturity-harvest.
PAPER = {
    "IL": [-0.25, 0.06, 0.06, -0.02, 0.31, 0.00, 0.31, -0.08],
    "IN": [-0.58, -0.19, -0.24, -0.32, 0.38, -0.05, 0.33, -0.08],
    "IA": [-0.55, -0.29, -0.09, -0.37, 0.26, 0.20, 0.46, -0.28],
    "KS": [-1.01, -0.81, -0.41, -0.66, 0.20, 0.40, 0.60, -0.25],
    "MI": [-0.33, -0.29, 0.07, -0.59, 0.04, 0.37, 0.40, -0.67],
    "MN": [-0.32, -0.15, -0.05, -0.50, 0.17, 0.10, 0.27, -0.45],
    "MO": [-0.62, -0.28, -0.25, -0.47, 0.35, 0.03, 0.37, -0.22],
    "NE": [-0.54, -0.25, -0.33, -0.53, 0.29, -0.08, 0.21, -0.19],
    "OH": [-0.55, -0.32, -0.22, -0.38, 0.23, 0.09, 0.32, -0.16],
}
PAPER_COLS = ["planted", "r1", "maturity", "harvested", "veg", "repro", "growth", "dry"]


def progress_path(s):
    return RAW / "nass_il_soybean_progress.csv" if s == "IL" else RAW / s / "nass_il_soybean_progress.csv"


def county_path(s):
    return RAW / "nass_il_soybeans_county_raw.csv" if s == "IL" else RAW / s / "nass_il_soybeans_county_raw.csv"


def load_progress():
    out = []
    for s in STATES:
        d = pd.read_csv(progress_path(s), low_memory=False,
                        usecols=["STATE_ALPHA", "YEAR", "WEEK_ENDING", "STATISTICCAT_DESC",
                                 "UNIT_DESC", "VALUE_NUM"])
        d = d[(d.STATISTICCAT_DESC == "PROGRESS") & d.UNIT_DESC.isin(UNIT.values())].copy()
        d["pct"] = pd.to_numeric(d.VALUE_NUM, errors="coerce")
        d["date"] = pd.to_datetime(d.WEEK_ENDING)
        d["doy"] = d.date.dt.dayofyear
        d = d.rename(columns={"STATE_ALPHA": "state", "YEAR": "year"})
        d = d[(d.year >= Y0) & (d.year <= Y1)].dropna(subset=["pct"])
        d["stage"] = d.UNIT_DESC.map({v: k for k, v in UNIT.items()})
        out.append(d[["state", "year", "stage", "doy", "pct"]].drop_duplicates(["state", "year", "stage", "doy"]))
    return pd.concat(out, ignore_index=True)


def curve(g):
    g = g.sort_values("doy")
    x = g.doy.to_numpy(float)
    y = np.maximum.accumulate(g.pct.to_numpy(float))
    return (x, y) if len(x) >= 3 else None


def crossing(x, y, level):
    """First day the PCHIP curve reaches `level`, only if the data bracket it."""
    if not (y[0] < level <= y[-1]):
        return np.nan
    f = PchipInterpolator(x, y, extrapolate=False)
    grid = np.arange(x[0], x[-1] + 1e-9, 0.02)
    v = f(grid)
    k = int(np.argmax(v >= level))
    return float(grid[k]) if v[k] >= level else np.nan


def state_dates(prog):
    rows = []
    for (s, yr, st), g in prog.groupby(["state", "year", "stage"]):
        c = curve(g)
        if c is None:
            continue
        r = dict(state=s, year=int(yr), stage=st)
        for L in [50] + FALLBACK:
            r[f"d{L}"] = crossing(*c, L)
        rows.append(r)
    d = pd.DataFrame(rows)

    est, nest = [], {}
    for (s, st), g in d.groupby(["state", "stage"]):
        gap = {L: float((g.d50 - g[f"d{L}"]).dropna().mean()) for L in FALLBACK
               if (g.d50.notna() & g[f"d{L}"].notna()).sum() >= 3}
        for _, r in g.iterrows():
            val, used = r.d50, 50
            if not np.isfinite(val):
                used = 0
                for L in FALLBACK:
                    if L in gap and np.isfinite(r[f"d{L}"]):
                        val, used = r[f"d{L}"] + gap[L], L
                        break
            est.append(dict(state=s, year=r.year, stage=st, doy=val, basis=used))
        nest[(s, st)] = int(sum(1 for e in est[-len(g):] if e["basis"] != 50 and np.isfinite(e["doy"])))
    e = pd.DataFrame(est)
    wide = e.pivot_table(index=["state", "year"], columns="stage", values="doy").reset_index()
    basis = e.pivot_table(index=["state", "year"], columns="stage", values="basis").reset_index()
    basis = basis.rename(columns={k: f"basis_{k}" for k in STAGES})
    wide = wide.merge(basis, on=["state", "year"])
    for st in STAGES:
        if st not in wide:
            wide[st] = np.nan
    return wide, nest


def add_intervals(df):
    for k, (a, b) in INTERVALS.items():
        df[k] = df[b] - df[a]
    return df


def stars(p):
    return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""


def trend(years, vals, lo, hi):
    years, vals = np.asarray(years, float), np.asarray(vals, float)
    m = np.isfinite(vals) & (years >= lo) & (years <= hi)
    if m.sum() < MIN_YEARS:
        return dict(n=int(m.sum()), slope=np.nan, se=np.nan, p=np.nan, mean=np.nan,
                    change=np.nan, first=np.nan, last=np.nan, sig="")
    r = stats.linregress(years[m], vals[m])
    return dict(n=int(m.sum()), slope=r.slope, se=r.stderr, p=r.pvalue, mean=float(vals[m].mean()),
                change=float(r.slope * (years[m].max() - years[m].min())),
                first=int(years[m].min()), last=int(years[m].max()), sig=stars(r.pvalue))


def harvested_weights():
    ser = {}
    for s in STATES:
        c = pd.read_csv(county_path(s), low_memory=False, usecols=["year", "acres_harvested"])
        c["a"] = pd.to_numeric(c.acres_harvested, errors="coerce")
        ser[s] = c.groupby("year").a.sum(min_count=1)
    return pd.DataFrame(ser)


def weighted_avg_dates(dates, hv, states, lo, hi):
    """Date-average US series: fixed weights = mean harvested area over lo..hi."""
    w = hv.loc[(hv.index >= lo) & (hv.index <= hi), states].mean()
    rows = []
    for yr, g in dates[dates.state.isin(states)].groupby("year"):
        if yr < lo or yr > hi:
            continue
        r = dict(year=int(yr))
        for st in STAGES:
            v = g.set_index("state")[st].reindex(states)
            r[st] = float((v * w).sum() / w.sum()) if v.notna().all() else np.nan
        rows.append(r)
    return add_intervals(pd.DataFrame(rows)), w


def curve_avg_dates(prog, hv, states, lo, hi):
    """Paper-style US series: weighted mean of daily PCHIP progress, then its 50% day."""
    w = hv.loc[(hv.index >= lo) & (hv.index <= hi), states].mean()
    grid = np.arange(1.0, 367.0, 0.1)
    rows = []
    for yr in range(lo, hi + 1):
        r = dict(year=yr)
        for st in STAGES:
            tot, ok = np.zeros_like(grid), True
            for s in states:
                g = prog[(prog.state == s) & (prog.year == yr) & (prog.stage == st)]
                c = curve(g) if len(g) else None
                if c is None or not (c[1][0] < 50 <= c[1][-1]):
                    ok = False
                    break
                f = PchipInterpolator(c[0], c[1], extrapolate=False)
                v = f(grid)
                v = np.where(grid < c[0][0], 0.0, np.where(grid > c[0][-1], c[1][-1], v))
                tot += w[s] * v
            r[st] = float(grid[int(np.argmax(tot / w[states].sum() >= 50))]) if ok else np.nan
        rows.append(r)
    return add_intervals(pd.DataFrame(rows))


def trend_table(series_by_name, windows, cols):
    rows = []
    for name, df in series_by_name.items():
        for wn, (lo, hi) in windows.items():
            for c in cols:
                t = trend(df.year, df[c], lo, hi)
                rows.append(dict(unit=name, window=wn, variable=c, **t))
    return pd.DataFrame(rows)


def main():
    prog = load_progress()
    print(f"[35] progress rows {len(prog):,}, states {prog.state.nunique()}, years {prog.year.min()}-{prog.year.max()}")

    dates, nest = state_dates(prog)
    dates = add_intervals(dates)
    dates.to_csv(RES / "table_state_dates.csv", index=False)
    est_tab = pd.DataFrame([dict(state=s, stage=st, n_estimated=n) for (s, st), n in nest.items()])
    est_tab.to_csv(RES / "table_estimated_dates.csv", index=False)
    print("\n[35] 50% dates that had to be ESTIMATED from 25/75/10/90% (count by state):")
    print(est_tab.pivot(index="state", columns="stage", values="n_estimated").reindex(STATES).to_string())

    hv = harvested_weights()
    il_state = pd.read_csv(RAW / "nass_il_state_totals.csv").set_index("year").acres_harvested
    ratio = (hv["IL"] / il_state).dropna()
    print(f"\n[35] weight check, IL county-sum / state total acres_harvested: "
          f"median {ratio.median():.3f}, min {ratio.min():.3f}")
    wfull = hv.loc[(hv.index >= 1981) & (hv.index <= Y1), STATES].mean()
    print("[35] mean harvested area used for weights (1981-2025, thousand acres):")
    print((wfull / 1000).round(0).astype(int).to_dict())

    cols = STAGES + list(INTERVALS)
    series = {s: dates[dates.state == s].sort_values("year") for s in STATES}

    us = {}
    us["core9_dates"], w9 = weighted_avg_dates(dates, hv, CORE9, Y0, Y1)
    us["core9_curve"] = curve_avg_dates(prog, hv, CORE9, Y0, Y1)
    all12_years = int(dates[dates.state.isin(["ND", "WI"])].groupby("state").year.min().max())
    us["all12_dates"], _ = weighted_avg_dates(dates, hv, STATES, all12_years, Y1)
    for k, v in us.items():
        v.to_csv(RES / f"table_us_{k}.csv", index=False)

    d, c = us["core9_dates"].set_index("year"), us["core9_curve"].set_index("year")
    print("\n[35] US core-9 average: date-average vs paper-style curve-average, 50% dates")
    for st in STAGES:
        j = pd.concat([d[st], c[st]], axis=1, keys=["date", "curve"]).dropna()
        print(f"   {st:10s} n={len(j):2d}  mean abs diff {np.abs(j.date - j.curve).mean():.2f} d  "
              f"corr {j.date.corr(j.curve):.3f}")

    named = {**{s: series[s] for s in STATES}, "US_core9": us["core9_dates"].assign(),
             "US_all12": us["all12_dates"]}
    tt = trend_table(named, WINDOWS, cols)
    tt.to_csv(RES / "table_trends.csv", index=False)

    full = tt[tt.window == "full"]
    def show(unit_list, variables, title):
        print(f"\n[35] {title}  (days/yr, 1980-2025 or available years)")
        out = {}
        for u in unit_list:
            r = full[full.unit == u].set_index("variable")
            out[u] = [f"{r.loc[v, 'slope']:+.2f}{r.loc[v, 'sig']}" if np.isfinite(r.loc[v, "slope"]) else "  -  "
                      for v in variables]
        print(pd.DataFrame(out, index=variables).T.to_string())
    units = STATES + ["US_core9", "US_all12"]
    show(units, STAGES, "Trends in 50% DATES")
    show(units, list(INTERVALS), "Trends in INTERVAL LENGTHS")

    print("\n[35] Does the trend continue after the paper's window? US core-9 slope by window:")
    for v in cols:
        r = tt[(tt.unit == "US_core9") & (tt.variable == v)].set_index("window")
        print(f"   {v:10s} " + "  ".join(f"{w}: {r.loc[w, 'slope']:+.2f}{r.loc[w, 'sig']}" for w in WINDOWS))

    cmp_rows = []
    for s in CORE9:
        r = tt[(tt.unit == s) & (tt.window == "paper")].set_index("variable")
        for col, pv in zip(PAPER_COLS, PAPER[s]):
            cmp_rows.append(dict(state=s, variable=col, this_study=r.loc[col, "slope"], paper=pv))
    cmp = pd.DataFrame(cmp_rows)
    cmp["diff"] = cmp.this_study - cmp.paper
    cmp.to_csv(RES / "table_paper_comparison.csv", index=False)
    print("\n[35] CHECK AGAINST PAPER, 9 shared states, 1981-2005 (Tables 2 and 3, soybean)")
    for grp, vs in (("dates", STAGES), ("intervals", list(INTERVALS))):
        x = cmp[cmp.variable.isin(vs)]
        sign = (np.sign(x.this_study) == np.sign(x.paper)).mean()
        print(f"   {grp:9s} n={len(x)}  corr {x.this_study.corr(x.paper):.3f}  "
              f"mean abs diff {x['diff'].abs().mean():.3f} d/yr  sign agreement {sign:.0%}")

    plot_series(us["core9_dates"], tt)
    plot_heatmaps(tt, units)

    (RES / "config.json").write_text(json.dumps(dict(
        reference="Sacks & Kucharik 2011, Agric. For. Meteorol. 151:882-894",
        crop="soybean", states=STATES, core9=CORE9, years=[Y0, Y1],
        interpolation="PCHIP, no extrapolation", date_definition="50% completion",
        fallback_levels=FALLBACK, min_years_for_trend=MIN_YEARS,
        us_weights="mean county-summed acres_harvested, fixed across years",
        all12_first_year=all12_years,
        not_done="GDD between stages and crop modelling (paper restricts to corn: photoperiod)"), indent=2))
    print(f"\n[35] -> {RES.relative_to(ROOT)}  and  {FIG.relative_to(ROOT)}")


def plot_series(us, tt):
    fig, ax = plt.subplots(2, 2, figsize=(10, 6.5), sharex=True)
    names = dict(planted="Planted", r1="R1 (blooming)", maturity="Maturity (dropping leaves)",
                 harvested="Harvested")
    for a, st in zip(ax.ravel(), STAGES):
        d = us.dropna(subset=[st])
        a.plot(d.year, d[st], "o-", ms=3, lw=1, color="#2E6B8C")
        r = tt[(tt.unit == "US_core9") & (tt.window == "full") & (tt.variable == st)].iloc[0]
        if np.isfinite(r.slope):
            b = np.polyfit(d.year, d[st], 1)
            a.plot(d.year, np.polyval(b, d.year), "--", color="#B5483A", lw=1.4)
            a.set_title(f"{names[st]}: {r.slope:+.2f} d/yr{r.sig}", fontsize=10)
        a.set_ylabel("day of year, 50% complete")
        a.grid(alpha=0.25)
    fig.suptitle("US soybean (9-state area-weighted average), crop-progress dates", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG / "fig_us_core9_dates.png", dpi=150)
    plt.close(fig)


def plot_heatmaps(tt, units):
    full = tt[tt.window == "full"]
    fig, axs = plt.subplots(1, 2, figsize=(11, 5.6))
    for ax, (vars_, title) in zip(axs, ((STAGES, "50% dates"), (list(INTERVALS), "Interval lengths"))):
        M = np.full((len(units), len(vars_)), np.nan)
        T = [[""] * len(vars_) for _ in units]
        for i, u in enumerate(units):
            for j, v in enumerate(vars_):
                r = full[(full.unit == u) & (full.variable == v)].iloc[0]
                if np.isfinite(r.slope):
                    M[i, j] = r.slope
                    T[i][j] = f"{r.slope:+.2f}{r.sig}"
        ax.imshow(M, cmap="RdBu", vmin=-1, vmax=1, aspect="auto")
        for i in range(len(units)):
            for j in range(len(vars_)):
                ax.text(j, i, T[i][j], ha="center", va="center", fontsize=8)
        ax.set_xticks(range(len(vars_)))
        ax.set_xticklabels(vars_, fontsize=9)
        ax.set_yticks(range(len(units)))
        ax.set_yticklabels(units, fontsize=9)
        ax.set_title(f"{title}, days/yr", fontsize=10)
    fig.suptitle("Soybean crop-progress trends by state, 1980-2025 (* p<0.05, ** p<0.01, *** p<0.001)",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG / "fig_state_trends.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
