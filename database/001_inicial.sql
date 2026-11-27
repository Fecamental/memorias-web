BEGIN;
CREATE TABLE IF NOT EXISTS memoria (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tipo text NOT NULL,
  correlativo integer NOT NULL CHECK (correlativo > 0),
  titulo text NOT NULL,
  generador text NOT NULL,
  estado text NOT NULL CHECK (estado IN ('borrador','revision','discrepancia','aprobacion','observada','devuelta','aprobada')),
  actual integer NOT NULL CHECK (actual > 0),
  version integer NOT NULL DEFAULT 1,
  creada timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tipo, correlativo)
);
CREATE TABLE IF NOT EXISTS correlativo_tipo (
  tipo text PRIMARY KEY,
  numero integer NOT NULL CHECK (numero > 0)
);
CREATE TABLE IF NOT EXISTS revision (
  memoria_id bigint NOT NULL REFERENCES memoria(id),
  numero integer NOT NULL CHECK (numero > 0),
  modelo integer NOT NULL DEFAULT 1,
  generador text NOT NULL,
  creada timestamptz NOT NULL DEFAULT now(),
  enviada timestamptz,
  alcance text NOT NULL DEFAULT '',
  desviacion text NOT NULL DEFAULT '',
  conclusion text NOT NULL DEFAULT '',
  veredicto text CHECK (veredicto IN ('cumple','no_cumple')),
  reporte jsonb,
  PRIMARY KEY (memoria_id, numero)
);
CREATE TABLE IF NOT EXISTS variable_revision (
  memoria_id bigint NOT NULL,
  revision integer NOT NULL,
  variable text NOT NULL,
  valor numeric NOT NULL,
  unidad text NOT NULL,
  fuente text NOT NULL,
  PRIMARY KEY (memoria_id, revision, variable),
  FOREIGN KEY (memoria_id, revision) REFERENCES revision(memoria_id, numero)
);
CREATE TABLE IF NOT EXISTS movimiento (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  memoria_id bigint NOT NULL,
  revision integer NOT NULL,
  actor text NOT NULL,
  rol text NOT NULL,
  accion text NOT NULL,
  motivo text NOT NULL,
  estado text NOT NULL,
  fecha timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (memoria_id, revision) REFERENCES revision(memoria_id, numero)
);
CREATE TABLE IF NOT EXISTS sesion (
  hash text PRIMARY KEY,
  usuario text NOT NULL,
  vence timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS memoria_generador ON memoria (generador);
CREATE INDEX IF NOT EXISTS movimiento_memoria ON movimiento (memoria_id, id);
COMMIT;
