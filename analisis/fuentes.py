"""Lectura de ventanas de DEM por HTTP (GDAL /vsicurl/, lecturas parciales) y reproyección métrica.

TLS queda a cargo de GDAL/curl con verificación activa; nunca se desactiva.
"""
import hashlib
import math
import os
import time

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.errors import RasterioIOError
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import Window, from_bounds

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
# Por HTTP el coste es la latencia por petición: bloques grandes y rangos agrupados (medido: 18 s -> 11 s por tesela GLO-30).
os.environ.setdefault("CPL_VSIL_CURL_CHUNK_SIZE", "10485760")
os.environ.setdefault("GDAL_HTTP_MERGE_CONSECUTIVE_RANGES", "YES")
os.environ.setdefault("GDAL_HTTP_MULTIPLEX", "YES")
# Sin límites, una conexión estancada bloqueó una celda 7,8 min (apertura 271 s + lectura 197 s, medido en logs).
# Se corta si no conecta en 15 s o si baja de 10 KB/s durante 30 s, y GDAL reintenta 3 veces.
os.environ.setdefault("GDAL_HTTP_CONNECTTIMEOUT", "15")
os.environ.setdefault("GDAL_HTTP_LOW_SPEED_LIMIT", "10240")
os.environ.setdefault("GDAL_HTTP_LOW_SPEED_TIME", "30")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "3")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "5")

LOLA_POLAR = ("https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/"
              "data/lola_gdr/polar/float_img/ldem_80s_40m_float.lbl")
# Disparos láser por píxel en la misma malla; 0 = altura interpolada, no medida.
LOLA_CONTEO = ("https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/"
               "data/lola_gdr/polar/img/ldec_80s_40m.lbl")
GLO30 = "https://copernicus-dem-30m.s3.amazonaws.com/{n}/{n}.tif"
R_LUNA = 1737400.0
R_MARTE = 3396190.0  # esfera de los DEM USGS de Marte (CTX/HiRISE en eqc); alturas en m sobre el areoide MOLA

CUERPOS = {
    # La etiqueta LOLA declara alturas en km sobre una esfera de 1737,4 km; el CRS se fija aquí
    # porque el WKT que construye GDAL trae ejes y unidades ambiguos.
    "luna": {"datum": f"+R={R_LUNA:.0f}", "factor_altura_m": 1000.0,
             "crs_fuente": CRS.from_proj4(f"+proj=stere +lat_0=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 +R={R_LUNA:.0f} +units=m +no_defs")},
    "tierra": {"datum": "+ellps=WGS84", "factor_altura_m": 1.0, "crs_fuente": None},
    # Marte no tiene un DEM global fino: cada referencia declara su producto regional (`dem`) y se usa su CRS.
    "marte": {"datum": f"+R={R_MARTE:.0f}", "factor_altura_m": 1.0, "crs_fuente": None},
}


def tesela_inexistente(exc: Exception) -> bool:
    """Solo un 404 significa que no hay tesela (GLO-30 no publica océano); otro error es un fallo de red."""
    return "HTTP response code: 404" in str(exc)


def teselas_glo30(lat, lon, lado_m):
    margen_lat = lado_m / 2 / 111_000 + 0.01
    margen_lon = margen_lat / max(math.cos(math.radians(lat)), 0.05)
    for la in range(math.floor(lat - margen_lat), math.floor(lat + margen_lat) + 1):
        for lo in range(math.floor(lon - margen_lon), math.floor(lon + margen_lon) + 1):
            name = (f"Copernicus_DSM_COG_10_{'N' if la >= 0 else 'S'}{abs(la):02d}_00_"
                    f"{'E' if lo >= 0 else 'W'}{abs(lo):03d}_00_DEM")
            yield GLO30.format(n=name)


def urls(cuerpo, lat, lon, lado_m, dem=None):
    if cuerpo == "marte":
        if not dem:
            raise ValueError("Una referencia marciana necesita su DEM regional (campo 'dem')")
        return [dem]
    if cuerpo == "luna":
        if lat > -80:
            raise ValueError("El mosaico LOLA polar ldem_80s_40m solo cubre de 80° S al polo")
        return [LOLA_POLAR]
    return list(teselas_glo30(lat, lon, lado_m))


def mascara_lola(win, transform):
    """Lee el conteo de disparos de la misma ventana; exige que la malla coincida con la del DEM."""
    with rasterio.open(f"/vsicurl/{LOLA_CONTEO}") as ds:
        if ds.transform != transform:
            raise ValueError("ldec y ldem no comparten malla; no se aplica la máscara a ciegas")
        return ds.read(1, window=win)


def abrir(url, nivel_reducido=None):
    if nivel_reducido is None:
        return rasterio.open(f"/vsicurl/{url}")
    # Las versiones reducidas del DEM de Gale viven en un .ovr aparte: solo aquí se permite buscarlo.
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="NO"):
        return rasterio.open(f"/vsicurl/{url}", overview_level=nivel_reducido)


def ventana(cuerpo, lat, lon, lado_m, resoluciones, alto_m=None, dem=None, nivel_reducido=None):
    """Lee cada fuente una vez y la reproyecta a cada resolución.

    La caja mide `lado_m` de ancho y `alto_m` (por defecto igual) de alto, centrada en (lat, lon).
    `dem` y `nivel_reducido` solo se usan en Marte (DEM regional y, si es muy fino, una versión reducida).
    Devuelve ({res: alturas en m float32 con NaN}, {res: transform}, crs, procedencia por fuente).
    """
    alto_m = alto_m or lado_m
    spec = CUERPOS[cuerpo]
    dst_crs = CRS.from_proj4(f"+proj=aeqd +lat_0={lat} +lon_0={lon} {spec['datum']} +units=m +no_defs")
    grids, transforms = {}, {}
    for res in resoluciones:
        nx, ny = int(round(lado_m / res)), int(round(alto_m / res))
        transforms[res] = from_origin(-nx * res / 2, ny * res / 2, res, res)
        grids[res] = np.full((ny, nx), np.nan, dtype="float32")
    half = max(lado_m, alto_m) / 2
    procedencia = []
    for url in urls(cuerpo, lat, lon, max(lado_m, alto_m), dem):
        inicio = time.monotonic()
        try:
            ds = abrir(url, nivel_reducido)
        except RasterioIOError as exc:
            if not tesela_inexistente(exc):
                raise  # corte de red: la celda falla y vuelve a la cola, no se guarda un hueco como si fuera océano
            procedencia.append({"url": url, "estado": "sin_tesela", "error": str(exc)[:200],
                                "duracion_s": round(time.monotonic() - inicio, 2)})
            continue
        abierto = time.monotonic()
        with ds:
            src_crs = spec["crs_fuente"] or ds.crs
            margin = 3 * max(max(resoluciones), abs(ds.transform.a))
            bounds = transform_bounds(dst_crs, src_crs, -half - margin, -half - margin,
                                      half + margin, half + margin, densify_pts=21)
            win = from_bounds(*bounds, transform=ds.transform).round_offsets().round_lengths()
            win = win.intersection(Window(0, 0, ds.width, ds.height))
            values = ds.read(1, window=win, masked=True).astype("float64").filled(np.nan)
            values *= spec["factor_altura_m"]
            record = {"url": url, "estado": "leido",
                      "ventana_fuente": {"col": int(win.col_off), "fila": int(win.row_off),
                                         "ancho": int(win.width), "alto": int(win.height)},
                      "res_nativa_m": abs(ds.transform.a) if src_crs.is_projected else None,
                      "sha256_valores_leidos": hashlib.sha256(values.astype("float32").tobytes()).hexdigest()}
            if url == LOLA_POLAR:
                counts = mascara_lola(win, ds.transform)
                record["mascara"] = LOLA_CONTEO
                record["fraccion_medida_ventana_leida"] = round(float(np.mean(counts > 0)), 4)
                values[counts == 0] = np.nan
            record["apertura_s"] = round(abierto - inicio, 2)
            record["lectura_s"] = round(time.monotonic() - abierto, 2)
            for res, grid in grids.items():
                reproject(values, grid, src_transform=ds.window_transform(win), src_crs=src_crs,
                          src_nodata=np.nan, dst_transform=transforms[res], dst_crs=dst_crs,
                          dst_nodata=np.nan, init_dest_nodata=False, resampling=Resampling.average)
            procedencia.append(record)
    return grids, transforms, dst_crs, procedencia
