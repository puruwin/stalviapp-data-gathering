# Scraping de supermercados

Scraping de productos de supermercados (DIA, Mercadona) con normalización de categorías e ingestión en Firebase.

## Requisitos

- Python 3.8 o superior
- Dependencias: `pip install -r requirements.txt` (desde `scripts/`)

## Documentación de uso

**Ver [USAGE.md](USAGE.md)** para:

- Comandos del CLI (`scrape`, `categories`)
- Opciones (`--test`, `--dry-run`, etc.)
- Gestión de categorías (pending, stats, map, taxonomy)
- Variables de entorno y flujo típico

## Resumen rápido

```bash
cd scripts

# Scrape de DIA (envía a Firebase)
python main.py scrape dia

# Prueba sin enviar
python main.py scrape dia --test --dry-run

# Ver categorías pendientes de mapeo
python main.py categories pending dia

# Ver taxonomía maestra
python main.py categories taxonomy
```

## Estructura

- **main.py** – CLI unificado (scrape + categories)
- **scrapers/** – Scrapers por supermercado (DIA, Mercadona), modelos, HTTP, validación, ingestión
- **scrapers/data/** – Taxonomía maestra y mapeos de categorías (JSON)
- **Firebase** – Colección `products` con historial de precios (`price_history`)

Los productos se envían al endpoint configurado en `FIREBASE_INGEST_URL`; cada producto incluye `category_path` y `master_category_id` para comparativas entre cadenas.
