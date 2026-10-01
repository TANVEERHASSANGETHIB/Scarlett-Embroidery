# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.12

# ── Build wheels ─────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS builder
ARG REQUIREMENTS=prod
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=10
WORKDIR /build
COPY requirements/ requirements/
RUN pip wheel --wheel-dir /wheels -r requirements/${REQUIREMENTS}.txt

# ── Runtime ──────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

RUN apt-get update \
    && apt-get install -y --no-install-recommends netcat-openbsd \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app && useradd --system --gid app --home /app app

COPY --from=builder /wheels /wheels
RUN pip install /wheels/* && rm -rf /wheels

WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/
COPY docker/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh \
    && mkdir -p /app/media /app/private_media /app/staticfiles \
    && SECRET_KEY=build-only DATABASE_URL=sqlite:////tmp/build.db REDIS_URL=redis://localhost:6379/0 \
       python src/manage.py collectstatic --noinput \
    && chown -R app:app /app

USER app
WORKDIR /app/src
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "--proxy-headers", "config.asgi:application"]
