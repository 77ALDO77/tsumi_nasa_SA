import json
import os

import psycopg
import pytest

from api.main import comparar


def metrics(**values):
    return {k: {"valor": v, "unidad": "x", "estado": "calculado" if v is not None else "evidencia_insuficiente"}
            for k, v in values.items()}


def test_description_uses_only_numbers_and_marks_missing():
    tierra = {"sitio_id": "TIE-A", "lat": 1, "lon": 2, "fuente_coordenadas": "f", "fraccion_valida": 1.0,
              "metricas": metrics(pendiente_mediana=3.9, relieve_p95_p5=None)}
    ref = {"sitio_id": "LUN-R", "metricas": metrics(pendiente_mediana=6.6, relieve_p95_p5=626.0)}
    result = comparar(tierra, ref)
    slope = next(v for v in result["variables"] if v["variable"] == "pendiente_mediana")
    assert slope["diferencia"] == -2.7 and slope["estado"] == "calculado"
    assert "3,9° frente a 6,6° en LUN-R (-2,7°)" in result["descripcion"]
    assert next(v for v in result["variables"] if v["variable"] == "relieve_p95_p5")["estado"] == "sin_dato"
    assert "sin dato comparable" in result["descripcion"]


DSN = os.environ.get("TEST_DATABASE_URL")


@pytest.mark.skipif(not DSN, reason="Requiere TEST_DATABASE_URL (PostgreSQL + PostGIS desechable)")
def test_endpoints_against_loaded_manifest(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from analisis.cargar import cargar
    from api.main import app

    run = tmp_path / "prueba-api"
    run.mkdir()
    base = {"estado": "calculado", "res_m": 60, "n_celdas": 250 * 250, "n_celdas_validas": 62500, "fraccion_valida": 1.0,
            "pendiente_mediana_grados": 3.0, "pendiente_p90_grados": 10.0, "relieve_p95_p5_m": 300.0,
            "rugosidad_rms_plano_m": 50.0, "fuentes": []}
    windows = [
        {**base, "id": "LUN-PRUEBA", "cuerpo": "luna", "rol": "r", "lat": -85.0, "lon": 10.0, "fuente_coordenadas": "prueba",
         "pendiente_mediana_grados": 6.0, "crs_calculo": "+proj=aeqd +lat_0=-85 +lon_0=10 +R=1737400 +units=m +no_defs"},
        {**base, "id": "TIE-PRUEBA", "cuerpo": "tierra", "rol": "r", "lat": 35.0, "lon": -111.0, "fuente_coordenadas": "prueba",
         "crs_calculo": "+proj=aeqd +lat_0=35 +lon_0=-111 +ellps=WGS84 +units=m +no_defs"},
    ]
    (run / "manifest.json").write_text(json.dumps({
        "config_sha256": "c", "version": "t", "git_commit": None, "inicio_utc": "2026-11-15T00:00:00+00:00",
        "lado_m": 15000, "escalas_m": [60], "remuestreo": "average", "proyeccion_calculo": "aeqd",
        "limites": [], "version_metodo": "prueba-api", "ventanas": windows}), encoding="utf-8")
    with psycopg.connect(DSN) as conn:
        cargar(conn, run)
    monkeypatch.setenv("DATABASE_URL", DSN)
    client = TestClient(app)
    assert client.get("/salud").json()["estado"] == "ok"
    mapa = client.get("/mapa/tierra", params={"version": "prueba-api"}).json()
    feature = next(f for f in mapa["features"] if f["properties"]["sitio_id"] == "TIE-PRUEBA")
    assert feature["geometry"]["type"] == "Polygon"
    assert feature["properties"]["metricas"]["relieve_p95_p5"]["valor"] == 300.0
    comp = client.get("/comparacion/LUN-PRUEBA", params={"version": "prueba-api"}).json()
    cand = next(c for c in comp["candidatos"] if c["sitio_id"] == "TIE-PRUEBA")
    assert next(v for v in cand["variables"] if v["variable"] == "pendiente_mediana")["diferencia"] == -3.0
    assert comp["orden"].startswith("sin_ranking") and comp["limites"]
    assert client.get("/comparacion/TIE-PRUEBA", params={"version": "prueba-api"}).status_code == 404


def test_frontend_is_served():
    from fastapi.testclient import TestClient

    from api.main import app

    client = TestClient(app)
    assert client.get("/", follow_redirects=False).headers["location"] == "/app/"
    page = client.get("/app/")
    assert page.status_code == 200 and 'id="mapa"' in page.text


@pytest.mark.skipif(not DSN, reason="Requiere TEST_DATABASE_URL (PostgreSQL + PostGIS desechable)")
def test_search_endpoints_rank_by_envelope(monkeypatch):
    from fastapi.testclient import TestClient
    from psycopg.types.json import Jsonb

    from analisis.cargar import aplicar_migraciones
    from api.main import app

    env = {"pendiente_mediana_grados": {"p10": 4, "p90": 8}, "pendiente_p90_grados": {"p10": 10, "p90": 16},
           "relieve_p95_p5_m": {"p10": 100, "p90": 300}}
    square = "ST_GeomFromText('POLYGON((%s %s,%s %s,%s %s,%s %s,%s %s))',4326)"
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            aplicar_migraciones(cur)
        conn.execute("DELETE FROM teselas WHERE version_metodo = 'prueba-busqueda'")
        conn.execute("""INSERT INTO referencias VALUES ('LUN-T','luna',-85,10,15000,3000,60,'prueba-busqueda','p',25,%s,now())
                        ON CONFLICT DO NOTHING""", (Jsonb(env),))
        conn.execute("""INSERT INTO celdas_busqueda (celda_id, lat_min, lon_min, zona, estado)
                        VALUES ('N10E010',10,10,'prueba','hecha') ON CONFLICT DO NOTHING""")
        for ix, (med, p90, rel) in enumerate([(6, 12, 200), (6, 30, 200), (1, 2, 5)]):
            x0 = 10 + ix * 0.1
            conn.execute(f"""INSERT INTO teselas VALUES ('N10E010',60,'prueba-busqueda',%s,0,10.05,%s,
                             {square % (x0, 10, x0 + .1, 10, x0 + .1, 10.1, x0, 10.1, x0, 10)},%s,%s,%s,1,1)""",
                         (ix, x0 + .05, med, p90, rel))
        conn.execute("""INSERT INTO sitios (sitio_id, cuerpo, lat, lon, fuente_coordenadas, geom)
                        VALUES ('TIE-T','tierra',10.05,10.05,'prueba',ST_SetSRID(ST_MakePoint(10.05,10.05),4326))
                        ON CONFLICT DO NOTHING""")
    monkeypatch.setenv("DATABASE_URL", DSN)
    client = TestClient(app)
    out = client.get("/analogos/LUN-T", params={"version": "prueba-busqueda", "minimo_dentro": 0}).json()
    ranked = [(f["properties"]["ix"], f["properties"]["n_dentro"]) for f in out["features"]]
    assert ranked == [(0, 3), (1, 2), (2, 0)]
    assert out["metadata"]["tasa_base"] == 1 / 3
    assert client.get("/analogos/LUN-T", params={"version": "prueba-busqueda"}).json()["features"][0]["properties"]["ix"] == 0
    coh = client.get("/coherencia/LUN-T", params={"version": "prueba-busqueda"}).json()["sitios"]
    assert coh[0]["sitio_id"] == "TIE-T" and coh[0]["n_dentro"] == 3 and abs(coh[0]["percentil"] - 2 / 3) < 1e-9
    assert client.get("/busqueda/estado").json()["celdas"]["hecha"] >= 1
    assert client.get("/analogos/NO-EXISTE").status_code == 404
