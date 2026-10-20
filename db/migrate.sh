#!/usr/bin/env bash
# Aplica db/migrations/*.sql en orden sobre el Postgres de docker-compose.
# Las migraciones son idempotentes (CREATE ... IF NOT EXISTS), así que
# reaplicarlas es seguro.
set -euo pipefail
cd "$(dirname "$0")/.."

for f in db/migrations/*.sql; do
    echo ">> aplicando $f"
    docker compose exec -T db psql -U stalvi -d stalvi -v ON_ERROR_STOP=1 < "$f"
done

echo "OK — migraciones aplicadas"
