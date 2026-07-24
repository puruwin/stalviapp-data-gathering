# F1 — Mercadona sólido y consistente

> Depende de F0. Convierte el scraper de Mercadona en un pipeline fiable y reproducible que persiste en Postgres con histórico de precios.

## Objetivo
Scrapear el catálogo completo de Mercadona de forma consistente y persistirlo en Postgres mediante upsert idempotente, registrando histórico de precios solo cuando cambian. Reemplaza la ingesta a Firestore.

## Contexto / estado actual
- `scraper/scrapers/mercadona/scraper.py` ya funciona: API JSON pública sin anti-bot.
  - Categorías: `https://tienda.mercadona.es/api/categories/?lang=es&wh=alc1`
  - PLP por categoría: `https://tienda.mercadona.es/api/categories/{id}/?lang=es&wh=alc1` (subcategorías anidadas con `products[]`).
  - Normaliza a `NormalizedProduct` (`scraper/scrapers/models.py`). `brand` = None (Mercadona no lo expone en PLP).
- Reutilizar: `models.py`, `validators.py`, `http_client.py`.
- **Portar** la lógica de detección de cambio de precio + histórico desde `functions/index.js` (hoy en Node/Firestore) a Python/Postgres.
- El schema PostgreSQL de referencia está en `scripts/database_schema.sql` (reescribir, no reutilizar tal cual).

## Tareas
1. **Schema en `db/` (migración SQL):**
   - `categories(id, market, external_id, name, parent_name, master_category_id, ...)` con `UNIQUE(market, external_id)`.
   - `products(id TEXT PK = "mercadona_{ext}", name, supermarket, category, master_category_id, price, price_per_unit, unit, brand, url, image_url, created_at, last_seen)`.
   - `price_history(id, product_id FK, price, price_per_unit, changed_at)`.
   - Índices en `product_id`, `changed_at`, `master_category_id`, `supermarket`.
2. **Capa de persistencia** `scraper/db.py`: conexión vía `DATABASE_URL`, upsert `INSERT ... ON CONFLICT (id) DO UPDATE`. Lógica: si `price` cambió → update + fila en `price_history`; si no → actualizar solo `last_seen`.
3. **Endurecer el scraper:** cobertura completa de categorías (no limitar salvo `--test`), reintentos/backoff ya en `http_client`, logging estructurado (nº categorías, productos, fallos por categoría), tolerancia a categorías vacías o caídas.
4. **Reemplazar ingesta:** sustituir `ingest.py`→Firestore por `scraper/db.py`→Postgres en el flujo de `main.py`. Mantener `--dry-run`.
5. **Validación:** aplicar `validators.py` antes del upsert; descartar productos sin `id`/`name`.
6. **Ejecución programada:** GitHub Actions (o cron) para run diario; artefacto/informe con métricas de cobertura.

## Decisiones abiertas
- ¿`psycopg` directo o SQLAlchemy? (recomendado: `psycopg3` directo, el schema es simple).
- ¿Migraciones con Supabase CLI, Alembic, o SQL plano versionado en `db/migrations/`? (recomendado: SQL plano si Supabase; Alembic si self-hosted).
- Frecuencia del run programado (recomendado: 1×/día).

## Criterios de aceptación
- Un run completo persiste el catálogo de Mercadona en `products`.
- Re-ejecutar sin cambios de precio → 0 filas nuevas en `price_history`, `last_seen` actualizado.
- Cambiar un precio (o simularlo) → 1 fila en `price_history`.
- Informe de cobertura con nº de productos/categorías/fallos.

## Verificación
```bash
python scraper/main.py scrape mercadona            # run completo
psql "$DATABASE_URL" -c "SELECT count(*) FROM products WHERE supermarket='mercadona';"
python scraper/main.py scrape mercadona            # segundo run
psql "$DATABASE_URL" -c "SELECT count(*) FROM price_history;"   # solo crece si cambian precios
```
