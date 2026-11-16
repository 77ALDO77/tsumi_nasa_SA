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

from api.main import DESCARGO, LIMITES, SQL_DISTANCIAS, VERSION_POR_DEFECTO, cifra, conectar, estado_busqueda

router = APIRouter()
RES_M = 60.0
ZONAS_EN_ATLAS = 50      # zonas de >=3 teselas cercanas, primero las más extensas
AISLADAS_EN_ATLAS = 10   # candidatas sin vecinas, por cercanía a la mediana
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
LOLA = {"title": "LRO LOLA, modelos de elevación polares (NASA PDS)", "url": "https://pds-geosciences.wustl.edu/missions/lro/lola.htm"}
GLO30 = {"title": "Copernicus DEM GLO-30 (AWS Open Data)", "url": "https://registry.opendata.aws/copernicus-dem/"}
CUERPO = {"luna": "Luna", "marte": "Marte"}
BANDAS = {"p10-p90": ("p10", "p90", "P10–P90"), "p25-p75": ("p25", "p75", "P25–P75")}
SIN_BUSQUEDA = ("Esta referencia no se usa para seleccionar candidatas: su relieve es una llanura suave muy común en "
                "los desiertos terrestres (en la prueba del equipo coincidían decenas de miles de teselas). "
                "Sirve para comparar lugares concretos.")


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


@router.get("/search/status")
def search_status():
    """Actividad medida en la base; nunca infiere salud por tener un contenedor encendido."""
    return estado_busqueda()


@router.get("/sites")
def sites():
    """Sitios NASA registrados más los mejores candidatos detectados (3/3 dentro de la envolvente) por referencia."""
    with conectar() as conn:
        out = [{"id": s["sitio_id"], "name": s["nombre"] or s["sitio_id"], "lat": s["lat"], "lon": s["lon"],
                "coverage": COBERTURA.get(s["rol"], "Sitio registrado"), "location": ubicacion(s)}
               for s in conn.execute(f"""SELECT s.*, {UBICACION_SQL} FROM sitios s {UBICACION_JOIN.format(t='s')}
                                         WHERE s.cuerpo = 'tierra' ORDER BY s.sitio_id""").fetchall()]
        refs_db = referencias(conn)
        nombres = {r["referencia_id"]: r["nombre"] for r in refs_db}
        cuerpos = {r["referencia_id"]: r["cuerpo"] for r in refs_db}
        # Zonas agrupadas por cuerpo, con cupo propio: las marcianas no quedan fuera por ser menos, o al revés.
        for cuerpo in ("luna", "marte"):
            for es_zona, orden, limite in ((True, "n_teselas DESC, dist_mediana", ZONAS_EN_ATLAS),
                                           (False, "dist_mediana", AISLADAS_EN_ATLAS)):
                for z in conn.execute(f"""SELECT z.*, {UBICACION_SQL} FROM zonas_candidatas z {UBICACION_JOIN.format(t='z')}
                                          WHERE z.res_m = %s AND z.version_metodo = %s AND z.cuerpo = %s AND z.es_zona = %s
                                          ORDER BY {orden}, zona_id LIMIT %s""",
                                      (RES_M, VERSION_POR_DEFECTO, cuerpo, es_zona, limite)).fetchall():
                    out.append(zona_sitio(z, es_zona, nombres, cuerpos))
    return out


UBICACION_SQL = "u.pais AS u_pais, u.provincia AS u_provincia, u.distrito AS u_distrito, u.estado AS u_estado"
UBICACION_JOIN = ("LEFT JOIN ubicaciones u ON u.lat = round({t}.lat::numeric, 2) "
                  "AND u.lon = round({t}.lon::numeric, 2)")


def ubicacion(fila):
    """None mientras el trabajador no la haya consultado; sin_resultado en el mar o sin división administrativa."""
    if fila["u_estado"] in (None, "error"):
        return None
    return {"status": fila["u_estado"], "country": fila["u_pais"], "province": fila["u_provincia"],
            "district": fila["u_distrito"], "source": "© OpenStreetMap (Nominatim)"}


def zona_sitio(z, es_zona, nombres, cuerpos):
    refs = " y ".join(f"{nombres.get(r, r)} ({CUERPO[cuerpos.get(r, 'luna')]})" for r in z["referencias"])
    cobertura = (f"Zona candidata · {z['n_teselas']} teselas ({cifra(z['area_km2'], 'km²')}) · 3/3 frente a {refs}"
                 if es_zona else f"Candidato aislado · 3/3 frente a {refs}")
    if z["conocida"]:
        cobertura += f" · a {cifra(z['sitio_cercano_km'], 'km')} de {z['sitio_cercano']} (análogo conocido)"
    # La misma tesela puede encabezar una zona lunar y otra marciana: el sufijo mantiene ids únicos.
    return {"id": "T~" + z["zona_id"] + ("~marte" if z["cuerpo"] == "marte" else ""),
            "name": f"{'Zona' if es_zona else 'Candidato'} {coordenadas(z['lat'], z['lon'])}",
            "lat": z["lat"], "lon": z["lon"], "coverage": cobertura, "location": ubicacion(z),
            "zone": {"tiles": z["n_teselas"], "areaKm2": round(z["area_km2"], 1), "isZone": es_zona,
                     "references": [nombres.get(r, r) for r in z["referencias"]],
                     "bodies": [z["cuerpo"]],
                     "searchArea": z["region"], "known": z["conocida"],
                     "nearestKnownSite": z["sitio_cercano"],
                     "nearestKnownKm": None if z["sitio_cercano_km"] is None else round(z["sitio_cercano_km"], 1),
                     "bbox": [z["lon_min"], z["lat_min"], z["lon_max"], z["lat_max"]]}}


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


def valores_contexto(tile, activo):
    if activo is None or tile["contexto_id"] != activo["contexto_id"]:
        return None
    return {"months": activo["metadata"]["meses"], "resolutionDegrees": 0.05,
            "ndviMax": tile["ndvi_max"], "ndviValidMonths": tile["ndvi_n"],
            "lstDayMaxK": tile["lst_dia_max_k"], "lstDayValidMonths": tile["lst_dia_n"],
            "lstNightMinK": tile["lst_noche_min_k"], "lstNightValidMonths": tile["lst_noche_n"],
            "ndviThreshold": activo["umbral_ndvi"],
            "passesNdviScreen": (tile["ndvi_max"] is not None
                                and tile["ndvi_n"] == len(activo["metadata"]["meses"])
                                and tile["ndvi_max"] <= activo["umbral_ndvi"])}


def tesela_de(site_id: str):
    """Condición SQL y parámetros para localizar la tesela de un sitio; None si el id no es válido."""
    if site_id.startswith("T~"):
        try:
            _, celda, ix, iy = site_id.removesuffix("~marte").split("~")
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
    return [{"id": f"{r['referencia_id']}~{var}", "label": f"{r['nombre']} · {nombre}", "variable": nombre,
             "reference": f"{CUERPO[r['cuerpo']]} · {r['nombre']}"}
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
    inf, sup, banda = BANDAS[ref.get("banda") or "p10-p90"]
    if env.get("p50") is None or env.get(inf) is None or env.get(sup) is None:
        return {"id": ident, "status": "insufficient_data",
                "message": "La envolvente de la referencia está incompleta: hay que recalcular las referencias."}
    fuente_dem = ref.get("fuente") or LOLA
    nota = "" if ref.get("buscar", True) else SIN_BUSQUEDA + " "
    earth, mid = tile[col], env["p50"]
    dentro = tile["d_" + col] == 0
    fuentes = [etiquetas()[e] for e in (sitio or {}).get("etiquetas") or [] if e in etiquetas()]
    contexto, fuentes_modis = contexto_nasa(tile, activo)
    coordenada = (f"Coordenada terrestre: {sitio['fuente_coordenadas']}. "
                  "La documentación del entorno no valida por sí sola esta tesela. ") if sitio else ""
    return {"id": ident, "status": "completed", "result": {
        "earthValue": round(earth, 2), "referenceValue": round(mid, 2), "unit": unidad,
        "difference": round(earth - mid, 2),
        "scale": (f"Tesela de 3 km a {RES_M:g} m (Copernicus GLO-30, celda {tile['celda_id']}) frente a la mediana de "
                  f"{ref['n_subventanas']} subventanas de 3 km de {ref['nombre'] or ref_id} "
                  f"({CUERPO[ref['cuerpo']]}, {fuente_dem['title']})."),
        "limitation": (f"{nombre}: la referencia va de {cifra(env[inf], unidad)} a {cifra(env[sup], unidad)} "
                       f"({banda}) y este sitio queda {'dentro' if dentro else 'fuera'}. En las 3 variables de relieve, "
                       f"{tile['n_dentro']}/3 dentro de la envolvente. " + nota + coordenada + contexto + " "
                       + " ".join(LIMITES[ref["cuerpo"]]) + " " + DESCARGO),
        "sources": fuentes + [fuente_dem, GLO30] + fuentes_modis, "earthContext": valores_contexto(tile, activo)}}


@router.post("/analyses")
def crear_analisis(solicitud: Solicitud):
    return analizar(solicitud.siteId, solicitud.comparisonId)


@router.get("/analyses/{analysis_id}")
def leer_analisis(analysis_id: str):
    site_id, sep, comparison_id = analysis_id.partition("|")
    if not sep:
        raise HTTPException(404, "Identificador de análisis no válido")
    return analizar(site_id, comparison_id)
