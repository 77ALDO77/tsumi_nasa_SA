-- 007: referencias marcianas. Cada referencia declara su banda de envolvente, si entra en la búsqueda
-- automática y la fuente de su DEM. Idempotente; los valores por defecto conservan el comportamiento lunar.
ALTER TABLE referencias ADD COLUMN IF NOT EXISTS banda text NOT NULL DEFAULT 'p10-p90';
ALTER TABLE referencias ADD COLUMN IF NOT EXISTS buscar boolean NOT NULL DEFAULT true;
ALTER TABLE referencias ADD COLUMN IF NOT EXISTS fuente jsonb;  -- {title, url} del DEM; null = LOLA (lunar)
DO $$ BEGIN
    ALTER TABLE referencias ADD CONSTRAINT referencias_banda CHECK (banda IN ('p10-p90', 'p25-p75'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Límites de la banda con las claves que leen dist_envolvente y dist_mediana (p10 = inferior, p90 = superior).
CREATE OR REPLACE FUNCTION banda(env jsonb, b text) RETURNS jsonb LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN b = 'p25-p75' THEN jsonb_build_object('p10', env->'p25', 'p50', env->'p50', 'p90', env->'p75')
                ELSE env END
$$;

-- Mismas columnas que en 004 (que se vuelve a ejecutar antes): solo cambian los límites usados.
CREATE OR REPLACE VIEW teselas_referencia AS
SELECT t.*, c.zona, r.referencia_id, r.cuerpo AS cuerpo_referencia, r.envolvente AS env, d.*,
       (d.d_pendiente_mediana = 0)::int + (d.d_pendiente_p90 = 0)::int + (d.d_relieve = 0)::int AS n_dentro,
       greatest(d.d_pendiente_mediana, d.d_pendiente_p90, d.d_relieve) AS dist_max,
       dist_mediana(t.pendiente_mediana, banda(r.envolvente->'pendiente_mediana_grados', r.banda))
         + dist_mediana(t.pendiente_p90, banda(r.envolvente->'pendiente_p90_grados', r.banda))
         + dist_mediana(t.relieve, banda(r.envolvente->'relieve_p95_p5_m', r.banda)) AS dist_mediana
FROM teselas t
JOIN celdas_busqueda c USING (celda_id)
JOIN referencias r ON r.res_m = t.res_m AND r.version_metodo = t.version_metodo
CROSS JOIN LATERAL (SELECT banda(r.envolvente->'pendiente_mediana_grados', r.banda) AS e_med,
                           banda(r.envolvente->'pendiente_p90_grados', r.banda) AS e_p90,
                           banda(r.envolvente->'relieve_p95_p5_m', r.banda) AS e_rel) b
CROSS JOIN LATERAL (SELECT
    CASE WHEN b.e_med->>'p10' IS NOT NULL AND b.e_med->>'p90' IS NOT NULL
         THEN dist_envolvente(t.pendiente_mediana, b.e_med) END AS d_pendiente_mediana,
    CASE WHEN b.e_p90->>'p10' IS NOT NULL AND b.e_p90->>'p90' IS NOT NULL
         THEN dist_envolvente(t.pendiente_p90, b.e_p90) END AS d_pendiente_p90,
    CASE WHEN b.e_rel->>'p10' IS NOT NULL AND b.e_rel->>'p90' IS NOT NULL
         THEN dist_envolvente(t.relieve, b.e_rel) END AS d_relieve) d;
