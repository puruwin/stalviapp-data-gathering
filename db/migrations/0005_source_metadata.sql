-- Trazabilidad del catálogo y de cada cambio de precio. Aditiva e idempotente.
ALTER TABLE products ADD COLUMN IF NOT EXISTS source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE price_history ADD COLUMN IF NOT EXISTS source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
