-- Extensiones base de la BD de Stalvi.
-- Se ejecuta automáticamente al inicializar el contenedor con la BD vacía.

-- pgvector: almacenamiento y búsqueda de embeddings (F2).
CREATE EXTENSION IF NOT EXISTS vector;

-- pg_trgm: búsqueda por similitud de texto (útil para búsqueda de productos).
CREATE EXTENSION IF NOT EXISTS pg_trgm;
