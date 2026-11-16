-- 006: zonas de teselas candidatas cercanas. Derivadas de `candidatos`: el trabajador las reemplaza
-- completas en la misma transacción que el ranking, así nunca quedan desfasadas.
CREATE TABLE IF NOT EXISTS zonas_candidatas (
    res_m            double precision NOT NULL,
    version_metodo   text NOT NULL,
    zona_id          text NOT NULL,              -- mejor tesela (celda~ix~iy); cambia si dos zonas se unen
    n_teselas        int NOT NULL,
    area_km2         double precision NOT NULL,  -- suma de las teselas, no del recuadro
    referencias      text[] NOT NULL,
    region           text NOT NULL,              -- zona de búsqueda más frecuente entre sus teselas
    lat              double precision NOT NULL,  -- centro de la mejor tesela, siempre dentro de la zona
    lon              double precision NOT NULL,
    dist_mediana     double precision NOT NULL,
    lon_min          double precision NOT NULL,  -- recuadro de las teselas
    lat_min          double precision NOT NULL,
    lon_max          double precision NOT NULL,
    lat_max          double precision NOT NULL,
    es_zona          boolean NOT NULL,           -- n_teselas >= mínimo configurado; si no, candidata aislada
    sitio_cercano    text,
    sitio_cercano_km double precision,
    conocida         boolean NOT NULL,           -- alguna tesela cerca de un análogo NASA registrado
    PRIMARY KEY (res_m, version_metodo, zona_id)
);
CREATE INDEX IF NOT EXISTS zonas_orden
    ON zonas_candidatas (res_m, version_metodo, es_zona, n_teselas DESC, dist_mediana);
