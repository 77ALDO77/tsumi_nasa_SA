# Despliegue en el servidor (Docker + nginx del host)

```
Internet ──443──► nginx del host (TLS, sitio nasa.azzu.tech; convive con azzu.tech y keycloak)
                     └─► 127.0.0.1:8080  contenedor web (nginx): /  landing · /atlas/  TSUMI Atlas · /api/ → api
                    contenedor api (uv, uvicorn 127.0.0.1:8000, rol de solo lectura)
                    contenedor trabajador (uv, búsqueda continua) ──► PostgreSQL 17 + PostGIS del host (127.0.0.1:5432)
```

Los tres contenedores usan la red del host y solo escuchan en `127.0.0.1`. Desde internet solo se ve `nasa.azzu.tech`, a través del nginx del host. PostgreSQL y `pg_hba.conf` no cambian. Las imágenes se construyen con **bun** (landing y atlas) y con **uv** (Python), y nunca incluyen `secretos/` (ver `.dockerignore`).

## Estructura en el servidor

```
/home/aldo/nasa/
├── tsumi_nasa_SA/        (este repo: deploy/compose.yaml, secretos/)
├── nasa-azzu-front/      (atlas; se compila con --base /atlas/ y VITE_API_BASE_URL=/api, sin tocar el repo)
└── nasa-azzu-landing/    (landing)
```

Las carpetas tienen que llamarse exactamente así: `compose.yaml` las encuentra por ruta relativa.

## Primera vez

```bash
cd /home/aldo/nasa/tsumi_nasa_SA
mkdir -p secretos && chmod 700 secretos
# Rol de escritura (trabajador). Formato NOMBRE=valor, una línea.
echo 'DATABASE_URL=postgresql://tsumi:<clave>@127.0.0.1:5432/tsumi' > secretos/.env
# Añadir EARTHDATA_TOKEN=<token de NASA Earthdata> al archivo de escritura, sin imprimirlo.
# Solo formato NOMBRE=valor; no NOMBRE:valor. Nunca añadirlo a secretos/api.env.
# Rol de solo lectura (API expuesta a internet).
sudo -u postgres createuser --pwprompt tsumi_lectura
sudo -u postgres psql -d tsumi -c "GRANT CONNECT ON DATABASE tsumi TO tsumi_lectura; GRANT USAGE ON SCHEMA public TO tsumi_lectura; GRANT SELECT ON ALL TABLES IN SCHEMA public TO tsumi_lectura; ALTER DEFAULT PRIVILEGES FOR ROLE tsumi IN SCHEMA public GRANT SELECT ON TABLES TO tsumi_lectura;"
echo 'DATABASE_URL=postgresql://tsumi_lectura:<clave>@127.0.0.1:5432/tsumi' > secretos/api.env
chmod 600 secretos/*.env

cd deploy
docker compose build
R="docker compose run --rm -T trabajador python -m analisis.trabajador analisis/inputs/busqueda.json"
$R referencias      # envolventes lunares (P10, P50, P90); aplica las migraciones
$R contexto         # descarga MODIS, prepara caché con QA, rellena teselas existentes y reconstruye candidatos
$R encolar          # celdas de las zonas de analisis/inputs/busqueda.json
docker compose up -d
```

Opcional: para que el catálogo muestre los nombres de los sitios NASA, carga el manifiesto de inspección (`python -m analisis.cargar analisis/data/<carpeta>`, con el rol `tsumi`).

## nginx del host y HTTPS (requiere el registro DNS A `nasa` → `2.25.252.196` en Hostinger)

```bash
dig +short nasa.azzu.tech                     # debe responder 2.25.252.196
sudo cp deploy/nginx-host.conf /etc/nginx/sites-available/nasa.azzu.tech
sudo ln -s ../sites-available/nasa.azzu.tech /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx  # nginx -t primero: el nginx es compartido
sudo certbot --nginx -d nasa.azzu.tech        # añade 443 y la redirección 80 → 443
```

## Actualizar

```bash
cd /home/aldo/nasa/<repo que cambió> && git pull
cd /home/aldo/nasa/tsumi_nasa_SA/deploy && docker compose up -d --build
```

### Actualización a MODIS y ranking precalculado (migración 004)

El procedimiento genérico anterior no basta para esta actualización: aplicar la migración
y rellenar el contexto **antes de arrancar la nueva API**. Ejecutar con autorización del equipo:

```bash
cd /home/aldo/nasa/tsumi_nasa_SA/deploy
docker compose stop trabajador api
docker compose build api
docker compose run --rm --no-deps -T trabajador python -m analisis.trabajador analisis/inputs/busqueda.json contexto
docker compose up -d api trabajador
```

La acción `contexto` usa `EARTHDATA_TOKEN` solo si necesita descargar HDF4. Los granulos y la
caché con QA viven en el volumen `tsumi_modis` (no usar `docker compose down -v`).
La API no necesita el token ni montar el volumen: lee los valores, la procedencia y el ranking de PostgreSQL.
El directorio del volumen se inicializa con permisos del usuario no privilegiado `tsumi`.
Se conserva la caché anterior sin QA, pero no se lee: el nuevo nombre empieza por `modis-qa-v2`.

`contexto` vuelve a muestrear **todas** las teselas, incluso las que ya tenían datos, y publica
valores, identidad del contexto, umbral y candidatos en una única transacción. Si falla,
no publica una actualización parcial. Repetir este procedimiento si cambian los meses,
la política QA o el umbral; reiniciar todos los trabajadores para no mezclar configuraciones.
Si se recalculan referencias, la acción `referencias` las publica junto a su nuevo ranking.
Los reemplazos del ranking se serializan entre trabajadores, y eliminan candidatos obsoletos.

La migración no recalcula el terreno ni modifica las celdas ya procesadas. No se debe
confundir contexto global MODIS con cobertura global de relieve.

### Zonas por cuerpo y ubicación administrativa (migraciones 008 y 009)

008 separa las zonas por cuerpo: antes, teselas lunares y marcianas cercanas formaban zonas mixtas.
Vacía la tabla derivada; el trabajador la rellena al terminar la siguiente celda.

009 crea `ubicaciones`: país, provincia y distrito por coordenada redondeada a 0,01°, consultados por
el trabajador en OpenStreetMap/Nominatim (`ubicacion` en `busqueda.json`): 2 consultas por celda y 20
cuando la cola está vacía, con agente propio, ≤1 consulta/s y caché permanente (política de Nominatim).
Los errores de red se reintentan al día siguiente. La API solo lee la caché y cita © OpenStreetMap.

### Referencias marcianas (migración 007)

Añade a `referencias` la banda (`p10-p90` o `p25-p75`), `buscar` y la fuente del DEM, y adapta la
vista de comparación sin cambiar sus columnas. Tras desplegar, ejecutar `referencias` con el mismo
comando del trabajador: lee LOLA y los DEM de Marte de USGS (unos minutos) y reconstruye
candidatos y zonas. El terreno terrestre no se recalcula. El DEM de Gale se lee desde su `.ovr`
externo: solo para esa apertura se permite a GDAL listar el directorio remoto.

### Zonas de candidatas (migración 006)

La tabla `zonas_candidatas` se llena sola al terminar la siguiente celda: no hace falta
recalcular el terreno. Para rellenarla sin esperar, basta `referencias` o `contexto`, que
también reconstruyen el ranking. El API solo la lee, con los permisos por defecto de `tsumi_lectura`.

### Búsqueda por lotes y actividad (migración 005)

El mismo trabajador repone la cola: lotes de 24 si quedan menos de 6 pendientes, sin reabrir
celdas hechas o con tres fallos. Harrat Khaybar, Tibesti y Namib tienen prioridad antes de
la exploración ampliada. Se recorre una selección **finita**, condicionada a disponer de
NDVI bajo y suficiente: la caché actual selecciona 4.145 celdas. No es cobertura completa
de todos los ambientes terrestres ni actualización automática de la serie MODIS.

Después de `contexto`, ejecutar `catalogo` con el mismo comando del trabajador para completar
nombres, roles y fuentes de los sitios existentes. `bucle` también lo verifica al arrancar.
No ejecutar una carga masiva de todas las coordenadas para mantener ocupada la cola.

`GET /api/search/status` muestra estado, cola, candidatos y señales del trabajador. El atlas
consulta cada 30 s; el trabajador avisa antes de procesar y cada 60 s cuando espera.
Una señal de más de cinco minutos se muestra como antigua, **no** como prueba de que murió
(una lectura HTTP puede seguir en curso). Las reservas de más de una hora se recuperan
respetando el máximo de tres intentos. Los errores definitivos requieren revisión.

Límites iniciales de los contenedores: trabajador 1 CPU/3 GiB, API 0,5 CPU/512 MiB y web
0,25 CPU/128 MiB. Un solo trabajador al principio; medir el pico con MODIS antes de escalar.
OpenBLAS, OpenMP y GDAL se limitan a un hilo en el trabajador.

Actualizar primero la imagen Python y preparar `contexto`/`catalogo`, luego arrancar API y
trabajador, y por último recrear web. Conservar una copia privada de la base y las imágenes
anteriores para poder volver atrás. El nginx del host y los otros sitios no necesitan cambios.

## Qué significa el contexto NASA

- **MOD13C2.061:** NDVI mensual. Se aceptan rango válido, `pixel reliability=0` (excluye
  relleno histórico=4), bits VI 0–1=0, sin nube adyacente/mixta y tierra (bits 11–13=1).
  La [guía C61, §8.3.2 y §9.3.2](https://modis-land.gsfc.nasa.gov/pdf/MOD13_User_Guide_V61.pdf)
  prevalece para estos bits sobre la especificación HTML antigua de CMG, que describe otra distribución.
- **MOD11C3.061:** LST diurna/nocturna mensual. Se aceptan rango válido, QC 0–1≤1
  (producida, buena u otra calidad) y bits 6–7≤1 (error medio declarado ≤2 K).
  No se interpreta QC=0 como relleno; el relleno de LST es 0.
  [Especificación NASA](https://ladsweb.modaps.eosdis.nasa.gov/filespec/MODIS/61/MOD11C3).
- Enero y julio de 2025 son una muestra, **no** extremos anuales, climatología, temperatura
  del aire, amplitud día/noche ni analogía térmica con la Luna. Cada capa conserva su número de meses válidos.
- Malla de 0,05° (unos 5,6 km norte-sur, menos este-oeste según latitud): se muestrea
  el píxel del centro de cada tesela de 3 km, no se mide toda su superficie.
- El catálogo muestra hasta 30 candidatos por referencia: 3/3 variables de relieve dentro de
  P10–P90, NDVI válido en **ambos** meses y máximo ≤0,3. Ese umbral es una heurística del
  equipo elegida después de inspeccionar Cinder Lake, no un criterio NASA ni prueba de suelo desnudo.
  Sin NDVI suficiente se excluye del ranking filtrado, pero los sitios registrados siguen consultables.
- PostgreSQL conserva URLs permanentes, meses, política QA y SHA-256 de cada HDF.
  Los resultados muestran procedencia y límites en `limitation`/`sources`, sin cambiar el contrato frontend.

## Seguimiento (logs JSON, una línea por evento, con rotación de 5 × 10 MB por contenedor)

Usa `docker logs`: `docker compose logs -f` en Compose 2.26 antepone el nombre del contenedor aunque se pase `--no-log-prefix`, y `jq` falla. `fromjson?` descarta cualquier línea que no sea JSON. Cada seguimiento con `-f` va en su propia terminal.

```bash
sudo docker logs -f --tail 50 tsumi-trabajador-1 2>&1 | jq -cR 'fromjson? | select(.evento != "fuente_leida") | {ts, evento, celda, estado, duracion_s}'
sudo docker logs tsumi-trabajador-1 2>&1 | jq -cR 'fromjson? | select(.nivel == "error")'
sudo docker logs tsumi-trabajador-1 2>&1 | jq -cR 'fromjson? | select(.evento == "fuente_leida" and .lectura_s > 60)'   # tramos lentos
sudo docker logs -f --tail 50 tsumi-api-1 2>&1 | jq -cR 'fromjson? | select(.evento == "peticion") | {ruta, estado, duracion_ms}'
curl -s 127.0.0.1:8000/busqueda/estado | jq    # avance de la cola (ruta interna, no se publica)
sudo -u postgres psql -d tsumi -c "SELECT pg_size_pretty(pg_total_relation_size('teselas')), count(*), count(DISTINCT celda_id) FROM teselas;"
```

| Evento | Servicio | Campos clave |
|---|---|---|
| `inicio` | trabajador | `accion`, `config_sha256`, `version_metodo` |
| `celda_tomada` / `celda_terminada` | trabajador | `celda`, `n_validas`, `lectura_s`, `metricas_s`, `insercion_s`, `duracion_s` |
| `fuente_leida` | trabajador | `url`, `estado`, `apertura_s`, `lectura_s` |
| `contexto_preparado` / `contexto_rellenado` | trabajador | Identidad y fuentes con SHA-256 / teselas muestreadas y candidatos |
| `lote_encolado` / `catalogo_actualizado` | trabajador | Nuevas celdas del lote, pendientes previas y dominio elegible / metadatos de sitios revisados |
| `celda_fallida` | trabajador | `celda`, `intentos`, `error`, `excepcion`. Tras 3 intentos queda en `error` |
| `celdas_recuperadas` / `cola_vacia` / `trabajador_detenido` | trabajador | Celdas de un trabajador caído devueltas a la cola / espera / excepción que lo detuvo |
| `peticion` / `peticion_fallida` / `base_no_disponible` | api | `metodo`, `ruta`, `estado`, `duracion_ms` |

Los logs nunca deben incluir `DATABASE_URL`, `EARTHDATA_TOKEN` ni URLs de descarga firmadas.

## Rendimiento y red

Por celda, el trabajador tarda unos **15 s en el servidor** (de 45 a 85 s desde una red doméstica), casi todo lectura de red, con unos 5 s de CPU y unos 300 MB de RAM en el pico. Las 29 celdas iniciales se procesaron en unos 7 minutos.

**Lentitud intermitente.** Algunas ejecuciones tardaron de 9 a 10 min, porque un tramo HTTP hacia el bucket de Copernicus iba muy lento. GDAL corta las conexiones estancadas (15 s para conectar, o menos de 10 KB/s durante 30 s) y reintenta 3 veces. Sus reintentos solo aparecen a nivel DEBUG, así que los tramos lentos se buscan con `fuente_leida`. Un error que no sea 404 hace fallar la celda, que vuelve a la cola: nunca se guarda un hueco como si fuera océano.

Para ir más rápido, se puede lanzar un segundo trabajador con `docker compose up -d --scale trabajador=2`, porque la cola reparte las celdas con `SKIP LOCKED`.
