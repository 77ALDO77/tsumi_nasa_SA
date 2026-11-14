"""Auditoría cuantitativa local: calidad de extracción, no validez científica.

python -m scrapping.nasa_scraper.analysis --run scrapping/data/analisis-consolidado
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from .pipeline import write_json


def analyze(run_dir: Path, baseline: Path | None = None):
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    before = {}
    if baseline:
        before = {r["source_id"]: r for r in json.loads((baseline / "manifest.json").read_text(encoding="utf-8"))["fuentes"]}
    rows = [json.loads(line) for line in (run_dir / "evidencia.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    sources = []
    for record in manifest["fuentes"]:
        sid = record["source_id"]
        document = json.loads((run_dir / record["document_path"]).read_text(encoding="utf-8")) if record.get("document_path") else {}
        selected = [r for r in rows if r["source_id"] == sid]
        pages = sorted({r["pagina"] for r in selected if r.get("pagina")})
        warnings = []
        if record["tipo"] == "portal":
            warnings.append("Portada o ficha de catálogo: no equivale a producto científico descargado.")
        if record["estado"] == "extraido" and not selected:
            warnings.append("Sin pasajes de las cinco dimensiones; revisar documento completo y alcance operativo.")
        if document.get("paginas_sin_texto"):
            warnings.append("Hay páginas sin texto extraíble; inspección visual/OCR pendiente.")
        if record.get("pasajes_antes_del_limite", len(selected)) > len(selected):
            warnings.append("Muestra limitada de pasajes; no es revisión exhaustiva.")
        sources.append({
            "source_id": sid, "fuente": record["nombre"], "url": record["url"],
            "estado_anterior": before.get(sid, {}).get("estado"), "estado_actual": record["estado"],
            "tipo_inventario": record["tipo"], "sha256": record.get("sha256"),
            "documento_local": record.get("document_path"), "bytes": record.get("bytes"),
            "segmentos": len(document.get("segmentos", [])),
            "caracteres_extraidos": sum(len(s["texto"]) for s in document.get("segmentos", [])),
            "enlaces": len(document.get("enlaces", [])), "pasajes_exportados": len(selected),
            "pasajes_antes_limite": record.get("pasajes_antes_del_limite"),
            "paginas_pdf": document.get("paginas"), "paginas_sin_texto": document.get("paginas_sin_texto", []),
            "paginas_con_pasajes_exportados": pages, "advertencias_interpretacion": warnings,
            "error": record.get("error"), "diagnostico": record.get("diagnostico"),
        })
    return {"ejecucion": str(run_dir), "baseline": str(baseline) if baseline else None,
            "estados": dict(Counter(r["estado_actual"] for r in sources)), "fuentes": sources,
            "pasajes_exportados": len(rows), "enlaces": sum(r["enlaces"] for r in sources),
            "limite": "Estas métricas auditan la extracción, no puntúan similitud ni solidez científica."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output", type=Path, help="JSON de salida; por defecto dentro de la ejecución")
    args = parser.parse_args()
    result = analyze(args.run, args.baseline)
    output = args.output or args.run / "analisis.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, result)
    with output.with_suffix(".csv").open("w", encoding="utf-8-sig", newline="") as stream:
        fields = ["source_id", "fuente", "estado_anterior", "estado_actual", "segmentos", "caracteres_extraidos",
                  "enlaces", "pasajes_exportados", "pasajes_antes_limite", "paginas_pdf"]
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(result["fuentes"])
    print(json.dumps({"fuentes": len(result["fuentes"]), "estados": result["estados"],
                      "pasajes": result["pasajes_exportados"], "enlaces": result["enlaces"]}, ensure_ascii=False))
    print(f"Análisis: {output}")


if __name__ == "__main__":
    main()
