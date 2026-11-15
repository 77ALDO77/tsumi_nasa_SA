# API de lectura (FastAPI)

Sirve al frontend las métricas que `analisis.cargar` dejó en PostgreSQL. No lee rásteres: solo consulta la base. `/analogos` ordena las teselas con la envolvente de la referencia (función SQL `dist_envolvente`); `/comparacion` solo da diferencias, sin orden. Registra cada petición como una línea JSON (ver [deploy/README.md](../deploy/README.md)).

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
| `GET /busqueda/estado` | Avance de la cola del trabajador: celdas por estado, teselas procesadas, última actualización y errores |
| `GET /referencias?res_m=60` | Regiones de referencia con su envolvente P10–P90 |
| `GET /analogos/{referencia}?res_m=60&limite=100&minimo_dentro=3` | GeoJSON de teselas de 3 km ordenadas por cercanía a la envolvente: primero las que tienen más variables dentro y, a igualdad, la menor distancia. `metadata.tasa_base` indica qué fracción de todas las teselas cae dentro; si es alta, coincidir no distingue |
| `GET /coherencia/{referencia}?res_m=60` | Percentil de la tesela que contiene cada sitio terrestre registrado (análogos NASA y controles) |
| `GET /comparacion/{referencia}?res_m=60` | Diferencias por variable entre cada ventana terrestre y la referencia lunar o marciana, en sus unidades. Incluye una descripción generada solo a partir de esas cifras, los límites de la analogía para ese cuerpo y un descargo |

Parámetros comunes:
- `version`: versión del método; por defecto `relieve-v2-aeqd-average-horn-ldec`.
- `res_m`: escala de cálculo, 60 o 120.

Entorno:
- `DATABASE_URL`: conexión a la base. Si no responde en 5 s, la API devuelve `503`.
- `ALLOWED_ORIGINS`: orígenes permitidos para CORS, separados por comas. Sin él no se habilita CORS.

Reglas de la API:
- **No calcula puntuaciones ni porcentajes de analogía.** Ordena por cuántas variables caen dentro de la envolvente y por su distancia en anchos de envolvente, y siempre informa la tasa base.
- **La descripción no lleva texto libre.** Se arma únicamente con los valores calculados.
- **Las ventanas sin dato aparecen como `sin_dato`, nunca como cero.**
