# Uso del scraper

CLI para scrapear Mercadona, normalizar categorías y persistir productos e
histórico de precios en Postgres.

---

## Requisitos

- Python 3.10+
- `pip install -r ../requirements.txt`
- Postgres en marcha: `docker compose up -d` (desde la raíz) y `.env` con `DATABASE_URL`
  (copia `.env.example` a `.env`). Aplica el esquema con `bash db/migrate.sh`.

## Ejecución

Desde la **raíz del repo**:

```bash
python scraper/main.py <comando> [opciones]
```

---

## Comandos

### 1. Scrapear productos

```bash
python scraper/main.py scrape mercadona [opciones]
```

| Opción | Descripción |
|--------|-------------|
| `--test` | Modo test: 5 categorías, 3 productos por categoría |
| `--categories N` | Límite de categorías a procesar |
| `--products N` | Límite de productos por categoría |
| `--dry-run` | No persiste (solo scrapea y valida) |
| `-v`, `--verbose` | Log más detallado |

**Ejemplos:**

```bash
# Prueba rápida sin persistir
python scraper/main.py scrape mercadona --test --dry-run

# Scrape completo (persiste en Postgres)
python scraper/main.py scrape mercadona

# Solo 8 categorías
python scraper/main.py scrape mercadona --categories 8
```

Al persistir se detectan altas y cambios de precio: cada producto nuevo genera una
fila *baseline* en `price_history` y cada cambio de precio una fila adicional. Los
productos ya vistos sin cambios solo actualizan `last_seen`. El resumen muestra
`nuevos / precio_cambiado / sin_cambios`.

---

### 2. Gestión de categorías

Las categorías de Mercadona se mapean a una **taxonomía maestra**. Los mapeos se
guardan en `scrapers/data/mappings/mercadona.json` (se migrarán a Postgres en F2).

```bash
python scraper/main.py categories pending mercadona    # pendientes de mapeo
python scraper/main.py categories stats mercadona      # conteo por estado
python scraper/main.py categories map mercadona <source_id> <master_id>   # mapear a mano
python scraper/main.py categories taxonomy             # ver taxonomía maestra
```

Ejemplo: `python scraper/main.py categories map mercadona 112 aceites.aceites`

---

### 3. Embeddings y catalogación (F2)

Genera embeddings de productos (modelo local ONNX multilingüe, dim 384), construye
un prototipo por categoría y cataloga por similitud los productos sin categoría.

```bash
python scraper/embed.py products      # embeddings de productos (incremental)
python scraper/embed.py prototypes    # prototipo por categoría (centroide/texto)
python scraper/embed.py classify       # cataloga por kNN los productos sin categoría
python scraper/embed.py eval           # evalúa la catalogación (hold-out + barrido de umbral)
python scraper/embed.py search "leche desnatada sin lactosa"   # búsqueda semántica
python scraper/embed.py all            # products + prototypes + classify
```

La catalogación es en cascada: primero la inferencia por keyword (durante el scrape,
a nivel de categoría), y para lo que quede sin categoría, kNN contra los prototipos;
si no supera el umbral de confianza, queda en `catalog_status='pending'` (revisión).

---

## Variables de entorno

| Variable | Descripción |
|----------|-------------|
| `DATABASE_URL` | Conexión a Postgres (ver `.env.example`) |

---

## Consultas útiles en la BD

```sql
SELECT count(*) FROM products;                          -- productos persistidos
SELECT count(*) FROM price_history;                     -- puntos de precio
SELECT * FROM price_history WHERE product_id = 'mercadona_XXXX' ORDER BY changed_at;
```

---

## Datos locales

- **Taxonomía maestra:** `scrapers/data/master_taxonomy.json`
- **Mapeos:** `scrapers/data/mappings/mercadona.json`
- **Categorías crudas (referencia):** `scrapers/data/raw_cats/mercadona.json`
