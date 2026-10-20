-- 0002 — Embeddings y catalogación por similitud (F2). Idempotente.

-- Vector del producto (dim 384: paraphrase-multilingual-MiniLM-L12-v2).
ALTER TABLE products ADD COLUMN IF NOT EXISTS embedding vector(384);

-- Cómo se catalogó el producto y con qué confianza.
--   'inference' -> heredado del mapeo de su categoría (keyword)
--   'knn'       -> asignado por similitud de embeddings
--   'pending'   -> sin catalogar con confianza (cola de revisión)
ALTER TABLE products ADD COLUMN IF NOT EXISTS catalog_status TEXT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS catalog_confidence REAL;

-- Prototipo (embedding representativo) de cada categoría maestra.
CREATE TABLE IF NOT EXISTS category_prototypes (
    master_category_id  TEXT PRIMARY KEY,
    embedding           vector(384) NOT NULL,
    source              TEXT NOT NULL,      -- 'centroid' | 'text'
    n_samples           INT NOT NULL DEFAULT 0,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Índices HNSW para búsqueda por coseno.
CREATE INDEX IF NOT EXISTS idx_products_embedding_hnsw
    ON products USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_prototypes_embedding_hnsw
    ON category_prototypes USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_products_catalog_status ON products (catalog_status);
