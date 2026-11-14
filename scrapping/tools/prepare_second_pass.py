"""Prepara cinco hallazgos revisados; exige el corpus consolidado y verifica sus hashes.

Desde la raíz: python -m scrapping.tools.prepare_second_pass
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/segunda-pasada-consolidada"


def main():
    manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
    records = {r["source_id"]: r for r in manifest["fuentes"]}
    uv = "78c732036d4e58a3"
    definitions = [
        ("UV-N-01", uv,
         "475 measurements of depth to ice-cemented ground in four high-elevation valleys",
         "475 mediciones distribuidas entre cuatro valles de Quartermain.",
         "tamano_campana_reportado", 475, "mediciones", "Cuatro valles de Quartermain",
         "El total no es exclusivo de University Valley. Falta la distribución completa por valle."),
        ("UV-DEPTH-01", uv,
         "In University Valley, the measured depth to ice-cemented ground ranges from 0–98 cm.",
         "Profundidad reportada hasta terreno cementado por hielo: 0–98 cm.",
         "intervalo_observado_reportado", {"min": 0, "max": 98}, "cm", "University Valley",
         "Intervalo observado del estudio; no es umbral de aptitud ni medición marciana."),
        ("UV-GRADIENT-01", uv,
         "a slope of 32 cm depth per kilometre along the valley floor.",
         "Tendencia reportada de 32 cm de profundidad por kilómetro a lo largo del valle.",
         "tendencia_espacial_reportada", 32, "cm/km", "University Valley",
         "Faltan incertidumbre, distribución de puntos y método completo; no extrapolar fuera del transecto."),
        ("DIVINER-NODATA-01", "f2356e0a838fe278",
         'Records with missing brightness temperature data have the value -9999 in the "tb" column (column 24) of the Diviner RDR data product.',
         "La documentación RDR señala -9999 como marcador de temperatura de brillo ausente en tb, columna 24.",
         "convencion_calidad_documentada", -9999, None, "Diviner RDR",
         "Marcador de ausencia; verificar etiqueta y versión del producto antes de implementar el filtro."),
        ("JETT-SIM-01", "3dd78a02b731e1b7",
         "To replicate the proper lighting conditions, the JETT3 simulated moonwalks will occur at night, and a simulated sun will produce lighting and shadows in the field.",
         "La noticia describe caminatas nocturnas y un sol simulado para JETT3.",
         "configuracion_ensayo_descrita", None, None, "Ensayo JETT3 en Arizona",
         "El artículo anuncia la configuración; no demuestra resultados del ensayo ni iluminación lunar natural."),
    ]
    entries = []
    for identifier, sid, literal, claim, kind, value, unit, site, limit in definitions:
        record = records[sid]
        document = json.loads((CORPUS / record["document_path"]).read_text(encoding="utf-8"))
        segments = [s for s in document["segmentos"] if literal in s["texto"]]
        if len(segments) != 1:
            raise ValueError(f"{identifier}: se esperaba un único pasaje literal, encontrados {len(segments)}")
        segment = segments[0]
        digest = hashlib.sha256((CORPUS / record["raw_path"]).read_bytes()).hexdigest()
        if digest != record["sha256"]:
            raise ValueError(f"{identifier}: hash inválido")
        entries.append({
            "evidence_id": identifier, "source_id": sid, "afirmacion_documental": claim,
            "tipo": kind, "valor_reportado": value, "unidad_reportada": unit, "sitio_o_alcance": site,
            "url": record["url"], "url_final": record["http"]["url_final"],
            "fecha_consulta_utc": record["http"]["fecha_consulta_utc"], "sha256_fuente": digest,
            "ejecucion_origen": record["ejecucion_original"],
            "documento_local": f"../data/segunda-pasada-consolidada/{record['document_path']}",
            "localizador": segment["localizador"], "pagina": segment["pagina"],
            "fragmento_literal": literal, "offset_texto_normalizado": segment["texto"].index(literal),
            "revision_asistente": "contrastado_con_texto_extraido", "revision_humana": "pendiente",
            "incertidumbre": None, "limite": limit, "medicion_propia": False,
        })
    result = {"corpus": "scrapping/data/segunda-pasada-consolidada",
              "estado": "revision_documental_asistente_pendiente_revision_humana",
              "proposito": "Antecedentes y decisiones de calidad para MVP 0",
              "entradas": entries, "comparacion_terrestre_planetaria": "pendiente"}
    output = ROOT / "docs/evidencia_segunda_pasada.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(entries)} registros con fragmentos y hashes comprobados: {output}")


if __name__ == "__main__":
    main()
