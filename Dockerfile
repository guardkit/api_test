# api_test — compose front-door image (Factory-2 S2).
# Runs alembic migrations then uvicorn src.main:app on :8901. Built as a NEW
# artifact; src/ is copied unmodified.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps: curl for the compose healthcheck. (asyncpg ships wheels — no
# build toolchain needed.)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first for layer caching.
COPY requirements/ ./requirements/
RUN pip install -r requirements/base.txt

# App source + migration assets.
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./alembic.ini
COPY docker-entrypoint.sh ./docker-entrypoint.sh
RUN chmod +x ./docker-entrypoint.sh

EXPOSE 8901

ENTRYPOINT ["./docker-entrypoint.sh"]
