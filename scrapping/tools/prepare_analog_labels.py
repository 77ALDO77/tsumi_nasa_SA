"""Convierte las definiciones de etiquetas de análogos en registros trazables.

Cada literal debe aparecer en un único segmento del corpus y el cuerpo guardado debe coincidir
con su SHA256. Comprueba trazabilidad textual; no valida la analogía ni sustituye la revisión humana.
La revisión humana se lee de la entrada y nunca se sobrescribe.

Desde la raíz: python -m scrapping.tools.prepare_analog_labels
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "inputs/etiquetas_analogos.json"
OUTPUT = ROOT / "docs/etiquetas_analogos.json"
DIMENSIONES = {
    "geologia_volcanica", "rocas_regolito", "atmosfera_viento", "iluminacion", "terreno_operaciones",
    "operaciones_rover", "paisaje_escala_rasgos", "entrenamiento_geologia", "operaciones_campo", "cuevas_lava",
    "hielo_subsuperficial", "terreno_peligros", "aridez_biofirmas", "ondulaciones_eolicas", "escala",
    "sales_perclorato", "sedimentos_minerales", "biofirmas", "hielo_cubierto", "geoquimica_volcanica",
}
ALLOWED = {
    "cuerpo_analogo": {"luna", "marte"},
    "relacion": {"similitud_documentada", "uso_documentado", "ruptura_documentada", "condicion_simulada"},
    "expectativa_perfil_eva_luna": {"positivo", "no_aplica", "ruptura"},
    "dimension": DIMENSIONES,
    "medibilidad_relieve": {"medible", "parcial", "no_medible", "ruptura"},
    "revision_humana": {"pendiente", "aprobada", "rechazada", "corregir"},
}


def preparar(spec: dict, corpus: Path) -> dict:
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    records = {r["source_id"]: r for r in manifest["fuentes"]}
    entries, seen = [], set()
    for label in spec["etiquetas"]:
        lid = label["label_id"]
        if lid in seen:
            raise ValueError(f"{lid}: identificador repetido")
        seen.add(lid)
        label = {"revision_humana": "pendiente", "revisor": None, "fecha_revision": None,
                 "autoridad_fuente": "nasa", **label}
        for field, values in ALLOWED.items():
            if label.get(field) not in values:
                raise ValueError(f"{lid}: {field}={label.get(field)!r} no está en {sorted(values)}")
        if label["medibilidad_relieve"] != "medible" and not label.get("motivo_medibilidad"):
            raise ValueError(f"{lid}: falta motivo_medibilidad")
        record = records.get(label["source_id"])
        if record is None:
            raise ValueError(f"{lid}: source_id {label['source_id']} no está en {corpus}/manifest.json")
        digest = hashlib.sha256((corpus / record["raw_path"]).read_bytes()).hexdigest()
        if digest != record["sha256"]:
            raise ValueError(f"{lid}: el cuerpo local no coincide con su SHA256")
        document = json.loads((corpus / record["document_path"]).read_text(encoding="utf-8"))
        literal = label["fragmento_literal"]
        segments = [s for s in document["segmentos"] if literal in s["texto"]]
        if len(segments) != 1:
            raise ValueError(f"{lid}: se esperaba un único segmento con el literal, encontrados {len(segments)}")
        segment = segments[0]
        entries.append({
            **label,
            "titulo_fuente": document.get("titulo"),
            "url": record["url"], "url_final": record["http"]["url_final"],
            "fecha_consulta_utc": record["http"]["fecha_consulta_utc"], "sha256_fuente": digest,
            "ejecucion_origen": Path(record.get("ejecucion_original") or spec["corpus"]).name,
            "localizador": segment["localizador"], "seccion": segment.get("seccion"),
            "offset_en_segmento": segment["texto"].index(literal),
            "offset_semantica": "caracteres Python desde el inicio del texto normalizado del segmento",
            "revision_asistente": "literal_contrastado_con_texto_extraido",
        })
    count = lambda field: {v: sum(e[field] == v for e in entries) for v in sorted({e[field] for e in entries})}
    return {"corpus": spec["corpus"],
            "estado": "pendiente_revision_humana" if any(e["revision_humana"] != "aprobada" for e in entries) else "revisado",
            "alcance": "Etiquetas documentales de uso o similitud declarados por NASA; no son mediciones ni certificaciones.",
            "recuento_expectativa_perfil_eva_luna": count("expectativa_perfil_eva_luna"),
            "recuento_medibilidad_relieve": count("medibilidad_relieve"),
            "recuento_revision_humana": count("revision_humana"),
            "etiquetas": entries}


def main():
    spec = json.loads(INPUT.read_text(encoding="utf-8"))
    result = preparar(spec, ROOT.parent / spec["corpus"])
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(result['etiquetas'])} etiquetas con literal y SHA256 comprobados: {OUTPUT}")
    print(result["recuento_medibilidad_relieve"], result["recuento_revision_humana"])


if __name__ == "__main__":
    main()
