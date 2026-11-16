-- 008: las zonas se agrupan por cuerpo. Si no, las teselas lunares y marcianas cercanas se unían en zonas
-- mixtas y no se podían distinguir. La tabla es derivada: el trabajador la rellena de nuevo en la siguiente celda.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'zonas_candidatas' AND column_name = 'cuerpo') THEN
        DELETE FROM zonas_candidatas;
        ALTER TABLE zonas_candidatas ADD COLUMN cuerpo text NOT NULL CHECK (cuerpo IN ('luna', 'marte'));
        ALTER TABLE zonas_candidatas DROP CONSTRAINT zonas_candidatas_pkey;
        ALTER TABLE zonas_candidatas ADD PRIMARY KEY (res_m, version_metodo, cuerpo, zona_id);
    END IF;
END $$;
