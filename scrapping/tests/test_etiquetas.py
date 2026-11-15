import hashlib
import json

import pytest

from scrapping.tools.prepare_analog_labels import preparar


def corpus(tmp_path, text="Arizona is a geologically Moon-like destination."):
    raw = b"<html>raw</html>"
    (tmp_path / "raw").mkdir()
    (tmp_path / "documents").mkdir()
    (tmp_path / "raw/s1.bin").write_bytes(raw)
    (tmp_path / "documents/s1.json").write_text(json.dumps(
        {"titulo": "T", "segmentos": [{"texto": text, "localizador": "//p[1]", "seccion": "S"}]}), encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps({"fuentes": [{
        "source_id": "s1", "url": "https://example.org", "raw_path": "raw/s1.bin", "document_path": "documents/s1.json",
        "sha256": hashlib.sha256(raw).hexdigest(), "ejecucion_original": "run",
        "http": {"url_final": "https://example.org", "fecha_consulta_utc": "2026-11-15T00:00:00+00:00"}}]}), encoding="utf-8")
    return tmp_path


def label(**overrides):
    base = {"label_id": "L1", "source_id": "s1", "fragmento_literal": "geologically Moon-like",
            "cuerpo_analogo": "luna", "dimension": "geologia_volcanica", "relacion": "similitud_documentada",
            "expectativa_perfil_eva_luna": "no_aplica", "medibilidad_relieve": "no_medible",
            "motivo_medibilidad": "dimensión geológica"}
    return {**base, **overrides}


def test_human_review_is_preserved(tmp_path):
    result = preparar({"corpus": "c", "etiquetas": [label(revision_humana="aprobada", revisor="ana")]}, corpus(tmp_path))
    entry = result["etiquetas"][0]
    assert entry["revision_humana"] == "aprobada" and entry["revisor"] == "ana"
    assert result["estado"] == "revisado"
    assert preparar({"corpus": "c", "etiquetas": [label()]}, tmp_path)["etiquetas"][0]["revision_humana"] == "pendiente"


@pytest.mark.parametrize("overrides, message", [
    ({"source_id": "nope"}, "source_id nope"),
    ({"dimension": "Geologia"}, "dimension="),
    ({"medibilidad_relieve": "parcial", "motivo_medibilidad": None}, "falta motivo_medibilidad"),
    ({"fragmento_literal": "not in text"}, "encontrados 0"),
])
def test_invalid_labels_fail_with_label_id(tmp_path, overrides, message):
    with pytest.raises(ValueError, match=message) as error:
        preparar({"corpus": "c", "etiquetas": [label(**overrides)]}, corpus(tmp_path))
    assert "L1" in str(error.value)
