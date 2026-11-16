"""Búsqueda continua de análogos: calcula envolventes de referencia y procesa una cola de celdas de 1°.

Desde la raíz, con DATABASE_URL en el entorno:
  python -m analisis.trabajador analisis/inputs/busqueda.json referencias   # envolventes lunares
  python -m analisis.trabajador analisis/inputs/busqueda.json encolar       # celdas de las zonas
  python -m analisis.trabajador analisis/inputs/busqueda.json contexto      # MODIS (NASA) por tesela; requiere EARTHDATA_TOKEN
  python -m analisis.trabajador analisis/inputs/busqueda.json catalogo      # nombres, roles y fuentes, sin recalcular terreno
  python -m analisis.trabajador analisis/inputs/busqueda.json una           # procesa una celda
  python -m analisis.trabajador analisis/inputs/busqueda.json bucle         # servicio: no termina
Varios trabajadores pueden correr a la vez: cada celda se reserva con FOR UPDATE SKIP LOCKED.
"""
import argparse
import hashlib
import json
import logging
import math
import os
import socket
import time
from collections import Counter, defaultdict
from itertools import groupby, product
from pathlib import Path

import httpx
import psycopg
import rasterio
from psycopg.types.json import Jsonb

from . import modis
from .busqueda import caja_celda, envolvente, geometrias
from .cargar import aplicar_migraciones
from .fuentes import ventana
from .metricas import VERSION_METODO, metricas_teselas
from .registro import configurar, evento

log = configurar("trabajador")

MAX_INTENTOS = 3
_contexto = {}
CATALOGO = Path(__file__).parent / "inputs/mvp0.json"
R_TIERRA_KM = 6371.0088
# 6 km junta teselas de 3 km pegadas y tolera el hueco de una; 10 km ya encadenaba franjas de 75 km.
AGRUPACION = {"distancia_km": 6, "min_teselas": 3, "sitio_conocido_km": 50}


def contexto(cfg):
    """Carga una vez; detecta reemplazos y nunca reutiliza la caché anterior sin QA."""
    c = cfg["contexto_modis"]
    npz = modis.ruta_cache(Path(c["cache"]), c["meses"])
    if not npz.exists():
        raise ValueError("Falta caché MODIS con QA; ejecutar primero la acción contexto")
    clave = (str(npz.resolve()), npz.stat().st_mtime_ns)
    if _contexto.get("clave") != clave:
        _contexto["ctx"] = modis.cargar(npz, c["meses"])
        _contexto["clave"] = clave
    return _contexto["ctx"]


def comprobar_contexto(conn, cfg):
    activo = conn.execute("SELECT contexto_id, umbral_ndvi FROM contexto_modis").fetchone()
    if activo != (contexto(cfg)["contexto_id"], cfg["ndvi_umbral_vegetacion"]):
        raise ValueError("Contexto/umbral MODIS distinto al de la base; detener trabajadores y ejecutar contexto")


def candidatos(conn, cfg, celda=None):
    """Reemplazo atómico: elimina también filas que dejaron de cumplir el filtro."""
    conn.execute("LOCK TABLE candidatos IN SHARE ROW EXCLUSIVE MODE")
    filtro = "t.celda_id = %(celda)s" if celda is not None else "TRUE"
    conn.execute("DELETE FROM candidatos" + (" WHERE celda_id = %s" if celda is not None else ""),
                 (celda,) if celda is not None else ())
    n = 0
    if conn.execute("SELECT 1 FROM contexto_modis").fetchone():
        comprobar_contexto(conn, cfg)
        n = conn.execute(f"""INSERT INTO candidatos
                           SELECT t.referencia_id, t.res_m, t.version_metodo, t.celda_id, t.ix, t.iy, t.lat, t.lon,
                                  t.dist_mediana
                           FROM teselas_referencia t JOIN contexto_modis c ON t.contexto_id = c.contexto_id
                           JOIN referencias r ON r.referencia_id = t.referencia_id AND r.res_m = t.res_m
                                AND r.version_metodo = t.version_metodo AND r.buscar
                           WHERE t.n_dentro = 3 AND {filtro} AND t.dist_mediana IS NOT NULL
                           AND t.ndvi_n = jsonb_array_length(c.metadata->'meses') AND t.ndvi_max <= c.umbral_ndvi""",
                             {"celda": celda}).rowcount
    zonas(conn, cfg)
    return n


def _xyz(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    return (R_TIERRA_KM * math.cos(la) * math.cos(lo), R_TIERRA_KM * math.cos(la) * math.sin(lo),
            R_TIERRA_KM * math.sin(la))


def _km(a, b):
    """Distancia sobre la esfera a partir de la cuerda entre dos puntos 3D."""
    return 2 * R_TIERRA_KM * math.asin(min(1.0, math.dist(a, b) / (2 * R_TIERRA_KM)))


def grupos(puntos, distancia_km):
    """Componentes conexas: dos puntos (lat, lon) van juntos si están a <= distancia_km, encadenando vecinos.
    Cubos 3D del tamaño de la cuerda equivalente: sin cortes en polos ni antimeridiano y sin comparar todos los pares."""
    cuerda = 2 * R_TIERRA_KM * math.sin(distancia_km / (2 * R_TIERRA_KM))
    xyz = [_xyz(*p) for p in puntos]
    padre = list(range(len(xyz)))

    def raiz(i):
        while padre[i] != i:
            padre[i] = padre[padre[i]]
            i = padre[i]
        return i

    cubos = defaultdict(list)
    for i, v in enumerate(xyz):
        cubos[tuple(math.floor(c / cuerda) for c in v)].append(i)
    for clave, miembros in cubos.items():
        for d in product((-1, 0, 1), repeat=3):
            for j in cubos.get(tuple(c + e for c, e in zip(clave, d)), ()):
                for i in miembros:
                    if i < j and math.dist(xyz[i], xyz[j]) <= cuerda:
                        padre[raiz(i)] = raiz(j)
    salida = defaultdict(list)
    for i in range(len(xyz)):
        salida[raiz(i)].append(i)  # en orden de entrada: el primero es el mejor si la entrada viene ordenada
    return list(salida.values())


def zonas(conn, cfg):
    """Reemplazo completo de las zonas a partir de las coordenadas de las candidatas (una vez por tesela).
    Se agrupa por cuerpo: una zona lunar y una marciana pueden solaparse, pero nunca se mezclan."""
    # ponytail: recálculo global en cada celda (113 ms con 2.824 filas). Si llega a pesar frente a los ~15 s
    # por celda, recalcular solo las zonas a <= distancia_km de la celda terminada.
    a = {**AGRUPACION, **cfg.get("agrupacion", {})}
    filas = conn.execute("""SELECT c.res_m, c.version_metodo, c.celda_id, c.ix, c.iy, c.lat, c.lon,
                                   min(c.dist_mediana), array_agg(DISTINCT c.referencia_id), b.zona,
                                   max(ST_Area(t.geom::geography)) / 1e6, min(ST_XMin(t.geom)), min(ST_YMin(t.geom)),
                                   max(ST_XMax(t.geom)), max(ST_YMax(t.geom)), r.cuerpo
                            FROM candidatos c JOIN celdas_busqueda b USING (celda_id)
                            JOIN teselas t USING (celda_id, res_m, version_metodo, ix, iy)
                            JOIN referencias r USING (referencia_id, res_m, version_metodo)
                            GROUP BY c.res_m, c.version_metodo, r.cuerpo, c.celda_id, c.ix, c.iy, c.lat, c.lon, b.zona
                            ORDER BY 1, 2, 16, 8, 3, 5, 4""").fetchall()
    conocidos = [(nombre, _xyz(lat, lon)) for nombre, lat, lon in conn.execute(
        "SELECT coalesce(nombre, sitio_id), lat, lon FROM sitios WHERE cuerpo = 'tierra' AND rol LIKE 'analogo_nasa%'")]
    salida = []
    for (res, version, cuerpo), parte in groupby(filas, key=lambda f: (f[0], f[1], f[15])):
        parte = list(parte)
        for miembros in grupos([(f[5], f[6]) for f in parte], a["distancia_km"]):
            ts = [parte[i] for i in miembros]
            mejor = ts[0]
            cerca = min(((_km(_xyz(t[5], t[6]), xyz), nombre) for t in ts for nombre, xyz in conocidos),
                        default=(None, None))
            salida.append((res, version, f"{mejor[2]}~{mejor[3]}~{mejor[4]}", len(ts), sum(t[10] for t in ts),
                           sorted({r for t in ts for r in t[8]}), Counter(t[9] for t in ts).most_common(1)[0][0],
                           mejor[5], mejor[6], mejor[7],
                           # ponytail: recuadro mínimo/máximo; una zona que cruce el antimeridiano daría la vuelta al mundo
                           min(t[11] for t in ts), min(t[12] for t in ts), max(t[13] for t in ts), max(t[14] for t in ts),
                           len(ts) >= a["min_teselas"], cerca[1], cerca[0],
                           cerca[0] is not None and cerca[0] <= a["sitio_conocido_km"], cuerpo))
    conn.execute("DELETE FROM zonas_candidatas")
    with conn.cursor() as cur:
        cur.executemany("""INSERT INTO zonas_candidatas (res_m, version_metodo, zona_id, n_teselas, area_km2, referencias,
                           region, lat, lon, dist_mediana, lon_min, lat_min, lon_max, lat_max, es_zona, sitio_cercano,
                           sitio_cercano_km, conocida, cuerpo) VALUES (""" + ",".join(["%s"] * 19) + ")", salida)
    return sum(z[14] for z in salida)


def ubicar(conn, cfg, maximo):
    """País, provincia y distrito de lugares aún sin ubicación, con OpenStreetMap (Nominatim).
    Política del servicio: agente propio, como máximo 1 consulta/s y resultados en caché."""
    u = cfg.get("ubicacion")
    if not u or maximo < 1:
        return 0
    pendientes = conn.execute("""SELECT p.lat, p.lon FROM (
            SELECT round(lat::numeric, 2) AS lat, round(lon::numeric, 2) AS lon, max(prioridad) AS prioridad FROM (
                -- Sitios registrados, luego las zonas más extensas (las que muestra el atlas) y al final las aisladas.
                SELECT lat, lon, 1000000 AS prioridad FROM sitios WHERE cuerpo = 'tierra'
                UNION ALL SELECT lat, lon, CASE WHEN es_zona THEN n_teselas ELSE 0 END FROM zonas_candidatas WHERE res_m = 60) x
            GROUP BY 1, 2) p
        LEFT JOIN ubicaciones u ON u.lat = p.lat AND u.lon = p.lon
        WHERE u.lat IS NULL OR (u.estado = 'error' AND u.consultado_utc < now() - interval '1 day')
        ORDER BY p.prioridad DESC, p.lat, p.lon LIMIT %s""", (maximo,)).fetchall()
    for i, (lat, lon) in enumerate(pendientes):
        if i:
            time.sleep(1.1)
        try:
            r = httpx.get(u["servicio"], params={"format": "jsonv2", "lat": str(lat), "lon": str(lon), "zoom": 10,
                                                 "accept-language": "es"},
                          headers={"User-Agent": u["agente"]}, timeout=15)
            r.raise_for_status()
            data = r.json()
            a = data.get("address") or {}
            fila = (a.get("country"), a.get("state") or a.get("region") or a.get("province"),
                    a.get("county") or a.get("state_district") or a.get("municipality") or a.get("city")
                    or a.get("town") or a.get("village"),
                    "ok" if a.get("country") else "sin_resultado")
        except (httpx.HTTPError, ValueError) as exc:
            evento(log, "ubicacion_fallida", logging.WARNING, lat=float(lat), lon=float(lon), error=type(exc).__name__)
            fila = (None, None, None, "error")
        conn.execute("""INSERT INTO ubicaciones (lat, lon, pais, provincia, distrito, estado) VALUES (%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (lat, lon) DO UPDATE SET pais = EXCLUDED.pais, provincia = EXCLUDED.provincia,
                        distrito = EXCLUDED.distrito, estado = EXCLUDED.estado, consultado_utc = now()""",
                     (lat, lon, *fila))
        conn.commit()
    return len(pendientes)


def celda_id(lat, lon):
    return f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}{'E' if lon >= 0 else 'W'}{abs(lon):03d}"


def catalogo(conn):
    """Solo metadatos de sitios existentes, comprobando que la coordenada no haya cambiado."""
    for s in json.loads(CATALOGO.read_text(encoding="utf-8"))["ventanas"]:
        previo = conn.execute("SELECT lat, lon FROM sitios WHERE sitio_id = %s", (s["id"],)).fetchone()
        if previo is None:
            continue
        if previo != (s["lat"], s["lon"]):
            raise ValueError(f"{s['id']}: coordenadas distintas; revisar antes de etiquetar")
        conn.execute("""UPDATE sitios SET nombre=%s, rol=%s, etiquetas=%s, fuente_coordenadas=%s
                        WHERE sitio_id=%s""",
                     (s["nombre"], s["rol"], s["etiquetas"], s["fuente_coordenadas"], s["id"]))
    conn.commit()
    evento(log, "catalogo_actualizado")


def celdas_config(cfg):
    """Orden finito y reproducible; las zonas prioritarias prevalecen sobre la exploración amplia."""
    celdas = {}
    for z in sorted(cfg["zonas"], key=lambda z: z["prioridad"]):
        bbox = z["bbox"]
        if len(bbox) != 4 or any(type(v) is not int for v in bbox):
            raise ValueError("Las cajas de búsqueda deben tener cuatro grados enteros")
        lon0, lat0, lon1, lat1 = bbox
        if not (-180 <= lon0 < lon1 <= 180 and -90 <= lat0 < lat1 <= 90):
            raise ValueError("Caja de búsqueda fuera de la Tierra")
        for lat in range(lat0, lat1):
            for lon in range(lon0, lon1):
                cid = celda_id(lat, lon)
                celdas.setdefault(cid, (cid, lat, lon, z["nombre"], z["prioridad"]))
    return list(celdas.values())


def celdas_del_perfil(cfg):
    ctx = contexto(cfg)
    mascara = modis.celdas_elegibles(ctx, cfg["contexto_modis"]["meses"], cfg["ndvi_umbral_vegetacion"])
    return [c for c in celdas_config(cfg) if mascara[89-c[1], c[2]+180]]


def alimentar_cola(conn, cfg, celdas):
    """Lotes pequeños, sin reabrir celdas hechas/error ni duplicar trabajo entre procesos."""
    auto = cfg["auto_encolar"]
    lote, minimo = auto["lote"], auto["minimo_pendientes"]
    if type(lote) is not int or type(minimo) is not int or not 1 <= minimo <= lote <= 100:
        raise ValueError("auto_encolar requiere 1 <= minimo_pendientes <= lote <= 100")
    conn.execute("SELECT pg_advisory_xact_lock(hashtext('tsumi:alimentar_cola'))")
    pendientes = conn.execute("SELECT count(*) FROM celdas_busqueda WHERE estado='pendiente'").fetchone()[0]
    if pendientes >= minimo:
        conn.commit()
        return 0
    existentes = {r[0] for r in conn.execute("SELECT celda_id FROM celdas_busqueda")}
    nuevas = [c for c in celdas if c[0] not in existentes][:lote]
    with conn.cursor() as cur:
        cur.executemany("""INSERT INTO celdas_busqueda (celda_id,lat_min,lon_min,zona,prioridad)
                           VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""", nuevas)
        n = max(cur.rowcount, 0)
    conn.commit()
    if n:
        evento(log, "lote_encolado", n=n, pendientes_antes=pendientes, elegibles=len(celdas))
    return n


def latido(conn, estado, celda=None, elegibles=None):
    conn.execute("""INSERT INTO trabajadores (trabajador_id,estado,celda_id,celdas_elegibles)
                    VALUES (%s,%s,%s,%s) ON CONFLICT (trabajador_id) DO UPDATE SET
                    estado=EXCLUDED.estado, celda_id=EXCLUDED.celda_id,
                    celdas_elegibles=coalesce(EXCLUDED.celdas_elegibles,trabajadores.celdas_elegibles),
                    actualizado_utc=now()""", (socket.gethostname(), estado, celda, elegibles))
    conn.commit()


def referencias(conn, cfg):
    tesela_m, minimo = cfg["tesela_m"], cfg["fraccion_valida_min"]
    conn.execute("LOCK TABLE candidatos IN SHARE ROW EXCLUSIVE MODE")
    for ref in cfg["referencias"]:
        grids, transforms, crs, _ = ventana(ref["cuerpo"], ref["lat"], ref["lon"], ref["lado_m"], cfg["escalas_m"],
                                            dem=ref.get("dem"), nivel_reducido=ref.get("dem_nivel_reducido"))
        for res, z in grids.items():
            env, n = envolvente(metricas_teselas(z, res, round(tesela_m / res), minimo), cfg["minimo_subventanas"])
            conn.execute("""INSERT INTO referencias (referencia_id, cuerpo, lat, lon, lado_m, tesela_m, res_m, version_metodo,
                             fuente_coordenadas, n_subventanas, envolvente, nombre, banda, buscar, fuente)
                             VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                             ON CONFLICT (referencia_id, res_m, version_metodo) DO UPDATE SET envolvente = EXCLUDED.envolvente,
                             n_subventanas = EXCLUDED.n_subventanas, nombre = EXCLUDED.nombre,
                             lat = EXCLUDED.lat, lon = EXCLUDED.lon, lado_m = EXCLUDED.lado_m,
                             tesela_m = EXCLUDED.tesela_m, fuente_coordenadas = EXCLUDED.fuente_coordenadas,
                             banda = EXCLUDED.banda, buscar = EXCLUDED.buscar, fuente = EXCLUDED.fuente,
                             calculado_utc = now()""",
                         (ref["id"], ref["cuerpo"], ref["lat"], ref["lon"], ref["lado_m"], tesela_m, res, VERSION_METODO,
                          ref["fuente_coordenadas"], n, Jsonb(env), ref.get("nombre"), ref.get("banda", "p10-p90"),
                          ref.get("buscar", True), Jsonb(ref["fuente"]) if ref.get("fuente") else None))
            evento(log, "referencia_calculada", referencia=ref["id"], res_m=res, n_subventanas=n, envolvente=env,
                   banda=ref.get("banda", "p10-p90"), buscar=ref.get("buscar", True))
    evento(log, "candidatos_reconstruidos", n=candidatos(conn, cfg))
    conn.commit()


def encolar(conn, cfg):
    if cfg.get("auto_encolar"):
        return alimentar_cola(conn, cfg, celdas_del_perfil(cfg))
    total = 0
    for c in celdas_config(cfg):
        cur = conn.execute("""INSERT INTO celdas_busqueda (celda_id, lat_min, lon_min, zona, prioridad)
                                      VALUES (%s,%s,%s,%s,%s) ON CONFLICT (celda_id) DO UPDATE
                                      SET prioridad = least(celdas_busqueda.prioridad, EXCLUDED.prioridad)""",
                           c)
        total += cur.rowcount
    conn.commit()
    evento(log, "celdas_encoladas", n=total)


def tomar(conn):
    # Recuperación durante el bucle, no solo al reiniciar; se respeta el techo de reintentos.
    conn.execute("""UPDATE celdas_busqueda SET estado=CASE WHEN intentos < %s THEN 'pendiente' ELSE 'error' END,
                    error='Reserva vencida tras una hora sin terminar', actualizado_utc=now()
                    WHERE estado='en_curso' AND actualizado_utc < now()-interval '1 hour'""", (MAX_INTENTOS,))
    row = conn.execute("""UPDATE celdas_busqueda SET estado = 'en_curso', intentos = intentos + 1, actualizado_utc = now()
                          WHERE celda_id = (SELECT celda_id FROM celdas_busqueda WHERE estado = 'pendiente'
                                            ORDER BY prioridad, celda_id FOR UPDATE SKIP LOCKED LIMIT 1)
                          RETURNING celda_id, lat_min, lon_min, intentos""").fetchone()
    conn.commit()
    return row


def procesar(conn, cfg, celda):
    cid, lat_min, lon_min, _ = celda
    tesela_m, minimo = cfg["tesela_m"], cfg["fraccion_valida_min"]
    lat_c, lon_c, ancho, alto = caja_celda(lat_min, lon_min)
    t0 = time.monotonic()
    grids, transforms, crs, fuentes = ventana("tierra", lat_c, lon_c, ancho, cfg["escalas_m"], alto_m=alto)
    t_lectura = time.monotonic() - t0
    for f in fuentes:
        evento(log, "fuente_leida", celda=cid, url=f["url"], estado=f["estado"], apertura_s=f.get("apertura_s"),
               lectura_s=f.get("lectura_s"), duracion_s=f.get("duracion_s"))
    t_metricas = t_insercion = 0.0
    n_total = n_validas = 0
    ctx = contexto(cfg)
    with conn.transaction():
        conn.execute("LOCK TABLE candidatos IN SHARE ROW EXCLUSIVE MODE")
        comprobar_contexto(conn, cfg)
        for res, z in grids.items():
            t1 = time.monotonic()
            teselas = metricas_teselas(z, res, round(tesela_m / res), minimo)
            n_total += len(teselas)
            ok = [t for t in teselas if t["estado"] == "calculado"]
            n_validas += len(ok)
            geometrias(transforms[res], crs, round(tesela_m / res), ok, "EPSG:4326")
            for t in ok:
                t.update(modis.muestrear(ctx, t["lat"], t["lon"]))
            t2 = time.monotonic()
            t_metricas += t2 - t1
            conn.cursor().executemany(
                """INSERT INTO teselas (celda_id, res_m, version_metodo, ix, iy, lat, lon, geom, pendiente_mediana,
                   pendiente_p90, relieve, rugosidad, fraccion_valida, ndvi_max, lst_dia_max_k, lst_noche_min_k,
                   ndvi_n, lst_dia_n, lst_noche_n, contexto_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,ST_SetSRID(ST_GeomFromGeoJSON(%s),4326),%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (celda_id, res_m, version_metodo, ix, iy) DO UPDATE SET
                   ndvi_max = EXCLUDED.ndvi_max, lst_dia_max_k = EXCLUDED.lst_dia_max_k,
                   lst_noche_min_k = EXCLUDED.lst_noche_min_k, ndvi_n = EXCLUDED.ndvi_n,
                   lst_dia_n = EXCLUDED.lst_dia_n, lst_noche_n = EXCLUDED.lst_noche_n,
                   contexto_id = EXCLUDED.contexto_id""",
                [(cid, res, VERSION_METODO, t["ix"], t["iy"], t["lat"], t["lon"],
                  json.dumps({"type": "Polygon", "coordinates": [t["poligono"]]}), t["pendiente_mediana_grados"],
                  t["pendiente_p90_grados"], t["relieve_p95_p5_m"], t["rugosidad_rms_plano_m"], t["fraccion_valida"],
                   t["ndvi_max"], t["lst_dia_max_k"], t["lst_noche_min_k"],
                   t["ndvi_n"], t["lst_dia_n"], t["lst_noche_n"], t["contexto_id"])
                 for t in ok])
            t_insercion += time.monotonic() - t2
        estado = "hecha" if n_validas else "sin_datos"
        motivo = None if n_validas else "; ".join(f["estado"] for f in fuentes) or "sin teselas válidas"
        conn.execute("""UPDATE celdas_busqueda SET estado = %s, n_teselas = %s, n_validas = %s, error = %s,
                        actualizado_utc = now() WHERE celda_id = %s""", (estado, n_total, n_validas, motivo, cid))
        n_candidatos = candidatos(conn, cfg, cid)
    evento(log, "celda_terminada", celda=cid, estado=estado, n_validas=n_validas, n_teselas=n_total,
           lectura_s=round(t_lectura, 2), metricas_s=round(t_metricas, 2), insercion_s=round(t_insercion, 2),
           duracion_s=round(time.monotonic() - t0, 2), motivo=motivo, candidatos=n_candidatos)


def rellenar_contexto(conn, cfg):
    """Sustituye contexto y ranking juntos; ejecutar sin otros trabajadores activos."""
    token = os.environ.get("EARTHDATA_TOKEN", "")
    c = cfg["contexto_modis"]
    t0 = time.monotonic()
    npz = modis.preparar(Path(c["cache"]), c["meses"], token)
    ctx = contexto(cfg)
    evento(log, "contexto_preparado", archivo=str(npz), contexto_id=ctx["contexto_id"],
           granulos=ctx["metadata"]["fuentes"], duracion_s=round(time.monotonic() - t0, 1))
    conn.execute("LOCK TABLE candidatos IN SHARE ROW EXCLUSIVE MODE")
    conn.execute("""INSERT INTO contexto_modis (contexto_id, metadata, umbral_ndvi) VALUES (%s,%s,%s)
                    ON CONFLICT (unico) DO UPDATE SET contexto_id = EXCLUDED.contexto_id,
                    metadata = EXCLUDED.metadata, umbral_ndvi = EXCLUDED.umbral_ndvi""",
                 (ctx["contexto_id"], Jsonb(ctx["metadata"]), cfg["ndvi_umbral_vegetacion"]))
    total = 0
    with conn.cursor(name="muestreo_modis") as cur:
        cur.execute("SELECT celda_id, res_m, version_metodo, ix, iy, lat, lon FROM teselas")
        while filas := cur.fetchmany(2000):
            valores = [(m["ndvi_max"], m["lst_dia_max_k"], m["lst_noche_min_k"], m["ndvi_n"], m["lst_dia_n"],
                        m["lst_noche_n"], m["contexto_id"], *f[:5])
                       for f in filas for m in [modis.muestrear(ctx, f[5], f[6])]]
            with conn.cursor() as escritura:
                escritura.executemany("""UPDATE teselas SET ndvi_max = %s, lst_dia_max_k = %s, lst_noche_min_k = %s,
                                         ndvi_n = %s, lst_dia_n = %s, lst_noche_n = %s, contexto_id = %s
                                         WHERE celda_id = %s AND res_m = %s AND version_metodo = %s AND ix = %s AND iy = %s""",
                                      valores)
            total += len(filas)
    n = candidatos(conn, cfg)
    conn.commit()
    evento(log, "contexto_rellenado", teselas=total, candidatos=n)


def fallo(conn, celda, exc):
    conn.rollback()
    estado = "error" if celda[3] >= MAX_INTENTOS else "pendiente"
    conn.execute("UPDATE celdas_busqueda SET estado = %s, error = %s, actualizado_utc = now() WHERE celda_id = %s",
                 (estado, f"{type(exc).__name__}: {exc}"[:500], celda[0]))
    conn.commit()
    evento(log, "celda_fallida", logging.ERROR, exc_info=exc, celda=celda[0], estado=estado, intentos=celda[3],
           error=f"{type(exc).__name__}: {exc}"[:500])


def main():
    parser = argparse.ArgumentParser(description="Búsqueda continua de análogos por relieve.")
    parser.add_argument("config", type=Path)
    parser.add_argument("accion", choices=["referencias", "encolar", "contexto", "catalogo", "una", "bucle"])
    args = parser.parse_args()
    if not os.environ.get("DATABASE_URL"):
        parser.error("Falta DATABASE_URL")
    raw = args.config.read_bytes()
    cfg = json.loads(raw)
    evento(log, "inicio", accion=args.accion, config=str(args.config), config_sha256=hashlib.sha256(raw).hexdigest(),
           version_metodo=VERSION_METODO, escalas_m=cfg["escalas_m"], tesela_m=cfg["tesela_m"])
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            aplicar_migraciones(cur)
        conn.commit()
        if args.accion == "referencias":
            return referencias(conn, cfg)
        if args.accion == "encolar":
            return encolar(conn, cfg)
        if args.accion == "contexto":
            return rellenar_contexto(conn, cfg)
        if args.accion == "catalogo":
            return catalogo(conn)
        comprobar_contexto(conn, cfg)
        conn.commit()
        catalogo(conn)
        celdas = []
        if args.accion == "bucle" and cfg.get("auto_encolar"):
            celdas = celdas_del_perfil(cfg)
            latido(conn, "preparando", elegibles=len(celdas))
        while True:
            if args.accion == "bucle" and cfg.get("auto_encolar"):
                alimentar_cola(conn, cfg, celdas)
            celda = tomar(conn)
            if celda is None:
                latido(conn, "agotado" if cfg.get("auto_encolar") else "esperando")
                if args.accion == "bucle":
                    ubicar(conn, cfg, cfg.get("ubicacion", {}).get("en_espera", 0))
                evento(log, "cola_vacia", espera_s=0 if args.accion == "una" else cfg["espera_cola_vacia_s"])
                if args.accion == "una":
                    return 0
                time.sleep(cfg["espera_cola_vacia_s"])
                continue
            evento(log, "celda_tomada", celda=celda[0], intento=celda[3])
            latido(conn, "procesando", celda=celda[0])
            try:
                procesar(conn, cfg, celda)
            except (ValueError, rasterio.errors.RasterioError, psycopg.DataError) as exc:
                fallo(conn, celda, exc)
            if args.accion == "bucle":
                ubicar(conn, cfg, cfg.get("ubicacion", {}).get("por_celda", 0))
            if args.accion == "una":
                return 0


def ejecutar():
    try:
        return main()
    except Exception as exc:  # deja constancia antes de que systemd lo reinicie
        evento(log, "trabajador_detenido", logging.ERROR, exc_info=exc, error=f"{type(exc).__name__}: {exc}"[:500])
        raise


if __name__ == "__main__":
    raise SystemExit(ejecutar())
