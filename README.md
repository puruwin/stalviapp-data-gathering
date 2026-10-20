# Stalvi

App para recopilar precios de supermercados (**solo Mercadona** por ahora) y ofrecer
al usuario una lista de la compra con el gasto estimado.

```
Mercadona API → Scraper (Python) → Postgres + pgvector
                     │                    │
        embeddings locales ───┘  catalogación en cascada
                                          │
        App Expo (web + móvil) ← API FastAPI (JWT + RLS) ┘
```

Este README reúne los comandos para arrancar el proyecto. Para el detalle de cada
parte mira `api/README.md`, `app/README.md` y `docs/roadmap/`. Convenciones y
arquitectura en `CLAUDE.md`.

## Requisitos
- Docker + Docker Compose (Postgres con pgvector)
- Python 3.12+
- Node.js 20+ (para la app Expo)

## 1. Configuración inicial (una vez)
```bash
cp .env.example .env          # ajusta credenciales si hace falta
cp app/.env.example app/.env  # EXPO_PUBLIC_API_URL (por defecto http://127.0.0.1:8000)

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt      # deps del scraper + embeddings
pip install -r api/requirements.txt  # deps del API
```

## 2. Base de datos
```bash
docker compose up -d          # levanta Postgres → localhost:5432
bash db/migrate.sh            # aplica db/migrations/*.sql (idempotente)
```

## 3. Datos (scraper + embeddings) — opcional
Necesario solo la primera vez para poblar el catálogo (la búsqueda no da resultados
sin datos). Con la BD levantada y el venv activo:
```bash
python scraper/main.py scrape mercadona    # scrapea y persiste en Postgres
python scraper/embed.py all                # embeddings + prototipos + catalogación
```
Prueba rápida sin persistir: `python scraper/main.py scrape mercadona --test --dry-run`

## 4. API (FastAPI)
Desde la raíz del repo, con el venv activo y la BD levantada:
```bash
uvicorn api.main:app --reload   # → http://127.0.0.1:8000  (docs en /docs)
```
Requiere en `.env`: `DATABASE_URL`, `APP_DATABASE_URL` y `API_JWT_SECRET`.

## 5. App (Expo — web + móvil)
En otra terminal, con el API arriba:
```bash
cd app
npm install                   # una vez
npx expo start --web          # web (prioridad actual)
# npx expo start --android    # emulador Android (usar http://10.0.2.2:8000)
# npx expo start --ios        # simulador iOS
```
> **Prioridad web.** El build nativo iOS/Android está aplazado; se pule primero la web.

## Resumen de puertos
| Servicio | URL / Puerto |
|----------|--------------|
| Postgres | `localhost:5432` |
| API FastAPI | `http://127.0.0.1:8000` (docs en `/docs`) |
| App Expo (web) | `http://localhost:8081` |

## Tests
```bash
python -m pytest scraper/tests/   # tests del scraper / embeddings
cd app && npx tsc --noEmit        # typecheck de la app
```

## Estructura
```
scraper/   # Python: scraper Mercadona, taxonomía, embeddings, upsert a Postgres
api/       # API FastAPI (auth JWT, búsqueda, listas) que consume la app
app/       # App Expo (Expo Router + React Native Paper)
db/        # esquema Postgres: init/ + migrations/ + migrate.sh
docs/      # hoja de ruta por fases (docs/roadmap/)
supabase/  # config Supabase (cloud, para Auth al desplegar)
```
