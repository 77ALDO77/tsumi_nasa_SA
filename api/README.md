# API de lectura (FastAPI)

Sirve al frontend las métricas que `analisis.cargar` dejó en PostgreSQL. No calcula nada. Tampoco ordena candidatos: para eso faltan la envolvente de referencia y la línea base, que deben fijarse antes en el preregistro (ver [concepts_brief.md](../concepts_brief.md)).

```bash
uv pip install -r api/requirements.txt
DATABASE_URL=postgresql://... uvicorn api.main:app --host 127.0.0.1 --port 8000   # documentación en /docs
python -m pytest -q api/tests        # la prueba con base de datos se omite si falta TEST_DATABASE_URL
```

| Endpoint | Devuelve |
|---|---|
| `GET /` → `/app/` | Página del mapa (`api/static/index.html`): Leaflet, selector de referencia lunar y de escala, una ficha por sitio y los límites de la analogía |
| `GET /salud` | Estado de la base y versión de PostGIS |
| `GET /ventanas?cuerpo=tierra\|luna\|marte&res_m=60` | Ventanas con sus métricas |
| `GET /mapa/tierra?res_m=60` | GeoJSON (EPSG:4326) con la huella de cada ventana terrestre y sus métricas, listo para Leaflet o MapLibre |
| `GET /comparacion/{referencia}?res_m=60` | Diferencias por variable entre cada ventana terrestre y la referencia lunar o marciana, en sus unidades. Incluye una descripción generada solo a partir de esas cifras, los límites de la analogía para ese cuerpo y un descargo |

Parámetros comunes:
- `version`: versión del método; por defecto `relieve-v2-aeqd-average-horn-ldec`.
- `res_m`: escala de cálculo, 60 o 120.

Entorno:
- `DATABASE_URL`: conexión a la base. Si no responde en 5 s, la API devuelve `503`.
- `ALLOWED_ORIGINS`: orígenes permitidos para CORS, separados por comas. Sin él no se habilita CORS.

Reglas de la API:
- **No calcula puntuaciones ni porcentajes de analogía.** Solo devuelve diferencias, sin ranking.
- **La descripción no lleva texto libre.** Se arma únicamente con los valores calculados.
- **Las ventanas sin dato aparecen como `sin_dato`, nunca como cero.**
