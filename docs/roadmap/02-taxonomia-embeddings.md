# F2 — Taxonomía transversal + embeddings + catalogación

> Depende de F1 (productos en Postgres). Añade la tipología transversal y un "modelo sencillo" de catalogación basado en embeddings para lo que no se cataloga por keywords.

## Objetivo
1. Consolidar `master_taxonomy.json` como **tipología transversal** definitiva.
2. Calcular **embeddings locales multilingües** de productos y prototipos de categoría, guardarlos en pgvector.
3. Implementar **catalogación en cascada**: keyword-inference → fallback kNN por similitud → cola de revisión.

## Contexto / estado actual
- Taxonomía: `scraper/scrapers/data/master_taxonomy.json` (253 categorías, cada una con `keywords[]`).
- Mapper actual: `scraper/scrapers/categories/mapper.py` mapea **solo por keywords** (umbral 0.7). Deja muchos productos en `pending`.
- Mappings **confirmados** de Mercadona (~400) sirven de **ground truth** para evaluar.
- Modelo elegido: **`intfloat/multilingual-e5-small`** (dim 384). Requiere prefijos: `"query: ..."` para consultas y `"passage: ..."` para documentos. Coseno como métrica.

## Tareas
1. **Consolidar taxonomía:** revisar hojas y keywords de `master_taxonomy.json`; asegurar cobertura transversal (no sesgada a un súper). Documentar criterios.
2. **Columna vectorial:** `ALTER TABLE products ADD COLUMN embedding vector(384);` + tabla `category_prototypes(master_category_id, embedding vector(384))`. Índice `hnsw` (o `ivfflat`) con `vector_cosine_ops`.
3. **Módulo `scraper/embeddings/`:**
   - Cargar el modelo con `sentence-transformers`.
   - `embed_products()`: para cada producto, `"passage: {name}"` → vector → guardar.
   - `build_category_prototypes()`: por categoría, combinar (nombre + keywords) y/o **centroide de los embeddings de productos ya confirmados** en esa categoría.
4. **Catalogación en cascada** (`scraper/categories/classify.py`):
   1. Keyword-inference actual (`CategoryMapper`).
   2. Si no cataloga con confianza → **kNN**: coseno del embedding del producto contra `category_prototypes`; asignar la mejor si supera `THRESHOLD`.
   3. Si nada supera el umbral → `status='pending'` (cola de revisión) con top-5 sugerencias.
5. **Arnés de evaluación:** medir precisión/recall de la cascada contra los mappings confirmados de Mercadona; barrer `THRESHOLD` para elegir el punto de operación. Reportar % auto-catalogado vs cola.
6. **Búsqueda semántica:** función SQL/RPC `search_products(query text)` que embebe `"query: {q}"` y ordena por coseno (la usará el front en F4).

## Decisiones abiertas
- Prototipo de categoría: ¿solo texto (nombre+keywords), solo centroide de confirmados, o mezcla? (recomendado: centroide si hay ≥N confirmados, si no texto).
- `THRESHOLD` de confianza: fijar tras el barrido de evaluación.
- ¿Embeber en el propio proceso de scrape o como job aparte? (recomendado: job aparte, solo para productos nuevos/cambiados).

## Criterios de aceptación
- Todos los productos de Mercadona tienen `embedding`.
- La cascada cataloga automáticamente ≥X% (X a fijar tras evaluación) con confianza medida; el resto en `pending`.
- `search_products('leche desnatada')` devuelve resultados relevantes por similitud.

## Verificación
```bash
python scraper/embeddings/run.py --products      # embeber productos
python scraper/embeddings/run.py --prototypes    # construir prototipos
python scraper/categories/classify.py --eval     # reporta precisión vs ground truth y % auto
psql "$DATABASE_URL" -c "SELECT count(*) FROM products WHERE master_category_id IS NULL;"
```
