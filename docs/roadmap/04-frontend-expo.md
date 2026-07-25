# F4 — Frontend Expo (web + móvil)

> Depende de F2 (búsqueda) y F3 (usuarios/listas). Construye la app donde el usuario hace la lista y ve el gasto.

---

## 🚀 Nota de arranque (leer primero — sesión nueva)

**Estado del proyecto:** F0–F3 hechos y commiteados en la rama `develop`. El backend
del MVP está completo: scrape Mercadona → Postgres → embeddings/búsqueda semántica →
usuarios/listas con RLS. Lee `CLAUDE.md` (raíz) y las memorias del proyecto para el
contexto completo antes de empezar.

**Levantar el entorno:**
```bash
docker compose up -d                     # Postgres 16 + pgvector (datos ya cargados: ~4.4k productos Mercadona)
source .venv/bin/activate                # o crea venv + pip install -r requirements.txt
# .env ya tiene DATABASE_URL (owner) y APP_DATABASE_URL (rol app_user, RLS aplica)
```

**Lo que YA existe y hay que consumir (no reimplementar):**
- **Datos**: `products` (name, price, price_per_unit, unit, brand, master_category_id, image_url, embedding), `price_history`.
- **Usuarios/listas** (F3): `profiles`, `shopping_lists`, `shopping_list_items`; RPC `list_total(list_id)` y `product_price_history(product_id)`; **RLS** vía `current_app_user()` (local: `SET app.user_id`; Supabase: `auth.uid()`).
- **Roles**: `stalvi` (owner, salta RLS) para el scraper; `app_user` (`APP_DATABASE_URL`) para la app — con este la RLS protege los datos de usuario.
- **Búsqueda semántica** (F2): `scraper/embeddings/search.py:search_products(query, k)`. ⚠️ Embebe la query con fastembed (**Python**) → el front NO puede calcular el embedding en JS; hace falta un servicio que lo exponga.

**Decisiones a confirmar con el usuario ANTES de escribir código (usar AskUserQuestion):**
1. **Backend/Auth.** La búsqueda necesita embeber la query en Python y la RLS necesita
   fijar la identidad. Opción recomendada: **un API fino en FastAPI** (Python) que
   reutilice `embeddings/search.py` + `db.py`, conecte como `app_user`, haga
   `SET app.user_id` por request y exponga `/search`, `/lists`, `/lists/{id}/items`,
   `/lists/{id}/total`. Alternativas: Supabase (cloud o CLI local) con Auth+RPC reales,
   o Supabase solo para Auth + este API para búsqueda.
2. **Auth concreto.** JWT propio del API vs Supabase Auth. (Si se elige FastAPI, un
   login simple contra `profiles` para el MVP puede bastar; Supabase Auth entra al desplegar.)
3. **UI kit** compatible con RN Web (p.ej. Tamagui o React Native Paper) y gestión de
   estado (React Query recomendado para datos remotos).

**Sugerencia de ejecución (para no agotar contexto):**
- Partir F4 en **dos tramos**: (A) API + scaffold Expo + auth + conexión; (B) pantallas
  buscar/lista + gasto total en vivo. Idealmente un tramo por sesión.
- Redirigir la salida de `npx create-expo-app`, `npm install` y `expo start` a un
  fichero y mirar solo el final (`> /tmp/x.log 2>&1; tail`), nunca volcarla entera.
- Levantar el dev server con `run_in_background` y observar con Monitor.

**Criterio de "hecho" del MVP:** usuario entra (login) → busca "leche" → añade a la
lista → el total refleja el gasto y se actualiza al cambiar cantidades; el build
móvil (iOS/Android) compila.

---

## Objetivo
App **Expo (React Native + React Native Web)** con una sola base de código para **web + iOS + Android**. MVP: login, buscar productos, construir lista de la compra y ver el **gasto total** en vivo. Se prioriza web; el móvil debe compilar aunque no se publique aún.

## Contexto / estado actual
- **No existe frontend.** Directorio objetivo: `app/`.
- Backend: Supabase (Auth + Postgres + RPC). La búsqueda semántica (`search_products`) viene de F2; listas y `list_total` de F3.
- Decisión de stack: Expo con Expo Router.

## Tareas
1. **Inicializar** app Expo con Expo Router en `app/`; configurar export web. Cliente `@supabase/supabase-js` con `SUPABASE_URL` / `SUPABASE_ANON_KEY`.
2. **Auth:** pantallas de registro/login con Supabase Auth; sesión persistida; rutas protegidas.
3. **Buscar productos:** input → `search_products(query)`; lista de resultados con nombre, precio, precio/unidad, imagen.
4. **Lista de la compra:** añadir/quitar productos, ajustar cantidad, marcar como comprado. Persistir en `shopping_lists` / `shopping_list_items`.
5. **Gasto total:** mostrar el total en vivo (vía `list_total` o cálculo cliente), actualizándose al cambiar cantidades.
6. **Validar multiplataforma:** `expo start --web` funcional; `expo run:android` / `run:ios` compilan.

## Decisiones abiertas
- ¿La app habla directa a Supabase (recomendado para MVP) o vía una API propia?
- Gestión de estado: recomendado ligero (Zustand / React Query) — confirmar.
- Diseño/UI kit (recomendado: algo compatible con RN Web, p.ej. Tamagui o RN Paper).

## Criterios de aceptación
- Usuario entra (login), busca "leche", añade a la lista, y el **total refleja el gasto** y se actualiza al cambiar cantidad.
- La misma base compila a iOS y Android sin ramificar código de negocio.

## Verificación
```bash
cd app && npx expo start --web     # flujo login -> buscar -> añadir -> ver total
npx expo run:android               # compila (o EAS build)
```

---

## Progreso

**Decisiones fijadas (con el usuario):**
- **Backend/Auth:** API fino en **FastAPI** (`api/`) que reutiliza el modelo de
  embeddings (búsqueda) y el esquema con RLS. La app NO habla directa a Postgres.
- **Auth:** **JWT propio** del API (login contra `profiles`). Supabase Auth entra
  al desplegar.
- **UI/estado:** **React Native Paper** + **React Query**. Sesión persistida con
  AsyncStorage.

**Tramo A — hecho:**
- `api/`: FastAPI con auth (register/login/me), `/search`, y CRUD de listas/items
  + `/lists/{id}/total`. Conexión `app_user` con `set_config('app.user_id')` →
  RLS aplica; endpoints de auth usan owner. Migración `0004_auth.sql`
  (`profiles.password_hash`). Probado end-to-end (total correcto, 401 sin token).
- `app/`: scaffold Expo (SDK 57) + Expo Router. Login/registro, rutas protegidas,
  "Mis listas" (crear/abrir) y detalle de lista con cantidades y **gasto total en
  vivo**. `tsc --noEmit` limpio y `expo export --platform web` OK.

**Tramo B — pendiente:**
- Pantalla de **búsqueda** de productos y añadir a la lista desde el detalle.
- Validar `expo run:android` / `run:ios` (build nativo / EAS).

**Deuda F2 — RESUELTA (2026-07-25):** la relevancia de `/search` estaba rota por
dos causas: (1) los embeddings del catálogo se calcularon con el pooling antiguo
de fastembed (CLS) mientras las consultas usaban el nuevo (mean) → se re-embebió
todo el catálogo con fastembed 0.8.0 (mean, el correcto para MiniLM); (2) las
consultas de una sola palabra caían en un "hub" de nombres cortos ("leche"→Brócoli)
→ se añadieron prefijos estilo e5 (`query:` / `passage:`, búsqueda asimétrica) en
`embeddings/model.py`. Catalogación sin regresión (eval top-1 ~0.52, top-3 ~0.69).
Casos débiles que quedan: palabras sueltas ambiguas o sin tilde ("agua", "platano");
mejorables con búsqueda híbrida keyword+vector en F5.
