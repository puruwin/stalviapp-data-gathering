# F0 — Limpieza y reset de arquitectura

> Prerrequisito de todas las demás fases. Deja el repo limpio, con una única arquitectura de datos (Postgres/Supabase) y foco en Mercadona.

## Objetivo
Retirar la deuda heredada, archivar los scrapers que no usamos, reorganizar el repo a la estructura objetivo y dejar un Postgres con `pgvector` accesible. Al terminar, el CLI de Mercadona sigue funcionando y el terreno está listo para F1.

## Contexto / estado actual
- Hay **4 scrapers** (`scripts/scrapers/{mercadona,dia,carrefour,consum}/`). Solo queremos Mercadona activo.
- **Deuda a limpiar:** `scripts/dia_scrap.py` (legacy), carpeta `prompts temp/` (dumps), `scripts/database.py` + `scripts/database_schema.sql` (Postgres abandonado — el schema se reescribe en F1), backend Firestore `functions/` (se mantiene en rama hasta migrar a Postgres).
- `requirements.txt` está en `.gitignore` (línea a eliminar); no hay `.env.example`.
- Decisión: **Postgres + pgvector vía Supabase**. Frontend Expo. Embeddings locales.

## Tareas
1. **Archivar súpers no usados:** mover `scripts/scrapers/{dia,carrefour,consum}/` y sus mappings a `scraper/archive/` (o crear rama `legacy-scrapers` y borrarlos de `master`). Actualizar `scripts/main.py` para que `get_scraper()` solo ofrezca `mercadona`. Mantener `http_client_curl_cffi.py` solo si Mercadona lo necesita (no lo necesita → archivar).
2. **Reorganizar estructura:** renombrar `scripts/` → `scraper/`. Crear directorios vacíos `db/`, `app/`, `supabase/`. Ajustar imports/paths y el CLI.
3. **Eliminar deuda:** borrar `dia_scrap.py`, `prompts temp/`, `database.py` (su lógica se reescribe en F1). Retirar `.eslintrc`/`functions` a rama si se decide, o dejarlos con nota de "deprecated, pendiente migración".
4. **Dependencias:** quitar `requirements.txt` del `.gitignore` y comprometerlo con las deps reales (`requests`, `python-dotenv`, `psycopg[binary]` o `sqlalchemy`, `sentence-transformers` se añade en F2). Crear `.env.example` con `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`.
5. **Infra de datos:** crear proyecto Supabase (o `docker-compose.yml` con Postgres 16 + `pgvector` para local). Habilitar extensión: `CREATE EXTENSION IF NOT EXISTS vector;`. Documentar cómo conectarse.
6. **CLAUDE.md raíz:** documentar arquitectura, estructura de carpetas, comandos (scrape, migraciones), convenciones de código y las 4 decisiones fijadas.

## Decisiones abiertas (confirmar antes de empezar)
- ¿Supabase gestionado o Postgres local con docker-compose para desarrollo? (recomendado: Supabase para tener Auth+pgvector de una).
- ¿Archivar en carpeta `archive/` o en rama `legacy-scrapers`? (recomendado: rama, para no arrastrar código muerto).

## Criterios de aceptación
- El repo solo tiene a Mercadona en el flujo activo; los demás súpers no aparecen en `main.py`.
- Estructura `scraper/ db/ app/ supabase/ docs/` en su sitio, imports arreglados.
- `requirements.txt` y `.env.example` comprometidos; `.gitignore` sin `requirements.txt`.
- Postgres con `pgvector` accesible y documentado.
- `CLAUDE.md` raíz presente.

## Verificación
```bash
python scraper/main.py scrape mercadona --test --dry-run   # corre sin errores
psql "$DATABASE_URL" -c "SELECT extname FROM pg_extension WHERE extname='vector';"  # devuelve 'vector'
```
