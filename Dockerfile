# ==============================================================================
# NormaCore API — Dockerfile
# ==============================================================================

FROM python:3.12-slim

# Prevents Python from writing .pyc files and buffers stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency manifests first for layer caching
COPY pyproject.toml .
COPY uv.lock .
COPY src/normacore/__init__.py src/normacore/__init__.py

# Install runtime dependencies only (no dev deps)
RUN uv sync --no-dev --frozen

# Copy application source
COPY src/ src/

# Create logs directory
RUN mkdir -p logs

# Non-root user for security
RUN adduser --disabled-password --gecos "" normacore && \
    chown -R normacore:normacore /app
USER normacore

EXPOSE 8000

CMD ["uv", "run", "normacore-api"]
