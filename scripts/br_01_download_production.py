"""BR 01 - Acquire IBGE municipal soybean production for one Brazilian state.

Source: IBGE SIDRA, tabela 1612 (Producao Agricola Municipal - PAM), which is
the direct analogue of the USDA NASS county table the US pipeline's script 01
downloads: for every municipality, area planted, area harvested, quantity
produced and average yield, one row per year per product. Filtered here to
produto 2713 "Soja (em grao)" and to every municipality in one state via
SIDRA's "n6/in n3 <uf>" query syntax.

No API key. One request per state returns every municipality x year x
variable at once (confirmed well under SIDRA's 50,000-value response cap for
a single state and the full time series).
"""
import sys, json, time, urllib.request, urllib.error
import pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _brcfg import RAW, RES, PROVENANCE, UF, UF_NAME, IBGE_UF

API_BASE = "https://apisidra.ibge.gov.br/values"
# 109 area plantada (ha), 216 area colhida (ha), 214 quantidade produzida (t),
# 112 rendimento medio (kg/ha); c81=2713 is "Soja (em grao)" in the produto
# das lavouras temporarias classification this table uses.
TABLE, VARS, PRODUTO = 1612, "109,216,214,112", 2713
VAR_NAMES = {109: "area_plantada_ha", 216: "area_colhida_ha",
             214: "producao_t", 112: "rendimento_kg_ha"}

RECIPE = f"""
Reproduce this pull:
  GET {API_BASE}/t/{TABLE}/n6/in%20n3%20{IBGE_UF}/v/{VARS}/p/all/c81/{PRODUTO}
  (SIDRA API, https://sidra.ibge.gov.br/tabela/{TABLE})
  n6 = municipality level; "in n3 {IBGE_UF}" restricts to every municipality
  in UF code {IBGE_UF} ({UF_NAME.title()}); p/all = every available year;
  c81/{PRODUTO} = produto das lavouras temporarias = Soja (em grao).
IBGE marks a cell "-" for not-applicable (no soy grown that municipio-year)
and ".." for data withheld/not collected; both are read as missing here, not
zero, mirroring the US pipeline's NASS sentinel handling in script 02.
"""


def fetch(retries=4):
    url = f"{API_BASE}/t/{TABLE}/n6/in%20n3%20{IBGE_UF}/v/{VARS}/p/all/c81/{PRODUTO}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=300) as f:
                return json.loads(f.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                json.JSONDecodeError) as e:
            if attempt == retries - 1:
                raise
            time.sleep(3 * (attempt + 1))
    return []


def main():
    print(f"[br01] {UF}: pulling IBGE PAM (tabela {TABLE}) for every "
          f"municipality, soja, all years", flush=True)
    t0 = time.time()
    raw = fetch()
    if not raw or "D1C" not in raw[0]:
        raise SystemExit(f"[br01] unexpected response shape: {raw[:2]}")
    rows = raw[1:]  # first element is SIDRA's header/description row
    d = pd.DataFrame(rows)
    print(f"[br01] {UF}: {len(d):,} raw values, {time.time()-t0:.1f}s", flush=True)

    d = d.rename(columns={
        "D1C": "municipio_codigo", "D1N": "municipio_nome",
        "D2C": "variavel_codigo", "D3C": "ano", "V": "valor",
    })
    d["variavel"] = d.variavel_codigo.astype(int).map(VAR_NAMES)
    d["ano"] = d.ano.astype(int)
    d["valor_num"] = pd.to_numeric(d.valor.replace({"-": None, "..": None,
                                                     "...": None, "X": None}),
                                    errors="coerce")

    wide = (d.pivot_table(index=["municipio_codigo", "municipio_nome", "ano"],
                          columns="variavel", values="valor_num", aggfunc="first")
             .reset_index())
    wide.columns.name = None
    for c in VAR_NAMES.values():
        if c not in wide.columns:
            wide[c] = float("nan")

    out = RAW / "ibge_pam_soja_municipios.csv"
    wide.to_csv(out, index=False)
    print(f"[br01] {UF}: {len(wide):,} municipio-year rows, "
          f"{wide.municipio_codigo.nunique()} municipalities, "
          f"years {int(wide.ano.min())}-{int(wide.ano.max())}")
    print(f"[br01] -> {out.relative_to(RAW.parents[3])}")

    (RES / "br01_provenance_production.json").write_text(json.dumps({
        **PROVENANCE["production"], "uf": UF, "rows": len(wide),
        "municipalities": int(wide.municipio_codigo.nunique()),
        "year_min": int(wide.ano.min()), "year_max": int(wide.ano.max()),
        "recipe": RECIPE.strip(), "accessed": time.strftime("%Y-%m-%d"),
    }, indent=2))
    print(f"[br01] -> results/BR/{UF}/br01_provenance_production.json")


if __name__ == "__main__":
    main()
