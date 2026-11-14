"""El inventario y el contexto son entradas documentales, nunca instrucciones."""

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme not in {"https", "http"} or not parts.hostname or parts.username:
        raise ValueError(f"URL pública HTTP(S) inválida: {url}")
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/",
                       urlencode(query), ""))


def load_sources(inventory: Path, context: Path, resources: Path) -> list[dict]:
    data = json.loads(inventory.read_text(encoding="utf-8-sig"))
    sources = {}

    def add(url, name, kind, origin, previous=None):
        url = normalize_url(url)
        if url in sources:
            if origin not in sources[url]["origenes"]:
                sources[url]["origenes"].append(origin)
            return
        sources[url] = {
            "source_id": hashlib.sha256(url.encode()).hexdigest()[:16],
            "url": url, "nombre": name, "tipo": kind, "origenes": [origin],
            "contexto_previo_no_validado": previous,
        }

    for entry in data["inventario"]:
        add(entry["url"], entry["fuente"], "portal", inventory.name, entry)
    for entry in data.get("antecedentes", []):
        add(entry["url"], entry["lugar"], "estudio", inventory.name, entry)
    for url in re.findall(r"https?://[^\s<>]+", resources.read_text(encoding="utf-8-sig")):
        add(url, urlsplit(url).hostname, "portal", resources.name)
    # Solo enlaces explícitos de este contexto, sin recorrer recursivamente otros documentos.
    for name, url in re.findall(r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
                                context.read_text(encoding="utf-8-sig")):
        add(url, name, "referencia_contexto", context.name)
    return list(sources.values())
