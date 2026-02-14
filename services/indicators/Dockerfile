FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY services/indicators/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/shared/ /app/shared/
COPY services/indicators/app.py /app/
RUN useradd -m rimuru && chown -R rimuru:rimuru /app
USER rimuru
ENV PYTHONUNBUFFERED=1
HEALTHCHECK --interval=60s --timeout=10s CMD curl -f http://localhost:8001/health || exit 1
EXPOSE 8001
CMD ["python", "app.py"]
