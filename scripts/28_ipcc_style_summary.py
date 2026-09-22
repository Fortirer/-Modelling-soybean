"""28 - An IPCC AR6 SPM-style summary figure for the Illinois soybean projections.

Two panels, deliberately in the visual language of the AR6 WG1/WG2 Summary for
Policymakers so the figure reads instantly to anyone who has seen one of those
reports:

  (a) "Future changes" panel, styled after AR6 SPM.7 / WG2 SPM.2: one row per
      scenario x horizon, a thick bar for the interquartile-equivalent range
      (here, the 8-CMIP6-model min-max, since 8 models is too few for real
      quartiles), a marker for the median, and a paler bar behind it showing
      how far the CO2-assumption range (no CO2 to the FACE curve) can move the
      same median. This is the picture for "how much do we lose, and how much
      of the uncertainty is the emissions path versus the model versus the
      CO2 assumption."
  (b) "Observed record" warming-stripe-style panel: county-mean yield anomaly
      by year, 1981-2024, colour-mapped like an AR6/Ed Hawkins stripe plot,
      with the running 10-year mean overlaid. This is the picture for "what
      the historical record actually did," set directly above the
      projections so the reader can see the projected range against the
      observed variability it is being compared with.

Both panels are built only from files already in results/ and data/final/, so
this script has the same "generated from results, cannot drift" property as
script 27. Output: figures/fig34_ipcc_style_summary.png, 300 dpi.
"""
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from _cfg import RES, FIG, FINAL

LAB = {"ssp245": "SSP2-4.5", "ssp585": "SSP5-8.5"}
HZ = {"mid_century": "2040–69", "late_century": "2070–99"}
ORDER = [("ssp585", "late_century"), ("ssp585", "mid_century"),
         ("ssp245", "late_century"), ("ssp245", "mid_century")]
SCEN_COLOR = {"ssp245": "#E6A94E", "ssp585": "#B5453B"}   # AR6-ish amber / brick red

T21 = pd.read_csv(RES / "table21_pheno_scenario_summary.csv").set_index(["scenario", "horizon"])
T22 = pd.read_csv(RES / "table22_pheno_scenario_model_spread.csv")

pan = pd.read_csv(FINAL / "soybean_illinois_climate_1980_2025.csv", dtype={"fips5": str})
pan = pan[pan.in_balanced_panel == 1]
yearly = pan.groupby("year").yield_anom.mean()
yearly = yearly[(yearly.index >= 1981) & (yearly.index <= 2024)]

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10.5, "axes.edgecolor": "#4A4A4A",
    "axes.labelcolor": "#1F2A37", "text.color": "#1F2A37", "xtick.color": "#4A4A4A",
    "ytick.color": "#4A4A4A",
})

fig = plt.figure(figsize=(10.5, 11.2), dpi=300)
gs = fig.add_gridspec(2, 1, height_ratios=[1.35, 1], hspace=0.60, top=0.80, bottom=0.09)

# =============================================================== Panel (a) ==========
ax = fig.add_subplot(gs[0])
# Built as two stacked text objects (not ax.set_title + a second line) so the bold heading
# and the grey subtitle can use different sizes/weights without matplotlib's title linespacing
# fighting the axes above it.
ax.text(0, 1.16, "(a) Projected change in Illinois soybean yield, climate effect only",
        transform=ax.transAxes, fontsize=12.5, fontweight="bold", color="#1F2A37")
ax.text(0, 1.075, "Relative to observed 1981–2024. Median across 8 CMIP6 models, Schlenker-Roberts "
                   "specification, R3-driver window.",
        transform=ax.transAxes, fontsize=9, color="#55606B")

ypos = np.arange(len(ORDER))[::-1]
for i, (scen, hz) in enumerate(ORDER):
    y = ypos[i]
    row = T21.loc[(scen, hz)]
    spread = T22[(T22.scenario == scen) & (T22.horizon == hz)].delta_sr
    lo, hi, med = spread.min(), spread.max(), row.climate_sr_bu
    co2_lo = min(row.net_none_bu, row.net_saturating_bu, row.net_face_bu)
    co2_hi = max(row.net_none_bu, row.net_saturating_bu, row.net_face_bu)
    c = SCEN_COLOR[scen]

    # pale band: what the CO2 assumption alone can do to the same median
    ax.add_patch(mpatches.FancyBboxPatch((co2_lo, y - 0.30), co2_hi - co2_lo, 0.60,
                 boxstyle="round,pad=0,rounding_size=0.05", linewidth=0, facecolor=c, alpha=0.16))
    # main bar: 8-model min-max of the climate-only effect
    ax.plot([lo, hi], [y, y], color=c, linewidth=9, solid_capstyle="butt", alpha=0.85, zorder=3)
    ax.plot([med, med], [y - 0.34, y + 0.34], color="#1F2A37", linewidth=2.2, zorder=4)
    ax.scatter([med], [y], marker="D", s=46, color="white", edgecolor="#1F2A37", linewidth=1.3, zorder=5)

    ax.text(hi + 0.6, y, f"{med:+.1f} bu/acre  ({lo:+.1f} to {hi:+.1f})", va="center", fontsize=9.2,
            color="#1F2A37")
    oor = row.out_of_range_pct
    tag = f"  •  {oor:.0f}% of county-years beyond the observed heat record" if oor > 5 else ""
    ax.text(-33.5, y, f"{LAB[scen]}, {HZ[hz]}", va="center", ha="left", fontsize=10.3, fontweight="bold",
            color="#1F2A37")

ax.axvline(0, color="#8A8F98", linewidth=1, linestyle="-", zorder=1)
ax.set_xlim(-33.5, 26)
ax.set_ylim(-0.8, len(ORDER) - 0.2)
ax.set_yticks([])
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.set_xlabel("bu/acre, county mean  (dark bar = 8-model range of the climate effect alone;  "
              "pale band = range the CO₂ assumption alone can move the net effect)")
ax.xaxis.grid(True, color="#E4E7EB", linewidth=0.8, zorder=0)
ax.set_axisbelow(True)

leg = [mpatches.Patch(facecolor="#8A8F98", alpha=0.85, label="Climate effect, 8-model range (no CO₂ response)"),
       mpatches.Patch(facecolor="#8A8F98", alpha=0.16, label="Net effect range across 3 CO₂ assumptions "
                                                              "(none / saturating / FACE)")]
ax.legend(handles=leg, loc="lower left", frameon=False, fontsize=8.6, bbox_to_anchor=(0.0, -0.30))

# =============================================================== Panel (b) ==========
ax2 = fig.add_subplot(gs[1])
ax2.set_title("(b) Observed county-mean yield anomaly, 1981–2024, for context",
              loc="left", fontsize=12.5, fontweight="bold", pad=10)

vmax = float(np.abs(yearly.values).max())
cmap = LinearSegmentedColormap.from_list("ipcc_div", ["#7A2E27", "#F2E4C9", "#1F4E79"])
years = yearly.index.values
for yr, v in zip(years, yearly.values):
    ax2.bar(yr, 1, bottom=0, width=1.0, color=cmap((v + vmax) / (2 * vmax)), edgecolor="none")

ax3 = ax2.twinx()
roll = yearly.rolling(10, center=True, min_periods=5).mean()
ax3.plot(years, roll.values, color="#1F2A37", linewidth=2.2, label="10-yr running mean")
ax3.axhline(0, color="#1F2A37", linewidth=0.7, linestyle="--", alpha=0.6)
ax3.set_ylabel("Yield anomaly, bu/acre (line)")
ax3.set_ylim(-vmax * 1.15, vmax * 1.15)
ax2.set_ylim(0, 1)
ax2.set_yticks([])
ax2.set_xlim(years.min() - 0.5, years.max() + 0.5)
ax2.set_xlabel("Year", labelpad=8)
for s in ("top", "left"):
    ax2.spines[s].set_visible(False)
ax3.spines["top"].set_visible(False)
ax3.legend(loc="lower left", frameon=False, fontsize=9)

sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(-vmax, vmax))
cax = fig.add_axes([0.125, 0.030, 0.775, 0.016])
cb = fig.colorbar(sm, cax=cax, orientation="horizontal")
cb.set_label("Yield anomaly, bu/acre (stripe colour)", fontsize=9)
cb.ax.tick_params(labelsize=8)

fig.suptitle("Illinois soybean yield and the climate signal: projected change against observed variability",
             fontsize=14.5, fontweight="bold", y=0.975, x=0.125, ha="left")
fig.text(0.125, 0.950,
          "Panel design follows the IPCC AR6 Summary for Policymakers convention (SPM.7 / WG2 SPM.2): "
          "a range bar with a scenario-coloured band and a marked central estimate, read against the observed "
          "record. Source: scripts 20 and 05–05; all numbers read from results/ at build time.",
          fontsize=8.7, color="#55606B")

out = FIG / "fig34_ipcc_style_summary.png"
fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
print(f"[28] wrote {out}")
