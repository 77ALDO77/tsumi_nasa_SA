"""Contrato del frontend TSUMI Atlas (repo nasa-azzu-front, ANALISIS-FRONTEND.md), montado en /api.

El frontend no se modifica: este módulo traduce la búsqueda (teselas de 3 km frente a la envolvente de 3 km
de cada región lunar) a sus rutas. Todo se compara a la misma escala; nunca ventanas de 15 km con teselas.
Las métricas ya están calculadas, así que /analyses responde al momento (sin cola de trabajos).
"""
import json
from functools import cache
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.main import DESCARGO, LIMITES, SQL_DISTANCIAS, VERSION_POR_DEFECTO, cifra, conectar

router = APIRouter()
RES_M = 60.0
CANDIDATOS_POR_REFERENCIA = 30
ETIQUETAS = Path(__file__).resolve().parent.parent / "scrapping/docs/etiquetas_analogos.json"
# id de variable -> (columna en teselas, clave de la envolvente, nombre, unidad)
VARIABLES = {
    "pendiente_mediana": ("pendiente_mediana", "pendiente_mediana_grados", "Pendiente mediana", "°"),
    "pendiente_p90": ("pendiente_p90", "pendiente_p90_grados", "Pendiente P90", "°"),
    "relieve": ("relieve", "relieve_p95_p5_m", "Relieve P95–P5", "m"),
}
COBERTURA = {
    "analogo_nasa": "Análogo NASA documentado",
    "analogo_nasa_otra_dimension": "Análogo NASA de otra dimensión (no de relieve)",
    "analogo_nasa_marte": "Análogo NASA para Marte",
    "referencia_gvp_no_es_sitio_de_ensayo": "Punto de referencia, no es sitio de ensayo",
}
FUENTES_DATOS = [
    {"title": "LRO LOLA, modelos de elevación polares (NASA PDS)", "url": "https://pds-geosciences.wustl.edu/missions/lro/lola.htm"},
    {"title": "Copernicus DEM GLO-30 (AWS Open Data)", "url": "https://registry.opendata.aws/copernicus-dem/"},
]


class Solicitud(BaseModel):
    siteId: str
    comparisonId: str


@cache
def etiquetas() -> dict:
    data = json.loads(ETIQUETAS.read_text(encoding="utf-8"))["etiquetas"]
    return {e["label_id"]: {"title": e["titulo_fuente"] or e["url"], "url": e["url"]} for e in data}


def coordenadas(lat, lon):
    return (f"{abs(lat):.2f}° {'N' if lat >= 0 else 'S'} {abs(lon):.2f}° {'E' if lon >= 0 else 'O'}").replace(".", ",")


def referencias(conn):
    return conn.execute("""SELECT referencia_id, coalesce(nombre, referencia_id) AS nombre, cuerpo FROM referencias
                           WHERE res_m = %s AND version_metodo = %s ORDER BY referencia_id""",
                        (RES_M, VERSION_POR_DEFECTO)).fetchall()


@router.get("/sites")
def sites():
    """Sitios NASA registrados más los mejores candidatos detectados (3/3 dentro de la envolvente) por referencia."""
    with conectar() as conn:
        out = [{"id": s["sitio_id"], "name": s["nombre"] or s["sitio_id"], "lat": s["lat"], "lon": s["lon"],
                "coverage": COBERTURA.get(s["rol"], "Sitio registrado")}
               for s in conn.execute("SELECT * FROM sitios WHERE cuerpo = 'tierra' ORDER BY sitio_id").fetchall()]
        seen = set()
        for ref in referencias(conn):
            rows = conn.execute("""SELECT celda_id, ix, iy, lat, lon FROM candidatos
                                     WHERE referencia_id = %(ref)s AND res_m = %(res)s AND version_metodo = %(version)s
                                    ORDER BY dist_mediana, celda_id, iy, ix LIMIT %(lim)s""",
                                {"ref": ref["referencia_id"], "res": RES_M, "version": VERSION_POR_DEFECTO,
                                 "lim": CANDIDATOS_POR_REFERENCIA}).fetchall()
            for r in rows:
                sid = f"T~{r['celda_id']}~{r['ix']}~{r['iy']}"
                if sid in seen:
                    continue
                seen.add(sid)
                out.append({"id": sid, "name": f"Candidato {coordenadas(r['lat'], r['lon'])}", "lat": r["lat"],
                            "lon": r["lon"], "coverage": f"Candidato detectado · 3/3 frente a {ref['nombre']}"})
    return out


def contexto_nasa(tile, activo):
    if activo is None or tile["contexto_id"] != activo["contexto_id"]:
        return "Contexto NASA MODIS aún no disponible para esta tesela.", []
    meta = activo["metadata"]
    meses = ", ".join(meta["meses"])
    ndvi = (f"NDVI máximo {tile['ndvi_max']:.4f} ({tile['ndvi_n']}/{len(meta['meses'])} meses válidos)"
            if tile["ndvi_max"] is not None else "NDVI sin dato válido")
    temperaturas = []
    for clave, conteo, nombre in (("lst_dia_max_k", "lst_dia_n", "máxima diurna"),
                                 ("lst_noche_min_k", "lst_noche_n", "mínima nocturna")):
        temperaturas.append(f"{nombre} {cifra(tile[clave], 'K')} ({tile[conteo]} meses válidos)"
                            if tile[clave] is not None else f"{nombre} sin dato válido")
    texto = (f"NASA MODIS 061, meses {meses}, píxel de 0,05° en el centro de la tesela (no detalle de 3 km): "
             f"{ndvi}; LST: {', '.join(temperaturas)}. Filtro heurístico NDVI ≤ {activo['umbral_ndvi']:g} "
             "con dato válido en todos los meses; no demuestra ausencia de vegetación. "
             "QA: NDVI ideal sobre tierra; LST producida (buena u otra calidad), error medio declarado ≤2 K. "
             "Son máximos/mínimos de medias mensuales disponibles: no extremos anuales, temperatura del aire, "
             "amplitud diurna ni comparación térmica lunar. "
             "El relieve puede orientar ensayos de movilidad y navegación; requiere inspección de campo.")
    fuentes = [{"title": f"NASA {f['producto']} 061 · {f['mes']}", "url": f["url"]} for f in meta["fuentes"]]
    return texto, fuentes


def tesela_de(site_id: str):
    """Condición SQL y parámetros para localizar la tesela de un sitio; None si el id no es válido."""
    if site_id.startswith("T~"):
        try:
            _, celda, ix, iy = site_id.split("~")
            return "celda_id = %(celda)s AND ix = %(ix)s AND iy = %(iy)s", {"celda": celda, "ix": int(ix), "iy": int(iy)}
        except ValueError:
            return None
    return ("ST_Contains(geom, (SELECT geom FROM sitios WHERE sitio_id = %(sitio)s AND cuerpo = 'tierra'))",
            {"sitio": site_id})


@router.get("/sites/{site_id}/comparisons")
def comparisons(site_id: str):
    with conectar() as conn:
        existe = (site_id.startswith("T~") and tesela_de(site_id) is not None) or conn.execute(
            "SELECT 1 FROM sitios WHERE sitio_id = %s AND cuerpo = 'tierra'", (site_id,)).fetchone()
        if not existe:
            raise HTTPException(404, f"Sitio desconocido: {site_id}")
        refs = referencias(conn)
    cuerpo = {"luna": "Luna", "marte": "Marte"}
    return [{"id": f"{r['referencia_id']}~{var}", "label": f"{r['nombre']} · {nombre}", "variable": nombre,
             "reference": f"{cuerpo[r['cuerpo']]} · {r['nombre']}"}
            for r in refs for var, (_, _, nombre, _) in VARIABLES.items()]


def analizar(site_id: str, comparison_id: str) -> dict:
    ident = f"{site_id}|{comparison_id}"
    ref_id, _, var = comparison_id.rpartition("~")
    where = tesela_de(site_id)
    if var not in VARIABLES or where is None:
        raise HTTPException(404, "Comparación o sitio no válidos")
    col, key, nombre, unidad = VARIABLES[var]
    with conectar() as conn:
        ref = conn.execute("SELECT * FROM referencias WHERE referencia_id = %s AND res_m = %s AND version_metodo = %s",
                           (ref_id, RES_M, VERSION_POR_DEFECTO)).fetchone()
        sitio = None if site_id.startswith("T~") else conn.execute(
            "SELECT * FROM sitios WHERE sitio_id = %s AND cuerpo = 'tierra'", (site_id,)).fetchone()
        if ref is None or (sitio is None and not site_id.startswith("T~")):
            raise HTTPException(404, "Comparación o sitio no encontrados")
        cond, params = where
        tile = conn.execute(f"SELECT * FROM ({SQL_DISTANCIAS}) x WHERE {cond} ORDER BY celda_id LIMIT 1",
                            {**params, "ref": ref_id, "res": RES_M, "version": VERSION_POR_DEFECTO}).fetchone()
        if tile is None:
            if sitio is None:
                raise HTTPException(404, f"Tesela no encontrada: {site_id}")
            celda = conn.execute("SELECT celda_id, estado FROM celdas_busqueda WHERE lat_min = floor(%s) AND lon_min = floor(%s)",
                                 (sitio["lat"], sitio["lon"])).fetchone()
            estado = f"{celda['celda_id']}: {celda['estado']}" if celda else "la celda no está en la cola de búsqueda"
            return {"id": ident, "status": "insufficient_data",
                    "message": f"La tesela de este sitio aún no se ha calculado ({estado})."}
        activo = conn.execute("SELECT * FROM contexto_modis").fetchone()
    env = ref["envolvente"][key]
    if env.get("p50") is None:
        return {"id": ident, "status": "insufficient_data",
                "message": "La envolvente de la referencia no tiene mediana: hay que recalcular las referencias."}
    earth, mid = tile[col], env["p50"]
    dentro = tile["d_" + col] == 0
    fuentes = [etiquetas()[e] for e in (sitio or {}).get("etiquetas") or [] if e in etiquetas()]
    contexto, fuentes_modis = contexto_nasa(tile, activo)
    return {"id": ident, "status": "completed", "result": {
        "earthValue": round(earth, 2), "referenceValue": round(mid, 2), "unit": unidad,
        "difference": round(earth - mid, 2),
        "scale": (f"Tesela de 3 km a {RES_M:g} m (Copernicus GLO-30, celda {tile['celda_id']}) frente a la mediana de "
                  f"{ref['n_subventanas']} subventanas de 3 km de {ref['nombre'] or ref_id} (LRO LOLA)."),
        "limitation": (f"{nombre}: la referencia va de {cifra(env['p10'], unidad)} a {cifra(env['p90'], unidad)} "
                       f"(P10–P90) y este sitio queda {'dentro' if dentro else 'fuera'}. En las 3 variables de relieve, "
                        f"{tile['n_dentro']}/3 dentro de la envolvente. " + contexto + " "
                        + " ".join(LIMITES[ref["cuerpo"]]) + " " + DESCARGO),
        "sources": fuentes + FUENTES_DATOS + fuentes_modis}}


@router.post("/analyses")
def crear_analisis(solicitud: Solicitud):
    return analizar(solicitud.siteId, solicitud.comparisonId)


@router.get("/analyses/{analysis_id}")
def leer_analisis(analysis_id: str):
    site_id, sep, comparison_id = analysis_id.partition("|")
    if not sep:
        raise HTTPException(404, "Identificador de análisis no válido")
    return analizar(site_id, comparison_id)
