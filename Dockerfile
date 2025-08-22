# syntax=docker/dockerfile:1.7

ARG BASE_IMAGE=python:3.10-slim
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
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

# Copy requirements first for better layer caching
COPY requirements/ requirements/
COPY requirements.txt ./

# Install Python deps (use constraints if available)
RUN python -m pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt -c requirements/constraints.txt || \
    pip install --no-cache-dir -r requirements.txt

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
    CMD python - <<'PY' \
import os, sys, urllib.request
port = os.environ.get('EV_DASHBOARD_PORT','9613')
url = f"http://127.0.0.1:{port}/"
try:
    with urllib.request.urlopen(url, timeout=3) as r:
        sys.exit(0 if 200 <= r.getcode() < 400 else 1)
except Exception:
    sys.exit(1)
PY

VOLUME ["/app/checkpoints", "/app/data", "/app/reports"]

ENTRYPOINT ["/app/scripts/docker/entrypoint.sh"]
