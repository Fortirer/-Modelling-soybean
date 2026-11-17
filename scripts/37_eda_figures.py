"""37 - Figures for the US vs Brazil soybean EDA (reads the tables script 36 wrote).

DESIGN RULES (one visual system across all figures)
  * Identity: United States = blue #2a78d6, Brazil = orange #eb6834. Slots 1 and 2
    of a palette documented as validated for all pairs; worst-case colour-vision
    separation checked here too (OKLab dE x100 >= 24.7).
  * IPCC AR6 conventions where they apply: SSP2-4.5 = #eadd3d and SSP5-8.5 = #840b22
    (the AR6 scenario colours), model range as a bar with the median marked, and
    the AR6 robustness convention for precipitation (filled marker when at least
    80% of models agree on the sign of change, hollow otherwise).
  * Magnitude uses one blue ramp; polarity uses blue-grey-red with a grey midpoint.
  * Identity is never colour alone: states are named on the axis, legends are
    always present for two or more series, and every figure has a CSV twin in
    results/_eda_us_brazil/.
  * The AR6 yellow has only 1.4:1 contrast on the page, so scenario rows are
    direct-labelled and the exact values are in projections_state.csv.
"""
import json
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "results" / "_eda_us_brazil"
F = ROOT / "figures" / "_eda_us_brazil"
F.mkdir(parents=True, exist_ok=True)

SURF, INK, INK2, MUTED, GRID, BASE = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
C_US, C_BR = "#2a78d6", "#eb6834"
CC = {"US": C_US, "BR": C_BR}
CNAME = {"US": "United States", "BR": "Brazil"}
SSP = {"ssp245": "#eadd3d", "ssp585": "#840b22"}
SSPN = {"ssp245": "SSP2-4.5", "ssp585": "SSP5-8.5"}
SEQ = LinearSegmentedColormap.from_list("seq", ["#eef4fc", "#cde2fb", "#86b6ef", "#3987e5", "#256abf", "#184f95", "#0d366b"])
DIV = LinearSegmentedColormap.from_list("div", ["#104281", "#2a78d6", "#9ec5f4", "#f0efec", "#f4b8b0", "#e34948", "#8f1d1d"])
G1, G2, G3 = "#8f8d85", "#b9b7ae", "#dddbd3"

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 9.5, "figure.facecolor": SURF,
    "axes.facecolor": SURF, "savefig.facecolor": SURF, "text.color": INK, "axes.labelcolor": INK2,
    "xtick.color": MUTED, "ytick.color": INK2, "axes.edgecolor": BASE, "axes.linewidth": 0.8,
    "xtick.major.size": 0, "ytick.major.size": 0, "axes.titleweight": "regular",
})

# analysis window, read from script 36's config so the two never disagree
_CFG = json.loads((T / "config.json").read_text())
W0, W1 = _CFG["window"]
R0, R1 = _CFG["recent"]
A0, A1 = _CFG["area_recent"]
WIN_TXT, REC_TXT = f"{W0}-{W1}", f"{R0}-{R1}"

tab = pd.read_csv(T / "state_summary.csv")
bal = pd.read_csv(T / "audit_balance.csv")
fun = pd.read_csv(T / "audit_funnel_na.csv")
act = pd.read_csv(T / "audit_active_units_by_year.csv", index_col=0)
proj = pd.read_csv(T / "projections_state.csv")
oor = pd.read_csv(T / "exposure_out_of_range.csv")
sens = pd.read_csv(T / "sensitivity_heat_rain.csv")
ya = pd.read_csv(T / "observed_state_year_anomalies.csv")
obs = pd.read_csv(T / "observed_trends.csv")
binned = pd.read_csv(T / "binned_climate_yield.csv")
pcs = pd.read_csv(T / "pca_scores.csv", index_col=0)
load = pd.read_csv(T / "pca_loadings.csv", index_col=0)
pev = pd.read_csv(T / "pca_explained.csv", index_col=0).share
corr = pd.read_csv(T / "feature_spearman.csv", index_col=0)
panel = pd.read_csv(T / "harmonised_panel.csv.gz", usecols=["country", "state", "year", "yield_kg_ha", "balanced"])

tests = pd.read_csv(T / "country_tests.csv").set_index("key")
NAME = dict(zip(tab.state, tab.name))
CTRY = dict(zip(tab.state, tab.country))
US_ORD = tab[tab.country == "US"].sort_values("yield_recent_mean", ascending=False).state.tolist()
BR_ORD = tab[tab.country == "BR"].sort_values("yield_recent_mean", ascending=False).state.tolist()
ROWS = US_ORD + [None] + BR_ORD          # a blank row separates the countries everywhere
POS = {s: i for i, s in enumerate(ROWS) if s}
NROW = len(ROWS)


def style(ax, grid="x"):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(BASE)
    ax.spines["bottom"].set_color(BASE)
    if grid:
        ax.grid(axis=grid, color=GRID, lw=0.6)
    ax.set_axisbelow(True)


def head(fig, title, sub, y=0.985):
    h = fig.get_size_inches()[1]
    fig.text(0.012, y, title, fontsize=14.5, fontweight="bold", color=INK, va="top")
    fig.text(0.012, y - 0.36 / h, sub, fontsize=9.6, color=INK2, va="top")


def foot(fig, text):
    fig.text(0.012, 0.008, textwrap.fill(text, width=int(fig.get_size_inches()[0] * 15.5)),
             fontsize=7.6, color=MUTED, va="bottom", linespacing=1.35)


def top_legend(fig, handles, y=0.05, ncol=None):
    """Figure-level legend row beneath the axes (kept off the data and off the panel titles)."""
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, y), ncol=ncol or len(handles),
               frameon=False, fontsize=8.6, labelcolor=INK2, columnspacing=1.8, handletextpad=0.6)


def rowlabels(ax, size=9, names=True):
    ax.set_yticks(list(POS.values()))
    ax.set_yticklabels([NAME[s] if names else s for s in POS], fontsize=size)
    ax.set_ylim(NROW - 0.4, -0.6)


def group_tags(ax, x, size=8.2):
    ax.text(x, 0 - 0.9, "UNITED STATES", color=C_US, fontsize=size, fontweight="bold", va="bottom")
    ax.text(x, POS[BR_ORD[0]] - 0.9, "BRAZIL", color=C_BR, fontsize=size, fontweight="bold", va="bottom")
    ax._has_tags = True


def country_legend(ax, loc="lower right", extra=None):
    h = [Patch(color=C_US, label="United States (counties)"), Patch(color=C_BR, label="Brazil (municipios)")]
    ax.legend(handles=h + (extra or []), frameon=False, loc=loc, fontsize=8.6, labelcolor=INK2)


def save(fig, name):
    if any(getattr(a, "_has_tags", False) for a in fig.axes):      # lift panel titles clear of the country tags
        for a in fig.axes:
            t = a.get_title(loc="left")
            if t:
                a.set_title(t, loc="left", fontsize=10.5, color=INK, pad=24)
    fig.savefig(F / name, dpi=200)
    plt.close(fig)
    print(f"[37] {name}")


# ============================================================ 1. inventory
def fig1():
    fig = plt.figure(figsize=(13, 9.4))
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 1.25], left=0.12, right=0.985, top=0.855, bottom=0.115, wspace=0.07)
    ax = fig.add_subplot(gs[0])
    b = bal.set_index("state")
    for s, i in POS.items():
        c = CC[CTRY[s]]
        ax.barh(i, b.loc[s, "units_total"], height=0.62, color=c, alpha=0.28, lw=0)
        ax.barh(i, b.loc[s, "units_balanced"], height=0.62, color=c, lw=0)
        ax.text(b.loc[s, "units_total"] + 7, i, f"{int(b.loc[s, 'units_balanced'])} of {int(b.loc[s, 'units_total'])}",
                va="center", fontsize=8, color=INK2)
    rowlabels(ax)
    ax.set_xlim(0, 640)
    ax.set_xlabel(f"Counties / municipios in the {WIN_TXT} panel")
    style(ax)
    group_tags(ax, 0)
    ax.legend(handles=[Patch(color=INK2, alpha=0.3, label="All units with a record"),
                       Patch(color=INK2, label="Balanced: at least 20 of 44 years")],
              frameon=False, loc="upper right", fontsize=8.4, labelcolor=INK2)
    ax.set_title("(a) How many units, and how many are usable", loc="left", fontsize=10.5, color=INK, pad=6)

    ax2 = fig.add_subplot(gs[1])
    years = [int(c) for c in act.columns]
    M = np.full((NROW, len(years)), np.nan)
    for s, i in POS.items():
        v = act.loc[s].values.astype(float)
        M[i] = 100 * v / v.max()
    im = ax2.imshow(M, aspect="auto", cmap=SEQ, vmin=0, vmax=100, extent=(years[0] - 0.5, years[-1] + 0.5, NROW - 0.5, -0.5),
                    interpolation="nearest")
    ax2.set_yticks([])
    ax2.set_xticks(range(W0, W1 + 1, 5))
    ax2.set_xlim(years[0] - 0.5, years[-1] + 0.5)
    ax2.set_ylim(NROW - 0.4, -0.6)
    for s_ in ("top", "right", "left"):
        ax2.spines[s_].set_visible(False)
    ax2.set_title("(b) Panel structure over time: units reporting each year, as % of the state's peak", loc="left",
                  fontsize=10.5, color=INK, pad=6)
    cax = fig.add_axes([0.62, 0.078, 0.28, 0.011])
    cb = fig.colorbar(im, cax=cax, orientation="horizontal")
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=8, length=0)
    cb.set_label("% of peak number of reporting units", fontsize=8.2, color=INK2)
    us_keep = int(bal[bal.country == "US"].units_balanced_repo_rule.sum())
    us_all = int(bal[bal.country == "US"].units_total.sum())
    us_com = int(bal[bal.country == "US"].units_balanced.sum())
    fu, fb = bal[bal.country == "US"].fill_rate_all.median(), bal[bal.country == "BR"].fill_rate_all.median()
    head(fig, "Brazil's panel is still filling in; the US panel is mature and mostly complete",
         f"Median share of the unit x year grid that is filled: United States {fu:.0f}%, Brazil {fb:.0f}%. Brazilian municipios enter as soybeans expand into them.")
    foot(fig, f"The repo's own US rule (at least 42 of 44 years) keeps {us_keep} of {us_all} US units; the common 20-year rule used here keeps {us_com}. "
              "Sources: USDA NASS county records; IBGE PAM municipal records.")
    save(fig, "fig01_data_inventory_balance.png")


# ====================================================== 2. missingness
def fig2():
    fig = plt.figure(figsize=(13, 9.4))
    gs = fig.add_gridspec(1, 2, left=0.12, right=0.985, top=0.855, bottom=0.17, wspace=0.07)
    b = bal.set_index("state")
    ax = fig.add_subplot(gs[0])
    parts = [("Observed, balanced units", "#256abf"), ("Observed, other units", "#9ec5f4"),
             ("Missing: before first record (late entry)", G1), ("Missing: after last record (exit)", G2),
             ("Missing: internal gap", G3)]
    for s, i in POS.items():
        r = b.loc[s]
        grid = r.units_total * 44
        obs_bal, obs_oth = r.rows_balanced, r.rows_total - r.rows_balanced
        miss = r.missing_cells
        vals = [obs_bal, obs_oth, miss * r.miss_late_entry_pct / 100, miss * r.miss_exit_pct / 100,
                miss * r.miss_internal_gap_pct / 100]
        left = 0
        for (lab, col), v in zip(parts, vals):
            w = 100 * v / grid
            ax.barh(i, w - 0.35 if w > 0.7 else w, left=left, height=0.62, color=col, lw=0)
            left += w
    rowlabels(ax)
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of the full unit x year grid (units x 44 years)")
    style(ax)
    group_tags(ax, 0)
    ax.legend(handles=[Patch(color=c, label=l) for l, c in parts], frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.07), ncol=2, fontsize=8.2, labelcolor=INK2)
    ax.set_title("(a) Why cells are empty: structure, not random loss", loc="left", fontsize=10.5, color=INK, pad=6)

    ax2 = fig.add_subplot(gs[1])
    f = fun.set_index("state")
    parts2 = [("Retained in balanced panel", "#256abf"), ("Lost: unit has under 20 years", G1),
              ("Lost: no climate match", G2), ("Lost: NA / suppressed value", G3)]
    for s, i in POS.items():
        r = f.loc[s]
        v = [r.balanced_rows, r.lost_unbalanced, r.lost_no_climate_match, r.lost_na_or_suppressed]
        left = 0
        for (lab, col), x in zip(parts2, v):
            w = 100 * x / r.raw_rows
            ax2.barh(i, w - 0.3 if w > 0.7 else w, left=left, height=0.62, color=col, lw=0)
            left += w
        ax2.text(101, i, f"{100 * r.balanced_rows / r.raw_rows:.0f}%", va="center", fontsize=8, color=INK2)
    ax2.set_yticks([])
    ax2.set_ylim(NROW - 0.4, -0.6)
    ax2.set_xlim(0, 106)
    ax2.set_xlabel(f"% of reported unit-years ({WIN_TXT})")
    style(ax2)
    ax2.legend(handles=[Patch(color=c, label=l) for l, c in parts2], frameon=False, loc="upper center",
               bbox_to_anchor=(0.5, -0.07), ncol=2, fontsize=8.2, labelcolor=INK2)
    ax2.set_title("(b) What is lost between the raw record and the analysis panel", loc="left", fontsize=10.5, color=INK, pad=6)
    na_max = max(fun.na_yield.max(), fun.na_area_harvested.max())
    head(fig, "Missing data is structural, not suppression: late entry in Brazil, gaps and exits in the US",
         f"Raw files hold almost no NA (at most {na_max:.1f}% of rows); the gaps are unit-years where the crop was not reported at all.")
    foot(fig, "Late entry = before a unit's first record; exit = after its last; internal gap = a missing year between two records. "
              "US 'county estimate' flag is 99-100% in every state, so it does not discriminate. Right-hand labels: share of reported records retained.")
    save(fig, "fig02_missingness_attrition.png")


# ====================================================== 3. distributions
def fig3():
    fig = plt.figure(figsize=(13, 9.4))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.15, 1], left=0.12, right=0.985, top=0.855, bottom=0.145, wspace=0.07)
    ax = fig.add_subplot(gs[0])
    rec = panel[(panel.year >= R0) & (panel.year <= R1)]
    t = tab.set_index("state")
    for s, i in POS.items():
        v = rec[rec.state == s].yield_kg_ha.dropna().values
        if len(v) < 5:
            continue
        c = CC[CTRY[s]]
        lo_, hi_ = np.percentile(v, [1, 99])
        vp = ax.violinplot([v[(v >= lo_) & (v <= hi_)]], positions=[i], orientation="horizontal", widths=0.85,
                           showextrema=False, bw_method=0.25)
        for body in vp["bodies"]:
            body.set_facecolor(c)
            body.set_alpha(0.32)
            body.set_edgecolor("none")
        p10, p50, p90 = np.percentile(v, [10, 50, 90])
        ax.plot([p10, p90], [i, i], color=c, lw=2.2, solid_capstyle="round")
        ax.scatter([p50], [i], s=22, color=SURF, edgecolor=c, linewidth=1.6, zorder=4)
        ax.scatter([t.loc[s, "yield_recent_p95"]], [i], marker="D", s=24, color=c, edgecolor=SURF, linewidth=1.2, zorder=5)
    rowlabels(ax)
    ax.set_xlim(500, 6000)
    ax.set_xlabel(f"Soybean yield, kg/ha (unit-years, {REC_TXT})")
    style(ax)
    group_tags(ax, 500)
    top_legend(fig, [Line2D([0], [0], color=INK2, lw=2.2, label="P10 to P90"),
                     Line2D([0], [0], marker="o", color="none", markerfacecolor=SURF, markeredgecolor=INK2, label="Median", markersize=6),
                     Line2D([0], [0], marker="D", color="none", markerfacecolor=INK2, markeredgecolor=SURF, label="P95: attainable-yield proxy", markersize=6),
                     Line2D([0], [0], marker="o", color="none", markerfacecolor=INK2, markeredgecolor=SURF, label="Mean (panel b)", markersize=7)])
    ax.set_title("(a) Distribution across counties and years", loc="left", fontsize=10.5, color=INK, pad=6)

    ax2 = fig.add_subplot(gs[1])
    for s, i in POS.items():
        c = CC[CTRY[s]]
        m, p95 = t.loc[s, "yield_recent_mean"], t.loc[s, "yield_recent_p95"]
        ax2.plot([m, p95], [i, i], color=c, lw=2.2, alpha=0.5, solid_capstyle="round")
        ax2.scatter([m], [i], s=34, color=c, edgecolor=SURF, linewidth=1.4, zorder=4)
        ax2.scatter([p95], [i], marker="D", s=30, color=c, edgecolor=SURF, linewidth=1.2, zorder=4)
        ax2.text(p95 + 70, i, f"{t.loc[s, 'efficiency_pct']:.0f}%", va="center", fontsize=8, color=INK2)
    ax2.set_yticks([])
    ax2.set_ylim(NROW - 0.4, -0.6)
    ax2.set_xlim(1500, 5400)
    ax2.set_xlabel("kg/ha")
    style(ax2)
    ax2.set_title("(b) Gap to the proxy; label = mean as % of P95", loc="left", fontsize=10.5, color=INK, pad=6)
    us_e, br_e = t[t.country == "US"].efficiency_pct.median(), t[t.country == "BR"].efficiency_pct.median()
    head(fig, "Yield levels and potential overlap between the two countries; the gap to the best units is similar",
         f"Median mean-as-%-of-P95: United States {us_e:.0f}%, Brazil {br_e:.0f}% (no significant difference after Holm correction).")
    foot(fig, "P95 across county/municipio-years in each state is a statistical frontier, not an agronomic yield potential. "
              "IBGE yields are rounded to 100 kg/ha, so several Brazilian P95 values tie. Bahia (9 units) and Maranhao (24) are thin samples.")
    save(fig, "fig03_yield_distribution_potential.png")


# ================================================ 4. potential vs risk
def fig4():
    fig = plt.figure(figsize=(13, 7.4))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.3, 1], left=0.07, right=0.985, top=0.83, bottom=0.115, wspace=0.18)
    ax = fig.add_subplot(gs[0])
    x, y = tab.yield_recent_p95, tab.anom_sd_pct
    mx, my = x.median(), y.median()
    ax.axvline(mx, color=GRID, lw=1)
    ax.axhline(my, color=GRID, lw=1)
    for _, r in tab.iterrows():
        ax.scatter(r.yield_recent_p95, r.anom_sd_pct, s=np.sqrt(max(r.area_recent_kha, 5)) * 9, color=CC[r.country],
                   alpha=0.85, edgecolor=SURF, linewidth=1.4, zorder=3)
        ax.annotate(r.state + ("*" if r.n_units_balanced < 30 else ""), (r.yield_recent_p95, r.anom_sd_pct),
                    xytext=(6, 5), textcoords="offset points", fontsize=8.4, color=INK2)
    ax.set_xlabel(f"Attainable-yield proxy: P95 of unit-year yields, {REC_TXT} (kg/ha)")
    ax.set_ylabel("Instability: SD of yield anomaly (% of trend)")
    ax.text(0.99, 0.02, "higher potential, steadier", transform=ax.transAxes, ha="right", fontsize=8.6, color=MUTED, style="italic")
    style(ax, "both")
    qs = [int(float(f"{v:.2g}")) for v in np.percentile(tab.area_recent_kha, [10, 50, 90])]
    sz = [Line2D([0], [0], marker="o", color="none", markerfacecolor=MUTED, markeredgecolor=SURF,
                 markersize=np.sqrt(np.sqrt(a) * 9), label=f"{a:,} thousand ha") for a in qs]
    country_legend(ax, "upper left", sz)
    ax.set_title(f"(a) Potential against stability; bubble = harvested area {A0}-{A1 % 100}", loc="left", fontsize=10.5, color=INK, pad=6)

    ax2 = fig.add_subplot(gs[1])
    n_bal = dict(zip(tab.state, tab.n_units_balanced))
    t = tab.sort_values(["country", "trend_rel_pct_yr"], ascending=[False, True]).reset_index(drop=True)
    pos, gap = {}, 0
    for i, r in t.iterrows():
        if i > 0 and r.country != t.loc[i - 1, "country"]:
            gap += 1
        pos[r.state] = i + gap
    for _, r in t.iterrows():
        yv = pos[r.state]
        ax2.barh(yv, r.trend_rel_pct_yr, height=0.62, color=CC[r.country], lw=0)
        ax2.text(r.trend_rel_pct_yr + 0.06, yv, f"{r.trend_rel_pct_yr:.1f}", va="center", fontsize=8, color=INK2)
    ax2.set_yticks(list(pos.values()))
    ax2.set_yticklabels([NAME[s] + ("*" if n_bal.get(s, 99) < 30 else "") for s in pos], fontsize=8.6)
    ax2.set_ylim(max(pos.values()) + 0.6, -0.8)
    ax2.set_xlabel(f"Yield trend, % of mean per year (balanced units, {WIN_TXT})")
    style(ax2)
    ax2.set_title("(b) Brazil is gaining faster from a similar level", loc="left", fontsize=10.5, color=INK, pad=6)
    tr = tests.loc["trend_rel_pct_yr"]
    p95, sd = tests.loc["yield_recent_p95"], tests.loc["anom_sd_pct"]
    head(fig, f"Similar potential and volatility, but Brazil's yields have grown about {tr.br_median / tr.us_median:.1f} times faster",
         f"Median relative trend: Brazil {tr.br_median:.1f} %/yr vs United States {tr.us_median:.1f} %/yr (Mann-Whitney, Holm-adjusted p = {tr.p_holm:.3f}). "
         f"Potential (p = {p95.p_holm:.2f}) and volatility (p = {sd.p_holm:.2f}) do not differ.")
    foot(fig, "Quadrant lines at the 22-state median. Trends use balanced-panel unit means, which avoids composition effects from Brazil's expansion into new municipios. "
              "* Fewer than 30 balanced units (Bahia 9, Maranhao 24): read as indicative only.")
    save(fig, "fig04_potential_vs_stability_trend.png")


# ===================================================== 5. stripes
def stripes(ax, wide, vmin, vmax, cmap, years, right_labels=None):
    M = np.full((NROW, len(years)), np.nan)
    for s, i in POS.items():
        if s in wide.index:
            M[i] = wide.loc[s].reindex(years).values
    cm = cmap.copy()
    cm.set_bad(SURF)
    im = ax.imshow(M, aspect="auto", cmap=cm, norm=TwoSlopeNorm(vmin=vmin, vcenter=0, vmax=vmax),
                   extent=(years[0] - 0.5, years[-1] + 0.5, NROW - 0.5, -0.5), interpolation="nearest")
    ax.set_xticks(range(W0, W1 + 1, 5))
    ax.set_xlim(years[0] - 0.5, years[-1] + 0.5)
    ax.set_ylim(NROW - 0.4, -0.6)
    for s_ in ("top", "right", "left", "bottom"):
        ax.spines[s_].set_visible(False)
    ax.tick_params(axis="x", labelsize=8)
    if right_labels:
        for s, i in POS.items():
            ax.text(years[-1] + 1.2, i, right_labels.get(s, ""), va="center", fontsize=8, color=INK2)
    return im


def fig5():
    years = list(range(W0, W1 + 1))
    fig = plt.figure(figsize=(14, 9.6))
    gs = fig.add_gridspec(1, 2, left=0.115, right=0.975, top=0.855, bottom=0.135, wspace=0.17)
    ax = fig.add_subplot(gs[0])
    w = ya.pivot(index="state", columns="year", values="tmax_anom_c")
    o = obs.set_index("state")
    lab = {s: f"{o.loc[s, 'tmax_trend_c_decade']:+.2f}" + ("*" if o.loc[s, "tmax_trend_p"] < 0.05 else "") for s in POS}
    im = stripes(ax, w, -2.2, 2.2, DIV, years, lab)
    rowlabels(ax)
    group_tags(ax, years[0] - 0.5)
    ax.set_title("(a) Critical-window maximum temperature anomaly (deg C vs unit mean)", loc="left", fontsize=10.2, color=INK, pad=6)
    ax.text(years[-1] + 1.2, -0.9, "deg C/decade", fontsize=7.8, color=MUTED)
    cax = fig.add_axes([0.14, 0.088, 0.22, 0.011])
    cb = fig.colorbar(im, cax=cax, orientation="horizontal")
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=8, length=0)
    cb.set_label("deg C: blue cooler, red warmer than the unit's own mean", fontsize=8, color=INK2)

    ax2 = fig.add_subplot(gs[1])
    w2 = ya.pivot(index="state", columns="year", values="yield_anom_pct")
    im2 = stripes(ax2, w2, -30, 30, DIV.reversed(), years)
    ax2.set_yticks([])
    ax2.set_title("(b) Yield anomaly (% of trend): blue above trend, red below", loc="left", fontsize=10.2, color=INK, pad=6)
    cax2 = fig.add_axes([0.575, 0.088, 0.22, 0.011])
    cb2 = fig.colorbar(im2, cax=cax2, orientation="horizontal")
    cb2.outline.set_visible(False)
    cb2.ax.tick_params(labelsize=8, length=0)
    cb2.set_label("% of unit trend", fontsize=8, color=INK2)
    nsig_br = int((obs[(obs.country == "BR")].tmax_trend_p < 0.05).sum())
    nsig_us = int((obs[(obs.country == "US")].tmax_trend_p < 0.05).sum())
    head(fig, f"Observed peak-season heat: {nsig_br} of 10 Brazilian states warm significantly, {nsig_us} of 12 US states do",
         f"State means of unit anomalies, {WIN_TXT}; significant trends (p<0.05) are marked * in the right-hand column.")
    foot(fig, "Caution: US temperatures come from NOAA nClimDiv station-based data, Brazil's from MERRA-2 reanalysis via NASA POWER, and the windows differ "
              "(July-August vs January-February). Cross-country trend differences may reflect the data source.")
    save(fig, "fig05_observed_warming_stripes.png")


# ============================================= 6/7. IPCC-style projections
def proj_fig(var, lo, hi, fname, title, sub, xlabel, xlim, agree=False):
    fig, axs = plt.subplots(1, 2, figsize=(13, 9.6), sharey=True)
    fig.subplots_adjust(left=0.12, right=0.985, top=0.855, bottom=0.165, wspace=0.05)
    for ax, hz, hzn in zip(axs, ("mid_century", "late_century"), ("2040-2069", "2070-2099")):
        for s, i in POS.items():
            for k, (sc, off) in enumerate((("ssp245", -0.17), ("ssp585", 0.17))):
                r = proj[(proj.state == s) & (proj.scenario == sc) & (proj.horizon == hz)].iloc[0]
                ax.plot([r[lo], r[hi]], [i + off, i + off], color=SSP[sc], lw=6.2, solid_capstyle="butt", zorder=3)
                robust = True if not agree else (r.pr_agree_pct >= 80)
                ax.scatter([r[var]], [i + off], marker="D", s=26, zorder=5, linewidth=1.3,
                           facecolor=SURF if not robust else INK, edgecolor=INK)
        ax.axvline(0, color=BASE, lw=0.9)
        ax.set_xlim(*xlim)
        ax.set_xlabel(xlabel)
        style(ax)
        ax.set_title(f"Mid-century {hzn}" if hz == "mid_century" else f"Late century {hzn}", loc="left", fontsize=10.5, color=INK, pad=6)
    rowlabels(axs[0])
    group_tags(axs[0], xlim[0])
    h = [Patch(color=SSP["ssp245"], label="SSP2-4.5 (intermediate emissions)"), Patch(color=SSP["ssp585"], label="SSP5-8.5 (very high emissions)"),
         Line2D([0], [0], marker="D", color="none", markerfacecolor=INK, markeredgecolor=INK, markersize=6, label="Median of 8 CMIP6 models" + (" (>=80% of models agree on sign)" if agree else ""))]
    if agree:
        h.append(Line2D([0], [0], marker="D", color="none", markerfacecolor=SURF, markeredgecolor=INK, markersize=6, label="Median, models disagree on sign"))
    top_legend(fig, h)
    head(fig, title, sub)
    foot(fig, "Bar = range across 8 CMIP6 models (ACCESS-ESM1-5, CanESM5, EC-Earth3, GFDL-ESM4, INM-CM5-0, MIROC6, MPI-ESM1-2-LR, MRI-ESM2-0), change vs 1985-2014. "
              "Area-weighted by harvested area. Critical window: July-August (US), January-February (Brazil). Min-max of 8 models is not an IPCC 'likely' range.")
    save(fig, fname)


def fig67():
    t585 = proj[(proj.scenario == "ssp585") & (proj.horizon == "late_century")].set_index("state")
    us_m = t585[t585.country == "US"].dT_med.median()
    br_m = t585[t585.country == "BR"].dT_med.median()
    ph = tests.loc["dT_ssp585_late"].p_holm
    proj_fig("dT_med", "dT_min", "dT_max", "fig06_ipcc_style_warming_projection.png",
             "Projected peak-season warming is larger in the US Midwest than in Brazil's soybean belt",
             f"SSP5-8.5, late century, median across states: United States +{us_m:.1f} deg C, Brazil +{br_m:.1f} deg C (Holm-adjusted p = {ph:.3f}).",
             "Change in critical-window maximum temperature (deg C)", (0, float(np.ceil(proj.dT_max.max() * 1.05))))
    n_disagree = int(((proj.pr_agree_pct < 80)).sum())
    lim = float(np.ceil(max(abs(proj.pr_min).max(), abs(proj.pr_max).max()) * 1.05))
    proj_fig("pr_med", "pr_min", "pr_max", "fig07_ipcc_style_precipitation_agreement.png",
             f"Precipitation change: {n_disagree} of {len(proj)} state projections fall short of 80% model agreement on the sign",
             "Hollow markers mark projections where fewer than 80% of the 8 models agree on the direction of change (the AR6 robustness convention).",
             "Change in critical-window precipitation (%)", (-lim, lim), agree=True)


# ==================================================== 8. risk framing
def fig8():
    fig = plt.figure(figsize=(13, 7.6))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.15, 1], left=0.075, right=0.985, top=0.83, bottom=0.185, wspace=0.28)
    ax = fig.add_subplot(gs[0])
    ax.axhline(0, color=BASE, lw=0.9)
    for _, r in tab.iterrows():
        c = CC[r.country]
        ax.plot([r.oor_ssp585_late] * 2, [r.heat_lo, r.heat_hi], color=c, lw=1.1, alpha=0.5, zorder=2)
        ax.scatter(r.oor_ssp585_late, r.heat_pct_per_c, s=np.sqrt(max(r.area_recent_kha, 5)) * 9, color=c, alpha=0.88,
                   edgecolor=SURF, linewidth=1.4, zorder=3)
        off = {"BA": (9, -14), "GO": (-20, 8), "MI": (9, -2), "ND": (9, -7), "OH": (9, 6), "SD": (-22, -13),
               "IN": (9, -13), "IL": (-20, -15), "MA": (7, 6)}.get(r.state, (6, 5))
        ax.annotate(r.state, (r.oor_ssp585_late, r.heat_pct_per_c), xytext=off, textcoords="offset points", fontsize=8.4, color=INK2)
    ax.set_xlabel(f"Hazard: unit-years above the {WIN_TXT} record under SSP5-8.5 late century (%)")
    ax.set_ylabel("Vulnerability: yield change per +1 deg C (%, 95% CI)")
    ax.text(0.99, 0.02, "higher hazard, yield falls with heat", transform=ax.transAxes, ha="right", fontsize=8.6, color="#9e2a2b", style="italic")
    ax.text(0.01, 0.98, "lower hazard, yield rises with heat", transform=ax.transAxes, va="top", fontsize=8.6, color=MUTED, style="italic")
    style(ax, "both")
    ax.set_title("(a) AR6 risk framing: hazard x vulnerability, exposure = bubble size", loc="left", fontsize=10.5, color=INK, pad=6)

    ax2 = fig.add_subplot(gs[1])
    for s, i in POS.items():
        for sc, off in (("ssp245", -0.17), ("ssp585", 0.17)):
            r = oor[(oor.state == s) & (oor.scenario == sc) & (oor.horizon == "late_century")].iloc[0]
            ax2.plot([r.out_of_range_pct_min, r.out_of_range_pct_max], [i + off] * 2, color=SSP[sc], lw=6.2, solid_capstyle="butt")
            ax2.scatter([r.out_of_range_pct_med], [i + off], marker="D", s=24, facecolor=INK, edgecolor=INK, zorder=5)
    rowlabels(ax2, 8.6)
    ax2.set_xlim(0, 100)
    ax2.set_xlabel(f"Unit-years hotter than any in the {WIN_TXT} record (%)")
    style(ax2)
    group_tags(ax2, 0, 7.8)
    fig.legend(handles=[Patch(color=C_US, label="United States (counties)"), Patch(color=C_BR, label="Brazil (municipios)"),
                        Patch(color=SSP["ssp245"], label="SSP2-4.5 (panel b)"), Patch(color=SSP["ssp585"], label="SSP5-8.5 (panel b)"),
                        Line2D([0], [0], marker="D", color="none", markerfacecolor=INK, markeredgecolor=INK, markersize=6, label="Model median (panel b)")],
               loc="lower center", bbox_to_anchor=(0.5, 0.05), ncol=5, frameon=False, fontsize=8.6, labelcolor=INK2, columnspacing=1.8)
    ax2.set_title("(b) Late century: how often the record is exceeded", loc="left", fontsize=10.5, color=INK, pad=6)
    o = tests.loc["oor_ssp585_late"]
    head(fig, f"Under SSP5-8.5 a median {o.us_median:.0f}% of US unit-years exceed the historical record, against {o.br_median:.0f}% in Brazil",
         "Hazard compares projected warming with each unit's own historical maximum. Vulnerability is the observed yield response to heat (shared specification).")
    foot(fig, "Vulnerability = coefficient on critical-window Tmax anomaly in a regression with rainfall control, unit-clustered 95% CI. Historical sensitivity, not a forecast: no adaptation, "
              "cultivar change or CO2 effect is assumed.")
    save(fig, "fig08_risk_hazard_vulnerability_exposure.png")


# ===================================================== 9. forest plot
def fig9():
    fig, axs = plt.subplots(1, 2, figsize=(13, 9.4), sharey=True)
    fig.subplots_adjust(left=0.12, right=0.985, top=0.855, bottom=0.09, wspace=0.06)
    for ax, term, xl, ttl in ((axs[0], "heat_pct_per_c", "Yield change per +1 deg C of critical-window Tmax (%)", "(a) Heat"),
                              (axs[1], "rain_pct_per_100mm", "Yield change per +100 mm of critical-window rainfall (%)", "(b) Rainfall")):
        ax.axvline(0, color=BASE, lw=0.9)
        for s, i in POS.items():
            c = CC[CTRY[s]]
            for spec, off, hollow in (("no_FE", -0.14, False), ("year_FE", 0.16, True)):
                r = sens[(sens.state == s) & (sens.term == term) & (sens.spec == spec)]
                if r.empty:
                    continue
                r = r.iloc[0]
                ax.plot([r.lo, r.hi], [i + off] * 2, color=c, lw=1.5, alpha=0.75)
                ax.scatter([r.coef], [i + off], s=30, marker="D" if hollow else "o", facecolor=SURF if hollow else c,
                           edgecolor=c, linewidth=1.5, zorder=4)
        ax.set_xlabel(xl)
        style(ax)
        ax.set_title(ttl, loc="left", fontsize=10.5, color=INK, pad=6)
    rowlabels(axs[0])
    group_tags(axs[0], axs[0].get_xlim()[0])
    axs[1].legend(handles=[Line2D([0], [0], marker="o", color=INK2, markerfacecolor=INK2, markersize=6, label="No year effects"),
                           Line2D([0], [0], marker="D", color=INK2, markerfacecolor=SURF, markersize=6, label="With year effects")],
                  frameon=False, loc="lower right", fontsize=8.4, labelcolor=INK2)
    a = sens[(sens.state == "ALL") & (sens.spec == "no_FE") & (sens.term == "heat_pct_per_c")].set_index("country")
    h = sens[(sens.state != "ALL") & (sens.spec == "no_FE") & (sens.term == "heat_pct_per_c") & (sens.p < 0.05)]
    cnt = {(c, sg): int(((h.country == c) & ((h.coef < 0) == (sg == "neg"))).sum()) for c in ("US", "BR") for sg in ("neg", "pos")}
    hh = sens[(sens.state != "ALL") & (sens.term == "heat_pct_per_c")].pivot_table(index=["country", "state"], columns="spec", values="coef")
    flips = (np.sign(hh.no_FE) != np.sign(hh.year_FE)).groupby(level="country").sum()
    head(fig, f"Heat lowers yield significantly in {cnt[('US', 'neg')]} of 12 US states and {cnt[('BR', 'neg')]} of 10 Brazilian states; it raises it in {cnt[('US', 'pos')]} and {cnt[('BR', 'pos')]}",
         f"Pooled heat effect without year effects: United States {a.loc['US', 'coef']:+.1f}%/deg C, Brazil {a.loc['BR', 'coef']:+.1f}%/deg C. "
         f"The sign changes when year effects are added in {int(flips['US'])} of 12 US and {int(flips['BR'])} of 10 Brazilian states, so positive heat effects are not robust.")
    foot(fig, "Yield anomaly (% of unit trend) on Tmax and rainfall anomalies, unit-clustered 95% CI. Year effects absorb shocks common to all units in a year, "
              "so they isolate cross-unit variation and are noisier. Balanced units only (at least 20 years).")
    save(fig, "fig09_heat_rain_sensitivity_forest.png")


# ================================================= 10. binned scatter
def fig10():
    fig, axs = plt.subplots(1, 2, figsize=(12.5, 5.6), sharey=True)
    fig.subplots_adjust(left=0.07, right=0.985, top=0.80, bottom=0.14, wspace=0.06)
    for ax, drv, xl, ttl in ((axs[0], "heat", "Critical-window Tmax anomaly (deg C vs unit mean)", "(a) Heat"),
                             (axs[1], "rain", "Critical-window rainfall anomaly (% of unit mean)", "(b) Rainfall")):
        ax.axhline(0, color=BASE, lw=0.9)
        ax.axvline(0, color=BASE, lw=0.9)
        for c in ("US", "BR"):
            b = binned[(binned.country == c) & (binned.driver == drv)].sort_values("bin")
            ax.fill_between(b.bin, b.q25, b.q75, color=CC[c], alpha=0.14, lw=0)
            ax.plot(b.bin, b["median"], color=CC[c], lw=2, marker="o", ms=4.5, mfc=CC[c], mec=SURF)
        ax.set_xlabel(xl)
        style(ax, "both")
        ax.set_title(ttl, loc="left", fontsize=10.5, color=INK, pad=6)
    axs[0].set_ylabel("Yield anomaly (% of trend), median and IQR")
    country_legend(axs[1], "lower right")
    hot = binned[(binned.driver == "heat") & (binned.bin >= 2)]
    wm = {c: np.average(g["median"], weights=g.n) for c, g in hot.groupby("country")}
    head(fig, f"In units running 2 deg C or more above normal, the median yield anomaly is {wm['US']:+.0f}% in the US and {wm['BR']:+.0f}% in Brazil",
         "Binned medians of unit-year yield anomalies against critical-window heat and rainfall anomalies; bins with fewer than 30 unit-years are dropped.", y=0.985)
    foot(fig, f"Balanced panel, {WIN_TXT}. Anomalies are deviations from each unit's own mean; the shaded band is the interquartile range within each bin. "
              "Raw associations: each panel ignores the other driver, so neither curve isolates one cause (the regression in figure 9 does control for rainfall).")
    save(fig, "fig10_climate_yield_binned.png")


# =========================================================== 11. PCA
def fig11():
    fig = plt.figure(figsize=(13.5, 6.8))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.1, 1], left=0.06, right=0.95, top=0.82, bottom=0.2, wspace=0.14)
    ax = fig.add_subplot(gs[0])
    ax.axhline(0, color=GRID, lw=0.9)
    ax.axvline(0, color=GRID, lw=0.9)
    for s, r in pcs.iterrows():
        ax.scatter(r.PC1, r.PC2, s=80, color=CC[CTRY[s]], edgecolor=SURF, linewidth=1.4, zorder=3)
        ax.annotate(s, (r.PC1, r.PC2), xytext=(6, 5), textcoords="offset points", fontsize=8.4, color=INK2)
    sc = 0.55 * max(abs(pcs.PC1).max(), abs(pcs.PC2).max()) / max(abs(load.PC1).max(), abs(load.PC2).max())
    short = {"yield_recent_mean": "mean yield", "yield_recent_p95": "P95 yield", "efficiency_pct": "mean/P95", "anom_sd_pct": "instability",
             "trend_rel_pct_yr": "yield trend", "tmax_mean_c": "Tmax", "pcp_crit_mean_mm": "rainfall", "heat_pct_per_c": "heat effect",
             "dT_ssp585_late": "warming SSP5-8.5", "share_units_balanced": "balanced %"}
    for f_, r in load.iterrows():
        ax.annotate("", xy=(r.PC1 * sc, r.PC2 * sc), xytext=(0, 0), arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=0.9, alpha=0.8))
        ax.text(r.PC1 * sc * 1.08, r.PC2 * sc * 1.08, short.get(f_, f_), fontsize=7.8, color=MUTED, ha="center", va="center")
    ax.set_xlabel(f"PC1 ({100 * pev['PC1']:.0f}% of variance)")
    ax.set_ylabel(f"PC2 ({100 * pev['PC2']:.0f}% of variance)")
    style(ax, "both")
    country_legend(ax, "lower left")
    ax.set_title("(a) States in feature space (PCA of 10 standardised features)", loc="left", fontsize=10.5, color=INK, pad=6)

    ax2 = fig.add_subplot(gs[1])
    names = [short.get(c, c) for c in corr.columns]
    im = ax2.imshow(corr.values, cmap=DIV.reversed(), vmin=-1, vmax=1)
    ax2.set_xticks(range(len(names)))
    ax2.set_xticklabels(names, rotation=45, ha="right", fontsize=8)
    ax2.set_yticks(range(len(names)))
    ax2.set_yticklabels(names, fontsize=8)
    for i in range(len(names)):
        for j in range(len(names)):
            v = corr.values[i, j]
            ax2.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=6.8, color=SURF if abs(v) > 0.65 else INK2)
    for s_ in ax2.spines.values():
        s_.set_visible(False)
    ax2.tick_params(length=0)
    cb = fig.colorbar(im, ax=ax2, fraction=0.04, pad=0.02)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=7.5, length=0)
    ax2.set_title("(b) Spearman correlation between state features (n = 22)", loc="left", fontsize=10.5, color=INK, pad=6)
    head(fig, "Where the 22 states sit in feature space", f"The first two components explain {100 * (pev['PC1'] + pev['PC2']):.0f}% of the variance across the 22 states.")
    foot(fig, "Features are standardised across states; missing values filled with the feature median. Exploratory structure, with 22 states and 10 features: do not read clusters as findings. "
              "Some features are mechanically linked (mean/P95 with instability, yield trend with panel maturity), so strong correlations between them are expected.")
    save(fig, "fig11_structure_pca_correlation.png")


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    fig4()
    fig5()
    fig67()
    fig8()
    fig9()
    fig10()
    fig11()
