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
uv pip install -r analisis/requirements.txt        # numpy, rasterio/GDAL, psycopg, httpx, pyhdf/HDF4
python -m pytest -q analisis/tests                 # 25 pruebas sin red
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

## Búsqueda continua (`python -m analisis.trabajador`)

Cómo funciona:
- **Referencia.** Cada región lunar de 15 km se divide en 25 subventanas de 3 km, y su rango P10–P90 por variable forma la envolvente.
- **Cola.** El trabajador toma celdas de 1° de la cola `celdas_busqueda`, por prioridad, y lee el relieve una sola vez.
- **Reposición.** Con `auto_encolar` repone lotes de 24 cuando hay menos de 6 pendientes.
  Prioriza las zonas explícitas y luego recorre la malla terrestre de 1°. Solo añade celdas
  con algún píxel MODIS que tenga NDVI ≤0,3 válido en ambos meses. No valida toda el área;
  excluye muchos ambientes vegetados, con nieve o con datos insuficientes. La acción `encolar`
  también respeta el lote y este filtro cuando está habilitado el modo automático.
- **Actividad.** Cada reserva y cada espera actualiza `trabajadores`. Una reserva de más de
  una hora se recupera durante el bucle, respetando un máximo de tres intentos.
- **Teselas.** Divide cada celda en teselas de 3 km a 60 y 120 m y guarda sus métricas en `teselas`.
- **Comparación.** Se hace en SQL al consultar la API (`/analogos`, `/coherencia`).
- **Contexto NASA.** La acción `contexto` prepara MOD13C2 (NDVI) y MOD11C3 (LST)
  con QA y SHA-256 de los HDF4, y muestrea todas las teselas existentes. El trabajador
  necesita ese contexto antes de procesar nuevas celdas.
- **Catálogo precalculado.** El trabajador mantiene `candidatos` tras cada celda, cambio de
  referencia o contexto. `/api/sites` lee las zonas derivadas de este ranking (ver «Zonas»).
  Exige 3/3 dentro y NDVI máximo ≤0,3 con dato válido en todos los meses seleccionados.
  Es un filtro exploratorio, no un umbral NASA ni prueba de ausencia de vegetación.
- **Zonas.** En la misma transacción que el ranking, las candidatas se agrupan por la distancia
  entre los centros de sus teselas: a ≤6 km se unen, encadenando vecinas (`agrupacion` en
  `busqueda.json`). Con 3 o más teselas forman una zona; si no, son candidatas aisladas. Cada
  zona guarda su mejor tesela, recuadro, área de las teselas que cumplen, referencias y si
  alguna tesela está a ≤50 km de un análogo NASA registrado. El valor se eligió con las 590
  candidatas reales disponibles: la vecina típica está a 3–4,25 km y con 10 km se formaban
  franjas de 75 km. Agrupar no valida la zona: solo evita contar como lugares distintos
  teselas pegadas.
- **Nombres y fuentes.** La acción `catalogo` completa los sitios existentes desde
  `inputs/mvp0.json`, verificando sus coordenadas y sin recalcular métricas.
- **Variables que puntúan.** Pendiente mediana, pendiente P90 y relieve. La rugosidad no puntúa porque está correlacionada con el relieve.

La configuración y las predicciones registradas antes del cálculo están en `inputs/busqueda.json`. El despliegue y los logs, en [deploy/README.md](../deploy/README.md).

La política MODIS, limitaciones y actualización segura están en
[deploy/README.md](../deploy/README.md#qué-significa-el-contexto-nasa).
Enero/julio de 2025 no constituyen una climatología ni extremos anuales; su píxel de
0,05° es contexto del centro de la tesela, no detalle de 3 km. No se puntúa analogía térmica.

La selección calculada con la caché QA actual contiene 4.145 celdas, incluidas las 27 iniciales.
Es un dominio finito: cuando todas están recorridas, el trabajador espera y el estado lo indica.
No se actualizan automáticamente los meses de MODIS ni se prometen descubrimientos infinitos.

Primera ejecución local, 2026-11-15, con las celdas N35W111, N35W112 y N43W103:
- **Tasa base:** de 0 % a 2,1 % de teselas con 3/3.
- **P2 se cumple:** el control N43W103 tiene 0 %, frente a un 0,2–2,1 % en Arizona.
- **P1 se cumple a medias:** SP Crater queda en el percentil 0,85–0,98, pero Cinder Lake en el 0,19–0,31. El punto GNIS de Cinder Lake es de clase *Flat* (el fondo del lago), no el campo de cráteres. No se corrigió después de ver el resultado.
- **Tiempo por celda:** de 60 a 85 s, casi todo lectura de red (CPU ~5 s).
- **Causa de las demoras de ~10 min (hallada con los logs `fuente_leida`).** Una sola petición HTTP estancada: la tesela `N36_W112` tardó 271 s en abrirse y 197 s en leerse, y en la celda siguiente 5 s.
- **Corrección en `fuentes.py`.** Límites de GDAL: conexión 15 s, corte si baja de 10 KB/s durante 30 s, 3 reintentos. Solo un `404` se trata como tesela inexistente (océano); cualquier otro error hace fallar la celda, que vuelve a la cola. Comprobado con una conexión estancada simulada, que corta en 3 s.
