"""Logs estructurados: una línea JSON por evento en stdout (en el servidor los recoge journald).

Uso: log = configurar("trabajador"); evento(log, "celda_hecha", celda="N35W112", duracion_s=63.1)
Consulta: journalctl -u tsumi-trabajador -o cat | jq 'select(.evento == "celda_hecha")'
Nunca pases credenciales (DATABASE_URL, tokens) como campos.
"""
import json
import logging
import sys
from datetime import datetime, timezone


class FormatoJSON(logging.Formatter):
    def format(self, record):
        data = {"ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
                "nivel": record.levelname.lower(), "servicio": record.name, "evento": record.getMessage(),
                **getattr(record, "campos", {})}
        if record.exc_info:
            data["excepcion"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False, default=str)


def configurar(servicio: str) -> logging.Logger:
    log = logging.getLogger(servicio)
    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(FormatoJSON())
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False
    return log


def evento(log: logging.Logger, nombre: str, nivel=logging.INFO, exc_info=None, **campos):
    log.log(nivel, nombre, exc_info=exc_info, extra={"campos": campos})
