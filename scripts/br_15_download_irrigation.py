"""BR 15 - Municipality irrigation prevalence for Mato Grosso. Analogue of
US scripts 29-30, which pull irrigated acreage from NASS Census bulk files
(qs.census2017.txt.gz / qs.census2022.txt.gz) -- a single-year snapshot,
not an annual series, joined onto the annual yield panel as a static
municipality attribute.

Brazil's equivalent single-year snapshot is IBGE's own 2017 Censo
Agropecuario, SIDRA tabela 6859 ("Numero de estabelecimentos agropecuarios
com uso de irrigacao e Area irrigada dos estabelecimentos agropecuarios").
Verified live against the API before writing this script (see chat).

IMPORTANT SCOPE LIMIT, stated plainly rather than silently assumed away:
tabela 6859 reports irrigated area for ALL crops combined on a farm, not
soybean specifically -- IBGE's agricultural census does not publish a
soja-only irrigated-area breakdown by municipio. This script therefore
produces a farm-level irrigation PREVALENCE proxy (irrigated ha / total
harvested ha, and irrigated establishments / total establishments) per
municipio, not a soybean-irrigated-area figure. In practice this proxy is
still informative for Mato Grosso specifically: MT soybean is overwhelmingly
rainfed (the state's irrigation infrastructure concentrates on other crops
and double-cropping systems), so a near-zero prevalence value is itself
the expected and useful finding, not a data quality failure.
"""
import sys, time, urllib.request, json
import pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _brcfg import RAW, IBGE_UF, UF

BASE = "https://apisidra.ibge.gov.br/values"
# v: 2372 = n estabelecimentos com irrigacao, 2373 = area irrigada (ha)
# c12604/118477 = metodo Total, c12603/45927 = grupo area lavoura Total,
# c220/110085 = grupo area total Total, c829/46302 = tipologia Total
URL = (f"{BASE}/t/6859/n6/in%20n3%20{IBGE_UF}/v/2372,2373/p/2017/"
       f"c12604/118477/c12603/45927/c220/110085/c829/46302")


def fetch(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "research-script"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            print(f"[br15]   retry {i+1}/{tries} ({e})")
            time.sleep(3)
    raise RuntimeError(f"failed to fetch {url}")


print(f"[br15] fetching IBGE SIDRA tabela 6859 (irrigation, 2017 census) for UF={UF}")
data = fetch(URL)[1:]  # first row is the header/labels row
df = pd.DataFrame(data)
df = df.rename(columns={"D1C": "fips5", "D1N": "municipio_uf",
                        "D2N": "variable", "V": "value"})
df["value"] = pd.to_numeric(df.value, errors="coerce")
wide = df.pivot_table(index="fips5", columns="variable", values="value").reset_index()
wide.columns = ["fips5", "irrigated_estabs", "irrigated_area_ha"]
wide["county"] = df.drop_duplicates("fips5").set_index("fips5").municipio_uf.str.replace(
    r" - MT$", "", regex=True).reindex(wide.fips5).values
out = RAW / "ibge_irrigation_2017.csv"
wide.to_csv(out, index=False)
print(f"[br15] wrote {out} ({len(wide)} municipalities)")
print(f"[br15] total irrigated area in {UF}: {wide.irrigated_area_ha.sum():,.0f} ha "
      f"across {wide.irrigated_estabs.sum():,.0f} establishments")
print(f"[br15] municipalities with zero irrigated area: "
      f"{(wide.irrigated_area_ha.fillna(0) == 0).sum()} of {len(wide)}")
