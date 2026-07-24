# CLAUDE.md — Stalvi

Guía para trabajar en este repositorio.

## Qué es
App para recopilar precios de supermercados y ofrecer al usuario una lista de la
compra con el gasto estimado. **Empezamos solo por Mercadona.**

## Arquitectura (objetivo)
```
Mercadona API → Scraper (Python) → normaliza → upsert → Postgres + pgvector
                                       │                     │
                 embeddings locales ───┘   catalogación en cascada
                 (multilingual-e5)         (keyword → kNN → revisión)
                                                             │
   App Expo (web + iOS + Android) ← Supabase Auth + RLS + RPC ┘
```

### Decisiones fijadas
- **Datos:** Postgres + pgvector como fuente de verdad única. Dev local con `docker-compose`; cloud con **Supabase** (a partir de F3, por su Auth).
- **Scrapers:** solo **Mercadona**. Dia/Carrefour/Consum y el backend Firestore antiguo están archivados en la rama `archive`.
- **Embeddings:** modelo **local multilingüe** `intfloat/multilingual-e5-small` (dim 384).
- **Frontend:** **Expo** (React Native + RN Web) para una sola base de código web + móvil.

## Estructura
```
scraper/          # Python: scraper Mercadona, taxonomía y catalogación (ex scripts/)
  main.py         # CLI: scrape / categories
  scrapers/       # BaseScraper + mercadona/ + categories/ + http_client + models + validators
db/               # Esquema Postgres: init/ (extensiones) + migrations/ (F1+)
docs/roadmap/     # Hoja de ruta por fases (00-reset … 05-calidad)
app/              # (F4) App Expo — aún no creada
supabase/         # (F3) Config Supabase — aún no creada
docker-compose.yml
requirements.txt
```

## Comandos
```bash
# Base de datos local
docker compose up -d

# Entorno Python
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Scraper (desde la raíz del repo)
python scraper/main.py scrape mercadona --test --dry-run   # prueba rápida
python scraper/main.py scrape mercadona                    # completo (persistencia: F1)
python scraper/main.py categories stats mercadona          # estado de mapeos
```
La persistencia a Postgres se implementa en F1; hasta entonces usa `--dry-run`.

## Convenciones
- Código y comentarios en **español** (coherente con el existente).
- Cada nuevo scraper hereda de `scrapers/base.py:BaseScraper`.
- La hoja de ruta manda: antes de una tarea grande, mira el archivo de `docs/roadmap/`
  correspondiente. F0 (reset) ya está hecho.
