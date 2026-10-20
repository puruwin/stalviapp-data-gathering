# Scrapers de supermercados

Scraping de Mercadona y el catálogo regional unificado de Consum, con normalización de categorías,
persistencia en Postgres e histórico de precios. Para Consum, consultar
[comandos, alcance y trazabilidad](../docs/consum.md).

> Los adaptadores antiguos de Dia/Carrefour/Consum y Firestore siguen en `archive`.
> Consum tiene una implementación nueva activa, con paginación por offset.

## Requisitos

- Python 3.10 o superior
- `pip install -r ../requirements.txt`

## Uso rápido

```bash
# desde la raíz del repo
python scraper/main.py scrape mercadona --test --dry-run   # prueba rápida sin persistir
python scraper/main.py scrape mercadona --dry-run          # scrape completo sin persistir
python scraper/main.py categories pending mercadona        # categorías pendientes de mapeo
python scraper/main.py categories stats mercadona          # estadísticas de mapeos
python scraper/main.py categories taxonomy                 # ver taxonomía maestra
```

`--dry-run` evita persistir productos, históricos y mapeos. Para importar datos,
aplica las migraciones y ejecuta el comando sin esa opción.

## Documentación

- **CLI**: [USAGE.md](USAGE.md)
- **Scrapers (arquitectura)**: [docs/SCRAPERS.md](docs/SCRAPERS.md) *(contiene referencias a
  scrapers ya archivados; la parte de Mercadona sigue vigente)*

## Estructura

- **main.py** — CLI (`scrape`, `categories`)
- **scrapers/** — `BaseScraper`, `mercadona/`, `consum/`, `categories/` (taxonomía + mapper), `http_client`, `models`, `validators`
- **scrapers/data/** — taxonomía maestra y mapeos de categorías (JSON)
