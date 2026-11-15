-- 003: datos que necesita el contrato del frontend (/api). Idempotente.
ALTER TABLE sitios ADD COLUMN IF NOT EXISTS nombre text;
ALTER TABLE sitios ADD COLUMN IF NOT EXISTS rol text;
ALTER TABLE sitios ADD COLUMN IF NOT EXISTS etiquetas text[];   -- label_id de scrapping/docs/etiquetas_analogos.json
ALTER TABLE referencias ADD COLUMN IF NOT EXISTS nombre text;

-- Distancia a la mediana de la referencia en anchos de envolvente; desempata teselas que ya están dentro.
CREATE OR REPLACE FUNCTION dist_mediana(x double precision, env jsonb)
RETURNS double precision LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN x IS NULL OR env->>'p50' IS NULL THEN NULL
        ELSE abs(x - (env->>'p50')::float8)
             / greatest((env->>'p90')::float8 - (env->>'p10')::float8, 1e-9) END
$$;
