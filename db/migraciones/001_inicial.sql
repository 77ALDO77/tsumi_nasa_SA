-- 001: esquema mínimo para cargar los manifiestos de analisis/ (MVP 0).
-- PostgreSQL >= 15 (NULLS NOT DISTINCT) + PostGIS. Idempotente: se puede ejecutar dos veces.
-- La geometría PostGIS solo se usa en la Tierra (EPSG:4326). La Luna y Marte guardan coordenadas
-- nativas y el CRS de cálculo como texto: no se les asigna un SRID terrestre.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS ejecuciones (
    ejecucion_id    text PRIMARY KEY,              -- nombre de la carpeta de salida
    tipo            text NOT NULL CHECK (tipo IN ('calculo_relieve')),
    config_sha256   text NOT NULL,
    version_config  text NOT NULL,
    git_commit      text,
    inicio_utc      timestamptz NOT NULL,
    fin_utc         timestamptz,
    parametros      jsonb NOT NULL,
    cargado_utc     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS productos (
    producto_id  serial PRIMARY KEY,
    proveedor    text NOT NULL,
    coleccion    text NOT NULL,
    version      text NOT NULL DEFAULT '',
    cuerpo       text NOT NULL CHECK (cuerpo IN ('tierra', 'luna', 'marte')),
    licencia     text,
    cita         text,
    UNIQUE (proveedor, coleccion, version)
);

CREATE TABLE IF NOT EXISTS sitios (
    sitio_id           text PRIMARY KEY,
    cuerpo             text NOT NULL CHECK (cuerpo IN ('tierra', 'luna', 'marte')),
    lat                double precision NOT NULL,
    lon                double precision NOT NULL,      -- este positivo, -180..180
    fuente_coordenadas text NOT NULL,
    geom               geometry(Point, 4326),
    CHECK (cuerpo = 'tierra' OR geom IS NULL)
);

CREATE TABLE IF NOT EXISTS ventanas (
    ventana_id   bigserial PRIMARY KEY,
    sitio_id     text NOT NULL REFERENCES sitios,
    lado_m       double precision NOT NULL,
    res_m        double precision NOT NULL,
    crs_calculo  text NOT NULL,                      -- proj4 de la proyección aeqd centrada
    geom         geometry(Polygon, 4326),            -- solo Tierra
    UNIQUE (sitio_id, lado_m, res_m)
);
CREATE INDEX IF NOT EXISTS ventanas_geom_gix ON ventanas USING gist (geom);

CREATE TABLE IF NOT EXISTS lecturas_fuente (
    ejecucion_id          text NOT NULL REFERENCES ejecuciones ON DELETE CASCADE,
    ventana_id            bigint NOT NULL REFERENCES ventanas,
    producto_id           int NOT NULL REFERENCES productos,
    url                   text NOT NULL,
    estado                text NOT NULL,             -- leido | sin_tesela
    ventana_fuente        jsonb,                     -- col, fila, ancho, alto en píxeles nativos
    res_nativa_m          double precision,
    sha256_valores_leidos text,
    PRIMARY KEY (ejecucion_id, ventana_id, url)
);

-- Formato largo: cualquier variable nueva entra sin cambiar el esquema.
CREATE TABLE IF NOT EXISTS metricas (
    ventana_id       bigint NOT NULL REFERENCES ventanas,
    variable         text NOT NULL,                  -- pendiente | relieve | rugosidad
    estadistico      text NOT NULL,                  -- mediana | p90 | p95_p5 | rms_plano
    version_metodo   text NOT NULL,
    valor            double precision,               -- NULL nunca significa cero
    unidad           text NOT NULL,
    estado           text NOT NULL CHECK (estado IN ('calculado', 'evidencia_insuficiente', 'error')),
    motivo           text,
    fraccion_valida  double precision,
    n_validas        int,
    n_total          int,
    ejecucion_id     text NOT NULL REFERENCES ejecuciones,
    CHECK (estado <> 'calculado' OR valor IS NOT NULL),
    UNIQUE NULLS NOT DISTINCT (ventana_id, variable, estadistico, version_metodo)
);
