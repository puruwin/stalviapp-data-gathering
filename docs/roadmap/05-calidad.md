# F5 — Calidad (transversal)

> No es una fase secuencial: se aplica de forma incremental durante F1–F4. Este archivo recoge el estándar de calidad mínimo.

## Objetivo
Tests, CI, linting y observabilidad básica para que el proyecto sea mantenible y los runs de scraping sean fiables.

## Contexto / estado actual
- **No hay tests ni CI** hoy. Solo ESLint en `functions/` (que se deprecia).

## Tareas
1. **Tests Python (`scraper/`):**
   - Unit: normalización de Mercadona (fixtures de PLP reales de `bruno/` o dumps), validadores, lógica de upsert/cambio de precio.
   - Catalogación: test de la cascada keyword→kNN contra un set pequeño etiquetado.
2. **Tests app (`app/`):** componentes clave (lista, total) y un smoke e2e del flujo principal.
3. **CI (GitHub Actions):**
   - Job Python: `ruff`/`black` + `pytest`.
   - Job app: lint + typecheck + test.
   - (Opcional) job de scrape en `--dry-run` para detectar cambios de la API de Mercadona.
4. **Observabilidad:** logging estructurado en el scraper; informe de cada run (productos/categorías/fallos, cambios de precio); alerta si la cobertura cae respecto al run anterior.
5. **Linting/format:** `ruff` + `black` (Python), `eslint` + `prettier` (app). Pre-commit opcional.

## Criterios de aceptación
- `pytest` verde en local y CI.
- CI ejecuta lint + tests en cada push/PR.
- Cada run de scrape emite un informe con métricas de cobertura.

## Verificación
```bash
cd scraper && pytest
# y CI en verde en el PR
```
