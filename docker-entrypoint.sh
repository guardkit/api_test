#!/bin/sh
# api_test container entrypoint (Factory-2 S2).
# Provisions the schema (alembic upgrade head) then serves the app. depends_on
# service_healthy in docker-compose.yml guarantees the db is accepting
# connections before this runs, so no manual wait loop is needed.
set -e

echo "[entrypoint] running database migrations (alembic upgrade head)..."
alembic upgrade head

echo "[entrypoint] starting uvicorn on 0.0.0.0:8901..."
exec uvicorn src.main:app --host 0.0.0.0 --port 8901
