# Análisis de relieve por ventanas (MVP 0)

Calcula las métricas de [docs/VARIABLES_PROTOTIPO.md](../docs/VARIABLES_PROTOTIPO.md) con el mismo método para la Luna y para la Tierra:
- pendiente mediana y P90, en grados;
- relieve P95–P5, en m;
- RMS respecto del plano, en m.

Cada ventana se lee por HTTP con lecturas parciales (GDAL `/vsicurl/`), sin descargar el producto completo. Después se reproyecta a una proyección equidistante (`aeqd`) centrada en la ventana y se promedia a la resolución común (`average`, sin interpolar).

| Cuerpo | Producto | Notas |
|---|---|---|
| Luna | LOLA GDR polar `ldem_80s_40m_float` (PDS Geosciences) | Alturas en km sobre una esfera de 1737,4 km; se convierten a m. Cubre de 80° S al polo |
| Tierra | Copernicus GLO-30 COG (AWS, sin cuenta) | Es un modelo de superficie. Lee varias teselas si la ventana cruza bordes |

```bash
uv pip install -r analisis/requirements.txt        # numpy, rasterio (trae GDAL)
python -m pytest -q analisis/tests                 # 4 pruebas sin red
python -m analisis analisis/inputs/mvp0.json --salida analisis/data/<carpeta-nueva> [--solo LUN-SHACKLETON]
```

La salida queda en `analisis/data/`, que está excluida de Git:
- `manifest.json`: configuración y su SHA256, commit, URL y ventana leída de cada fuente, SHA256 de los valores leídos, CRS de cálculo, métricas y límites;
- `metricas.csv`;
- `ventanas/<id>.tif`: alturas en m a la resolución común;
- `ventanas/<id>.png`: sombreado con iluminación artificial, solo para inspección.

## Carga en PostgreSQL

```bash
DATABASE_URL=postgresql://usuario:clave@host:puerto/base python -m analisis.cargar analisis/data/<carpeta>
```

- **Requisitos:** PostgreSQL 15 o posterior (el servidor del equipo tiene la 17) con PostGIS.
- **Migraciones:** el cargador aplica las de `db/migraciones/*.sql` en orden. Son idempotentes.
- **Idempotencia:** volver a cargar no duplica nada. Si una métrica ya existe con otro valor, la carga falla. Si cambias el cálculo, sube `VERSION_METODO` en `metricas.py`.
- **Geometría:** solo las ventanas terrestres llevan geometría PostGIS. Las lunares guardan su CRS de cálculo como texto.
- **Credenciales:** `DATABASE_URL` va en `secretos/.env` o en el entorno, nunca en el código.

Código de salida `2` si alguna ventana no se pudo calcular. En Windows, si GDAL falla por TLS, define `GDAL_CURL_CA_BUNDLE` con un PEM validado; nunca desactives la verificación.

**Método v2 (`relieve-v2-aeqd-average-horn-ldec`).**
- **Máscara LOLA.** Los píxeles sin disparos láser según `ldec_80s_40m` se excluyen antes de promediar. La fracción medida queda en la procedencia: 0,99 en Shackleton, 0,97 en Malapert y 0,90 en Mons Mouton Plateau.
- **Escalas.** Cada fuente se lee una vez y se calcula a las escalas de `escalas_m` (60 y 120 m). Ninguna se elige después de ver los resultados.
- **Ventanas.** En el manifiesto hay una entrada por ventana y escala, y los archivos se llaman `<id>_<res>m.tif`.

**`TIE-SFVF` no es un sitio de ensayo.** Su coordenada GVP cae a 80 m de la cumbre de Humphreys Peak (USGS GNIS 30290). Los sitios de ensayo NASA son Cinder Lake y SP Crater.

**Comprobación de orientación (2026-11-15).** En la ventana de 15 km centrada en Shackleton (89,67° S, 129,78° E), el centro queda 3,1 km por debajo del borde. El CRS escrito a mano y el que construye GDAL a partir de la etiqueta asignan los mismos píxeles.

Estas cifras son una inspección de datos, no una prueba de coherencia con NASA. La regla de coincidencia y la línea base se fijan en el preregistro ([concepts_brief.md](../concepts_brief.md)).
