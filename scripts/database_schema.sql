-- Esquema de base de datos para Supermarket Scraping
-- PostgreSQL

CREATE TABLE IF NOT EXISTS master_categories (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    parent_id INTEGER REFERENCES master_categories(id) ON DELETE SET NULL,
    level SMALLINT NOT NULL DEFAULT 0,
    needs_review BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_category_mappings (
    id SERIAL PRIMARY KEY,
    market VARCHAR(50) NOT NULL,
    external_id VARCHAR(255) NOT NULL,
    external_name VARCHAR(255),
    external_parent VARCHAR(255),
    master_category_id INTEGER REFERENCES master_categories(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    confidence NUMERIC(5, 2),
    notes TEXT,
    last_reviewed TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (market, external_id)
);

CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    market VARCHAR(50) NOT NULL DEFAULT 'unknown',
    external_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    link VARCHAR(500),
    parent_category VARCHAR(255),
    master_category_id INTEGER REFERENCES master_categories(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (market, external_id)
);

-- Tabla de productos
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    display_name VARCHAR(500) NOT NULL,
    brand VARCHAR(255),
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    current_price DECIMAL(10, 2),
    current_price_per_unit DECIMAL(10, 2),
    measure_unit VARCHAR(50),
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(display_name, brand, category_id)
);

-- Tabla de historial de precios
CREATE TABLE IF NOT EXISTS price_history (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    price DECIMAL(10, 2) NOT NULL,
    price_per_unit DECIMAL(10, 2),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para mejorar el rendimiento
CREATE INDEX IF NOT EXISTS idx_price_history_product_id ON price_history(product_id);
CREATE INDEX IF NOT EXISTS idx_price_history_recorded_at ON price_history(recorded_at);
CREATE INDEX IF NOT EXISTS idx_products_category_id ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_display_name ON products(display_name);
CREATE INDEX IF NOT EXISTS idx_categories_external_id ON categories(external_id);
CREATE INDEX IF NOT EXISTS idx_categories_master_category_id ON categories(master_category_id);
CREATE INDEX IF NOT EXISTS idx_master_categories_parent_id ON master_categories(parent_id);
CREATE INDEX IF NOT EXISTS idx_market_category_mappings_master ON market_category_mappings(master_category_id);
CREATE INDEX IF NOT EXISTS idx_market_category_mappings_market_external ON market_category_mappings(market, external_id);

