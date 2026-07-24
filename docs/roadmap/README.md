# Hoja de ruta — Stalvi

Reset y escalado coherente del proyecto. Cada fase tiene un **archivo de prompt autocontenido**: ábrelo en una sesión de Claude Code y pídele que lo ejecute. Se ejecutan en orden; F0 desbloquea el resto.

## Objetivo del producto (MVP)
1. Scrapear **Mercadona** de forma sólida y consistente (solo este súper para empezar).
2. **Tipología transversal + embeddings** para catalogar productos no inferibles por keywords.
3. **Modelo de datos de usuarios** + prototipo de qué información/funcionalidades ofrecer.
4. **Front** donde el usuario hace una lista de la compra y ve el gasto.

## Decisiones de arquitectura (fijadas)
| Área | Decisión | Alternativa reversible |
|------|----------|------------------------|
| Datos | **Postgres + pgvector** (vía **Supabase**: BD gestionada + pgvector + Auth) | Postgres self-hosted + FastAPI |
| Scrapers | **Solo Mercadona**; Dia/Carrefour/Consum archivados | Reactivar súpers más adelante |
| Embeddings | **Modelo local multilingüe** `intfloat/multilingual-e5-small` | API (OpenAI text-embedding-3) |
| Frontend | **Expo** (React Native + RN Web): web + iOS + Android | Flutter |

## Fases
| Fase | Archivo | Estado |
|------|---------|--------|
| F0 — Reset de arquitectura | [`00-reset.md`](./00-reset.md) | ☐ |
| F1 — Scraper Mercadona sólido | [`01-scraper-mercadona.md`](./01-scraper-mercadona.md) | ☐ |
| F2 — Taxonomía + embeddings + catalogación | [`02-taxonomia-embeddings.md`](./02-taxonomia-embeddings.md) | ☐ |
| F3 — Usuarios + funcionalidades | [`03-usuarios-datos.md`](./03-usuarios-datos.md) | ☐ |
| F4 — Frontend Expo | [`04-frontend-expo.md`](./04-frontend-expo.md) | ☐ |
| F5 — Calidad (transversal) | [`05-calidad.md`](./05-calidad.md) | ☐ |

## Estructura de repositorio objetivo
```
stalvi/
  scraper/          # ex scripts/ — Python: Mercadona + taxonomía + embeddings + upsert a Postgres
  db/               # migraciones SQL (productos, precios, usuarios, listas) + funciones RPC
  app/              # Expo (web + móvil)
  supabase/         # config, RLS, migraciones gestionadas
  docs/roadmap/     # estos archivos de prompts
```

## Cómo usar cada archivo
Cada `NN-*.md` contiene: **Objetivo**, **Contexto/estado actual**, **Tareas**, **Criterios de aceptación** y **Verificación**. Empieza una sesión nueva con:
> "Lee `docs/roadmap/NN-*.md` y ejecútalo. Antes de empezar, confirma conmigo las decisiones abiertas."
