"""BR 19 - Download the ZARC (Zoneamento Agricola de Risco Climatico) planting-
risk table for Mato Grosso soybean, at municipio x maturity-group x soil-class
x 10-day-window resolution -- the finest resolution any source in this branch
has found for anything phenology-adjacent (see br_10/br_17/br_18's docstrings
for the municipio-level phenology-calibration gap this partially closes).

WHAT ZARC IS, AND WHAT IT IS NOT
  ZARC is the federal government's (MAPA) official climate-risk zoning for
  crop insurance and planting-window guidance, published as yearly ordinances
  and queryable live through a Qlik Sense BI panel at
  https://mapa-indicadores.agricultura.gov.br/publico/extensions/Zarc/Zarc.html.
  It is a MODEL OUTPUT (a water-balance/climate-risk simulation using >=15
  years of daily weather per Instrucao Normativa SPA/MAPA), not an observed
  crop-progress series like NASS's. It tells you the government's assessed
  climate risk of planting soybean in a given municipio, in a given soil
  water-holding class (AD1-AD6), for a given cultivar maturity group (Grupo
  I-VI), in each 10-day window of the year -- not what farmers actually did.
  It is still the finest first-party, structured, municipio-resolution
  source this branch has found for anything maturity-group/planting-window
  related, and a legitimate substitute where true crop-progress data does
  not exist.

HOW THIS SCRIPT TALKS TO IT
  The public panel runs an anonymous Qlik Sense session (no login) but the
  actual data lives behind the QIX Engine JSON-RPC API over a websocket, not
  a simple REST endpoint -- verified live in a real browser session before
  writing this script (see chat): opened the app via window.qlik, listed
  its fields, made real field selections (UF=MT, Cultura=Soja, Safra=
  2024/2025), and pulled a live hypercube of municipio x grupo x solo x
  decendio x mes -> risco before writing a line of this script.

  This script reimplements that same handshake directly over websockets:
    1. GET the Zarc.html page once, to receive the qlik session cookies
       (X-Qlik-Session-Publico, and a renamed anti-CSRF cookie -- Qlik's
       proxy names it arbitrarily per deployment, currently "Abacaxi" on
       this instance; the code below does not hardcode that name, it just
       forwards whatever cookies the session received).
    2. GET .../publico/qps/csrftoken?xrfkey=<random> with those cookies and
       a Referer header -- the response's qlik-csrf-token header (NOT the
       xrfkey you sent) is the value the websocket URL needs.
    3. Open wss://.../publico/app/<appId>?reloadUri=...&qlik-csrf-token=...
       with the same cookies attached, and speak QIX JSON-RPC: OpenDoc,
       then GetField+Select to filter to UF/Cultura/Safra, then
       CreateSessionObject with a qHyperCubeDef to page through the result.

  App id and field names (Zarc.Municipio, Zarc.UF, Zarc.Zoneamento.Cultura,
  Zarc.Zoneamento.AnoSafratabua, Nome_Ciclo, Nome_Solo, DescDecendio,
  MesDecendio, Risco) come from that live browser session's field list, not
  guessed.
"""
import sys, json, time, secrets
import requests
import websockets
import asyncio
import pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _brcfg import RAW, UF

HOST = "mapa-indicadores.agricultura.gov.br"
APP_ID = "6d8f45b7-dffc-41d8-a022-83cc28bb4199"
ENTRY_PAGE = f"https://{HOST}/publico/extensions/Zarc/Zarc.html"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

DIMENSIONS = ["Zarc.Municipio", "Nome_Ciclo", "Nome_Solo", "DescDecendio", "MesDecendio"]
MEASURE = "=Only(Risco)"
PAGE_SIZE = 1000


def get_session_and_csrf():
    s = requests.Session()
    headers = {"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"}
    r0 = s.get(ENTRY_PAGE, headers=headers, timeout=30)
    r0.raise_for_status()
    xrfkey = secrets.token_hex(8)
    h2 = dict(headers, **{"Accept": "*/*", "Referer": ENTRY_PAGE})
    r1 = s.get(f"https://{HOST}/publico/qps/csrftoken?xrfkey={xrfkey}", headers=h2, timeout=30)
    r1.raise_for_status()
    token = r1.headers["qlik-csrf-token"]
    cookie_header = "; ".join(f"{k}={v}" for k, v in s.cookies.get_dict().items())
    return cookie_header, token


class QixClient:
    """Minimal QIX Engine JSON-RPC client -- just enough to open a doc, select
    field values, and page through one hypercube. Not a general Qlik client."""

    def __init__(self, ws):
        self.ws = ws
        self.msg_id = 0
        self.doc_handle = None

    async def call(self, handle, method, params):
        self.msg_id += 1
        req = dict(jsonrpc="2.0", id=self.msg_id, handle=handle, method=method, params=params)
        await self.ws.send(json.dumps(req))
        while True:
            raw = await self.ws.recv()
            resp = json.loads(raw)
            if resp.get("id") == self.msg_id:
                if "error" in resp:
                    raise RuntimeError(f"{method} failed: {resp['error']}")
                return resp["result"]
            # otherwise it's an out-of-band notification (OnConnected etc.) -- ignore

    async def open_doc(self):
        result = await self.call(-1, "OpenDoc", [APP_ID])
        self.doc_handle = result["qReturn"]["qHandle"]
        return self.doc_handle

    async def get_field_handle(self, field_name):
        result = await self.call(self.doc_handle, "GetField", [field_name, ""])
        return result["qReturn"]["qHandle"]

    async def select_value(self, field_name, text_value):
        h = await self.get_field_handle(field_name)
        result = await self.call(h, "Select", [text_value, False, 0])
        return result["qReturn"]

    async def create_hypercube_object(self, dims, measure_expr, height, top=0):
        obj_def = dict(
            qInfo=dict(qType="sn-table"),
            qHyperCubeDef=dict(
                qDimensions=[dict(qDef=dict(qFieldDefs=[d])) for d in dims],
                qMeasures=[dict(qDef=dict(qDef=measure_expr))],
                qInitialDataFetch=[dict(qTop=top, qLeft=0, qHeight=height, qWidth=len(dims) + 1)],
            ),
        )
        result = await self.call(self.doc_handle, "CreateSessionObject", [obj_def])
        return result["qReturn"]["qHandle"]

    async def get_layout(self, handle):
        result = await self.call(handle, "GetLayout", [])
        return result["qLayout"]

    async def get_hypercube_data(self, handle, dims_n, top, height):
        page = dict(qTop=top, qLeft=0, qHeight=height, qWidth=dims_n + 1)
        result = await self.call(handle, "GetHyperCubeData", ["/qHyperCubeDef", [page]])
        return result["qDataPages"][0]["qMatrix"]


async def open_session(uf_value, cultura_value, safra_value):
    """Fresh websocket connection, doc open, selections applied, hypercube
    object recreated. Returns (client, obj_handle, n_rows). Called once at
    the start and again after any dropped connection -- the Qlik session
    server-side appears to time out mid-pagination on a large result, so
    reconnecting and recreating the same selections/object is the resilient
    path rather than trying to keep one connection alive for the whole pull."""
    cookie_header, csrf = get_session_and_csrf()
    url = (f"wss://{HOST}/publico/app/{APP_ID}"
          f"?reloadUri={requests.utils.quote(ENTRY_PAGE, safe='')}"
          f"&qlik-csrf-token={csrf}")
    headers = {"Cookie": cookie_header, "User-Agent": UA, "Origin": f"https://{HOST}"}
    ws = await websockets.connect(url, additional_headers=headers, max_size=None,
                                  ping_interval=15, ping_timeout=20, open_timeout=30)
    client = QixClient(ws)
    await client.open_doc()
    await client.select_value("Zarc.UF", uf_value)
    await client.select_value("Zarc.Zoneamento.Cultura", cultura_value)
    await client.select_value("Zarc.Zoneamento.AnoSafratabua", safra_value)
    obj_handle = await client.create_hypercube_object(DIMENSIONS, MEASURE, height=1)
    layout = await client.get_layout(obj_handle)
    n_rows = layout["qHyperCube"]["qSize"]["qcy"]
    return client, obj_handle, n_rows


async def fetch_zarc(uf_value, cultura_value, safra_value, max_reconnects=15):
    rows = []
    top = 0
    n_rows = None
    client = obj_handle = None
    reconnects = 0
    while n_rows is None or top < n_rows:
        try:
            if client is None:
                client, obj_handle, n_rows = await open_session(uf_value, cultura_value, safra_value)
                print(f"[br19] session open (reconnect #{reconnects}); result size: "
                      f"{n_rows:,} rows; resuming from row {top:,}")
            height = min(PAGE_SIZE, n_rows - top)
            page = await client.get_hypercube_data(obj_handle, len(DIMENSIONS), top, height)
            for r in page:
                rows.append([cell["qText"] for cell in r])
            top += height
            if top % (PAGE_SIZE * 10) == 0 or top >= n_rows:
                print(f"[br19]   fetched {top:,}/{n_rows:,}", flush=True)
        except (websockets.exceptions.ConnectionClosed, TimeoutError, OSError) as e:
            reconnects += 1
            if reconnects > max_reconnects:
                raise
            print(f"[br19]   connection dropped at row {top:,} ({e}); reconnecting "
                  f"({reconnects}/{max_reconnects}) ...")
            try:
                await client.ws.close()
            except Exception:
                pass
            client = None
            await asyncio.sleep(2)
    if client is not None:
        await client.ws.close()
    return rows


def main():
    cultura, safra = "Soja", "2024\\2025"
    rows = asyncio.run(fetch_zarc(UF, cultura, safra))
    cols = ["municipio", "grupo_maturacao", "classe_solo", "decendio", "mes", "risco"]
    df = pd.DataFrame(rows, columns=cols)
    df["risco"] = pd.to_numeric(df["risco"], errors="coerce")
    out = RAW / "zarc_soja_risco.csv"
    df.to_csv(out, index=False)
    print(f"[br19] wrote {out} ({len(df):,} rows, {df.municipio.nunique()} municipios, "
          f"{df.grupo_maturacao.nunique()} maturity groups, {df.classe_solo.nunique()} soil "
          f"classes)")
    print(df.risco.describe())


if __name__ == "__main__":
    main()
