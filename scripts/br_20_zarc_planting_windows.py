"""BR 20 - Municipio x maturity-group recommended planting window, from ZARC
(br_19). This is the finest-resolution phenology-adjacent check this branch
has been able to build: real government climate-risk zoning at exactly the
municipio x cultivar-maturity-group resolution the br_05/br_10 fixed-calendar
assumption and the still-open adaptation/maturity-group analysis (US script
21 equivalent) have been missing a genuine data source for.

WHAT THE RISK CODE MEANS
  Only decades ZARC actually evaluated for a given (municipio, maturity
  group, soil class) carry a nonzero risco (20/30/40, matching the panel's
  legend: Menor Risco, Risco Medio, Maior Risco); a 0 means "not evaluated
  for sowing in this decade" -- overwhelmingly outside Sep-Dec, as expected.
  "Recommended window" here means the officially evaluated decade(s) with
  the LOWEST risk code for that municipio x group, not an assumption.

WHAT THIS DOES NOT DO
  ZARC is a risk-zoning MODEL, not an observed crop-progress series (see
  br_19's docstring) -- it tells you where/when the government's water-
  balance model says risk is lowest, not what farmers actually planted. It
  does not replace true phenology stage calibration (US scripts 23-25); it
  is the closest legitimate substitute this branch has found.
"""
import sys, json, gzip, urllib.request
import numpy as np, pandas as pd
from scipy.stats import f_oneway
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _brcfg import RAW, RES, FIG, IBGE_UF, FOCAL_MUNICIPIO, UF_NAME
from _viz import *

MONTH_NUM = dict(Jan=1, Fev=2, Mar=3, Abr=4, Mai=5, Jun=6, Jul=7, Ago=8,
                 Set=9, Out=10, Nov=11, Dez=12)
DEC_OFFSET = {"01-10": 5, "11-20": 15, "21-28": 24, "21-30": 25, "21-31": 25}  # midpoint day-of-month


def mesorregioes():
    url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{IBGE_UF}/municipios"
    req = urllib.request.Request(url, headers={"User-Agent": "research-script"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    js = json.loads(body.decode("utf-8"))
    rows = []
    for m in js:
        micro = m.get("microrregiao")
        if micro and micro.get("mesorregiao"):
            rows.append(dict(municipio=m["nome"], mesorregiao=micro["mesorregiao"]["nome"]))
    return pd.DataFrame(rows)


def main():
    d = pd.read_csv(RAW / "zarc_soja_risco.csv")
    d["month_num"] = d.mes.map(MONTH_NUM)
    d["day_in_month"] = d.decendio.map(DEC_OFFSET)
    # season day-of-year measured from 1-Sep (matches br_05/br_10/br_18's anchor),
    # wrapping Jan-Aug forward past Dec
    d["doy_raw"] = (d.month_num - 1) * 30 + d.day_in_month  # coarse 30-day-month calendar
    sep1 = (9 - 1) * 30 + 1
    d["day_from_sep1"] = np.where(d.doy_raw >= sep1, d.doy_raw - sep1, d.doy_raw - sep1 + 360)

    evaluated = d[d.risco > 0].copy()
    print(f"[br20] {len(d):,} total rows, {len(evaluated):,} with a nonzero (evaluated) risk "
          f"code ({len(evaluated) / len(d) * 100:.1f}%)")
    print("[br20] risk code distribution (evaluated rows only):")
    print(evaluated.risco.value_counts().sort_index().to_string())

    # per municipio x grupo (pooling soil classes): the recommended decade(s) are
    # those with the minimum risk code; take the mean day_from_sep1 across ties
    # and across soil classes, weighted equally
    best = (evaluated.groupby(["municipio", "grupo_maturacao"])
                     .apply(lambda g: g[g.risco == g.risco.min()].day_from_sep1.mean(),
                           include_groups=False)
                     .rename("recommended_day_from_sep1").reset_index())
    best.round(2).to_csv(RES / "br26_zarc_recommended_window.csv", index=False)

    print(f"\n[br20] recommended planting day (days after 1-Sep), by maturity group, "
          f"pooled across {best.municipio.nunique()} municipios:")
    by_group = best.groupby("grupo_maturacao").recommended_day_from_sep1.agg(["mean", "std", "count"])
    print(by_group.round(2).to_string())
    groups = [g.recommended_day_from_sep1.values for _, g in best.groupby("grupo_maturacao")]
    if len(groups) >= 2 and all(len(g) >= 3 for g in groups):
        F, p = f_oneway(*groups)
        print(f"[br20] one-way ANOVA across maturity groups: F={F:.2f}, p={p:.4f}")
        print("[br20] " + (
            "recommended planting timing differs significantly by maturity group (p<0.05) -- "
            "confirms, with official government risk-zoning data rather than an assumption, "
            "that the US script 21 (adaptation/maturity-group) question has real substance here"
            if p < .05 else
            "no significant difference in recommended timing across maturity groups at the "
            "municipio-pooled level"))
    else:
        F = p = None

    # municipio-level (pooled across groups): does the recommended window differ
    # geographically, same test as br_17/br_18
    by_muni = best.groupby("municipio").recommended_day_from_sep1.mean().rename("day_from_sep1")
    meso = mesorregioes().set_index("municipio").mesorregiao
    joined = by_muni.to_frame().join(meso, how="inner")
    print(f"\n[br20] municipio-level recommended day matched to {joined.mesorregiao.nunique()} "
          f"mesorregioes ({len(joined)} of {len(by_muni)} municipios matched)")
    by_meso = joined.groupby("mesorregiao").day_from_sep1.agg(["mean", "std", "count"]).sort_values("mean")
    print(by_meso.round(2).to_string())
    meso_groups = [g.day_from_sep1.values for _, g in joined.groupby("mesorregiao") if len(g) >= 3]
    F2 = p2 = None
    if len(meso_groups) >= 2:
        F2, p2 = f_oneway(*meso_groups)
        print(f"[br20] one-way ANOVA across mesorregioes: F={F2:.2f}, p={p2:.4f}")

    if FOCAL_MUNICIPIO.title() in by_muni.index:
        print(f"\n[br20] {FOCAL_MUNICIPIO.title()}: recommended planting day = "
              f"{by_muni.loc[FOCAL_MUNICIPIO.title()]:.1f} days after 1-Sep")

    json.dump(dict(
        source="ZARC (br_19), Censo year 2024/2025, official MAPA climate-risk zoning",
        method="Recommended decade = minimum evaluated risk code (20/30/40) per municipio x "
              "maturity group, pooled across soil classes; expressed as days after 1-Sep to "
              "match br_05/br_10/br_18's anchor",
        n_municipios=int(best.municipio.nunique()),
        by_maturity_group=by_group["mean"].round(2).to_dict(),
        maturity_group_anova=dict(F=float(F), p=float(p)) if F is not None else None,
        by_mesorregiao=by_meso["mean"].round(2).to_dict(),
        mesorregiao_anova=dict(F=float(F2), p=float(p2)) if F2 is not None else None,
        caveat="ZARC is a climate-risk model output, not observed crop progress -- see br_19"),
        open(RES / "br27_zarc_window_config.json", "w"), indent=2)

    # ---------- figure -----------------------------------------------------------
    f, axes = plt.subplots(1, 2, figsize=(12.5, 5.4), dpi=200)
    f.patch.set_facecolor(SURFACE)
    ax = axes[0]; ax.set_facecolor(SURFACE)
    gg = by_group.sort_values("mean")
    ax.barh(range(len(gg)), gg["mean"], xerr=gg["std"], color=S1, capsize=4)
    ax.set_yticks(range(len(gg))); ax.set_yticklabels(gg.index, fontsize=10)
    ax.set_xlabel("Recommended day, days after 1-Sep", fontsize=9.5, color=INK2)
    ax.set_title(f"By maturity group (ANOVA p={p:.3f})" if p is not None else "By maturity group",
                fontsize=10.5, color=INK)
    ax = axes[1]; ax.set_facecolor(SURFACE)
    bm = by_meso.sort_values("mean")
    ax.barh(range(len(bm)), bm["mean"], xerr=bm["std"].fillna(0), color=S2, capsize=4)
    ax.set_yticks(range(len(bm))); ax.set_yticklabels(bm.index, fontsize=9)
    ax.set_xlabel("Recommended day, days after 1-Sep", fontsize=9.5, color=INK2)
    ax.set_title(f"By mesorregiao (ANOVA p={p2:.3f})" if p2 is not None else "By mesorregiao",
                fontsize=10.5, color=INK)
    for ax in axes:
        ax.grid(axis="x", color=GRID, lw=.7); ax.set_axisbelow(True)
        for s_ in ("top", "right"):
            ax.spines[s_].set_visible(False)
        ax.tick_params(colors=MUTED, labelsize=8.5)
    f.suptitle(f"Figure BR-23. ZARC recommended soybean planting window, {UF_NAME.title()} 2024/25",
              fontsize=13.5, color=INK, x=.02, ha="left", y=1.08, fontweight="semibold")
    f.text(.02, .975, "Official government climate-risk zoning (not observed crop progress) -- "
          "does maturity group or geography move the recommended sowing decade?",
          fontsize=9.6, color=INK2, va="bottom")
    f.tight_layout(rect=[0, 0, 1, .88])
    f.savefig(FIG / "fig_br23_zarc_planting_window.png", facecolor=SURFACE, bbox_inches="tight")
    plt.close(f)
    print("\n[br20] wrote br26, br27, fig_br23")


if __name__ == "__main__":
    main()
