# ============================================
# RIMURU AUTO-TRADER v2.0 — TRADE GOD EDITION
# Docker Container for 24/7 Autonomous Trading
# ============================================

FROM python:3.11-slim

LABEL maintainer="ellenjoecrypto@gmail.com"
LABEL version="2.0.0-TRADE-GOD"
LABEL description="Rimuru Crypto Empire Auto-Trader — 7 strategies, self-adapting"

# System setup
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app user (non-root for security)
RUN useradd -m -s /bin/bash rimuru

# Working directory
WORKDIR /app

# Copy the auto-trader
COPY rimuru_auto_trader.py /app/
COPY _SENSITIVE/ /app/_SENSITIVE/

# Create data directory for state persistence
RUN mkdir -p /app/data/auto_trader && chown -R rimuru:rimuru /app

# Switch to non-root user
USER rimuru

# Health check — verify the script can import
HEALTHCHECK --interval=300s --timeout=10s --retries=3 \
    CMD python -c "from rimuru_auto_trader import VERSION; print(f'OK v{VERSION}')" || exit 1

# Environment variables for Docker mode
ENV RIMURU_DOCKER=1
ENV RIMURU_LIVE=1
ENV PYTHONUNBUFFERED=1

# Default: run in LIVE mode
CMD ["python", "-u", "rimuru_auto_trader.py", "--live"]
