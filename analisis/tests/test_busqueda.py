import numpy as np
import pytest
from rasterio.crs import CRS
from rasterio.transform import from_origin

from analisis.busqueda import envolvente, geometrias
from analisis.metricas import metricas_teselas


def test_tiles_keep_slope_and_borders():
    cols = np.arange(100) * 60.0
    z = np.tile(cols * np.tan(np.radians(10)), (100, 1))
    tiles = metricas_teselas(z, 60.0, 50, 0.9)
    assert len(tiles) == 4
    # La pendiente se calcula sobre toda la caja: solo el borde exterior pierde celdas, no los bordes internos.
    assert all(abs(t["pendiente_mediana_grados"] - 10) < 0.1 for t in tiles)
    z[:50, :50] = np.nan
    assert metricas_teselas(z, 60.0, 50, 0.9)[0]["estado"] == "evidencia_insuficiente"


def test_envelope_is_p10_p90_and_requires_enough_windows():
    tiles = [{"estado": "calculado", "pendiente_mediana_grados": i, "pendiente_p90_grados": 2 * i,
              "relieve_p95_p5_m": 10 * i} for i in range(1, 21)]
    env, n = envolvente(tiles, 20)
    assert n == 20 and env["pendiente_mediana_grados"] == {"p10": 2.9, "p50": 10.5, "p90": 18.1}
    with pytest.raises(ValueError):
        envolvente(tiles[:5], 20)


def test_tile_geometry_center():
    crs = CRS.from_proj4("+proj=aeqd +lat_0=35 +lon_0=-111 +ellps=WGS84 +units=m +no_defs")
    tile = [{"ix": 1, "iy": 1}]
    geometrias(from_origin(-4500, 4500, 60, 60), crs, 50, tile, "EPSG:4326")  # 3x3 teselas de 3 km
    assert abs(tile[0]["lat"] - 35) < 1e-6 and abs(tile[0]["lon"] + 111) < 1e-6
    assert len(tile[0]["poligono"]) == 5 and tile[0]["poligono"][0] == tile[0]["poligono"][-1]


def test_structured_log_is_one_json_line(capsys):
    import json
    import logging

    from analisis.registro import configurar, evento

    log = configurar("prueba")
    try:
        raise ValueError("fallo")
    except ValueError as exc:
        evento(log, "celda_fallida", logging.ERROR, exc_info=exc, celda="N35W112", duracion_s=1.5)
    line = capsys.readouterr().out.strip()
    data = json.loads(line)
    assert "\n" not in line and data["evento"] == "celda_fallida" and data["celda"] == "N35W112"
    assert data["nivel"] == "error" and data["servicio"] == "prueba" and "ValueError" in data["excepcion"]


def test_queue_cells_deduplicate_and_keep_priority(monkeypatch):
    from analisis import trabajador
    from analisis.trabajador import celdas_config
    cfg = {"zonas": [
        {"nombre": "amplia", "bbox": [0, 0, 2, 2], "prioridad": 100},
        {"nombre": "prioritaria", "bbox": [0, 0, 1, 1], "prioridad": 1}]}
    cells = celdas_config(cfg)
    assert len(cells) == 4
    assert cells[0] == ("N00E000", 0, 0, "prioritaria", 1)
    mask = np.zeros((180, 360), dtype=bool)
    mask[89, 180] = True
    monkeypatch.setattr(trabajador, "contexto", lambda cfg: {})
    monkeypatch.setattr(trabajador.modis, "celdas_elegibles", lambda *a: mask)
    cfg.update({"contexto_modis": {"meses": ["2025-01"]}, "ndvi_umbral_vegetacion": .3})
    assert trabajador.celdas_del_perfil(cfg) == [cells[0]]


def test_groups_chain_close_points_without_grid_cuts():
    from analisis.trabajador import grupos
    # 3 km entre vecinas en el ecuador (0,027°); la cuarta queda a 7 km de la tercera.
    fila = [(0, 0), (0, .027), (0, .054), (0, .117)]
    assert grupos(fila, 6) == [[0, 1, 2], [3]]
    assert grupos(fila, 10) == [[0, 1, 2, 3]]
    assert grupos([(10, 179.99), (10, -179.99)], 6) == [[0, 1]]  # antimeridiano: ~2,2 km
    assert grupos([(89.99, 0), (89.99, 180)], 6) == [[0, 1]]      # polo: ~2,2 km
    assert grupos([(35, -111), (35.1, -111)], 6) == [[0], [1]]    # 11 km
    assert grupos([], 6) == []


def test_queue_cells_reject_bad_coordinates():
    from analisis.trabajador import celdas_config
    for bbox in [[-181, 0, 1, 1], [0, -91, 1, 1], [0, 0, 0, 1], [0.5, 0, 1, 1], [0, 0, 1]]:
        with pytest.raises(ValueError):
            celdas_config({"zonas": [{"nombre": "prueba", "bbox": bbox, "prioridad": 1}]})
