import argparse
from datetime import datetime, timezone
from pathlib import Path

from .pipeline import run
from .sources import load_sources
from .transport import Client

ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = ROOT.parent


def main():
    parser = argparse.ArgumentParser(description="Scraping documental NASA con Scrapling; extracción no equivale a validación científica.")
    parser.add_argument("--inventory", type=Path, default=ROOT / "inputs/extraccion_fuentes.json")
    parser.add_argument("--context", type=Path, default=PROJECT_ROOT / "CONTEXTO_RETO.md")
    parser.add_argument("--resources", type=Path, default=PROJECT_ROOT / "resources.txt")
    parser.add_argument("--list", action="store_true", help="Lista el inventario sin usar la red")
    parser.add_argument("--source", action="append", default=[], help="ID exacto o nombre (se puede repetir)")
    parser.add_argument("--output", type=Path, help="Carpeta NUEVA de salida")
    parser.add_argument("--offline", type=Path, action="append", help="Reprocesa respuestas sin red; repetible, la última ejecución prevalece por fuente")
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--delay", type=float, default=1)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--ca-bundle", type=Path, help="Archivo PEM de autoridades confiables; TLS permanece activado")
    args = parser.parse_args()
    if args.timeout <= 0 or args.delay < 0 or not 1 <= args.attempts <= 3:
        parser.error("timeout > 0, delay >= 0 y attempts entre 1 y 3")
    if args.ca_bundle and not args.ca_bundle.is_file():
        parser.error("--ca-bundle debe indicar un archivo PEM existente")
    try:
        sources = load_sources(args.inventory, args.context, args.resources)
        if args.source:
            requested = {name.casefold() for name in args.source}
            found = {name.casefold() for source in sources for name in (source["source_id"], source["nombre"]) if name.casefold() in requested}
            if requested - found:
                parser.error(f"Fuentes desconocidas: {', '.join(sorted(requested - found))}. Usa --list.")
            sources = [s for s in sources if {s["source_id"].casefold(), s["nombre"].casefold()} & requested]
        if args.list:
            for source in sources:
                print(f"{source['source_id']}  {source['nombre']}  {source['url']}")
            return 0
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output = args.output or ROOT / "data" / stamp
        result = run(sources, output, args.context, Client(args.timeout, args.delay, args.attempts,
                                                        ca_bundle=args.ca_bundle), args.offline)
    except (ValueError, OSError, KeyError) as exc:
        parser.error(str(exc))
    print(f"Resultado: {output.resolve()}")
    print(result["estados"])
    # 2 = ejecución parcial, conservando resultados y motivos por fuente.
    return 0 if all(r["estado"] == "extraido" for r in result["fuentes"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
