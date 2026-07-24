# F4 — Frontend Expo (web + móvil)

> Depende de F2 (búsqueda) y F3 (usuarios/listas). Construye la app donde el usuario hace la lista y ve el gasto.

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
