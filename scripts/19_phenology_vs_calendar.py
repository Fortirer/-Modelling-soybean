"""19 - Does a moving crop window beat a fixed calendar window? Tables 18-19,
Figures 24-25.

Script 18 replaced July-August with a phenological R3-to-leaf-drop window, both
ends calibrated to the observed NASS record (scripts 23-25), and added the
variables soybean physiology actually responds to: extreme degree days above
30 C, vapour pressure deficit, and a soil water balance. This script asks
whether any of that earns its place, under exactly the validation protocol of
script 08 -- expanding window, rolling origin, no random splits.

The comparison is deliberately unfair to the new features in one respect: the
calendar set has 20 features tuned over the life of this repo, the process set
has 13 and has never been tuned at all.

NOTE ON win_gdd. An earlier version excluded it, because with R3 and R6 defined
as fixed points on the thermal-time axis the GDD between them was a constant by
construction (543.7 +/- 6.2). The window is no longer built that way, so
win_gdd varies (sd about 91) and is included.
"""
import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.inspection import permutation_importance
from matplotlib.patches import Patch
from _cfg import FINAL, PROC, RES, FIG, SEED
from _viz import *

d = pd.read_csv(FINAL / "soybean_illinois_climate_1980_2025.csv",
                dtype={"county_ansi": str, "fips5": str})
d = d[d.in_balanced_panel == 1].copy()
ph = pd.read_csv(PROC / "phenology_features.csv", dtype={"fips5": str})

n_before = len(d)
d = d.merge(ph, on=["fips5", "year"], how="inner", validate="one_to_one")
print(f"[19] panel rows {n_before:,} -> {len(d):,} after joining phenology")
print(f"[19] years {d.year.min()}-{d.year.max()}  counties {d.county.nunique()}")
print("[19] rows lost are 1980 and 2025, outside the NASA POWER record pulled in 17")

cfg = json.load(open(RES / "08_ml_config.json"))
CALENDAR, TARGET = cfg["features"], cfg["target"]

# process-based set: nothing here is a calendar month
PROCESS = ["win_gdd", "win_edd", "win_hot_days", "win_vpd_mean", "win_vpd_max",
           "win_prcp_mm", "win_et0_mm", "win_water_deficit_mm", "win_tmax_mean",
           "wb_stress_days", "wb_min_water_frac", "wb_season_deficit_mm",
           "window_days", "season_gdd", "season_edd", "season_prcp_mm",
           "plant_doy", "end_doy"]
PROCESS = [c for c in PROCESS if c in d.columns]
print(f"[19] calendar features {len(CALENDAR)} | process features {len(PROCESS)}")


def metrics(a, p):
    e = p - a
    return dict(RMSE=float(np.sqrt((e ** 2).mean())), MAE=float(np.abs(e).mean()),
                R2=float(1 - (e ** 2).sum() / ((a - a.mean()) ** 2).sum()))


# ---------- how do the new variables relate to yield at all? ------------------
print("\n[19] CORRELATION WITH YIELD ANOMALY")
cor = (pd.DataFrame(dict(feature=PROCESS,
                         r=[float(np.corrcoef(d[c], d[TARGET])[0, 1]) for c in PROCESS]))
       .assign(abs_r=lambda x: x.r.abs()).sort_values("abs_r", ascending=False))
print(cor[["feature", "r"]].head(10).round(3).to_string(index=False))
best_cal = max(CALENDAR, key=lambda c: abs(np.corrcoef(d[c], d[TARGET])[0, 1]))
print(f"[19] strongest calendar feature: {best_cal}  "
      f"r = {np.corrcoef(d[best_cal], d[TARGET])[0, 1]:+.3f}")
cor.round(5).to_csv(RES / "table18_process_feature_correlations.csv", index=False)

# ---------- expanding-window head to head -------------------------------------
SETS = {"calendar (script 08)": CALENDAR,
        "process (script 18)": PROCESS,
        "both": CALENDAR + PROCESS}
d = d.sort_values(["county", "year"]).reset_index(drop=True)
acc, preds = [], {k: [] for k in SETS}
preds["baseline: anomaly = 0"] = []
for t in range(2001, int(d.year.max()) + 1):
    trn, tst = d[d.year < t], d[d.year == t]
    if len(tst) == 0:
        continue
    acc.append(tst[TARGET].values)
    preds["baseline: anomaly = 0"].append(np.zeros(len(tst)))
    for name, F in SETS.items():
        mdl = GradientBoostingRegressor(n_estimators=200, max_depth=3,
                                        learning_rate=.05, random_state=SEED)
        preds[name].append(mdl.fit(trn[F], trn[TARGET]).predict(tst[F]))
a = np.concatenate(acc)
T = pd.DataFrame([dict(features=k, n_features=len(SETS.get(k, [])),
                       **metrics(a, np.concatenate(v))) for k, v in preds.items()])
base = T.loc[T.features.str.startswith("baseline"), "RMSE"].iloc[0]
T["skill_vs_baseline_pct"] = ((1 - T.RMSE / base) * 100).round(2)
cal = T.loc[T.features == "calendar (script 08)", "RMSE"].iloc[0]
T["gain_vs_calendar_pct"] = ((1 - T.RMSE / cal) * 100).round(2)
T = T.sort_values("RMSE")
print(f"\n[19] EXPANDING-WINDOW VALIDATION 2001-{int(d.year.max())}  ({len(a):,} test obs)")
print(T.round(4).to_string(index=False))
T.round(5).to_csv(RES / "table19_phenology_vs_calendar.csv", index=False)

# ---------- what is carrying the combined model? ------------------------------
tr2, te2 = d[d.year < 2019], d[d.year >= 2019]
F = CALENDAR + PROCESS
mdl = GradientBoostingRegressor(n_estimators=200, max_depth=3, learning_rate=.05,
                                random_state=SEED).fit(tr2[F], tr2[TARGET])
pi = permutation_importance(mdl, te2[F], te2[TARGET], n_repeats=12,
                            random_state=SEED, n_jobs=-1)
imp = (pd.DataFrame(dict(feature=F, importance=pi.importances_mean, sd=pi.importances_std))
       .sort_values("importance", ascending=False).reset_index(drop=True))
imp["kind"] = np.where(imp.feature.isin(PROCESS), "process", "calendar")
imp.to_csv(RES / "table20_importance_process_vs_calendar.csv", index=False)
print("\n[19] permutation importance, top 14 (both sets, tested on 2019 onward)")
print(imp.head(14).round(4).to_string(index=False))
pr = imp.index[imp.kind == "process"]
if len(pr):
    print(f"[19] best process feature: {imp.feature[pr[0]]} at rank {int(pr[0])+1} of {len(F)}")
print(f"[19] process features in the top 10: {int((imp.head(10).kind=='process').sum())}")

# ---------- Figure 24: the modelled window ------------------------------------
yr = d.groupby("year").agg(end=("end_doy", "mean"), win=("window_days", "mean"),
                           edd=("win_edd", "mean")).reset_index()
f, axes = plt.subplots(1, 3, figsize=(13.5, 4.6), dpi=200)
f.patch.set_facecolor(SURFACE)
panels = [("end", yr.end, "Day of year, end of the yield window", S2),
          ("win", yr.win, "Length of the yield window (days)", S1),
          ("edd", yr.edd, "Extreme degree days >30 °C in the window", S4)]
for ax_, (_, v, yl, col) in zip(axes, panels):
    ax_.set_facecolor(SURFACE)
    ax_.plot(yr.year, v, color=col, lw=1.3, marker="o", ms=3.2)
    b = np.polyfit(yr.year, v, 1)
    ax_.plot(yr.year, np.polyval(b, yr.year), color=INK, lw=1.7, ls="--")
    ax_.text(.03, .06, f"{b[0]*10:+.2f} per decade", transform=ax_.transAxes,
             fontsize=10, color=INK2)
    ax_.grid(color=GRID, lw=.7); ax_.set_axisbelow(True)
    for s in ("top", "right"):
        ax_.spines[s].set_visible(False)
    ax_.tick_params(colors=MUTED, labelsize=8.5)
    ax_.set_ylabel(yl, fontsize=9.5, color=INK2)
    ax_.set_xlabel("Year", fontsize=9.5, color=INK2)
f.suptitle("Figure 24. The modelled yield window, 1981-2024",
           fontsize=14.5, color=INK, x=.02, ha="left", y=1.06, fontweight="semibold")
f.text(.02, .975, "State means of the calibrated model. The window ends near the observed "
       "leaf-drop date, which has not advanced over the record (Figure 32); this figure "
       "shows what the model does, not what was observed.", fontsize=9.6, color=INK2)
f.tight_layout(rect=[0, 0, 1, .91])
f.savefig(FIG / "fig24_modelled_window.png", facecolor=SURFACE, bbox_inches="tight")
plt.close(f)
print("   figure -> fig24_modelled_window.png")

# ---------- Figure 25: process vs calendar importance -------------------------
f, ax = fig(10.5, 7)
k = imp.head(16).iloc[::-1]
ax.barh(range(len(k)), k.importance, xerr=k.sd, height=.68,
        color=[S3 if v == "process" else S1 for v in k.kind],
        error_kw=dict(ecolor=MUTED, lw=.9, capsize=2.5))
ax.set_yticks(range(len(k)))
ax.set_yticklabels(k.feature, fontsize=9)
ax.grid(axis="y", lw=0); ax.grid(axis="x", color=GRID, lw=.7)
ax.legend(handles=[Patch(color=S1, label="calendar month"),
                   Patch(color=S3, label="crop process")],
          frameon=False, fontsize=9.5, labelcolor=INK2, loc="lower right")
style(ax, "Figure 25. Which description of the weather does the model use?",
      "Permutation importance on held-out years, calendar and process features "
      "competing in one model.",
      "Increase in MSE when permuted", None,
      src="Source: USDA NASS; NASA POWER; USDA-NRCS SSURGO")
save(f, FIG / "fig25_process_vs_calendar.png")

json.dump(dict(
    calendar_features=CALENDAR, process_features=PROCESS,
    excluded=dict(win_gdd="constant by construction; R3 and R6 are fixed points "
                          "on the thermal-time axis"),
    validation="expanding window, rolling origin, no random splits",
    years=[int(d.year.min()), int(d.year.max())],
    rows=int(len(d)), test_obs=int(len(a)),
), open(RES / "19_comparison_config.json", "w"), indent=2)
print("\n[19] wrote table18, table19, table20, fig24, fig25")
