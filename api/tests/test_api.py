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
        conn.execute("""INSERT INTO referencias (referencia_id, cuerpo, lat, lon, lado_m, tesela_m, res_m, version_metodo,
                        fuente_coordenadas, n_subventanas, envolvente, calculado_utc)
                        VALUES ('LUN-T','luna',-85,10,15000,3000,60,'prueba-busqueda','p',25,%s,now())
                        ON CONFLICT DO NOTHING""", (Jsonb(env),))
        conn.execute("""INSERT INTO celdas_busqueda (celda_id, lat_min, lon_min, zona, estado)
                        VALUES ('N10E010',10,10,'prueba','hecha') ON CONFLICT DO NOTHING""")
        for ix, (med, p90, rel) in enumerate([(6, 12, 200), (6, 30, 200), (1, 2, 5)]):
            x0 = 10 + ix * 0.1
            conn.execute(f"""INSERT INTO teselas (celda_id, res_m, version_metodo, ix, iy, lat, lon, geom,
                             pendiente_mediana, pendiente_p90, relieve, rugosidad, fraccion_valida)
                             VALUES ('N10E010',60,'prueba-busqueda',%s,0,10.05,%s,
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


@pytest.mark.skipif(not DSN, reason="Requiere TEST_DATABASE_URL (PostgreSQL + PostGIS desechable)")
def test_frontend_contract(monkeypatch):
    from fastapi.testclient import TestClient
    from psycopg.types.json import Jsonb

    from analisis.cargar import aplicar_migraciones
    from api.main import VERSION_POR_DEFECTO, app

    env = {"pendiente_mediana_grados": {"p10": 4, "p50": 6, "p90": 8},
           "pendiente_p90_grados": {"p10": 10, "p50": 13, "p90": 16},
           "relieve_p95_p5_m": {"p10": 100, "p50": 200, "p90": 300}}
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            aplicar_migraciones(cur)
        conn.execute("DELETE FROM teselas WHERE celda_id = 'N30E030'")
        conn.execute("""INSERT INTO referencias (referencia_id, cuerpo, lat, lon, lado_m, tesela_m, res_m, version_metodo,
                        fuente_coordenadas, n_subventanas, envolvente, nombre)
                        VALUES ('LUN-C','luna',-85,10,15000,3000,60,%s,'p',25,%s,'Región C') ON CONFLICT DO NOTHING""",
                     (VERSION_POR_DEFECTO, Jsonb(env)))
        conn.execute("""INSERT INTO celdas_busqueda (celda_id, lat_min, lon_min, zona, estado) VALUES
                        ('N30E030',30,30,'prueba','hecha'), ('N31E031',31,31,'prueba','pendiente') ON CONFLICT DO NOTHING""")
        conn.execute("""INSERT INTO teselas (celda_id, res_m, version_metodo, ix, iy, lat, lon, geom,
                        pendiente_mediana, pendiente_p90, relieve, rugosidad, fraccion_valida,
                        ndvi_max, ndvi_n, lst_dia_max_k, lst_dia_n, contexto_id)
                        VALUES ('N30E030',60,%s,0,0,30.05,30.05,
                        ST_GeomFromText('POLYGON((30 30,30.1 30,30.1 30.1,30 30.1,30 30))',4326),
                        7,12,250,40,1,0.2,2,310,1,'test-modis')""",
                      (VERSION_POR_DEFECTO,))
        from analisis.trabajador import candidatos
        from analisis import trabajador

        meta = {"meses": ["2025-01", "2025-07"], "fuentes": [
            {"producto": "MOD13C2", "mes": "2025-01", "url": "https://data.lpdaac.earthdatacloud.nasa.gov/test.hdf"}]}
        conn.execute("""INSERT INTO contexto_modis (contexto_id, metadata, umbral_ndvi) VALUES ('test-modis',%s,0.3)
                        ON CONFLICT (unico) DO UPDATE SET contexto_id = EXCLUDED.contexto_id,
                        metadata = EXCLUDED.metadata, umbral_ndvi = EXCLUDED.umbral_ndvi""", (Jsonb(meta),))
        monkeypatch.setattr(trabajador, "contexto", lambda cfg: {"contexto_id": "test-modis"})
        candidatos(conn, {"ndvi_umbral_vegetacion": 0.3}, "N30E030")
        for sid, lat, rol, tags in (("TIE-C", 30.05, "analogo_nasa", ["JETT3-TERRENO-01"]),
                                    ("TIE-P", 31.5, "analogo_nasa_marte", None)):
            conn.execute("""INSERT INTO sitios (sitio_id, cuerpo, lat, lon, fuente_coordenadas, geom, nombre, rol, etiquetas)
                            VALUES (%s,'tierra',%s,%s,'prueba',ST_SetSRID(ST_MakePoint(%s,%s),4326),%s,%s,%s)
                            ON CONFLICT DO NOTHING""", (sid, lat, lat, lat, lat, "Sitio " + sid, rol, tags))
    monkeypatch.setenv("DATABASE_URL", DSN)
    client = TestClient(app)

    sites = {s["id"]: s for s in client.get("/api/sites").json()}
    assert sites["TIE-C"] == {"id": "TIE-C", "name": "Sitio TIE-C", "lat": 30.05, "lon": 30.05,
                              "coverage": "Análogo NASA documentado"}
    candidate = sites["T~N30E030~0~0"]
    assert candidate["coverage"] == "Candidato detectado · 3/3 frente a Región C" and set(candidate) == {"id", "name", "lat", "lon", "coverage"}

    comps = client.get("/api/sites/TIE-C/comparisons").json()
    comp = next(c for c in comps if c["id"] == "LUN-C~relieve")
    assert comp == {"id": "LUN-C~relieve", "label": "Región C · Relieve P95–P5", "variable": "Relieve P95–P5",
                    "reference": "Luna · Región C"}

    done = client.post("/api/analyses", json={"siteId": "TIE-C", "comparisonId": "LUN-C~relieve"}).json()
    assert done["status"] == "completed" and done["id"] == "TIE-C|LUN-C~relieve"
    res = done["result"]
    assert (res["earthValue"], res["referenceValue"], res["difference"], res["unit"]) == (250, 200, 50, "m")
    assert "3/3 dentro" in res["limitation"] and "dentro" in res["limitation"]
    assert "NDVI máximo 0.2000 (2/2" in res["limitation"]
    assert "máxima diurna 310,0 K (1 meses válidos)" in res["limitation"]
    assert "no extremos anuales" in res["limitation"]
    assert any("test.hdf" in s["url"] for s in res["sources"])
    assert any("nasa.gov" in s["url"] for s in res["sources"]) and set(res) == {
        "earthValue", "referenceValue", "unit", "difference", "scale", "limitation", "sources", "earthContext"}
    assert res["earthContext"]["months"] == ["2025-01", "2025-07"]
    assert res["earthContext"]["passesNdviScreen"] is True
    assert res["earthContext"]["lstNightMinK"] is None
    assert client.get("/api/analyses/" + done["id"]).json() == done

    pending = client.post("/api/analyses", json={"siteId": "TIE-P", "comparisonId": "LUN-C~relieve"}).json()
    assert pending["status"] == "insufficient_data" and "N31E031: pendiente" in pending["message"]

    assert client.post("/api/analyses", json={"siteId": "T~N30E030~0~0", "comparisonId": "LUN-C~pendiente_p90"}).json()["result"]["earthValue"] == 12
    assert client.get("/api/sites/NO-EXISTE/comparisons").status_code == 404
    assert client.post("/api/analyses", json={"siteId": "TIE-C", "comparisonId": "LUN-C~otra"}).status_code == 404


@pytest.mark.skipif(not DSN, reason="Requiere PostgreSQL + PostGIS desechable")
def test_candidates_refresh_filter_limit_and_atomicity(monkeypatch):
    from fastapi.testclient import TestClient
    from psycopg.types.json import Jsonb

    from analisis import trabajador
    from analisis.cargar import aplicar_migraciones
    from api import contrato
    from api.main import app

    version = "prueba-modis"
    cfg = {"ndvi_umbral_vegetacion": .3}
    env = {k: {"p10": a, "p50": b, "p90": c} for k, a, b, c in [
        ("pendiente_mediana_grados", 4, 6, 8), ("pendiente_p90_grados", 10, 13, 16),
        ("relieve_p95_p5_m", 100, 200, 300)]}
    monkeypatch.setattr(trabajador, "contexto", lambda cfg: {"contexto_id": "qa-test"})
    monkeypatch.setattr(contrato, "VERSION_POR_DEFECTO", version)
    monkeypatch.setenv("DATABASE_URL", DSN)
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            aplicar_migraciones(cur)
            aplicar_migraciones(cur)
        conn.execute("DELETE FROM teselas WHERE version_metodo = %s", (version,))
        conn.execute("DELETE FROM referencias WHERE version_metodo = %s", (version,))
        conn.execute("""INSERT INTO referencias (referencia_id, cuerpo, lat, lon, lado_m, tesela_m, res_m,
                        version_metodo, fuente_coordenadas, n_subventanas, envolvente)
                        VALUES ('LUN-Q','luna',-85,10,15000,3000,60,%s,'prueba',25,%s)""", (version, Jsonb(env)))
        conn.execute("""INSERT INTO celdas_busqueda (celda_id, lat_min, lon_min, zona)
                        VALUES ('N20E020',20,20,'qa') ON CONFLICT DO NOTHING""")
        conn.execute("""INSERT INTO contexto_modis (contexto_id, metadata, umbral_ndvi) VALUES ('qa-test',%s,0.3)
                        ON CONFLICT (unico) DO UPDATE SET contexto_id = EXCLUDED.contexto_id,
                        metadata = EXCLUDED.metadata, umbral_ndvi = EXCLUDED.umbral_ndvi""",
                     (Jsonb({"meses": ["2025-01", "2025-07"]}),))
        for ix in range(42):
            ndvi, n, ctx = (.2, 2, "qa-test")
            if ix >= 35:
                ndvi, n, ctx = [(.3, 2, "qa-test"), (.3001, 2, "qa-test"), (None, 0, "qa-test"),
                                (.1, 1, "qa-test"), (.1, 2, "otro"), (.8, 2, "qa-test"), (.1, 0, "qa-test")][ix - 35]
            conn.execute("""INSERT INTO teselas (celda_id, res_m, version_metodo, ix, iy, lat, lon, geom,
                            pendiente_mediana, pendiente_p90, relieve, rugosidad, fraccion_valida,
                            ndvi_max, ndvi_n, contexto_id)
                            VALUES ('N20E020',60,%s,%s,0,20.05,20.05,
                            ST_GeomFromText('POLYGON((20 20,20.1 20,20.1 20.1,20 20.1,20 20))',4326),
                            6,13,200,1,1,%s,%s,%s)""", (version, ix, ndvi, n, ctx))
        assert trabajador.candidatos(conn, cfg, "N20E020") == 36
        assert trabajador.candidatos(conn, cfg, "N20E020") == 36  # idempotente
        conn.commit()
        client = TestClient(app)
        detectados = [s for s in client.get("/api/sites").json() if s["id"].startswith("T~N20E020")]
        assert len(detectados) == 30 and detectados[-1]["id"] == "T~N20E020~29~0"
        conn.execute("UPDATE teselas SET ndvi_max = .9 WHERE version_metodo = %s AND ix = 0", (version,))
        assert trabajador.candidatos(conn, cfg, "N20E020") == 35  # no deja candidato obsoleto
        conn.commit()
        with pytest.raises(ValueError, match="Contexto/umbral"):
            trabajador.candidatos(conn, {"ndvi_umbral_vegetacion": .2})
        conn.rollback()
        assert conn.execute("SELECT count(*) FROM candidatos WHERE referencia_id = 'LUN-Q'").fetchone()[0] == 35
        env["pendiente_mediana_grados"]["p10"] = None
        conn.execute("UPDATE referencias SET envolvente = %s WHERE referencia_id = 'LUN-Q'", (Jsonb(env),))
        assert trabajador.candidatos(conn, cfg, "N20E020") == 0
        conn.rollback()  # referencia + ranking vuelven juntos al estado anterior
        assert conn.execute("SELECT count(*) FROM candidatos WHERE referencia_id = 'LUN-Q'").fetchone()[0] == 35


@pytest.mark.skipif(not DSN, reason="Requiere PostgreSQL + PostGIS desechable")
def test_context_backfill_replaces_previous_values_and_rolls_back(tmp_path, monkeypatch):
    from analisis import trabajador
    from analisis.cargar import aplicar_migraciones

    ctx = {"contexto_id": "backfill-nuevo", "metadata": {"meses": ["2025-01", "2025-07"], "fuentes": []}}
    monkeypatch.setattr(trabajador, "contexto", lambda cfg: ctx)
    monkeypatch.setattr(trabajador.modis, "preparar", lambda *args: tmp_path / "test.npz")
    sample = {"contexto_id": ctx["contexto_id"], "ndvi_max": None, "ndvi_n": 0, "lst_dia_max_k": 305.2,
              "lst_dia_n": 1, "lst_noche_min_k": None, "lst_noche_n": 0}
    monkeypatch.setattr(trabajador.modis, "muestrear", lambda *args: sample)
    cfg = {"contexto_modis": {"cache": str(tmp_path), "meses": ctx["metadata"]["meses"]}, "ndvi_umbral_vegetacion": .3}
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            aplicar_migraciones(cur)
        # Fixture propia: esta prueba no depende de que se hayan ejecutado las anteriores.
        conn.execute("""INSERT INTO celdas_busqueda (celda_id, lat_min, lon_min, zona)
                        VALUES ('N21E021',21,21,'backfill') ON CONFLICT DO NOTHING""")
        conn.execute("""INSERT INTO teselas (celda_id, res_m, version_metodo, ix, iy, lat, lon, geom,
                        pendiente_mediana, pendiente_p90, relieve, rugosidad, fraccion_valida, ndvi_max)
                        VALUES ('N21E021',60,'prueba-backfill',0,0,21.05,21.05,
                        ST_GeomFromText('POLYGON((21 21,21.1 21,21.1 21.1,21 21.1,21 21))',4326),
                        6,13,200,1,1,.2) ON CONFLICT DO NOTHING""")
        trabajador.rellenar_contexto(conn, cfg)
        row = conn.execute("""SELECT ndvi_max, ndvi_n, lst_dia_max_k, contexto_id FROM teselas
                              WHERE celda_id = 'N21E021'""").fetchone()
        assert row[0:2] == (None, 0) and abs(row[2] - 305.2) < .001 and row[3] == ctx["contexto_id"]
        assert conn.execute("SELECT count(*) FROM candidatos").fetchone()[0] == 0
        ctx["contexto_id"] = "no-publicar"
        def fallo(*args):
            raise ValueError("simula fallo durante muestreo")
        monkeypatch.setattr(trabajador.modis, "muestrear", fallo)
        with pytest.raises(ValueError, match="simula fallo"):
            trabajador.rellenar_contexto(conn, cfg)
        conn.rollback()
        assert conn.execute("SELECT contexto_id FROM contexto_modis").fetchone()[0] == "backfill-nuevo"


@pytest.mark.skipif(not DSN, reason="Requiere PostgreSQL + PostGIS desechable")
def test_worker_stores_context_and_refreshes_cell_candidates(monkeypatch):
    import numpy as np
    from psycopg.types.json import Jsonb
    from rasterio.crs import CRS
    from rasterio.transform import from_origin

    from analisis import trabajador
    from analisis.cargar import aplicar_migraciones
    from analisis.metricas import VERSION_METODO

    z = np.tile(np.arange(100) * 60 * np.tan(np.radians(6)), (100, 1))
    crs = CRS.from_proj4("+proj=aeqd +lat_0=35.32 +lon_0=-111.52 +ellps=WGS84 +units=m +no_defs")
    monkeypatch.setattr(trabajador, "ventana", lambda *a, **kw: (
        {60: z}, {60: from_origin(-3000, 3000, 60, 60)}, crs, []))
    monkeypatch.setattr(trabajador, "contexto", lambda cfg: {"contexto_id": "worker-test"})
    sample = {"ndvi_max": .2, "ndvi_n": 2, "lst_dia_max_k": 310, "lst_dia_n": 2,
              "lst_noche_min_k": 270, "lst_noche_n": 2, "contexto_id": "worker-test"}
    monkeypatch.setattr(trabajador.modis, "muestrear", lambda *a: sample)
    cfg = {"tesela_m": 3000, "fraccion_valida_min": .9, "escalas_m": [60], "ndvi_umbral_vegetacion": .3}
    env = {k: {"p10": 0, "p50": 100, "p90": 1000} for k in
           ("pendiente_mediana_grados", "pendiente_p90_grados", "relieve_p95_p5_m")}
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            aplicar_migraciones(cur)
        conn.execute("DELETE FROM teselas WHERE celda_id = 'N35W112'")
        conn.execute("""INSERT INTO celdas_busqueda (celda_id, lat_min, lon_min, zona)
                        VALUES ('N35W112',35,-112,'worker') ON CONFLICT DO NOTHING""")
        conn.execute("""INSERT INTO referencias (referencia_id, cuerpo, lat, lon, lado_m, tesela_m, res_m,
                        version_metodo, fuente_coordenadas, n_subventanas, envolvente)
                        VALUES ('LUN-W','luna',-85,10,15000,3000,60,%s,'prueba',25,%s)
                        ON CONFLICT (referencia_id, res_m, version_metodo)
                        DO UPDATE SET envolvente = EXCLUDED.envolvente""", (VERSION_METODO, Jsonb(env)))
        conn.execute("""INSERT INTO contexto_modis (contexto_id, metadata, umbral_ndvi) VALUES ('worker-test',%s,.3)
                        ON CONFLICT (unico) DO UPDATE SET contexto_id = EXCLUDED.contexto_id,
                        metadata = EXCLUDED.metadata, umbral_ndvi = EXCLUDED.umbral_ndvi""",
                     (Jsonb({"meses": ["2025-01", "2025-07"]}),))
        conn.commit()
        trabajador.procesar(conn, cfg, ("N35W112", 35, -112, 1))
        assert conn.execute("SELECT count(*) FROM candidatos WHERE referencia_id = 'LUN-W'").fetchone()[0] == 4
        assert conn.execute("SELECT DISTINCT ndvi_max, ndvi_n, contexto_id FROM teselas WHERE celda_id = 'N35W112'").fetchall() == [
            (.2, 2, "worker-test")]
        conn.commit()
        sample["ndvi_max"] = .8
        trabajador.procesar(conn, cfg, ("N35W112", 35, -112, 2))
        assert conn.execute("SELECT count(*) FROM candidatos WHERE referencia_id = 'LUN-W'").fetchone()[0] == 0
        conn.commit()
        cfg.update({"minimo_subventanas": 4, "referencias": [{
            "id": "LUN-W", "cuerpo": "luna", "lat": -84, "lon": 11, "lado_m": 6000,
            "fuente_coordenadas": "coordenadas actualizadas", "nombre": "Referencia actualizada"}]})
        trabajador.referencias(conn, cfg)
        assert conn.execute("""SELECT lat, lon, lado_m, fuente_coordenadas FROM referencias
                               WHERE referencia_id = 'LUN-W'""").fetchone() == (-84, 11, 6000, "coordenadas actualizadas")


@pytest.mark.skipif(not DSN, reason="Requiere PostgreSQL + PostGIS desechable")
def test_automatic_batches_are_bounded_and_do_not_reopen_finished_cells():
    from analisis.cargar import aplicar_migraciones
    from analisis.trabajador import alimentar_cola, celdas_config

    cfg = {"auto_encolar": {"lote": 100, "minimo_pendientes": 100},
           "zonas": [{"bbox": [60, -50, 161, -49], "prioridad": 100, "nombre": "prueba lotes"}]}
    cells = celdas_config(cfg)
    ids = [c[0] for c in cells]
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            aplicar_migraciones(cur)
        conn.execute("DELETE FROM celdas_busqueda WHERE celda_id=ANY(%s)", (ids,))
        conn.commit()
        assert alimentar_cola(conn, cfg, cells) == 100
        assert alimentar_cola(conn, cfg, cells) == 0  # no sobrealimenta mientras hay suficientes pendientes
        conn.execute("UPDATE celdas_busqueda SET estado='hecha' WHERE celda_id=ANY(%s)", (ids,))
        conn.commit()
        assert alimentar_cola(conn, cfg, cells) == 1
        assert alimentar_cola(conn, cfg, cells) == 0  # dominio agotado, sin duplicar ni reabrir las hechas
        assert conn.execute("SELECT count(*) FROM celdas_busqueda WHERE celda_id=ANY(%s)", (ids,)).fetchone()[0] == 101
        assert conn.execute("SELECT count(*) FROM celdas_busqueda WHERE celda_id=ANY(%s) AND estado='hecha'", (ids,)).fetchone()[0] == 100


@pytest.mark.skipif(not DSN, reason="Requiere PostgreSQL + PostGIS desechable")
def test_expired_reservations_are_recovered_with_a_retry_ceiling():
    from analisis.cargar import aplicar_migraciones
    from analisis.trabajador import tomar

    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            aplicar_migraciones(cur)
        for cid, lon, intentos in [("S80W170", -170, 1), ("S80W169", -169, 3)]:
            conn.execute("""INSERT INTO celdas_busqueda (celda_id,lat_min,lon_min,zona,prioridad,estado,intentos,actualizado_utc)
                            VALUES (%s,-80,%s,'prueba reserva',-1000,'en_curso',%s,now()-interval '2 hours')
                            ON CONFLICT (celda_id) DO UPDATE SET estado='en_curso',intentos=EXCLUDED.intentos,
                            actualizado_utc=EXCLUDED.actualizado_utc""", (cid, lon, intentos))
        conn.commit()
        row = tomar(conn)
        assert row[0] == "S80W170" and row[3] == 2
        assert conn.execute("SELECT estado FROM celdas_busqueda WHERE celda_id='S80W169'").fetchone()[0] == "error"
        conn.execute("UPDATE celdas_busqueda SET estado='hecha' WHERE celda_id='S80W170'")


@pytest.mark.skipif(not DSN, reason="Requiere PostgreSQL + PostGIS desechable")
def test_catalog_metadata_and_live_status_without_recomputing_terrain(monkeypatch):
    from fastapi.testclient import TestClient
    from analisis.cargar import aplicar_migraciones
    from analisis import trabajador
    from api.main import app

    monkeypatch.setenv("DATABASE_URL", DSN)
    monkeypatch.setattr(trabajador.socket, "gethostname", lambda: "worker-prueba")
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            aplicar_migraciones(cur)
        conn.execute("""INSERT INTO sitios (sitio_id,cuerpo,lat,lon,fuente_coordenadas)
                        VALUES ('TIE-CINDER-LAKE','tierra',35.3197,-111.5171,'prueba')
                        ON CONFLICT (sitio_id) DO UPDATE SET lat=EXCLUDED.lat,lon=EXCLUDED.lon,nombre=NULL,rol=NULL,etiquetas=NULL""")
        before = conn.execute("SELECT count(*) FROM teselas").fetchone()[0]
        trabajador.catalogo(conn)
        trabajador.catalogo(conn)
        row = conn.execute("SELECT nombre,rol,etiquetas FROM sitios WHERE sitio_id='TIE-CINDER-LAKE'").fetchone()
        assert row == ("Cinder Lake (Arizona)", "analogo_nasa", ["JETT3-TERRENO-01"])
        assert conn.execute("SELECT count(*) FROM teselas").fetchone()[0] == before
        trabajador.latido(conn, "procesando", "S80W170", 100)
        client = TestClient(app)
        state = client.get("/api/search/status")
        assert state.status_code == 200
        worker = next(w for w in state.json()["trabajadores"] if w["trabajador_id"] == "worker-prueba")
        assert worker["senal_reciente"] and worker["estado"] == "procesando" and worker["celdas_elegibles"] == 100
        conn.execute("UPDATE trabajadores SET actualizado_utc=now()-interval '10 minutes' WHERE trabajador_id='worker-prueba'")
        conn.commit()
        worker = next(w for w in client.get("/api/search/status").json()["trabajadores"] if w["trabajador_id"] == "worker-prueba")
        assert worker["senal_reciente"] is False
        conn.execute("UPDATE sitios SET lat=0 WHERE sitio_id='TIE-CINDER-LAKE'")
        with pytest.raises(ValueError, match="coordenadas distintas"):
            trabajador.catalogo(conn)
        conn.rollback()
