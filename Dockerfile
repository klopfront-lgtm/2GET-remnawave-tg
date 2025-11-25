# ====================================
# Stage 1: Builder
# ====================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Copy only requirements first for better caching
COPY requirements.txt .

# Install dependencies with cache mount for faster rebuilds
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# ====================================
# Stage 2: Production
# ====================================
FROM python:3.11-slim

# Metadata labels
LABEL maintainer="remnawave-tg-shop"
LABEL version="1.0"
LABEL description="Telegram VPN Subscription Bot"
LABEL org.opencontainers.image.source="https://github.com/machka-pasla/remnawave-tg-shop"

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Install curl for health checks and clean up in single layer
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /root/.cache

# Create non-root user and set ownership
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app

# Copy application code
COPY --chown=botuser:botuser . .

# Switch to non-root user
USER botuser

# Health check endpoint (requires /health endpoint in web_server.py)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Expose web server port (default 8080)
EXPOSE 8080

# Start application
CMD ["python", "main.py"]
