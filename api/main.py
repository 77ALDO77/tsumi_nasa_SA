"""API de solo lectura sobre las métricas de relieve cargadas por analisis.cargar.

Desde la raíz: DATABASE_URL=... uvicorn api.main:app --host 127.0.0.1 --port 8000
No calcula nada: lee la base. No ordena candidatos hasta que exista la envolvente de referencia preregistrada.
"""
import os
from pathlib import Path

import psycopg
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from psycopg.rows import dict_row

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
origins = [o for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o]
if origins:
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET"], allow_headers=["*"])


def conectar():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise HTTPException(503, "DATABASE_URL no está configurada")
    try:
        return psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5)
    except psycopg.OperationalError as exc:
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


@app.get("/", include_in_schema=False)
def inicio():
    return RedirectResponse("/app/")


# El frontend estático se sirve desde el mismo origen que la API: no necesita CORS.
app.mount("/app", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="app")
