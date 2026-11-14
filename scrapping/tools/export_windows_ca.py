"""Exporta certificados públicos ya confiados por Windows, sin modificar el sistema.

Ejecutar desde la raíz: python -m scrapping.tools.export_windows_ca
El bundle es local a este equipo. No contiene claves privadas.
"""
import hashlib
import json
import ssl
import sys
from datetime import datetime, timezone
from pathlib import Path

import certifi


def main():
    if sys.platform != "win32":
        raise SystemExit("Este exportador requiere Windows; usa un PEM confiable del sistema en otras plataformas.")
    output = Path(__file__).resolve().parents[1] / "certs/windows-ca.pem"
    output.parent.mkdir(exist_ok=True)
    pem = Path(certifi.where()).read_text(encoding="ascii")
    seen = set()
    for store in ("ROOT", "CA"):
        for certificate, encoding, trust in ssl.enum_certificates(store):
            if encoding != "x509_asn" or not (trust is True or ssl.Purpose.SERVER_AUTH.oid in trust):
                continue
            digest = hashlib.sha256(certificate).hexdigest()
            if digest not in seen:
                pem += "\n" + ssl.DER_cert_to_PEM_cert(certificate)
                seen.add(digest)
    output.write_text(pem, encoding="ascii")
    output.with_suffix(".json").write_text(json.dumps({
        "origen": "certifi + almacenes ROOT/CA de Windows (SERVER_AUTH)",
        "exportado_utc": datetime.now(timezone.utc).isoformat(),
        "certificados_windows": len(seen), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Bundle local: {output}; certificados Windows: {len(seen)}")


if __name__ == "__main__":
    main()
