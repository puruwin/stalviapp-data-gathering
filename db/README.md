# db/ — Base de datos

Fuente de verdad del esquema Postgres (con `pgvector`).

```
db/
  init/         # Se ejecuta al crear la BD vacía (extensiones). Lo aplica docker-compose.
  migrations/   # Migraciones de esquema versionadas (F1 en adelante).
```

## Desarrollo local

```bash
docker compose up -d          # levanta Postgres 16 + pgvector en localhost:5432
docker compose down           # detiene (conserva el volumen de datos)
docker compose down -v        # detiene y BORRA los datos
```

Credenciales por defecto (ver `docker-compose.yml` y `.env.example`):
`postgresql://stalvi:stalvi@localhost:5432/stalvi`

Las extensiones (`vector`, `pg_trgm`) solo se crean automáticamente la **primera vez**
que se inicializa el volumen. Si ya tenías el volumen creado, aplícalas a mano:

```bash
docker compose exec db psql -U stalvi -d stalvi -f /docker-entrypoint-initdb.d/001_extensions.sql
```

El esquema de tablas (`products`, `price_history`, `categories`, ...) se define en
`db/migrations/` durante F1 (`docs/roadmap/01-scraper-mercadona.md`).
