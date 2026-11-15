"""API de solo lectura sobre las métricas de relieve cargadas por analisis.cargar.

Desde la raíz: DATABASE_URL=... uvicorn api.main:app --host 127.0.0.1 --port 8000
No calcula rásteres: lee la base. /comparacion no ordena; /analogos ordena por la envolvente P10–P90 de la referencia.
Logs: una línea JSON por petición (analisis.registro); lanzar uvicorn con --no-access-log para no duplicarlos.
"""
import logging
import os
import time
from pathlib import Path

import psycopg
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from psycopg.rows import dict_row

from analisis.registro import configurar, evento

log = configurar("api")

VERSION_POR_DEFECTO = "relieve-v2-aeqd-average-horn-ldec"
DESCARGO = ("Comparación de relieve calculada con modelos digitales de elevación. No es una certificación de "
            "analogía ni una evaluación de NASA.")
VARIABLES = {
    "pendiente_mediana": ("Pendiente mediana", "°"),
    "pendiente_p90": ("Pendiente P90", "°"),
    "relieve_p95_p5": ("Relieve P95–P5", "m"),
    "rugosidad_rms_plano": ("Rugosidad (RMS respecto al plano)", "m"),
}
LIMITES = {
    "luna": ["Gravedad: ~1/6 de la terrestre; la misma pendiente no implica la misma tracción ni el mismo esfuerzo.",
             "Sin atmósfera: no hay viento ni erosión eólica; en la Tierra el viento interrumpió ensayos (JETT, NASA).",
             "Iluminación polar rasante y sombra permanente: no se reproducen en la Tierra (NASA la simuló con focos).",
             "Temperatura y regolito: no se comparan en este perfil de relieve."],
    "marte": ["Gravedad: ~0,38 de la terrestre.",
              "Atmósfera tenue de CO2: presión y viento distintos.",
              "Temperatura y regolito: no se comparan en este perfil de relieve."],
}

app = FastAPI(title="Análogos terrestres: API de lectura", version="0.1.0")


@app.middleware("http")
async def registrar_peticion(request, call_next):
    inicio = time.monotonic()
    try:
        response = await call_next(request)
    except Exception as exc:
        evento(log, "peticion_fallida", logging.ERROR, exc_info=exc, metodo=request.method, ruta=request.url.path)
        raise
    evento(log, "peticion", metodo=request.method, ruta=request.url.path, consulta=str(request.url.query) or None,
           estado=response.status_code, duracion_ms=round((time.monotonic() - inicio) * 1000, 1))
    return response


origins = [o for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o]
if origins:
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["*"])


def conectar():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise HTTPException(503, "DATABASE_URL no está configurada")
    try:
        return psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5)
    except psycopg.OperationalError as exc:
        evento(log, "base_no_disponible", logging.ERROR, error=type(exc).__name__)
        raise HTTPException(503, "Base de datos no disponible") from exc


SQL_VENTANAS = """
SELECT s.sitio_id, s.cuerpo, s.lat, s.lon, s.fuente_coordenadas, v.lado_m, v.res_m,
       ST_AsGeoJSON(v.geom)::json AS geom, max(m.fraccion_valida) AS fraccion_valida,
       jsonb_object_agg(m.variable || '_' || m.estadistico,
                        jsonb_build_object('valor', m.valor, 'unidad', m.unidad, 'estado', m.estado)) AS metricas
FROM ventanas v JOIN sitios s USING (sitio_id) JOIN metricas m USING (ventana_id)
WHERE m.version_metodo = %(version)s AND v.res_m = %(res)s
  AND (%(cuerpo)s::text IS NULL OR s.cuerpo = %(cuerpo)s) AND (%(sitio)s::text IS NULL OR s.sitio_id = %(sitio)s)
GROUP BY s.sitio_id, v.ventana_id
ORDER BY s.sitio_id"""


def ventanas(cuerpo=None, sitio=None, res_m=60.0, version=VERSION_POR_DEFECTO):
    with conectar() as conn:
        return conn.execute(SQL_VENTANAS, {"cuerpo": cuerpo, "sitio": sitio, "res": res_m, "version": version}).fetchall()


def cifra(valor: float, unidad: str, signo=False) -> str:
    """Formato para el texto en español: coma decimal, «°» pegado y «m» separado."""
    texto = f"{valor:+.1f}" if signo else f"{valor:.1f}"
    return texto.replace(".", ",") + ("°" if unidad == "°" else f" {unidad}")


def comparar(tierra: dict, ref: dict) -> dict:
    """Diferencias por variable en sus unidades y una descripción generada solo a partir de esas cifras."""
    def valor(metrica):
        return metrica["valor"] if metrica and metrica["estado"] == "calculado" else None

    variables, frases = [], []
    for key, (nombre, unidad) in VARIABLES.items():
        va, vb = valor(tierra["metricas"].get(key)), valor(ref["metricas"].get(key))
        if va is None or vb is None:
            variables.append({"variable": key, "nombre": nombre, "unidad": unidad, "estado": "sin_dato"})
            frases.append(f"{nombre}: sin dato comparable.")
            continue
        diferencia = round(va - vb, 2)
        variables.append({"variable": key, "nombre": nombre, "unidad": unidad, "tierra": round(va, 2),
                          "referencia": round(vb, 2), "diferencia": diferencia, "estado": "calculado"})
        frases.append(f"{nombre}: {cifra(va, unidad)} frente a {cifra(vb, unidad)} en {ref['sitio_id']} "
                      f"({cifra(diferencia, unidad, signo=True)}).")
    return {"sitio_id": tierra["sitio_id"], "lat": tierra["lat"], "lon": tierra["lon"],
            "fuente_coordenadas": tierra["fuente_coordenadas"], "fraccion_valida": tierra["fraccion_valida"],
            "variables": variables, "descripcion": " ".join(frases)}


@app.get("/salud")
def salud():
    with conectar() as conn:
        version = conn.execute("SELECT postgis_lib_version() AS postgis").fetchone()
    return {"estado": "ok", **version}


@app.get("/ventanas")
def listar(cuerpo: str | None = Query(None, pattern="^(tierra|luna|marte)$"), res_m: float = 60,
           version: str = VERSION_POR_DEFECTO):
    return {"version_metodo": version, "res_m": res_m, "ventanas": ventanas(cuerpo, None, res_m, version)}


@app.get("/mapa/tierra")
def mapa(res_m: float = 60, version: str = VERSION_POR_DEFECTO):
    """GeoJSON (EPSG:4326) con la huella de cada ventana terrestre y sus métricas, para el mapa."""
    features = [{"type": "Feature", "geometry": v.pop("geom"), "properties": v}
                for v in ventanas("tierra", None, res_m, version)]
    return {"type": "FeatureCollection", "features": features,
            "metadata": {"version_metodo": version, "res_m": res_m, "descargo": DESCARGO}}


@app.get("/comparacion/{referencia}")
def comparacion(referencia: str, res_m: float = 60, version: str = VERSION_POR_DEFECTO):
    refs = ventanas(None, referencia, res_m, version)
    if not refs or refs[0]["cuerpo"] == "tierra":
        raise HTTPException(404, f"No hay una ventana lunar o marciana '{referencia}' a {res_m} m con {version}")
    ref = refs[0]
    ref.pop("geom", None)
    return {"referencia": ref, "version_metodo": version, "res_m": res_m,
            "orden": "sin_ranking: falta la envolvente de referencia y la línea base preregistradas",
            "limites": LIMITES[ref["cuerpo"]], "descargo": DESCARGO,
            "candidatos": [comparar(t, ref) for t in ventanas("tierra", None, res_m, version)]}


SQL_DISTANCIAS = """
SELECT * FROM teselas_referencia
WHERE referencia_id = %(ref)s AND res_m = %(res)s AND version_metodo = %(version)s"""


def referencia(conn, ref, res_m, version):
    row = conn.execute("SELECT * FROM referencias WHERE referencia_id = %s AND res_m = %s AND version_metodo = %s",
                       (ref, res_m, version)).fetchone()
    if row is None:
        raise HTTPException(404, f"Sin envolvente para '{ref}' a {res_m} m con {version}")
    return row


@app.get("/busqueda/estado")
def estado_busqueda():
    """Avance de la cola del trabajador, para mostrar el progreso en el frontend."""
    with conectar() as conn:
        celdas = conn.execute("SELECT estado, count(*) AS n FROM celdas_busqueda GROUP BY estado").fetchall()
        teselas = conn.execute("SELECT count(*) AS n, max(c.actualizado_utc) AS ultima FROM teselas "
                               "JOIN celdas_busqueda c USING (celda_id)").fetchone()
        errores = conn.execute("SELECT celda_id, error FROM celdas_busqueda WHERE estado = 'error' LIMIT 20").fetchall()
    return {"celdas": {c["estado"]: c["n"] for c in celdas}, "teselas": teselas["n"],
            "ultima_actualizacion": teselas["ultima"], "errores": errores}


@app.get("/referencias")
def listar_referencias(res_m: float = 60, version: str = VERSION_POR_DEFECTO):
    with conectar() as conn:
        return conn.execute("SELECT * FROM referencias WHERE res_m = %s AND version_metodo = %s ORDER BY referencia_id",
                            (res_m, version)).fetchall()


@app.get("/analogos/{ref}")
def analogos(ref: str, res_m: float = 60, version: str = VERSION_POR_DEFECTO,
             limite: int = Query(100, ge=1, le=2000), minimo_dentro: int = Query(3, ge=0, le=3)):
    """Teselas terrestres ordenadas por cercanía a la envolvente de la referencia (GeoJSON para el mapa).

    Orden: más variables dentro de [P10, P90] y, a igualdad, menor distancia máxima en anchos de envolvente.
    """
    params = {"ref": ref, "res": res_m, "version": version, "min": minimo_dentro, "lim": limite}
    with conectar() as conn:
        env = referencia(conn, ref, res_m, version)
        rows = conn.execute(f"""SELECT *, ST_AsGeoJSON(geom)::json AS geojson FROM ({SQL_DISTANCIAS}) x
                                WHERE n_dentro >= %(min)s ORDER BY n_dentro DESC, dist_max, dist_mediana, celda_id, iy, ix
                                LIMIT %(lim)s""", params).fetchall()
        base = conn.execute(f"SELECT count(*) AS total, count(*) FILTER (WHERE n_dentro = 3) AS dentro "
                            f"FROM ({SQL_DISTANCIAS}) x", params).fetchone()
    features = []
    for r in rows:
        geometry = r.pop("geojson")
        r.pop("geom")
        r.pop("env")
        features.append({"type": "Feature", "geometry": geometry, "properties": r})
    tasa = base["dentro"] / base["total"] if base["total"] else None
    return {"type": "FeatureCollection", "features": features, "metadata": {
        "referencia": env, "version_metodo": version, "res_m": res_m, "descargo": DESCARGO,
        "teselas_procesadas": base["total"], "teselas_3_de_3": base["dentro"], "tasa_base": tasa,
        "lectura_tasa_base": ("Fracción de todas las teselas procesadas con las 3 variables dentro de la envolvente. "
                              "Si es alta, coincidir no distingue un lugar de otro."),
        "limites": LIMITES[env["cuerpo"]]}}


@app.get("/coherencia/{ref}")
def coherencia(ref: str, res_m: float = 60, version: str = VERSION_POR_DEFECTO):
    """Dónde quedan los sitios terrestres registrados (análogos NASA y controles) frente a todas las teselas.

    percentil = fracción de teselas procesadas que quedan peor ordenadas que la tesela que contiene el sitio.
    """
    params = {"ref": ref, "res": res_m, "version": version}
    with conectar() as conn:
        referencia(conn, ref, res_m, version)
        rows = conn.execute(f"""
            WITH x AS ({SQL_DISTANCIAS})
            SELECT s.sitio_id, s.fuente_coordenadas, t.celda_id, t.n_dentro, t.dist_max,
                   (SELECT count(*) FROM x o WHERE o.n_dentro < t.n_dentro
                        OR (o.n_dentro = t.n_dentro AND o.dist_max > t.dist_max))::float
                   / (SELECT count(*) FROM x) AS percentil
            FROM sitios s JOIN x t ON ST_Contains(t.geom, s.geom)
            WHERE s.cuerpo = 'tierra' ORDER BY s.sitio_id""", params).fetchall()
    return {"referencia": ref, "res_m": res_m, "version_metodo": version, "sitios": rows,
            "nota": "Solo aparecen sitios cuya tesela ya fue procesada. Un percentil alto es coherente con la "
                    "declaración NASA; no es una validación estadística (N pequeño)."}


from api.contrato import router as contrato  # noqa: E402  (usa SQL_DISTANCIAS y conectar de este módulo)

app.include_router(contrato, prefix="/api")


@app.get("/", include_in_schema=False)
def inicio():
    return RedirectResponse("/app/")


# El frontend estático se sirve desde el mismo origen que la API: no necesita CORS.
app.mount("/app", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="app")
