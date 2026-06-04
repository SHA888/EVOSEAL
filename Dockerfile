ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1 \
    EV_DASHBOARD_PORT=9613

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g 10001 evoseal \
 && useradd -m -u 10001 -g 10001 -s /bin/bash evoseal

WORKDIR /app

# Install uv for fast dependency resolution
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
 && mv /root/.local/bin/uv /usr/local/bin/uv

# Copy pyproject.toml first for better layer caching
COPY pyproject.toml ./

# Install Python deps from pyproject.toml (include benchmarks extra for scripts)
RUN uv pip install -e ".[benchmarks]"

# Copy source
COPY . .

# Ensure entrypoint is executable
RUN chmod +x /app/scripts/docker/entrypoint.sh || true \
 && chown -R evoseal:evoseal /app

USER evoseal

# Expose dashboard port
EXPOSE 9613

# Healthcheck: dashboard HTTP (override EV_DASHBOARD_PORT as needed)
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os, sys, urllib.request; port = os.environ.get('EV_DASHBOARD_PORT','9613'); url = f'http://127.0.0.1:{port}/'; sys.exit(0 if (200 <= urllib.request.urlopen(url, timeout=3).getcode() < 400) else 1)"

VOLUME ["/app/checkpoints", "/app/data", "/app/reports"]

ENTRYPOINT ["/app/scripts/docker/entrypoint.sh"]
