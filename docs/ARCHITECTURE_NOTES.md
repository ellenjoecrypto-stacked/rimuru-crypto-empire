# Architecture Notes — Rimuru Crypto Empire

## Component Design

### Core AI (`backend/core/rimuru_ai.py`)
`RimuruAICore` is a self-learning trading intelligence module combining:
- **Scikit-learn RandomForestClassifier** for signal generation from technical indicators
- **Ollama LLM integration** for natural-language market reasoning
- **Incremental learning** — retrains every 50 outcomes; persists model metadata to `data/ai_models/knowledge_base.json`

All async methods use `asyncio.get_event_loop().run_in_executor` to wrap synchronous `requests` calls, keeping the event loop unblocked.

### AI Service (`backend/api/ai_service.py`)
FastAPI service exposing the AI core over HTTP.  Model selection for `/ollama/query` is passed as a parameter to `query_ollama(prompt, model=...)` rather than mutating shared state, making it safe for concurrent requests.

### Rimuru Bridge (`backend/integrators/rimuru_bridge.py`)
Central data bus connecting scanner findings, live prices, and wallet balances into a unified pipeline for AI decision-making.  Uses a module-level `_ai_core` singleton so the model is loaded only once per process.

### Qrow Intelligence (`qrow/core/rimuru_intelligence.py`)
Event-scoring overseer with graduated risk levels (0–10) and response actions: `allow → flag → throttle → freeze_sandbox → quarantine → emergency_shutdown`.  Full event history is retained in `_event_history` for audit trails.

---

## Ollama Integration

| Environment | `OLLAMA_URL` |
|---|---|
| Local development | `http://localhost:11434` (default) |
| Docker Compose | `http://ollama:11434` |

Set the variable in `.env.security` (see `.env.security.example`).  The AI service and bridge both read `OLLAMA_URL` at startup.

### Adding a new Ollama model
1. Pull the model: `docker exec rimuru-ollama ollama pull <model-name>`
2. Set `OLLAMA_MODEL=<model-name>` in `.env.security`, or pass `model` in the `/ollama/query` request body.

---

## Environment Variable Reference

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server endpoint |
| `AI_MODEL_PATH` | `data/ai_models` | Directory for ML model persistence |
| `AI_SERVICE_PORT` | `8300` | AI service listen port |
| `CRYPTO_DB_PATH` | `data/crypto_findings.db` | SQLite findings database |
| `SCAN_BASE_DIR` | `~` (home dir) | Root directory for crypto scanner |
| `CDP_KEY_PATH` | `cdp_api_key.json` | Coinbase CDP key JSON file path |
| `RIMURU_SCAN_PATHS` | `` (empty) | Comma-separated project paths to scan |
| `RIMURU_DATA_OUTPUT_DIR` | `data` | Output directory for project scan findings |
| `VAULT_MASTER_PASSWORD` | *(must set)* | Master password for credential vault |
| `DATA_DIR` | `data` | Bridge data directory |

---

## Deployment Strategies

### Local (development)
```bash
pip install -r requirements.txt
python backend/api/ai_service.py
```

### Docker Compose (recommended)
```bash
cp .env.security.example .env.security
# Edit .env.security with real values
docker compose -f docker-compose.team.yml up -d
```

### Ollama in Docker
The `ollama` service is declared in `docker-compose.yml`.  The bridge and AI service communicate with it via `OLLAMA_URL=http://ollama:11434` (set in `.env.security`).

### CI/CD
The `.github/workflows/build-and-test.yml` pipeline:
1. **Lint** — `ruff check services/` + format check
2. **Unit Tests** — `pytest tests/`
3. **Build Docker Images** — one per microservice
4. **Compose Validation** — `docker compose -f docker-compose.team.yml config --quiet`  
   The `touch .env.security` step ensures CI passes even without a real secrets file.
