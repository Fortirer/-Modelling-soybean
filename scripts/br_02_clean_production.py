"""BR 02 - Clean IBGE municipal production data. Mirrors US script 02's
cleaning contract (sentinel handling, identity check, unit conversion).

Identity check here is producao_t / area_colhida_ha vs rendimento_kg_ha (in
t/ha, so rendimento_kg_ha/1000): IBGE publishes rendimento as its own field
rather than deriving it, same relationship the US NASS identity check
verifies for yield_bu_ac.
"""
import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _brcfg import RAW, PROC, RES, UF, IBGE_UF

def main():
    d = pd.read_csv(RAW / "ibge_pam_soja_municipios.csv",
                    dtype={"municipio_codigo": str})
    rep = {"rows_in": len(d)}

    # -- 1. require the three core measures ------------------------------------
    have_core = d[["area_colhida_ha", "producao_t", "rendimento_kg_ha"]].notna().all(axis=1)
    rep["rows_missing_core_measure"] = int((~have_core).sum())
    d = d[have_core].copy()

    # -- 2. duplicate key audit -------------------------------------------------
    dup = d.duplicated(["municipio_codigo", "ano"]).sum()
    rep["duplicate_municipio_year"] = int(dup)
    assert dup == 0, "duplicate municipio-year rows survived cleaning"

    # -- 3. zero / non-positive rows --------------------------------------------
    rep["zero_production_rows"] = int((d.producao_t == 0).sum())
    d = d[d.producao_t > 0].copy()

    # -- 4. identity check: producao_t / area_colhida_ha (t/ha) vs
    #       rendimento_kg_ha / 1000 -------------------------------------------
    implied_t_ha = d.producao_t / d.area_colhida_ha
    published_t_ha = d.rendimento_kg_ha / 1000.0
    resid = (implied_t_ha - published_t_ha).abs()
    rep["identity_checked"] = len(d)
    rep["identity_max_residual_t_ha"] = round(float(resid.max()), 4)
    rep["identity_failures_gt_0.1"] = int((resid > 0.1).sum())
    rep["harvested_gt_planted"] = int(
        (d.area_colhida_ha > d.area_plantada_ha.fillna(np.inf) + 0.5).sum())

    # -- 5. unit conversions, to match the US pipeline's column names so the
    #    same downstream logic (climate merge, detrending, ML features) can
    #    eventually be shared rather than reimplemented -------------------------
    HA_PER_ACRE, KG_PER_BU = 0.404685642, 27.2155
    d["yield_kg_ha"]       = d.rendimento_kg_ha
    d["yield_bu_ac"]       = d.rendimento_kg_ha * HA_PER_ACRE / KG_PER_BU
    d["production_tonnes"] = d.producao_t
    d["production_bu"]     = d.producao_t * 1000 / KG_PER_BU
    d["area_harvested_ha"] = d.area_colhida_ha
    d["acres_harvested"]   = d.area_colhida_ha / HA_PER_ACRE
    d["acres_planted"]     = d.area_plantada_ha / HA_PER_ACRE
    d["fips5"] = d.municipio_codigo   # IBGE 7-digit code plays the fips5 role
    d["county"] = d.municipio_nome.str.replace(r"\s*-\s*MT$", "", regex=True).str.upper()
    d["year"] = d.ano
    d["state"] = "MATO GROSSO"

    keep = ["state", "county", "municipio_codigo", "fips5", "year",
            "acres_planted", "acres_harvested", "production_bu", "yield_bu_ac",
            "yield_kg_ha", "production_tonnes", "area_harvested_ha"]
    d = d[keep].sort_values(["county", "year"]).reset_index(drop=True)
    rep.update(rows_out=len(d), municipalities=int(d.fips5.nunique()),
               year_min=int(d.year.min()), year_max=int(d.year.max()))

    out = PROC / "production_clean.csv"
    d.to_csv(out, index=False)
    (RES / "br02_cleaning_report.json").write_text(json.dumps(rep, indent=2))
    for k, v in rep.items():
        print(f"[br02] {k:32} {v}")
    print(f"[br02] -> data/processed/BR/{UF}/production_clean.csv")


if __name__ == "__main__":
    main()
