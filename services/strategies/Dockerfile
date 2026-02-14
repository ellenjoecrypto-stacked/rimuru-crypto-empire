FROM python:3.11-slim
ARG STRATEGY_DIR=ma_crossover
ARG PORT=8010
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY services/strategies/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/shared/ /app/shared/
COPY services/strategies/${STRATEGY_DIR}/app.py /app/
RUN useradd -m rimuru && chown -R rimuru:rimuru /app
USER rimuru
ENV PYTHONUNBUFFERED=1 PORT=${PORT}
HEALTHCHECK --interval=60s --timeout=10s CMD curl -f http://localhost:${PORT}/health || exit 1
EXPOSE ${PORT}
CMD ["python", "app.py"]
