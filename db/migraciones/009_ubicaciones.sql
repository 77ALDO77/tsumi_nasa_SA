-- 009: país, provincia y distrito de cada lugar del atlas (geocodificación inversa de OpenStreetMap/Nominatim).
-- Caché por coordenada redondeada a 0,01° (~1 km): el trabajador consulta una sola vez cada punto.
CREATE TABLE IF NOT EXISTS ubicaciones (
    lat            numeric(5,2) NOT NULL,
    lon            numeric(5,2) NOT NULL,
    pais           text,
    provincia      text,
    distrito       text,
    estado         text NOT NULL CHECK (estado IN ('ok', 'sin_resultado', 'error')),  -- sin_resultado: mar o sin datos
    consultado_utc timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (lat, lon)
);
