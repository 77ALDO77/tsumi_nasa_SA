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
