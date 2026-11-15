"""Búsqueda continua de análogos: calcula envolventes de referencia y procesa una cola de celdas de 1°.

Desde la raíz, con DATABASE_URL en el entorno:
  python -m analisis.trabajador analisis/inputs/busqueda.json referencias   # envolventes lunares
  python -m analisis.trabajador analisis/inputs/busqueda.json encolar       # celdas de las zonas
  python -m analisis.trabajador analisis/inputs/busqueda.json una           # procesa una celda
  python -m analisis.trabajador analisis/inputs/busqueda.json bucle         # servicio: no termina
Varios trabajadores pueden correr a la vez: cada celda se reserva con FOR UPDATE SKIP LOCKED.
"""
import argparse
import hashlib
import json
import logging
import os
import time
from pathlib import Path

import psycopg
import rasterio
from psycopg.types.json import Jsonb

from .busqueda import caja_celda, envolvente, geometrias
from .cargar import aplicar_migraciones
from .fuentes import ventana
from .metricas import VERSION_METODO, metricas_teselas
from .registro import configurar, evento

log = configurar("trabajador")

MAX_INTENTOS = 3


def celda_id(lat, lon):
    return f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}{'E' if lon >= 0 else 'W'}{abs(lon):03d}"


def referencias(conn, cfg):
    tesela_m, minimo = cfg["tesela_m"], cfg["fraccion_valida_min"]
    for ref in cfg["referencias"]:
        grids, transforms, crs, _ = ventana(ref["cuerpo"], ref["lat"], ref["lon"], ref["lado_m"], cfg["escalas_m"])
        for res, z in grids.items():
            env, n = envolvente(metricas_teselas(z, res, round(tesela_m / res), minimo), cfg["minimo_subventanas"])
            conn.execute("""INSERT INTO referencias (referencia_id, cuerpo, lat, lon, lado_m, tesela_m, res_m, version_metodo,
                            fuente_coordenadas, n_subventanas, envolvente) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (referencia_id, res_m, version_metodo) DO UPDATE SET envolvente = EXCLUDED.envolvente,
                            n_subventanas = EXCLUDED.n_subventanas, calculado_utc = now()""",
                         (ref["id"], ref["cuerpo"], ref["lat"], ref["lon"], ref["lado_m"], tesela_m, res, VERSION_METODO,
                          ref["fuente_coordenadas"], n, Jsonb(env)))
            conn.commit()
            evento(log, "referencia_calculada", referencia=ref["id"], res_m=res, n_subventanas=n, envolvente=env)


def encolar(conn, cfg):
    total = 0
    for zona in cfg["zonas"]:
        lon0, lat0, lon1, lat1 = zona["bbox"]  # grados enteros: [lon0, lon1) x [lat0, lat1)
        for lat in range(lat0, lat1):
            for lon in range(lon0, lon1):
                cur = conn.execute("""INSERT INTO celdas_busqueda (celda_id, lat_min, lon_min, zona, prioridad)
                                      VALUES (%s,%s,%s,%s,%s) ON CONFLICT (celda_id) DO UPDATE
                                      SET prioridad = least(celdas_busqueda.prioridad, EXCLUDED.prioridad)""",
                                   (celda_id(lat, lon), lat, lon, zona["nombre"], zona["prioridad"]))
                total += cur.rowcount
    conn.commit()
    evento(log, "celdas_encoladas", n=total)


def tomar(conn):
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
    with conn.transaction():
        for res, z in grids.items():
            t1 = time.monotonic()
            teselas = metricas_teselas(z, res, round(tesela_m / res), minimo)
            n_total += len(teselas)
            ok = [t for t in teselas if t["estado"] == "calculado"]
            n_validas += len(ok)
            geometrias(transforms[res], crs, round(tesela_m / res), ok, "EPSG:4326")
            t2 = time.monotonic()
            t_metricas += t2 - t1
            conn.cursor().executemany(
                """INSERT INTO teselas (celda_id, res_m, version_metodo, ix, iy, lat, lon, geom, pendiente_mediana,
                   pendiente_p90, relieve, rugosidad, fraccion_valida) VALUES (%s,%s,%s,%s,%s,%s,%s,
                   ST_SetSRID(ST_GeomFromGeoJSON(%s),4326),%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                [(cid, res, VERSION_METODO, t["ix"], t["iy"], t["lat"], t["lon"],
                  json.dumps({"type": "Polygon", "coordinates": [t["poligono"]]}), t["pendiente_mediana_grados"],
                  t["pendiente_p90_grados"], t["relieve_p95_p5_m"], t["rugosidad_rms_plano_m"], t["fraccion_valida"])
                 for t in ok])
            t_insercion += time.monotonic() - t2
        estado = "hecha" if n_validas else "sin_datos"
        motivo = None if n_validas else "; ".join(f["estado"] for f in fuentes) or "sin teselas válidas"
        conn.execute("""UPDATE celdas_busqueda SET estado = %s, n_teselas = %s, n_validas = %s, error = %s,
                        actualizado_utc = now() WHERE celda_id = %s""", (estado, n_total, n_validas, motivo, cid))
    evento(log, "celda_terminada", celda=cid, estado=estado, n_validas=n_validas, n_teselas=n_total,
           lectura_s=round(t_lectura, 2), metricas_s=round(t_metricas, 2), insercion_s=round(t_insercion, 2),
           duracion_s=round(time.monotonic() - t0, 2), motivo=motivo)


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
    parser.add_argument("accion", choices=["referencias", "encolar", "una", "bucle"])
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
        # Un trabajador caído deja celdas 'en_curso': se devuelven a la cola pasada una hora.
        devueltas = conn.execute("""UPDATE celdas_busqueda SET estado = 'pendiente' WHERE estado = 'en_curso'
                        AND actualizado_utc < now() - interval '1 hour'""").rowcount
        conn.commit()
        if devueltas:
            evento(log, "celdas_recuperadas", logging.WARNING, n=devueltas)
        if args.accion == "referencias":
            return referencias(conn, cfg)
        if args.accion == "encolar":
            return encolar(conn, cfg)
        while True:
            celda = tomar(conn)
            if celda is None:
                evento(log, "cola_vacia", espera_s=0 if args.accion == "una" else cfg["espera_cola_vacia_s"])
                if args.accion == "una":
                    return 0
                time.sleep(cfg["espera_cola_vacia_s"])
                continue
            evento(log, "celda_tomada", celda=celda[0], intento=celda[3])
            try:
                procesar(conn, cfg, celda)
            except (ValueError, rasterio.errors.RasterioError, psycopg.DataError) as exc:
                fallo(conn, celda, exc)
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
