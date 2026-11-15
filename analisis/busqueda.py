"""Envolvente de una región de referencia y geometría de teselas para la búsqueda continua.

La comparación tesela-envolvente vive en SQL (db/migraciones/002_busqueda.sql, dist_envolvente) para
que la API ordene sobre la base completa; aquí solo se calcula lo que necesita leer rásteres.
"""
import numpy as np
from rasterio.warp import transform as transformar

# Rugosidad no puntúa: está correlacionada con el relieve y contaría dos veces la misma propiedad.
VARIABLES = ("pendiente_mediana_grados", "pendiente_p90_grados", "relieve_p95_p5_m")
GRADO_M = 111_320.0  # metros por grado de latitud (aprox.), solo para dimensionar la caja de una celda


def envolvente(teselas: list[dict], minimo: int) -> tuple[dict, int]:
    """P10, P50 y P90 de cada variable sobre las subventanas válidas de la referencia."""
    ok = [t for t in teselas if t["estado"] == "calculado"]
    if len(ok) < minimo:
        raise ValueError(f"Solo {len(ok)} subventanas válidas (mínimo {minimo}); envolvente no fiable")
    env = {v: {f"p{q}": round(float(np.percentile([t[v] for t in ok], q)), 4) for q in (10, 50, 90)}
           for v in VARIABLES}
    return env, len(ok)


def geometrias(transform, crs, tesela_px: int, teselas: list[dict], geo_crs: str) -> None:
    """Añade a cada tesela su centro (lat, lon) y su polígono en `geo_crs`, in place."""
    lado = tesela_px * transform.a
    xs, ys = [], []
    for t in teselas:
        x0, y1 = transform.c + t["ix"] * lado, transform.f - t["iy"] * lado
        xs += [x0, x0 + lado, x0 + lado, x0, x0, x0 + lado / 2]
        ys += [y1 - lado, y1 - lado, y1, y1, y1 - lado, y1 - lado / 2]
    lons, lats = transformar(crs, geo_crs, xs, ys)
    for i, t in enumerate(teselas):
        k = 6 * i
        t["poligono"] = [[round(lons[j], 6), round(lats[j], 6)] for j in range(k, k + 5)]
        t["lon"], t["lat"] = round(lons[k + 5], 6), round(lats[k + 5], 6)


def caja_celda(lat_min: int, lon_min: int) -> tuple[float, float, float, float]:
    """Centro y tamaño (ancho, alto en m) de la caja métrica que cubre una celda de 1°."""
    # shortcut: la caja aeqd aproxima la celda de 1°; en los bordes puede solapar o dejar huecos de menos de
    # una tesela con las celdas vecinas. Si se necesita cobertura exacta, recortar por la geometría de la celda.
    lat_c, lon_c = lat_min + 0.5, lon_min + 0.5
    return lat_c, lon_c, GRADO_M * np.cos(np.radians(lat_c)), GRADO_M
