# ── Stage 1: Dependency builder ──────────────────────────────────────────────
FROM python:3.11-slim AS builder
WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ build-essential libpq-dev libssl-dev libffi-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install all deps (web3 needs gcc for some C extensions)
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Production image ────────────────────────────────────────────────
FROM python:3.11-slim AS production
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl tini libssl3 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

# Non-root user for security
RUN groupadd -r botuser && useradd -r -g botuser -u 1000 botuser
RUN mkdir -p /app/logs /app/models /app/reports /app/data && \
    chown -R botuser:botuser /app

COPY --chown=botuser:botuser . .

# Remove secrets from image
RUN rm -f .env

USER botuser

EXPOSE 8000 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "src.main"]
