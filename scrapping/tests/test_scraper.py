import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pypdf import PdfWriter

from scrapping.nasa_scraper.extraction import evidence_rows, extract_html, extract_pdf
from scrapping.nasa_scraper.pipeline import parse_download, run
from scrapping.nasa_scraper.sources import load_sources, normalize_url
from scrapping.nasa_scraper.transport import Client, Download, FetchError

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
HTML = b'''<html><head><title>Ice study</title><meta name="citation_author" content="Researcher"></head>
<body><nav>Dust on Mars</nav><main><h1>University Valley</h1><p>The Antarctic permafrost contains ice at a measured depth.
This observation concerns the terrestrial site only and does not establish the presence of ice on Mars.
Independent measurements and compatible scales are necessary for a comparison.</p>
<table><tr><th>Soil depth</th><td>98 cm</td></tr></table><a href="/data?lang=en&amp;utm_source=test">Data</a></main>
<footer>Footer dust</footer></body></html>'''


def download(body=HTML, status=200, kind="text/html", url="https://example.org/study"):
    return Download(body, {"http_status": status, "content_type": kind, "url_final": url,
                           "fecha_consulta_utc": "2026-11-14T12:00:00+00:00", "encoding": "utf-8", "headers": {}})


def test_inventory_deduplicates_and_preserves_query():
    sources = load_sources(ROOT / "inputs/extraccion_fuentes.json", PROJECT_ROOT / "CONTEXTO_RETO.md", PROJECT_ROOT / "resources.txt")
    assert len(sources) == 17
    assert len({s["url"] for s in sources}) == 17
    assert normalize_url("https://www.gportal.jaxa.jp/?lang=en&utm_source=x#foo") == "https://www.gportal.jaxa.jp/?lang=en"
    assert next(s for s in sources if s["nombre"] == "PDS")["origenes"] == ["extraccion_fuentes.json", "resources.txt"]


def test_html_evidence_has_locator_and_no_inferred_measurement():
    doc = extract_html(HTML, "https://example.org/study")
    assert doc["estado"] == "extraido"
    assert doc["autor_institucion_reportado"] == "Researcher"
    assert not any("Footer dust" in s["texto"] or "Dust on Mars" in s["texto"] for s in doc["segmentos"])
    assert any("98 cm" in s["texto"] for s in doc["segmentos"])
    assert doc["enlaces"][0]["url"] == "https://example.org/data?lang=en"
    rows = evidence_rows({"source_id": "abc", "url": "https://example.org/study"}, doc)
    assert rows
    assert all(r["pagina_seccion"].startswith("/") for r in rows)
    assert all(r["valor_o_umbral"] is None and r["revision_manual"] == "pendiente" for r in rows)
    assert any("Antártida" in r["sitios_mencionados"] for r in rows)


def test_javascript_and_challenge_are_not_success():
    assert extract_html(b"<body><p>You need to enable JavaScript to run this app.</p></body>", "https://x.org")["estado"] == "requiere_javascript_o_api"
    assert extract_html(b"<title>Just a moment...</title><p>Verify you are human.</p>", "https://x.org")["estado"] == "bloqueo_acceso"


def test_pdf_page_locator_and_no_ocr_claim(tmp_path):
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=800)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 40 700 Td (Mojave dust measurements.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    pdf = tmp_path / "test.pdf"
    writer.write(pdf)
    doc = extract_pdf(pdf.read_bytes(), "https://example.org/study.pdf")
    assert doc["segmentos"][0]["pagina"] == 1
    assert doc["paginas_sin_texto"] == []
    assert "Mojave dust" in doc["segmentos"][0]["texto"]
    empty = PdfWriter()
    empty.add_blank_page(width=100, height=100)
    empty.write(pdf)
    assert extract_pdf(pdf.read_bytes(), "https://example.org/scan.pdf")["estado"] == "pdf_sin_texto_requiere_ocr"


@pytest.mark.parametrize("status,state", [(403, "bloqueo_acceso"), (404, "error_http"), (429, "error_http")])
def test_http_error_not_parsed_as_evidence(status, state):
    with pytest.raises(FetchError) as error:
        parse_download(download(status=status))
    assert error.value.state == state


def test_robots_blocks_redirect_destination_and_caches(monkeypatch):
    client = Client(delay=0)
    calls = []

    def request(url):
        calls.append(url)
        if url == "https://a.org/robots.txt":
            return download(b"User-agent: *\nDisallow:\n", kind="text/plain", url=url)
        if url == "https://a.org/study":
            result = download(status=302, url=url)
            result.metadata["headers"]["location"] = "https://b.org/private/study"
            return result
        if url == "https://b.org/robots.txt":
            return download(b"User-agent: *\nDisallow: /private/*\n", kind="text/plain", url=url)
        pytest.fail(f"No debe solicitar: {url}")

    monkeypatch.setattr(client, "_request", request)
    with pytest.raises(FetchError, match="robots.txt no permite"):
        client.fetch("https://a.org/study")
    client.check_robots("https://a.org/other")
    assert calls.count("https://a.org/robots.txt") == 1
    assert "https://b.org/private/study" not in calls


def test_robots_timeout_is_not_permission(monkeypatch):
    client = Client(delay=0)

    def fail(url):
        raise FetchError("error_red", "timeout robots")

    monkeypatch.setattr(client, "_request", fail)
    with pytest.raises(FetchError):
        client.fetch("https://example.org/study")
    assert client.robots_log["https://example.org"]["error"] == "timeout robots"


def test_pipeline_offline_integrity_duplicates_and_isolated_failures(tmp_path):
    context = tmp_path / "context.md"
    context.write_text("Contexto de prueba", encoding="utf-8")
    sources = [{"source_id": sid, "url": f"https://example.org/{sid}", "nombre": sid, "tipo": "estudio"} for sid in ("one", "two", "bad")]

    def fetch(url):
        return download(status=404 if url.endswith("bad") else 200, url=url)

    client = SimpleNamespace(fetch=fetch, robots_log={})
    output = tmp_path / "run"
    manifest = run(sources, output, context, client)
    assert manifest["estados"] == {"extraido": 2, "error_http": 1}
    assert manifest["fuentes"][1]["duplicado_de"] == "one"
    assert manifest["fuentes"][0]["sha256"] == hashlib.sha256(HTML).hexdigest()
    offline = tmp_path / "offline"
    result = run(sources, offline, context, offline=output)
    assert result["estados"] == manifest["estados"]
    assert (offline / "evidencia.jsonl").read_bytes() == (output / "evidencia.jsonl").read_bytes()
    assert len((offline / "cobertura.csv").read_text(encoding="utf-8-sig").splitlines()) == 36
    (output / "raw/one.bin").write_bytes(b"alterado")
    result = run(sources, tmp_path / "corrupt", context, offline=output)
    assert result["fuentes"][0]["estado"] == "integridad_invalida"


def test_transport_capture_and_size_limit(monkeypatch):
    from scrapping.nasa_scraper import transport
    calls = []

    def fake_get(url, **kwargs):
        calls.append(kwargs)
        kwargs["content_callback"](b"hello")
        return SimpleNamespace(status=200, headers={"Content-Type": "text/html"}, encoding="utf-8")

    monkeypatch.setattr(transport.Fetcher, "get", fake_get)
    result = Client(delay=0)._request("https://example.org")
    assert result.body == b"hello"
    assert calls[0]["follow_redirects"] is False

    def too_large(url, **kwargs):
        assert kwargs["content_callback"](b"123456") == transport.CURL_WRITEFUNC_ERROR
        raise RuntimeError("write aborted")

    monkeypatch.setattr(transport.Fetcher, "get", too_large)
    with pytest.raises(FetchError) as error:
        Client(delay=0, max_bytes=5)._request("https://example.org")
    assert error.value.state == "limite_tamano"


@pytest.mark.parametrize("retry_after, expected_calls, expected_status", [("0", 2, 200), ("120", 1, 429)])
def test_retry_after_is_respected(monkeypatch, retry_after, expected_calls, expected_status):
    from scrapping.nasa_scraper import transport
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return SimpleNamespace(status=429 if len(calls) == 1 else 200,
                               headers={"Retry-After": retry_after}, encoding="utf-8")

    monkeypatch.setattr(transport.Fetcher, "get", get)
    result = Client(delay=0)._request("https://example.org")
    assert len(calls) == expected_calls
    assert result.metadata["http_status"] == expected_status


def test_offline_merge_uses_latest_source_response(tmp_path):
    context = tmp_path / "context.md"
    context.write_text("Context", encoding="utf-8")
    sources = [{"source_id": "one", "url": "https://example.org/one", "nombre": "one", "tipo": "estudio"}]
    first, second, merged = [tmp_path / name for name in ("first", "second", "merged")]
    run(sources, first, context, SimpleNamespace(fetch=lambda u: download(status=404), robots_log={}))
    run(sources, second, context, SimpleNamespace(fetch=lambda u: download(), robots_log={}))
    result = run(sources, merged, context, offline=[first, second])
    assert result["estados"] == {"extraido": 1}
    assert result["fuentes"][0]["ejecucion_original"] == str(second)


def test_legacy_lro_navigation_does_not_create_evidence():
    html = b'<table><tr><td><ul><li>Atacama permafrost</li></ul></td><td><h1>Diviner</h1><p>Lunar temperature products.</p><table><tr><td>Product</td><td>Coverage</td></tr></table></td></tr></table>'
    doc = extract_html(html, "https://pds-geosciences.wustl.edu/missions/lro/diviner.htm")
    assert not any("Atacama" in s["texto"] for s in doc["segmentos"])
    assert any("Product Coverage" == s["texto"] for s in doc["segmentos"])


def test_certificate_failure_is_specific_and_not_retried(monkeypatch):
    from scrapping.nasa_scraper import transport
    calls = []

    class CertificateError(Exception):
        code = 60

    def fail(url, **kwargs):
        calls.append(url)
        assert kwargs["verify"] is True
        raise CertificateError("missing issuer")

    monkeypatch.setattr(transport.Fetcher, "get", fail)
    with pytest.raises(FetchError) as error:
        Client(attempts=3, delay=0).fetch("https://example.org/data")
    assert error.value.state == "error_tls"
    assert error.value.details == {"curl_code": 60, "url_solicitud": "https://example.org/robots.txt", "fase": "robots", "reintentable": False}
    assert len(calls) == 1


def test_ca_bundle_preserves_verification(monkeypatch):
    from scrapping.nasa_scraper import transport

    def get(url, **kwargs):
        assert kwargs["verify"] == "trusted.pem"
        return SimpleNamespace(status=200, headers={}, encoding="utf-8")

    monkeypatch.setattr(transport.Fetcher, "get", get)
    result = Client(ca_bundle="trusted.pem")._request("https://example.org")
    assert result.metadata["tls_verificado"] is True


def test_robots_html_is_recorded_as_uninterpretable(monkeypatch):
    client = Client()
    monkeypatch.setattr(client, "_request", lambda url: download(b"<!doctype html><html><title>SPA</title></html>"))
    with pytest.raises(FetchError) as error:
        client.fetch("https://example.org")
    assert error.value.state == "robots_no_disponible"
    assert "<!doctype html>" in client.robots_log["https://example.org"]["respuesta_preview"]


def test_sampling_reaches_end_of_document_and_ignores_headings():
    doc = {"titulo": "Study", "segmentos": [{"texto": f"Dust observation number {i}", "pagina": i,
            "localizador": f"page {i}", "seccion": None} for i in range(1, 101)]}
    source = {"source_id": "test", "url": "https://example.org"}
    rows = evidence_rows(source, doc, max_fragments=20)
    assert len(rows) == 20
    assert rows[0]["pagina"] == 1 and rows[-1]["pagina"] == 100
    assert len(evidence_rows(source, doc, max_fragments=None)) == 100
    doc["segmentos"] = [{**doc["segmentos"][0], "tipo_segmento": "h1"}]
    assert evidence_rows(source, doc) == []


def test_jaxa_navigation_is_not_scientific_evidence():
    doc = extract_html(b'<main id="main"><div id="left_menus"><a href="/search">Physical quantities</a><a href="/csw">CSW / SFTP</a></div></main>', 'https://www.gportal.jaxa.jp/?lang=en')
    assert doc["estado"] == "portal_navegacion"
    assert doc["segmentos"][0]["texto"] == "Physical quantities"


def test_cambridge_and_github_ignore_site_navigation():
    for url, html in [
        ('https://www.cambridge.org/core/study', b'<p>Breadcrumb ice</p><div id="article-tab"><h2>Abstract</h2><p>Ice measurement in Antarctica.</p></div>'),
        ('https://github.com/org/repo', b'<main><p>Navigation ice</p><article class="markdown-body"><p>Real SAR tutorial.</p></article></main>'),
    ]:
        doc = extract_html(html, url)
        assert not any('Breadcrumb' in s['texto'] or 'Navigation' in s['texto'] for s in doc['segmentos'])


def test_analog_explorer_image_details_are_segments():
    html = b'''<main><h2>Basalt Landscapes: Kilauea and the Moon</h2><div class="image-details-panel">
    <button><span>Image Details</span></button><div class="image-details-wrapper">
    On the slopes of Kilauea, researchers characterize their surroundings.</div></div><div class="other">Ignored layout text</div></main>'''
    doc = extract_html(html, 'https://science.nasa.gov/solar-system/analog-explorer/')
    details = [s for s in doc['segmentos'] if 'slopes of Kilauea' in s['texto']]
    assert len(details) == 1
    assert details[0]['seccion'] == 'Basalt Landscapes: Kilauea and the Moon'
    assert not any('Ignored layout' in s['texto'] for s in doc['segmentos'])


def test_sampling_keeps_site_evidence_inside_document():
    segments = [{"texto": f"Dust observation number {i}", "pagina": i, "localizador": f"page {i}", "seccion": None}
                for i in range(1, 101)]
    segments[54]["texto"] = "Mojave dust observation with documented site context."
    rows = evidence_rows({"source_id": "test", "url": "https://example.org"}, {"titulo": "Study", "segmentos": segments}, 20)
    assert len(rows) == 20
    assert any("Mojave" in row["sitios_mencionados"] for row in rows)
    assert rows[0]["pagina"] == 1 and rows[-1]["pagina"] == 100


def test_offline_preserves_diagnostic_without_refetch(tmp_path):
    context = tmp_path / "context.md"
    context.write_text("Context", encoding="utf-8")
    sources = [{"source_id": "one", "url": "https://example.org/one", "nombre": "one", "tipo": "estudio"}]

    def fail(url):
        raise FetchError("error_tls", "issuer missing", fase="robots", curl_code=60)

    first, second = tmp_path / "first", tmp_path / "second"
    run(sources, first, context, SimpleNamespace(fetch=fail, robots_log={}))
    result = run(sources, second, context, offline=first)
    record = result["fuentes"][0]
    assert record["sin_cuerpo_local"] is True
    assert record["diagnostico"] == {"fase": "robots", "curl_code": 60}
    assert record["error"] == "issuer missing"


def test_analysis_counts_documents_without_claiming_science(tmp_path):
    from scrapping.nasa_scraper.analysis import analyze
    context = tmp_path / "context.md"
    context.write_text("Context", encoding="utf-8")
    sources = [{"source_id": "one", "url": "https://example.org/one", "nombre": "one", "tipo": "portal"}]
    directory = tmp_path / "result"
    run(sources, directory, context, SimpleNamespace(fetch=lambda url: download(), robots_log={}))
    report = analyze(directory)
    assert report["estados"] == {"extraido": 1}
    assert report["fuentes"][0]["caracteres_extraidos"] > 200
    assert report["fuentes"][0]["advertencias_interpretacion"]
    assert report["pasajes_exportados"] == report["fuentes"][0]["pasajes_exportados"]
