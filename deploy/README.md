# Despliegue en el servidor Debian

Requisitos previos (ya hechos): PostgreSQL 17 + PostGIS 3.5, base y rol `tsumi`, acceso solo por `127.0.0.1`.

```bash
# En el servidor, como aldo (las rutas de los .service asumen /home/aldo/tsumi_nasa_SA)
git clone <repo> ~/tsumi_nasa_SA && cd ~/tsumi_nasa_SA
python3 -m venv .venv && .venv/bin/pip install -r analisis/requirements.txt -r api/requirements.txt
mkdir -p secretos && chmod 700 secretos
echo 'DATABASE_URL=postgresql://tsumi:<clave>@127.0.0.1:5432/tsumi' > secretos/.env && chmod 600 secretos/.env

export $(cat secretos/.env)   # una vez, para preparar la búsqueda
.venv/bin/python -m analisis.trabajador analisis/inputs/busqueda.json referencias
.venv/bin/python -m analisis.trabajador analisis/inputs/busqueda.json encolar

sudo cp deploy/tsumi-*.service /etc/systemd/system/ && sudo systemctl daemon-reload
sudo systemctl enable --now tsumi-trabajador tsumi-api
```

Seguimiento (logs JSON, una línea por evento):

```bash
journalctl -u tsumi-trabajador -f -o cat | jq -c '{ts, evento, celda, estado, duracion_s}'
journalctl -u tsumi-trabajador -o cat | jq 'select(.nivel == "error")'
journalctl -u tsumi-api -f -o cat | jq -c 'select(.evento == "peticion") | {ruta, estado, duracion_ms}'
curl -s 127.0.0.1:8000/busqueda/estado | jq      # avance de la cola
```

| Evento | Servicio | Campos clave |
|---|---|---|
| `inicio` | trabajador | `accion`, `config_sha256`, `version_metodo` |
| `celda_tomada` / `celda_terminada` | trabajador | `celda`, `n_validas`, `lectura_s`, `metricas_s`, `insercion_s`, `duracion_s` |
| `fuente_leida` | trabajador | `url`, `estado`, `apertura_s`, `lectura_s` |
| `celda_fallida` | trabajador | `celda`, `intentos`, `error`, `excepcion`. Tras 3 intentos la celda queda en `error` |
| `celdas_recuperadas` | trabajador | Celdas `en_curso` de un trabajador caído, devueltas a la cola |
| `cola_vacia` / `trabajador_detenido` | trabajador | Espera entre revisiones de la cola / excepción que detuvo el proceso |
| `peticion` / `peticion_fallida` / `base_no_disponible` | api | `metodo`, `ruta`, `estado`, `duracion_ms` |

Para añadir zonas de búsqueda, edita `zonas` en `analisis/inputs/busqueda.json` y vuelve a ejecutar `encolar`. El trabajador las toma por prioridad sin reiniciarse. Los logs nunca incluyen `DATABASE_URL`.
