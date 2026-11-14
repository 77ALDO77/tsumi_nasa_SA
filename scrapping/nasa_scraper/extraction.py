"""Extrae texto localizable; no infiere mediciones, analogías ni umbrales."""

import io
import re
import unicodedata
from urllib.parse import urljoin, urlsplit

from pypdf import PdfReader
from scrapling.parser import Selector

from .sources import normalize_url

DIMENSIONS = {
    "suelo": r"\b(soil\w*|regolith|grain size|granulometr\w*|suelo\w*|sediment\w*)\b",
    "minerales": r"\b(mineral\w*|spectr\w*|basalt\w*|sulfat\w*|sulphat\w*|raman)\b",
    "polvo": r"\b(dust|polvo|aeolian|eolian|eolic\w*)\b",
    "hielo": r"\b(ice|icy|hielo|frozen|glaci\w*)\b",
    "permafrost": r"\b(permafrost|active layer|cryosol\w*|capa activa)\b",
}
SITES = {
    "Atacama": r"\b(atacama|yungay)\b",
    "Antártida": r"\b(antarctic\w*|antart\w*|university valley|mcmurdo|quartermain)\b",
    "Islandia": r"\b(iceland\w*|islandia)\b",
    "Hawái": r"\b(hawai\w*|mauna loa|mauna kea|kilauea)\b",
    "Mojave": r"\bmojave\b",
    "Valle de la Muerte": r"\b(death valley|valle de la muerte)\b",
    "Haughton": r"\b(haughton|devon island)\b",
}


def clean(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def matching(text, patterns):
    folded = "".join(c for c in unicodedata.normalize("NFKD", text.lower())
                     if not unicodedata.combining(c))
    return [label for label, pattern in patterns.items() if re.search(pattern, folded)]


def extract_html(body: bytes, url: str, encoding="utf-8") -> dict:
    page = Selector(body.decode(encoding or "utf-8", errors="replace"), url=url)

    def meta(*names):
        for name in names:
            result = page.css(f'meta[name="{name}"]::attr(content), meta[property="{name}"]::attr(content)').getall()
            if result:
                return "; ".join(clean(value) for value in result)
        return None

    title = meta("citation_title", "og:title") or page.css("title::text").get()
    author = meta("citation_author", "author", "dc.creator")
    date = meta("citation_publication_date", "article:published_time", "dc.date")
    # El archivo LRO usa tablas de maquetación: su barra lateral no es evidencia.
    host = urlsplit(url).hostname
    roots = page.xpath("//td[h1]") if host == "pds-geosciences.wustl.edu" else []
    if host == "github.com":
        roots = page.css("article.markdown-body")
    elif host == "www.cambridge.org":
        roots = page.css("#article-tab")
    elif host == "www.gportal.jaxa.jp":
        roots = page.css("#main")
    if not roots:
        roots = page.css("main, [role='main'], article, #main-content, #content")
    root = roots[0] if roots else page
    segments = []
    section = None
    # XPath conservado sobre el árbol original, sin mutarlo ni perder localizadores.
    nodes = root.xpath(".//*[self::h1 or self::h2 or self::h3 or self::h4 or self::p or self::li or self::tr or self::pre or self::dt or self::dd][not(ancestor::nav or ancestor::footer or ancestor::header or ancestor::script or ancestor::style)]")
    if host == "www.gportal.jaxa.jp":
        nodes = root.css("#left_menus a, #contents a")
    for node in nodes:
        # No duplicar una tabla de maquetación entera como si fuera una fila de datos.
        if node.tag in {"tr", "li"} and node.css("p, table, ul, ol"):
            continue
        text = clean(" ".join(node.xpath(".//text()[not(ancestor::script or ancestor::style)]").getall()))
        if not text:
            continue
        tag = node.tag
        if tag in {"h1", "h2", "h3", "h4"}:
            section = text
        segments.append({"texto": text, "seccion": section, "tipo_segmento": tag,
                         "localizador": node.generate_full_xpath_selector,
                         "pagina": None})
    if not segments:
        text = clean(" ".join(root.xpath(".//text()[not(ancestor::script or ancestor::style or ancestor::nav or ancestor::footer or ancestor::header)]").getall()))
        if text:
            segments.append({"texto": text, "seccion": None, "localizador": "texto visible (fallback)", "pagina": None})
    links, seen = [], set()
    for anchor in root.css("a[href]"):
        try:
            target = normalize_url(urljoin(url, anchor.attrib["href"]))
        except ValueError:
            continue
        if target in seen:
            continue
        seen.add(target)
        links.append({"url": target, "texto": clean(" ".join(anchor.xpath(".//text()").getall()))})
    visible = " ".join(s["texto"] for s in segments)
    state = "extraido" if len(visible) >= 200 else "contenido_insuficiente"
    if host == "www.gportal.jaxa.jp" and segments:
        state = "portal_navegacion"
    if len(visible) < 1500 and (page.css("iframe") or re.search(r"enable javascript|requires javascript|need to enable javascript", visible, re.I)):
        state = "requiere_javascript_o_api"
    if re.search(r"just a moment|access denied|verify you are human|robot check|403 forbidden", clean(title), re.I):
        state = "bloqueo_acceso"
        segments = []
    return {"estado": state, "titulo": clean(title) or None, "autor_institucion_reportado": author,
            "fecha_publicacion_reportada": date, "segmentos": segments, "enlaces": links,
            "formato": "html", "alcance": "documentacion_web_no_medicion"}


def extract_pdf(body: bytes, url: str) -> dict:
    reader = PdfReader(io.BytesIO(body))
    segments = []
    empty_pages = []
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        if not clean(text):
            empty_pages.append(number)
        # Líneas consecutivas: un localizador de página sigue siendo verificable.
        for index, block in enumerate(re.split(r"\n\s*\n", text), 1):
            if clean(block):
                segments.append({"texto": clean(block), "seccion": None,
                                 "pagina": number, "localizador": f"pagina PDF {number}, bloque {index}"})
    metadata = reader.metadata or {}
    return {"estado": "extraido" if segments else "pdf_sin_texto_requiere_ocr",
            "titulo": metadata.get("/Title"), "autor_institucion_reportado": metadata.get("/Author"),
            "fecha_publicacion_reportada": None, "segmentos": segments, "enlaces": [],
            "formato": "pdf", "paginas": len(reader.pages), "paginas_sin_texto": empty_pages,
            "alcance": "documento_no_medicion_propia"}


def evidence_rows(source: dict, document: dict, max_fragments=20):
    rows, seen = [], set()
    for segment in document["segmentos"]:
        if segment.get("tipo_segmento") in {"h1", "h2", "h3", "h4"}:
            continue  # Un título por sí solo no es un pasaje de evidencia.
        text = segment["texto"]
        # Ventanas breves alrededor de una coincidencia, manteniendo el pasaje literal.
        hits = [m for pattern in DIMENSIONS.values() for m in re.finditer(pattern, text, re.I)]
        covered_until = -1
        for hit in sorted(hits, key=lambda m: m.start()):
            if hit.start() < covered_until:
                continue
            start = max(0, hit.start() - 160)
            end = min(len(text), start + 600)
            fragment = text[start:end]
            covered_until = end
            if fragment in seen:
                continue
            seen.add(fragment)
            dimensions = matching(fragment, DIMENSIONS)
            row = {key: None for key in (
                "objetivo_estudio", "referencia_planetaria", "tipo_analogia", "criterio", "metrica",
                "unidad", "escala_espacial_temporal", "valor_o_umbral", "alcance_del_umbral",
                "metodo_medicion", "dataset", "incertidumbre", "restriccion_operativa", "limitacion_analogia")}
            row.update({"source_id": source["source_id"], "url": source["url"],
                        "titulo": document["titulo"], "pagina_seccion": segment["localizador"],
                        "seccion": segment["seccion"], "pagina": segment["pagina"],
                        "fragmento": fragment, "offset_texto_normalizado": start,
                        "dimensiones_mencionadas": dimensions,
                        "sitios_mencionados": matching(fragment, SITES),
                        "estado_evidencia": "coincidencia_textual_no_validada", "revision_manual": "pendiente"})
            rows.append(row)
    if max_fragments is None or len(rows) <= max_fragments:
        return rows
    if max_fragments <= 0:
        return []
    if max_fragments == 1:
        return rows[:1]
    # Recorrer todo el documento antes de limitar: evitar quedarse en sus primeras páginas.
    indices = {0, len(rows) - 1}
    # Conservar al menos un pasaje que mencione cada sitio, si cabe en la muestra.
    for site in SITES:
        first = next((i for i, row in enumerate(rows) if site in row["sitios_mencionados"]), None)
        if first is not None and len(indices) < max_fragments:
            indices.add(first)
    available = [i for i in range(len(rows)) if i not in indices]
    remaining = max_fragments - len(indices)
    if remaining == 1:
        indices.add(available[len(available) // 2])
    elif remaining > 1:
        indices.update(available[round(i * (len(available) - 1) / (remaining - 1))] for i in range(remaining))
    return [rows[index] for index in sorted(indices)]
