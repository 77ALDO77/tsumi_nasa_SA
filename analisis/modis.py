"""Contexto NASA MODIS 061; CMG de 0,05°, muestreado en el centro de cada tesela.

NDVI es un cribado de vegetación, no una medida del suelo desnudo. LST es contexto
terrestre: los meses seleccionados no establecen extremos anuales ni analogía térmica.
QA NDVI: https://modis-land.gsfc.nasa.gov/pdf/MOD13_User_Guide_V61.pdf (§8.3.2 y §9.3.2).
Conversiones: https://ladsweb.modaps.eosdis.nasa.gov/filespec/MODIS/61/MOD13C2
y https://ladsweb.modaps.eosdis.nasa.gov/filespec/MODIS/61/MOD11C3
"""
import calendar
import hashlib
import json
import math
import warnings
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import numpy as np

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
PASO = 0.05
FORMA = (3600, 7200)
VERSION = "modis-qa-v2"
QA = {
    "ndvi": "reliability=0; VI bits 0-1=0, 11-13=1 (tierra), 8 y 10=0; guia C61",
    "lst": "QC bits 0-1<=1 (producida, buena u otra calidad), bits 6-7<=1 (error medio declarado <=2 K)",
}
CAPAS = {
    "MOD13C2": [("CMG 0.05 Deg Monthly NDVI", "ndvi_max")],
    "MOD11C3": [("LST_Day_CMG", "lst_dia_max_k"), ("LST_Night_CMG", "lst_noche_min_k")],
}
CONTEOS = {"ndvi_max": "ndvi_n", "lst_dia_max_k": "lst_dia_n", "lst_noche_min_k": "lst_noche_n"}


def ruta_cache(destino: Path, meses: list[str]) -> Path:
    if not meses or len(meses) > 255 or meses != sorted(set(meses)):
        raise ValueError("Los meses deben ser únicos, ordenados y entre 1 y 255")
    for mes in meses:
        if date.fromisoformat(mes + "-01").strftime("%Y-%m") != mes:
            raise ValueError("Mes inválido; se espera AAAA-MM")
    return destino / f"{VERSION}_{'_'.join(meses)}.npz"


def granulo(producto: str, mes: str) -> str:
    ultimo = calendar.monthrange(*map(int, mes.split("-")))[1]
    r = httpx.get(CMR, params={"short_name": producto, "version": "061", "page_size": 10,
                               "temporal": f"{mes}-01T00:00:00Z,{mes}-{ultimo}T23:59:59Z"}, timeout=60)
    r.raise_for_status()
    urls = {l["href"] for g in r.json()["feed"]["entry"] if g["time_start"].startswith(mes)
            for l in g["links"] if l["href"].startswith("https://data.lpdaac.earthdatacloud.nasa.gov/")
            and l["href"].endswith(".hdf") and not l.get("inherited", False)}
    if len(urls) != 1:
        raise ValueError(f"{producto} {mes}: se esperaba un granulo de LP DAAC, encontrados {len(urls)}")
    return urls.pop()


def descargar(url: str, destino: Path, token: str) -> Path:
    if urlsplit(url).hostname != "data.lpdaac.earthdatacloud.nasa.gov" or not url.startswith("https://"):
        raise ValueError("La descarga autenticada requiere HTTPS de LP DAAC")
    archivo = destino / url.rsplit("/", 1)[1]
    if archivo.exists():
        return archivo
    if not token:
        raise ValueError("Falta EARTHDATA_TOKEN para descargar MODIS")
    parcial = archivo.with_suffix(".part")
    try:
        # httpx no reenvía Authorization al almacén S3 de otro dominio.
        with httpx.stream("GET", url, headers={"Authorization": f"Bearer {token}"}, follow_redirects=True,
                          timeout=httpx.Timeout(60, read=300)) as r:
            if r.status_code != 200:
                raise ValueError(f"MODIS: descarga HTTP {r.status_code}")  # no registrar URL firmada ni token
            with parcial.open("wb") as fh:
                for chunk in r.iter_bytes(1 << 20):
                    fh.write(chunk)
        with parcial.open("rb") as fh:
            if fh.read(4) != b"\x0e\x03\x13\x01":
                raise ValueError("La descarga MODIS no es HDF4")
        parcial.replace(archivo)
    except httpx.HTTPError:
        raise ValueError("MODIS: error de red en la descarga; reintentar contexto") from None
    finally:
        parcial.unlink(missing_ok=True)
    return archivo


def filtrar(raw, atributos, qa, fiabilidad=None):
    """Rangos en unidades almacenadas; MOD13 divide por scale_factor, MOD11 multiplica."""
    if qa.shape != raw.shape or (fiabilidad is not None and fiabilidad.shape != raw.shape):
        raise ValueError("Bandas de calidad MODIS con dimensiones distintas")
    if not math.isfinite(atributos["scale_factor"]) or atributos["scale_factor"] <= 0:
        raise ValueError("Factor de escala MODIS inválido")
    minimo, maximo = atributos["valid_range"]
    valido = (raw >= minimo) & (raw <= maximo) & (raw != atributos["_FillValue"])
    if fiabilidad is not None:
        valido &= (fiabilidad == 0) & ((qa & 3) == 0) & (((qa >> 11) & 7) == 1)
        valido &= (qa & ((1 << 8) | (1 << 10))) == 0
    else:
        valido &= ((qa & 3) <= 1) & (((qa >> 6) & 3) <= 1)
    a = raw.astype("float32")
    if fiabilidad is not None:
        a -= atributos.get("add_offset", 0)
        a /= atributos["scale_factor"]
    else:
        a *= atributos["scale_factor"]
        a += atributos.get("add_offset", 0)
    a[~valido] = np.nan
    return a


def leer(archivo: Path, sds: str) -> np.ndarray:
    from pyhdf.SD import SD, SDC

    f = SD(str(archivo), SDC.READ)
    try:
        ds = f.select(sds)
        try:
            raw, atributos = ds[:], ds.attributes()
        finally:
            ds.endaccess()
        if raw.shape != FORMA:
            raise ValueError(f"{archivo.name}: malla MODIS inesperada {raw.shape}")
        nombres = (["CMG 0.05 Deg Monthly VI Quality", "CMG 0.05 Deg Monthly pixel reliability"]
                   if sds.endswith("NDVI") else ["QC_Day" if sds == "LST_Day_CMG" else "QC_Night"])
        calidad = []
        for nombre in nombres:
            ds = f.select(nombre)
            try:
                calidad.append(ds[:])
            finally:
                ds.endaccess()
        return filtrar(raw, atributos, *calidad)
    finally:
        f.end()


def combinar(ndvi: list, dia: list, noche: list) -> dict:
    """Máximo/mínimo de medias mensuales válidas, con cobertura temporal explícita."""
    out = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # todo NaN -> sin dato, no cero
        for clave, capas in zip(CONTEOS, (ndvi, dia, noche)):
            out[clave] = (np.nanmin if clave == "lst_noche_min_k" else np.nanmax)(capas, axis=0)
            out[CONTEOS[clave]] = np.sum([np.isfinite(a) for a in capas], axis=0).astype("uint8")
    return out


def identidad(meta: dict) -> str:
    return hashlib.sha256(json.dumps(meta, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def preparar(destino: Path, meses: list[str], token: str) -> Path:
    salida = ruta_cache(destino, meses)
    destino.mkdir(parents=True, exist_ok=True)
    if salida.exists():
        cargar(salida, meses)  # rechazar cachés viejas, incompletas o de otros meses
        return salida
    capas, fuentes = {k: [] for k in CONTEOS}, []
    for mes in meses:
        for producto, sds_list in CAPAS.items():
            url = granulo(producto, mes)
            archivo = descargar(url, destino, token)
            with archivo.open("rb") as fh:
                sha = hashlib.file_digest(fh, "sha256").hexdigest()
            fuentes.append({"producto": producto, "mes": mes, "url": url, "sha256": sha})
            for sds, clave in sds_list:
                capas[clave].append(leer(archivo, sds))
    meta = {"version": VERSION, "meses": meses, "paso_grados": PASO, "qa": QA, "fuentes": fuentes}
    datos = combinar(*capas.values())
    parcial = salida.with_suffix(".part")
    try:
        with parcial.open("wb") as fh:
            np.savez_compressed(fh, **datos, metadata=np.array(json.dumps(meta)))
        parcial.replace(salida)
    finally:
        parcial.unlink(missing_ok=True)
    return salida


def cargar(npz: Path, meses: list[str]) -> dict:
    with np.load(npz, allow_pickle=False) as f:
        meta = json.loads(str(f["metadata"]))
        if meta["version"] != VERSION or meta["meses"] != meses or meta["qa"] != QA or meta["paso_grados"] != PASO:
            raise ValueError("Caché MODIS incompatible: preparar de nuevo")
        datos = {k: f[k] for k in (*CONTEOS, *CONTEOS.values())}
        if any(a.shape != FORMA for a in datos.values()):
            raise ValueError("Caché MODIS con malla inesperada")
    return datos | {"metadata": meta, "contexto_id": identidad(meta)}


def muestrear(ctx: dict, lat: float, lon: float) -> dict:
    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Coordenadas fuera de la malla MODIS")
    fila = min(int((90 - lat) / PASO), FORMA[0] - 1)
    col = min(int((lon + 180) / PASO), FORMA[1] - 1)
    out = {"contexto_id": ctx["contexto_id"]}
    for k, conteo in CONTEOS.items():
        v = float(ctx[k][fila, col])
        # La cuantización original evita ruido float32 justo en el umbral (0,3000 != 0,3001).
        out[k] = round(v, 4 if k == "ndvi_max" else 2) if np.isfinite(v) else None
        out[conteo] = int(ctx[conteo][fila, col])
    return out


def celdas_elegibles(ctx: dict, meses: list[str], umbral: float) -> np.ndarray:
    """Celdas de 1° con algún píxel que pasa el filtro NDVI; no validación de toda el área."""
    validos = (ctx["ndvi_n"] == len(meses)) & (ctx["ndvi_max"] <= umbral)
    filas, cols = validos.shape
    px = round(1 / PASO)
    return validos.reshape(filas // px, px, cols // px, px).any(axis=(1, 3))
