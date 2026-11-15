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
# Rol de solo lectura (API expuesta a internet).
sudo -u postgres createuser --pwprompt tsumi_lectura
sudo -u postgres psql -d tsumi -c "GRANT CONNECT ON DATABASE tsumi TO tsumi_lectura; GRANT USAGE ON SCHEMA public TO tsumi_lectura; GRANT SELECT ON ALL TABLES IN SCHEMA public TO tsumi_lectura; ALTER DEFAULT PRIVILEGES FOR ROLE tsumi IN SCHEMA public GRANT SELECT ON TABLES TO tsumi_lectura;"
echo 'DATABASE_URL=postgresql://tsumi_lectura:<clave>@127.0.0.1:5432/tsumi' > secretos/api.env
chmod 600 secretos/*.env

cd deploy
docker compose build
R="docker compose run --rm -T trabajador python -m analisis.trabajador analisis/inputs/busqueda.json"
$R referencias      # envolventes lunares (P10, P50, P90); aplica las migraciones
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

## Seguimiento (logs JSON, una línea por evento, con rotación de 5 × 10 MB por contenedor)

```bash
docker compose logs -f --no-log-prefix trabajador | jq -c '{ts, evento, celda, estado, duracion_s}'
docker compose logs --no-log-prefix trabajador | jq 'select(.nivel == "error")'
docker compose logs --no-log-prefix trabajador | jq -c 'select(.evento == "fuente_leida" and .lectura_s > 60)'   # tramos lentos
docker compose logs -f --no-log-prefix api | jq -c 'select(.evento == "peticion") | {ruta, estado, duracion_ms}'
curl -s 127.0.0.1:8000/busqueda/estado | jq    # avance de la cola (ruta interna, no se publica)
```

| Evento | Servicio | Campos clave |
|---|---|---|
| `inicio` | trabajador | `accion`, `config_sha256`, `version_metodo` |
| `celda_tomada` / `celda_terminada` | trabajador | `celda`, `n_validas`, `lectura_s`, `metricas_s`, `insercion_s`, `duracion_s` |
| `fuente_leida` | trabajador | `url`, `estado`, `apertura_s`, `lectura_s` |
| `celda_fallida` | trabajador | `celda`, `intentos`, `error`, `excepcion`. Tras 3 intentos queda en `error` |
| `celdas_recuperadas` / `cola_vacia` / `trabajador_detenido` | trabajador | Celdas de un trabajador caído devueltas a la cola / espera / excepción que lo detuvo |
| `peticion` / `peticion_fallida` / `base_no_disponible` | api | `metodo`, `ruta`, `estado`, `duracion_ms` |

Los logs nunca incluyen `DATABASE_URL`.

## Rendimiento y red

Por celda, el trabajador tarda de 45 a 85 s, casi todo lectura de red, con unos 5 s de CPU y unos 300 MB de RAM en el pico.

**Lentitud intermitente.** Algunas ejecuciones tardaron de 9 a 10 min, porque un tramo HTTP hacia el bucket de Copernicus iba muy lento. GDAL corta las conexiones estancadas (15 s para conectar, o menos de 10 KB/s durante 30 s) y reintenta 3 veces. Sus reintentos solo aparecen a nivel DEBUG, así que los tramos lentos se buscan con `fuente_leida`. Un error que no sea 404 hace fallar la celda, que vuelve a la cola: nunca se guarda un hueco como si fuera océano.

Para ir más rápido, se puede lanzar un segundo trabajador con `docker compose up -d --scale trabajador=2`, porque la cola reparte las celdas con `SKIP LOCKED`.
