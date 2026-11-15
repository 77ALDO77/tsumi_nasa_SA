"""MVP 0: métricas de relieve por ventana para la Luna y la Tierra, con procedencia.

Desde la raíz: python -m analisis analisis/inputs/mvp0.json --salida analisis/data/<carpeta-nueva>
"""
import argparse
import csv
import hashlib
import json
import subprocess
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio

from .fuentes import ventana
from .metricas import VERSION_METODO, metricas, sombreado

ROOT = Path(__file__).resolve().parent
# El PNG es solo una vista previa sin georreferencia; la georreferencia está en el GeoTIFF.
warnings.filterwarnings("ignore", category=rasterio.errors.NotGeoreferencedWarning)
CAMPOS = ["id", "cuerpo", "rol", "lat", "lon", "estado", "pendiente_mediana_grados", "pendiente_p90_grados",
          "relieve_p95_p5_m", "rugosidad_rms_plano_m", "fraccion_valida", "n_celdas_validas", "res_m"]


def commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or None
    except OSError:
        return None


def main():
    parser = argparse.ArgumentParser(description="Métricas de relieve por ventana (Luna/Tierra); no son una certificación de analogía.")
    parser.add_argument("config", type=Path)
    parser.add_argument("--salida", type=Path, required=True, help="Carpeta NUEVA de salida")
    parser.add_argument("--solo", action="append", default=[], help="ID de ventana (repetible)")
    args = parser.parse_args()
    raw = args.config.read_bytes()
    config = json.loads(raw)
    selected = [v for v in config["ventanas"] if not args.solo or v["id"] in args.solo]
    if not selected:
        parser.error("Ninguna ventana coincide con --solo")
    args.salida.mkdir(parents=True, exist_ok=False)
    (args.salida / "ventanas").mkdir()
    lado, escalas, minimo = config["lado_m"], config["escalas_m"], config["fraccion_valida_min"]
    manifest = {"config": str(args.config), "config_sha256": hashlib.sha256(raw).hexdigest(),
                "version": config["version"], "git_commit": commit(),
                "inicio_utc": datetime.now(timezone.utc).isoformat(), "lado_m": lado, "escalas_m": escalas,
                "version_metodo": VERSION_METODO, "remuestreo": "average", "proyeccion_calculo": "aeqd centrada en cada ventana",
                "limites": config.get("limites", []), "ventanas": []}
    rows = []
    for item in selected:
        base = {k: item[k] for k in ("id", "cuerpo", "rol", "lat", "lon", "fuente_coordenadas")}
        try:
            grids, transforms, crs, sources = ventana(item["cuerpo"], item["lat"], item["lon"], lado, escalas)
        except (ValueError, rasterio.errors.RasterioError) as exc:
            grids, error = {}, str(exc)[:300]
        for res in escalas:
            record = {**base, "res_m": res}
            if res not in grids:
                record.update(estado="error", motivo=error)
            else:
                z = grids[res]
                record.update(metricas(z, res, minimo), fuentes=sources, crs_calculo=crs.to_proj4())
                stem = args.salida / "ventanas" / f"{item['id']}_{res}m"
                profile = {"driver": "GTiff", "height": z.shape[0], "width": z.shape[1], "count": 1, "dtype": "float32",
                           "crs": crs, "transform": transforms[res], "nodata": np.nan, "compress": "deflate"}
                with rasterio.open(stem.with_suffix(".tif"), "w", **profile) as dst:
                    dst.write(z, 1)
                shade = sombreado(z, res)
                with rasterio.open(stem.with_suffix(".png"), "w", driver="PNG", height=shade.shape[0],
                                   width=shade.shape[1], count=1, dtype="uint8") as dst:
                    dst.write(shade, 1)
            manifest["ventanas"].append(record)
            rows.append({k: record.get(k) for k in CAMPOS})
            print(f"{item['id']} @{res} m: {record['estado']}", {k: record.get(k) for k in CAMPOS[6:11]})
        (args.salida / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest["fin_utc"] = datetime.now(timezone.utc).isoformat()
    (args.salida / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with open(args.salida / "metricas.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, CAMPOS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Resultado: {args.salida.resolve()}")
    return 0 if all(r["estado"] == "calculado" for r in manifest["ventanas"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
