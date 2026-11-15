-- 002: búsqueda continua de análogos. Idempotente.
-- referencias: envolvente P10–P90 de cada región lunar o marciana.
-- celdas_busqueda: cola de celdas de 1° que el trabajador procesa en orden de prioridad.
-- teselas: métricas de cada tesela terrestre (solo las válidas; los huecos no se guardan como cero).

CREATE TABLE IF NOT EXISTS referencias (
    referencia_id      text NOT NULL,
    cuerpo             text NOT NULL CHECK (cuerpo IN ('luna', 'marte')),
    lat                double precision NOT NULL,
    lon                double precision NOT NULL,
    lado_m             double precision NOT NULL,
    tesela_m           double precision NOT NULL,
    res_m              double precision NOT NULL,
    version_metodo     text NOT NULL,
    fuente_coordenadas text NOT NULL,
    n_subventanas      int NOT NULL,
    envolvente         jsonb NOT NULL,          -- {variable: {p10, p90}}
    calculado_utc      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (referencia_id, res_m, version_metodo)
);

CREATE TABLE IF NOT EXISTS celdas_busqueda (
    celda_id        text PRIMARY KEY,           -- p. ej. N35W112: [35, 36) x [-112, -111)
    lat_min         int NOT NULL,
    lon_min         int NOT NULL,
    zona            text NOT NULL,
    prioridad       int NOT NULL DEFAULT 100,   -- menor = antes
    estado          text NOT NULL DEFAULT 'pendiente'
                    CHECK (estado IN ('pendiente', 'en_curso', 'hecha', 'sin_datos', 'error')),
    intentos        int NOT NULL DEFAULT 0,
    n_teselas       int,
    n_validas       int,
    error           text,
    actualizado_utc timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS celdas_pendientes ON celdas_busqueda (prioridad, celda_id) WHERE estado = 'pendiente';

CREATE TABLE IF NOT EXISTS teselas (
    celda_id          text NOT NULL REFERENCES celdas_busqueda,
    res_m             double precision NOT NULL,
    version_metodo    text NOT NULL,
    ix                int NOT NULL,
    iy                int NOT NULL,
    lat               double precision NOT NULL,
    lon               double precision NOT NULL,
    geom              geometry(Polygon, 4326) NOT NULL,
    pendiente_mediana real NOT NULL,
    pendiente_p90     real NOT NULL,
    relieve           real NOT NULL,
    rugosidad         real NOT NULL,
    fraccion_valida   real NOT NULL,
    PRIMARY KEY (celda_id, res_m, version_metodo, ix, iy)
);
CREATE INDEX IF NOT EXISTS teselas_geom ON teselas USING gist (geom);

-- 0 dentro de [p10, p90]; fuera, la distancia al borde más cercano en anchos de envolvente.
CREATE OR REPLACE FUNCTION dist_envolvente(x double precision, env jsonb)
RETURNS double precision LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN x IS NULL OR env IS NULL THEN NULL
        WHEN x < (env->>'p10')::float8 THEN ((env->>'p10')::float8 - x)
             / greatest((env->>'p90')::float8 - (env->>'p10')::float8, 1e-9)
        WHEN x > (env->>'p90')::float8 THEN (x - (env->>'p90')::float8)
             / greatest((env->>'p90')::float8 - (env->>'p10')::float8, 1e-9)
        ELSE 0 END
$$;
