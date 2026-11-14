"""HTTP público con Scrapling, robots, límites y redirecciones comprobadas."""

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit

from curl_cffi.curl import CURL_WRITEFUNC_ERROR
from protego import Protego
from scrapling.fetchers import Fetcher

from .sources import normalize_url

USER_AGENT = "AnalogEvidenceBot/0.1"
REDIRECTS = {301, 302, 303, 307, 308}


def now():
    return datetime.now(timezone.utc).isoformat()


class FetchError(Exception):
    def __init__(self, state, message, **details):
        super().__init__(message)
        self.state = state
        self.details = details


@dataclass
class Download:
    body: bytes
    metadata: dict


class Client:
    def __init__(self, timeout=60, delay=1, attempts=2, max_bytes=25 * 1024 * 1024, ca_bundle=None):
        self.timeout, self.delay, self.attempts, self.max_bytes = timeout, delay, attempts, max_bytes
        self.verify = str(ca_bundle) if ca_bundle else True
        self.robots = {}
        self.robots_log = {}
        self.last_request = {}
        self.delays = {}

    def _request(self, url):
        origin = "{0.scheme}://{0.netloc}".format(urlsplit(url))
        for attempt in range(self.attempts):
            pause = self.delays.get(origin, self.delay) - (time.monotonic() - self.last_request.get(origin, 0))
            if pause > 0:
                time.sleep(pause)
            chunks, size = [], 0

            def receive(chunk):
                nonlocal size
                size += len(chunk)
                if size > self.max_bytes:
                    return CURL_WRITEFUNC_ERROR  # Aborta también en el wrapper curl_cffi.
                chunks.append(chunk)
                return len(chunk)

            try:
                response = Fetcher.get(url, timeout=self.timeout, retries=1, follow_redirects=False,
                                       impersonate=None, stealthy_headers=False,
                                       verify=self.verify,
                                       headers={"User-Agent": USER_AGENT}, content_callback=receive)
            except Exception as exc:
                if size > self.max_bytes:
                    raise FetchError("limite_tamano", f"Supera {self.max_bytes} bytes: {url}") from exc
                code = getattr(exc, "code", None)
                if code in {51, 58, 60, 77, 83, 90, 91}:
                    raise FetchError("error_tls", str(exc), curl_code=int(code), url_solicitud=url,
                                     fase="descarga", reintentable=False) from exc
                if attempt + 1 == self.attempts:
                    state = "timeout" if code == 28 else "error_red"
                    raise FetchError(state, str(exc), curl_code=int(code) if code is not None else None,
                                     url_solicitud=url, fase="descarga", reintentable=True) from exc
                time.sleep(2 ** attempt)
                continue
            finally:
                self.last_request[origin] = time.monotonic()
            headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
            if response.status in {429, 500, 502, 503, 504} and attempt + 1 < self.attempts:
                retry = headers.get("retry-after", "")
                try:
                    wait = float(retry) if retry.isdigit() else (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds()
                except (ValueError, TypeError):
                    wait = 2 ** attempt
                if wait <= 30:
                    time.sleep(max(0, wait))
                    continue
            return Download(b"".join(chunks), {"url_final": url, "http_status": response.status,
                                             "tls_verificado": True, "ca_bundle": self.verify if isinstance(self.verify, str) else "certifi",
                                             "content_type": headers.get("content-type", ""),
                                             "encoding": response.encoding, "headers": {k: v for k, v in headers.items()
                                             if k in {"content-type", "last-modified", "etag", "location", "retry-after"}},
                                             "fecha_consulta_utc": now()})
        raise FetchError("error_red", "No se obtuvo respuesta")

    def check_robots(self, url):
        origin = "{0.scheme}://{0.netloc}".format(urlsplit(url))
        if origin not in self.robots:
            robots_url = origin + "/robots.txt"
            record = {"url": robots_url, "fecha_consulta_utc": now()}
            try:
                for _ in range(6):
                    result = self._request(robots_url)
                    if result.metadata["http_status"] not in REDIRECTS:
                        break
                    robots_url = normalize_url(urljoin(robots_url, result.metadata["headers"].get("location", "")))
                else:
                    raise FetchError("robots_no_disponible", "Demasiadas redirecciones de robots.txt")
                status = result.metadata["http_status"]
                record.update(result.metadata)
                text = result.body.decode("utf-8", errors="replace")
                record["respuesta_preview"] = text[:500]
                if status in {404, 410}:
                    text = ""
                elif status in {401, 403}:
                    text = "User-agent: *\nDisallow: /"
                elif status != 200 or "<html" in text[:1000].lower() or "<!doctype html" in text[:1000].lower():
                    raise FetchError("robots_no_disponible", f"robots.txt no interpretable (HTTP {status})")
                parser = Protego.parse(text)
                record["texto"] = text
                self.robots[origin] = parser
                rate = parser.request_rate(USER_AGENT)
                self.delays[origin] = max(self.delay, parser.crawl_delay(USER_AGENT) or 0,
                                         rate.seconds / rate.requests if rate and rate.requests else 0)
            except FetchError as exc:
                exc.details.update({"fase": "robots", "url_solicitud": robots_url})
                self.robots[origin] = exc
                record.update({"estado": exc.state, "error": str(exc), "diagnostico": exc.details})
            self.robots_log[origin] = record
        parser = self.robots[origin]
        if isinstance(parser, FetchError):
            raise parser
        if not parser.can_fetch(url, USER_AGENT):
            raise FetchError("excluido_por_robots", f"robots.txt no permite: {url}")

    def fetch(self, url):
        redirects = []
        for _ in range(6):
            self.check_robots(url)
            result = self._request(url)
            if result.metadata["http_status"] not in REDIRECTS:
                result.metadata["redirecciones"] = redirects
                return result
            location = result.metadata["headers"].get("location")
            if not location:
                raise FetchError("error_redireccion", "Redirección sin Location")
            redirects.append(url)
            url = normalize_url(urljoin(url, location))
        raise FetchError("error_redireccion", "Más de cinco redirecciones")
