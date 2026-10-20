-- Producto único por cadena/SKU; disponibilidad y precio separados por zona.
CREATE TABLE IF NOT EXISTS catalogue_zones (
    market TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    label TEXT NOT NULL,
    last_completed_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (market, zone_id)
);
CREATE TABLE IF NOT EXISTS catalogue_zone_provinces (
    market TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    province_code TEXT NOT NULL CHECK (province_code ~ '^[0-9]{2}$'),
    province TEXT NOT NULL,
    postal_codes TEXT[] NOT NULL DEFAULT '{}',
    evidence_kind TEXT NOT NULL,
    PRIMARY KEY (market, zone_id, province_code),
    FOREIGN KEY (market, zone_id) REFERENCES catalogue_zones(market, zone_id)
);
CREATE INDEX IF NOT EXISTS idx_zone_province ON catalogue_zone_provinces(province_code, market, zone_id);
CREATE TABLE IF NOT EXISTS product_availability (
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    market TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    price NUMERIC(10,2),
    price_per_unit NUMERIC(12,4),
    unit TEXT,
    available BOOLEAN NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (product_id, market, zone_id),
    FOREIGN KEY (market, zone_id) REFERENCES catalogue_zones(market, zone_id)
);
CREATE INDEX IF NOT EXISTS idx_availability_zone ON product_availability(market, zone_id, product_id) WHERE available;
CREATE TABLE IF NOT EXISTS regional_price_history (
    id BIGSERIAL PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    market TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    price NUMERIC(10,2),
    price_per_unit NUMERIC(12,4),
    changed_at TIMESTAMPTZ NOT NULL,
    FOREIGN KEY (market, zone_id) REFERENCES catalogue_zones(market, zone_id)
);
CREATE INDEX IF NOT EXISTS idx_regional_history ON regional_price_history(product_id, market, zone_id, changed_at DESC, id DESC);
GRANT SELECT ON catalogue_zones, catalogue_zone_provinces, product_availability, regional_price_history TO app_user;
