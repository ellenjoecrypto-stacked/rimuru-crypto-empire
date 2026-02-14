FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY services/executor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/shared/ /app/shared/
COPY services/executor/app.py /app/
COPY _SENSITIVE/ /app/_SENSITIVE/
RUN useradd -m rimuru && mkdir -p /app/data/executor && chown -R rimuru:rimuru /app
USER rimuru
ENV PYTHONUNBUFFERED=1 PAPER_MODE=true
HEALTHCHECK --interval=60s --timeout=10s CMD curl -f http://localhost:8020/health || exit 1
EXPOSE 8020
CMD ["python", "app.py"]
