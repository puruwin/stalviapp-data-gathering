-- 0001 — Esquema de productos, precios y categorías (F1).
-- Idempotente: se puede reaplicar sin efectos secundarios.

-- Categorías nativas de cada supermercado, con su mapeo a la taxonomía maestra.
CREATE TABLE IF NOT EXISTS categories (
    id                  BIGSERIAL PRIMARY KEY,
    market              TEXT NOT NULL,
    external_id         TEXT NOT NULL,
    name                TEXT NOT NULL,
    parent_name         TEXT,
    master_category_id  TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (market, external_id)
);

-- Producto (estado actual). id = "{market}_{external_id}".
CREATE TABLE IF NOT EXISTS products (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    supermarket         TEXT NOT NULL,
    category            TEXT,               -- ruta original del supermercado
    master_category_id  TEXT,               -- id de la taxonomía maestra
    price               NUMERIC(10,2),
    price_per_unit      NUMERIC(12,4),
    unit                TEXT,
    brand               TEXT,
    url                 TEXT,
    image_url           TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Histórico de precios: una fila por producto nuevo (baseline) y por cada
-- cambio de precio detectado. Permite reconstruir la serie temporal.
CREATE TABLE IF NOT EXISTS price_history (
    id              BIGSERIAL PRIMARY KEY,
    product_id      TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    price           NUMERIC(10,2),
    price_per_unit  NUMERIC(12,4),
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_price_history_product     ON price_history (product_id);
CREATE INDEX IF NOT EXISTS idx_price_history_changed_at  ON price_history (changed_at);
CREATE INDEX IF NOT EXISTS idx_products_master_category  ON products (master_category_id);
CREATE INDEX IF NOT EXISTS idx_products_supermarket      ON products (supermarket);

-- Nota: market_category_mappings sigue gestionándose por ahora como JSON
-- (scraper/scrapers/data/mappings/) vía CategoryMapper. Se migrará a tabla en F2
-- junto con embeddings y catalogación.
