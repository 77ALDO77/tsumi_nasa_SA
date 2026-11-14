import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from .extraction import DIMENSIONS, SITES, evidence_rows, extract_html, extract_pdf
from .transport import Client, Download, FetchError, now


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_download(download):
    body, meta = download.body, download.metadata
    status = meta["http_status"]
    if not 200 <= status < 300:
        raise FetchError("bloqueo_acceso" if status in {401, 403} else "error_http", f"HTTP {status}")
    if body.startswith(b"%PDF-"):
        return extract_pdf(body, meta["url_final"])
    content_type = meta["content_type"].lower()
    if "html" in content_type or (not content_type and body.lstrip().startswith(b"<")):
        return extract_html(body, meta["url_final"], meta.get("encoding", "utf-8"))
    raise FetchError("formato_no_soportado", f"Content-Type: {content_type}; no es HTML/PDF")


def run(sources, output: Path, context: Path, client=None, offline: Path | list[Path] | None = None):
    output.mkdir(parents=True, exist_ok=False)
    for folder in ("raw", "documents"):
        (output / folder).mkdir()
    context_bytes = context.read_bytes()
    (output / "CONTEXTO_RETO.md").write_bytes(context_bytes)
    write_json(output / "sources.json", sources)
    client = client or Client()
    records, rows, hashes = [], [], {}
    offline_paths = [offline] if isinstance(offline, Path) else (offline or [])
    old_records, original_runs, old_robots = {}, {}, {}
    for previous in offline_paths:
        old_manifest = json.loads((previous / "manifest.json").read_text(encoding="utf-8"))
        for record in old_manifest["fuentes"]:
            old_records[record["source_id"]] = record
            original_runs[record["source_id"]] = previous
        if (previous / "robots.json").exists():
            old_robots.update(json.loads((previous / "robots.json").read_text(encoding="utf-8")))
    for source in sources:
        sid = source["source_id"]
        record = {**source, "procesado_utc": now(), "modo": "offline" if offline else "red"}
        try:
            if offline:
                old = old_records.get(sid, {})
                if sid in original_runs:
                    record["ejecucion_original"] = str(original_runs[sid])
                if "raw_path" not in old:
                    record["sin_cuerpo_local"] = True
                    raise FetchError(old.get("estado", "sin_copia_local"),
                                     old.get("error", "fuente no descargada"), **old.get("diagnostico", {}))
                # Rutas construidas desde IDs del inventario, nunca desde datos remotos.
                previous = original_runs[sid]
                body = (previous / "raw" / f"{sid}.bin").read_bytes()
                if hashlib.sha256(body).hexdigest() != old["sha256"]:
                    raise FetchError("integridad_invalida", "SHA256 de copia local diferente al manifest")
                download = Download(body, old["http"])
                record["ejecucion_original"] = str(previous)
            else:
                download = client.fetch(source["url"])
            digest = hashlib.sha256(download.body).hexdigest()
            raw_path = f"raw/{sid}.bin"
            (output / raw_path).write_bytes(download.body)
            record.update({"http": download.metadata, "raw_path": raw_path, "sha256": digest,
                           "bytes": len(download.body)})
            document = parse_download(download)
            document["seleccion_fragmentos"] = "hasta_20_ventanas_distribuidas_por_orden_documental_no_exhaustivo"
            record["estado"] = document["estado"]
            if digest in hashes:
                record["duplicado_de"] = hashes[digest]
            else:
                hashes[digest] = sid
                candidates = evidence_rows(source, document) if document["estado"] == "extraido" else []
                record["pasajes_antes_del_limite"] = len(evidence_rows(source, document, max_fragments=None)) if candidates else 0
                for row in candidates:
                    row.update({"url_final": download.metadata["url_final"], "sha256": digest,
                                "fecha_consulta_utc": download.metadata["fecha_consulta_utc"],
                                "autor_institucion": document["autor_institucion_reportado"],
                                "fecha": document["fecha_publicacion_reportada"], "tipo_fuente": source["tipo"]})
                rows.extend(candidates)
                record["fragmentos_candidatos"] = len(candidates)
            document.update({"source_id": sid, "url": source["url"], "http": download.metadata,
                             "sha256": digest, "revision_manual": "pendiente"})
            record["document_path"] = f"documents/{sid}.json"
            write_json(output / record["document_path"], document)
        except FetchError as exc:
            record.update({"estado": exc.state, "error": str(exc), "diagnostico": exc.details})
        except Exception as exc:
            record.update({"estado": "error_extraccion", "error": f"{type(exc).__name__}: {exc}"})
        records.append(record)
        print(f"{source['nombre']}: {record['estado']}", flush=True)
        # Checkpoint por fuente: una interrupción no elimina lo ya descargado.
        write_json(output / "manifest.json", {"completo": False, "fuentes": records})
        write_json(output / "robots.json", old_robots if offline else client.robots_log)
    with (output / "evidencia.jsonl").open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (output / "cobertura.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["sitio", "dimension", "fragmentos_candidatos", "estado", "source_ids"])
        writer.writeheader()
        for site in SITES:
            for dimension in DIMENSIONS:
                matches = [r for r in rows if site in r["sitios_mencionados"] and dimension in r["dimensiones_mencionadas"]]
                writer.writerow({"sitio": site, "dimension": dimension, "fragmentos_candidatos": len(matches),
                                 "estado": "pendiente_revision" if matches else "sin_coincidencias_en_esta_extraccion",
                                 "source_ids": ";".join(sorted({r["source_id"] for r in matches}))})
    counts = dict(Counter(r["estado"] for r in records))
    manifest = {"completo": True, "finalizado_utc": now(), "scrapling_version": "0.5.1",
                "contexto_sha256": hashlib.sha256(context_bytes).hexdigest(), "estados": counts,
                "fuentes": records, "fragmentos_candidatos": len(rows)}
    write_json(output / "manifest.json", manifest)
    lines = ["# Resultado de extracción documental", "", f"Fuentes: {len(records)}. Fragmentos candidatos: {len(rows)}.",
             "", "Los fragmentos son coincidencias textuales pendientes de revisión. No constituyen mediciones ni validación de analogías.",
             "Las 35 celdas de cobertura registran coocurrencias; no encontrar texto no demuestra ausencia científica.",
             "", "| Fuente | Estado | Fragmentos |", "|---|---|---|"]
    for record in records:
        lines.append(f"| {record['nombre']} | {record['estado']} | {record.get('fragmentos_candidatos', 0)} |")
    (output / "resumen.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest
