# Scraper de Mercadona

Scraping de productos de Mercadona con normalización de categorías a una taxonomía
maestra. La persistencia a Postgres se implementa en F1
(ver [`../docs/roadmap/01-scraper-mercadona.md`](../docs/roadmap/01-scraper-mercadona.md)).

> Nota: en el reset de arquitectura (F0) se retiraron los scrapers de Dia/Carrefour/Consum
> y el backend Firestore. Siguen disponibles en la rama `archive`.

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

Hasta que F1 añada la persistencia a Postgres, usa siempre `--dry-run`.

## Documentación

- **CLI**: [USAGE.md](USAGE.md)
- **Scrapers (arquitectura)**: [docs/SCRAPERS.md](docs/SCRAPERS.md) *(contiene referencias a
  scrapers ya archivados; la parte de Mercadona sigue vigente)*

## Estructura

- **main.py** — CLI (`scrape`, `categories`)
- **scrapers/** — `BaseScraper`, `mercadona/`, `categories/` (taxonomía + mapper), `http_client`, `models`, `validators`
- **scrapers/data/** — taxonomía maestra y mapeos de categorías (JSON)
