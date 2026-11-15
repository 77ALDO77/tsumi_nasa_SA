-- Señal del trabajador, independiente de que haya celdas pendientes.
CREATE TABLE IF NOT EXISTS trabajadores (
    trabajador_id text PRIMARY KEY,
    estado text NOT NULL CHECK (estado IN ('preparando', 'procesando', 'esperando', 'agotado')),
    celda_id text,
    celdas_elegibles int,
    actualizado_utc timestamptz NOT NULL DEFAULT now()
);
