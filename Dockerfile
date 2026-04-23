# ── Stage 1: Dependency builder ──────────────────────────────────────────────
FROM python:3.11-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ build-essential libpq-dev libssl-dev libffi-dev curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Production image ────────────────────────────────────────────────
FROM python:3.11-slim AS production
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl tini && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local
RUN groupadd -r botuser && useradd -r -g botuser -u 1000 botuser
RUN mkdir -p /app/logs /app/models /app/reports && chown -R botuser:botuser /app
COPY --chown=botuser:botuser . .
RUN chmod +x scripts/health_check.sh 2>/dev/null || true
USER botuser
EXPOSE 8000 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "src.main"]
