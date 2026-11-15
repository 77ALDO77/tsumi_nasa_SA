"""Carga un manifiesto de analisis/ en PostgreSQL de forma idempotente.

Desde la raíz: DATABASE_URL=postgresql://... python -m analisis.cargar analisis/data/<carpeta>
Volver a cargar no duplica filas. Si una clave ya existe con otro valor, falla en lugar de sobrescribir.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

import psycopg
from psycopg.types.json import Jsonb
from rasterio.warp import transform_geom

from .metricas import VERSION_METODO

MIGRACIONES = Path(__file__).resolve().parent.parent / "db/migraciones"
METRICAS = {
    "pendiente_mediana_grados": ("pendiente", "mediana", "grados"),
    "pendiente_p90_grados": ("pendiente", "p90", "grados"),
    "relieve_p95_p5_m": ("relieve", "p95_p5", "m"),
    "rugosidad_rms_plano_m": ("rugosidad", "rms_plano", "m"),
}


def producto(url):
    host = urlsplit(url).hostname
    if host == "pds-geosciences.wustl.edu":
        return ("NASA PDS Geosciences", "LRO LOLA GDR polar " + Path(urlsplit(url).path).stem, "", "luna",
                None, "LRO LOLA Gridded Data Record, NASA PDS")
    if host == "copernicus-dem-30m.s3.amazonaws.com":
        return ("Copernicus (AWS Open Data)", "Copernicus DEM GLO-30 COG", "", "tierra", None,
                "Copernicus DEM GLO-30, ESA/Airbus")
    raise ValueError(f"Fuente sin producto registrado: {host}")


def aplicar_migraciones(cur):
    for sql in sorted(MIGRACIONES.glob("*.sql")):
        cur.execute(sql.read_text(encoding="utf-8"))


def una(cur, sql, params):
    cur.execute(sql, params)
    return cur.fetchone()


def cargar(conn, carpeta: Path):
    manifest = json.loads((carpeta / "manifest.json").read_text(encoding="utf-8"))
    run_id = carpeta.name
    version = manifest.get("version_metodo", VERSION_METODO)
    with conn.transaction(), conn.cursor() as cur:
        aplicar_migraciones(cur)
        params = {k: manifest[k] for k in ("lado_m", "remuestreo", "proyeccion_calculo", "limites") }
        params["escalas_m"] = manifest.get("escalas_m") or [manifest["res_m"]]  # manifiestos v1 tenían res_m
        params["version_metodo"] = version
        cur.execute("""INSERT INTO ejecuciones (ejecucion_id, tipo, config_sha256, version_config, git_commit,
                       inicio_utc, fin_utc, parametros) VALUES (%s,'calculo_relieve',%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (ejecucion_id) DO NOTHING""",
                    (run_id, manifest["config_sha256"], manifest["version"], manifest["git_commit"],
                     manifest["inicio_utc"], manifest.get("fin_utc"), Jsonb(params)))
        stored = una(cur, "SELECT config_sha256 FROM ejecuciones WHERE ejecucion_id=%s", (run_id,))[0]
        if stored != manifest["config_sha256"]:
            raise ValueError(f"{run_id}: ya existe con otra configuración")
        totals = {"metricas_nuevas": 0, "metricas_existentes": 0}
        # Nombre y etiquetas son descriptivos: se leen de la configuración actual, así no hace falta recalcular.
        config = Path(manifest.get("config", ""))
        catalogo = ({c["id"]: c for c in json.loads(config.read_text(encoding="utf-8"))["ventanas"]}
                    if config.is_file() else {})
        for v in manifest["ventanas"]:
            earth = v["cuerpo"] == "tierra"
            extra = catalogo.get(v["id"], {})
            cur.execute("""INSERT INTO sitios (sitio_id, cuerpo, lat, lon, fuente_coordenadas, geom, nombre, rol, etiquetas)
                           VALUES (%s,%s,%s,%s,%s, CASE WHEN %s THEN ST_SetSRID(ST_MakePoint(%s,%s),4326) END, %s,%s,%s)
                            ON CONFLICT (sitio_id) DO UPDATE SET rol = coalesce(nullif(EXCLUDED.rol,''), sitios.rol),
                               nombre = coalesce(EXCLUDED.nombre, sitios.nombre),
                               etiquetas = coalesce(EXCLUDED.etiquetas, sitios.etiquetas)""",
                        (v["id"], v["cuerpo"], v["lat"], v["lon"], v["fuente_coordenadas"], earth, v["lon"], v["lat"],
                          extra.get("nombre"), extra.get("rol") or v.get("rol"), extra.get("etiquetas")))
            if una(cur, "SELECT lat, lon FROM sitios WHERE sitio_id=%s", (v["id"],)) != (v["lat"], v["lon"]):
                raise ValueError(f"{v['id']}: el sitio ya existe con otras coordenadas")
            if v["estado"] == "error":
                print(f"{v['id']}: omitida (error en el cálculo: {v.get('motivo')})", file=sys.stderr)
                continue
            half = v["n_celdas"] ** 0.5 * v["res_m"] / 2
            geom = None
            if earth:
                box = {"type": "Polygon", "coordinates": [[(-half, -half), (half, -half), (half, half), (-half, half), (-half, -half)]]}
                geom = json.dumps(transform_geom(v["crs_calculo"], "EPSG:4326", box, precision=7))
            cur.execute("""INSERT INTO ventanas (sitio_id, lado_m, res_m, crs_calculo, geom)
                           VALUES (%s,%s,%s,%s, ST_SetSRID(ST_GeomFromGeoJSON(%s),4326))
                           ON CONFLICT (sitio_id, lado_m, res_m) DO NOTHING""",
                        (v["id"], manifest["lado_m"], v["res_m"], v["crs_calculo"], geom))
            window_id = una(cur, "SELECT ventana_id FROM ventanas WHERE sitio_id=%s AND lado_m=%s AND res_m=%s",
                            (v["id"], manifest["lado_m"], v["res_m"]))[0]
            for source in v.get("fuentes", []):
                prov, coll, ver, body, lic, cite = producto(source["url"])
                cur.execute("""INSERT INTO productos (proveedor, coleccion, version, cuerpo, licencia, cita)
                               VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (proveedor, coleccion, version) DO NOTHING""",
                            (prov, coll, ver, body, lic, cite))
                product_id = una(cur, "SELECT producto_id FROM productos WHERE proveedor=%s AND coleccion=%s AND version=%s",
                                 (prov, coll, ver))[0]
                cur.execute("""INSERT INTO lecturas_fuente VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                            (run_id, window_id, product_id, source["url"], source["estado"],
                             Jsonb(source.get("ventana_fuente")), source.get("res_nativa_m"), source.get("sha256_valores_leidos")))
            for key, (variable, stat, unit) in METRICAS.items():
                value = v.get(key)
                cur.execute("""INSERT INTO metricas (ventana_id, variable, estadistico, version_metodo, valor, unidad, estado,
                               motivo, fraccion_valida, n_validas, n_total, ejecucion_id)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                               ON CONFLICT (ventana_id, variable, estadistico, version_metodo) DO NOTHING RETURNING 1""",
                            (window_id, variable, stat, version, value, unit, v["estado"], v.get("motivo"),
                             v.get("fraccion_valida"), v.get("n_celdas_validas"), v.get("n_celdas"), run_id))
                if cur.fetchone():
                    totals["metricas_nuevas"] += 1
                    continue
                totals["metricas_existentes"] += 1
                stored = una(cur, """SELECT valor FROM metricas WHERE ventana_id=%s AND variable=%s AND estadistico=%s
                                     AND version_metodo=%s""", (window_id, variable, stat, version))[0]
                if stored != value:
                    raise ValueError(f"{v['id']} {variable}/{stat}: ya existe {stored}, la nueva ejecución da {value}. "
                                     "Si el método cambió, sube VERSION_METODO.")
    return totals


def main():
    parser = argparse.ArgumentParser(description="Carga un manifiesto de analisis/ en PostgreSQL (idempotente).")
    parser.add_argument("carpeta", type=Path)
    args = parser.parse_args()
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        parser.error("Falta DATABASE_URL (defínela en secretos/.env o en el entorno; nunca en el código)")
    with psycopg.connect(dsn) as conn:
        print(cargar(conn, args.carpeta))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
