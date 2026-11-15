-- 004: contexto NASA (MODIS) por tesela, comparación tesela-envolvente en un solo lugar y ranking precalculado.
-- Idempotente. Sin DROP VIEW: conserva los permisos de lectura en despliegues sucesivos.

CREATE TABLE IF NOT EXISTS contexto_modis (
    unico boolean PRIMARY KEY DEFAULT true CHECK (unico),
    contexto_id text NOT NULL,
    metadata jsonb NOT NULL,
    umbral_ndvi double precision NOT NULL CHECK (umbral_ndvi BETWEEN -0.2 AND 1)
);

ALTER TABLE teselas ADD COLUMN IF NOT EXISTS ndvi_max double precision; -- MOD13C2, máximo de los meses usados
ALTER TABLE teselas ADD COLUMN IF NOT EXISTS lst_dia_max_k real;     -- MOD11C3, temperatura superficial diurna máxima
ALTER TABLE teselas ADD COLUMN IF NOT EXISTS lst_noche_min_k real;   -- MOD11C3, nocturna mínima
ALTER TABLE teselas ADD COLUMN IF NOT EXISTS ndvi_n int;
ALTER TABLE teselas ADD COLUMN IF NOT EXISTS lst_dia_n int;
ALTER TABLE teselas ADD COLUMN IF NOT EXISTS lst_noche_n int;
ALTER TABLE teselas ADD COLUMN IF NOT EXISTS contexto_id text;

CREATE OR REPLACE VIEW teselas_referencia AS
SELECT t.*, c.zona, r.referencia_id, r.cuerpo AS cuerpo_referencia, r.envolvente AS env, d.*,
       (d.d_pendiente_mediana = 0)::int + (d.d_pendiente_p90 = 0)::int + (d.d_relieve = 0)::int AS n_dentro,
       greatest(d.d_pendiente_mediana, d.d_pendiente_p90, d.d_relieve) AS dist_max,
       dist_mediana(t.pendiente_mediana, r.envolvente->'pendiente_mediana_grados')
         + dist_mediana(t.pendiente_p90, r.envolvente->'pendiente_p90_grados')
         + dist_mediana(t.relieve, r.envolvente->'relieve_p95_p5_m') AS dist_mediana
FROM teselas t
JOIN celdas_busqueda c USING (celda_id)
JOIN referencias r ON r.res_m = t.res_m AND r.version_metodo = t.version_metodo
CROSS JOIN LATERAL (SELECT
    CASE WHEN r.envolvente->'pendiente_mediana_grados'->>'p10' IS NOT NULL
          AND r.envolvente->'pendiente_mediana_grados'->>'p90' IS NOT NULL
         THEN dist_envolvente(t.pendiente_mediana, r.envolvente->'pendiente_mediana_grados') END AS d_pendiente_mediana,
    CASE WHEN r.envolvente->'pendiente_p90_grados'->>'p10' IS NOT NULL
          AND r.envolvente->'pendiente_p90_grados'->>'p90' IS NOT NULL
         THEN dist_envolvente(t.pendiente_p90, r.envolvente->'pendiente_p90_grados') END AS d_pendiente_p90,
    CASE WHEN r.envolvente->'relieve_p95_p5_m'->>'p10' IS NOT NULL
          AND r.envolvente->'relieve_p95_p5_m'->>'p90' IS NOT NULL
         THEN dist_envolvente(t.relieve, r.envolvente->'relieve_p95_p5_m') END AS d_relieve) d;

-- Teselas 3/3 y NDVI válido en todos los meses, por debajo del umbral heurístico.
-- La mantiene el trabajador al cerrar cada celda; así /api/sites no ordena todas las teselas en cada petición.
CREATE TABLE IF NOT EXISTS candidatos (
    referencia_id  text NOT NULL,
    res_m          double precision NOT NULL,
    version_metodo text NOT NULL,
    celda_id       text NOT NULL,
    ix             int NOT NULL,
    iy             int NOT NULL,
    lat            double precision NOT NULL,
    lon            double precision NOT NULL,
    dist_mediana   double precision NOT NULL,
    PRIMARY KEY (referencia_id, res_m, version_metodo, celda_id, ix, iy),
    FOREIGN KEY (referencia_id, res_m, version_metodo)
        REFERENCES referencias ON DELETE CASCADE,
    FOREIGN KEY (celda_id, res_m, version_metodo, ix, iy)
        REFERENCES teselas ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS candidatos_orden
    ON candidatos (referencia_id, res_m, version_metodo, dist_mediana, celda_id, iy, ix);
