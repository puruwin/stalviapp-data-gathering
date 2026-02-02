# Scraping de supermercados

Scraping de productos de supermercados (DIA, Mercadona, Carrefour) con normalización de categorías e ingestión en Firebase.

## Requisitos

- Python 3.8 o superior
- Dependencias: `pip install -r requirements.txt` (desde `scripts/`)
- **Carrefour**: para evitar 403 por fingerprint TLS, `requirements.txt` incluye `curl_cffi`; si no lo instalas, el scraper usará `requests` (puede seguir devolviendo 403).

## Documentación

- **Uso del CLI**: [USAGE.md](USAGE.md) – Comandos, opciones, gestión de categorías y variables de entorno.
- **Funcionamiento de los scrapers**: [docs/SCRAPERS.md](docs/SCRAPERS.md) – Arquitectura común, modelos de datos y particularidades de DIA, Mercadona y Carrefour.

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
- **scrapers/** – Scrapers por supermercado (DIA, Mercadona, Carrefour), modelos, HTTP, validación, ingestión
- **scrapers/docs/** – Documentación técnica de scrapers ([SCRAPERS.md](docs/SCRAPERS.md))
- **scrapers/data/** – Taxonomía maestra y mapeos de categorías (JSON)
- **Firebase** – Colección `products` con historial de precios (`price_history`)

Los productos se envían al endpoint configurado en `FIREBASE_INGEST_URL`; cada producto incluye `category_path` y `master_category_id` para comparativas entre cadenas.
