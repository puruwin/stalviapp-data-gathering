# app/ — App Expo (F4)

App **Expo (React Native + RN Web)** del MVP de Stalvi: login, listas de la compra
y gasto total. Una sola base de código para web, iOS y Android.

## Stack
- **Expo Router** (rutas por ficheros en `app/`).
- **React Native Paper** (UI, Material 3).
- **React Query** (`@tanstack/react-query`) para datos remotos.
- Sesión (JWT) persistida con AsyncStorage.

Habla con el **API FastAPI** (`../api/`), no directamente con Postgres.

## Arranque
```bash
cd app
cp .env.example .env          # ajusta EXPO_PUBLIC_API_URL si hace falta
npm install
npx expo start --web          # web; --android / --ios para móvil
```
Requiere el API levantado (`uvicorn api.main:app --reload` desde la raíz) y la BD.

## Estructura
```
app/                 # rutas (Expo Router)
  _layout.tsx        # providers (Paper, React Query, Auth) + Stack
  index.tsx          # redirección según sesión
  login.tsx          # login / registro
  (app)/             # zona autenticada (guardia de sesión)
    index.tsx        # Mis listas (crear / abrir)
    list/[id].tsx    # detalle de lista + gasto total en vivo
src/
  config.ts          # URL del API
  theme.ts           # tema Paper
  api/               # cliente HTTP + tipos
  auth/AuthContext   # sesión + persistencia
```

## Estado (F4)
- **Tramo A (hecho):** API + scaffold + auth (login/registro, sesión persistida,
  rutas protegidas) + listas (crear, ver, ajustar cantidades, total en vivo).
- **Tramo B (pendiente):** búsqueda de productos y añadir a la lista desde el
  detalle; validación `expo run:android` / `run:ios`.
