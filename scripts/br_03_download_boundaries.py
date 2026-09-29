"""BR 03 - Municipality boundary polygons for one Brazilian state, and the
centroids computed from them for the climate pull (br_04).

Source: IBGE's public Malhas Territoriais service, GeoJSON, minimum quality
(smallest file that still gives an honest centroid -- this pipeline never
needs survey-grade boundaries, only a representative point per municipality,
the same "qualidade minima" choice the US pipeline makes with Census
cartographic boundaries in script 10).

Written in the same simple "codarea|lon,lat lon,lat ..." text format the US
pipeline's script 10 writes county polygons in, so br_04's centroid()
function can be lifted nearly verbatim from US script 17's.
"""
import gzip, sys, json, time, urllib.request, urllib.error
import numpy as np
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from _brcfg import RAW, RES, UF, UF_NAME, IBGE_UF

API = ("https://servicodados.ibge.gov.br/api/v3/malhas/estados/{uf}"
       "?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=municipio")


def fetch(retries=4):
    url = API.format(uf=IBGE_UF)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=120) as f:
                body = f.read()
            if body[:2] == b"\x1f\x8b":   # gzip magic, even without a
                body = gzip.decompress(body)  # Content-Encoding header
            return json.loads(body.decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                json.JSONDecodeError) as e:
            if attempt == retries - 1:
                raise
            time.sleep(3 * (attempt + 1))
    return {}


def outer_ring_lonlat(geom):
    """First ring of a Polygon, or the first polygon's first ring of a
    MultiPolygon -- enough for a centroid, not for area-accurate work."""
    if geom["type"] == "Polygon":
        return geom["coordinates"][0]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"][0][0]
    raise ValueError(f"unexpected geometry type {geom['type']}")


def main():
    print(f"[br03] {UF}: fetching municipality polygons "
          f"(IBGE malha, UF {IBGE_UF})", flush=True)
    gj = fetch()
    feats = gj.get("features", [])
    if not feats:
        raise SystemExit(f"[br03] no features returned: {gj}")

    lines, rows = [], []
    for feat in feats:
        code = feat["properties"]["codarea"]
        ring = outer_ring_lonlat(feat["geometry"])
        pts = np.array(ring, dtype=float)
        lines.append(code + "|" + " ".join(f"{x:.4f},{y:.4f}" for x, y in pts))
        rows.append((code, float(pts[:, 0].mean()), float(pts[:, 1].mean())))

    out = RAW / "mt_municipio_boundaries.txt"
    out.write_text("\n".join(lines))
    print(f"[br03] {UF}: wrote {len(lines)} municipality polygons -> {out.name}")
    print(f"[br03] centroid lon range {min(r[1] for r in rows):.2f} to "
          f"{max(r[1] for r in rows):.2f}, lat range "
          f"{min(r[2] for r in rows):.2f} to {max(r[2] for r in rows):.2f}")

    (RES / "br03_provenance_boundaries.json").write_text(json.dumps(dict(
        source="IBGE Malhas Territoriais", url=API.format(uf=IBGE_UF),
        accessed=time.strftime("%Y-%m-%d"),
        note="qualidade=minima -- generalized geometry, adequate for a "
             "centroid, not for area-accurate cartography.",
        municipalities=len(lines),
    ), indent=2))
    print(f"[br03] -> results/BR/{UF}/br03_provenance_boundaries.json")


if __name__ == "__main__":
    main()
