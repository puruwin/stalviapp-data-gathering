# api/ — API FastAPI del MVP (F4)

API fino en Python que la app Expo consume. Reutiliza el backend F0–F3:

- **Búsqueda semántica** (F2): embebe la query con `scraper/embeddings/model.py`
  (fastembed, Python) — por eso hace falta este servicio y el front NO puede
  calcular el embedding en JS.
- **Datos y RLS** (F3): se conecta como `app_user` (`APP_DATABASE_URL`) y fija la
  identidad con `set_config('app.user_id', <uuid>)` para que la RLS aplique.
- **Auth**: JWT propio (login simple contra `profiles`). Ver decisión en
  `docs/roadmap/04-frontend-expo.md`. Al desplegar se sustituye por Supabase Auth.

## Arranque

```bash
docker compose up -d                     # Postgres con datos
source .venv/bin/activate
pip install -r requirements.txt          # deps del scraper (embeddings)
pip install -r api/requirements.txt      # deps del API
uvicorn api.main:app --reload            # desde la raíz del repo → http://127.0.0.1:8000
```

Requiere en `.env`: `DATABASE_URL`, `APP_DATABASE_URL` y `API_JWT_SECRET`.
Docs interactivas en `http://127.0.0.1:8000/docs`.

## Endpoints

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| POST | `/auth/register` | — | Registro (email + password) → JWT |
| POST | `/auth/login` | — | Login → JWT |
| GET | `/auth/me` | ✔ | Perfil del token |
| GET | `/search?q=&k=` | ✔ | Búsqueda semántica de productos |
| GET | `/lists` | ✔ | Listas del usuario (con nº items y total) |
| POST | `/lists` | ✔ | Crear lista |
| GET | `/lists/{id}` | ✔ | Lista + items (con datos de producto) |
| PATCH | `/lists/{id}` | ✔ | Renombrar lista |
| DELETE | `/lists/{id}` | ✔ | Borrar lista |
| DELETE | `/lists/{id}/items` | ✔ | Vaciar lista (borra todos los items) |
| POST | `/lists/{id}/items` | ✔ | Añadir/actualizar item (upsert por producto) |
| PATCH | `/lists/{id}/items/{iid}` | ✔ | Cambiar cantidad / marcar comprado |
| DELETE | `/lists/{id}/items/{iid}` | ✔ | Quitar item |
| GET | `/lists/{id}/total` | ✔ | Gasto total (RPC `list_total`) |

La auth va por header `Authorization: Bearer <token>`.

## Notas

- Los endpoints de auth (`register`/`login`) usan la conexión **owner** porque
  aún no hay sesión y la RLS de `profiles` bloquearía. El resto usa `app_user`.
- **Búsqueda:** los embeddings de F2 están afectados por un cambio de pooling de
  fastembed (CLS → mean); la relevancia es baja hasta re-embeber el catálogo con
  el modelo/pooling correctos (tarea de F2/F5, ver roadmap).
