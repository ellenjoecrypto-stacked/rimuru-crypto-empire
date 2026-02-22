# Rimuru Crypto Empire — Architecture Notes

Canonical reference for design decisions, deployment strategies, and system
architecture. Extracted from original design sessions and development notes.

---

## 1. Architectural Vision

The **Rimuru Crypto Empire** is a multi-agent, microservice-based system for
autonomous cryptocurrency intelligence, trading, and asset management. Its
guiding principles are:

- **AI-first decision making** — all trading signals pass through the Rimuru AI
  Core before execution.
- **Self-learning** — the ML layer accumulates trade outcomes and retrains
  periodically without human intervention.
- **Zero-trust security** — credentials are never stored in plaintext; all
  secrets are injected via environment variables or the SecureVault component.
- **Separation of concerns** — discovery (scanner), intelligence (AI Core /
  Qrow), execution (bots), and monitoring (Watchtower) are independent services
  connected by the Rimuru Bridge.

---

## 2. Core Components

### 2.1 Rimuru AI Core (`backend/core/rimuru_ai.py`)

- Random-Forest classifier for buy/sell/hold signal generation.
- Incremental learning: accumulates `LearningData` points and retrains every
  50 outcomes. Model version is bumped on each retrain cycle.
- Ollama integration for LLM-backed contextual reasoning alongside the ML
  model. Falls back gracefully to ML-only when Ollama is unavailable.
- Knowledge persistence: `knowledge_base.json`, `performance_history.json`,
  and `learning_data.json` are written to `DATA_DIR/ai_models/` on each
  retrain.

### 2.2 Rimuru Bridge (`backend/integrators/rimuru_bridge.py`)

Central data bus. Ingests scanner findings, live prices, and wallet balances,
then routes everything to the AI Core for decisions.

- Uses a **module-level singleton** (`_ai_core`) so learned state is preserved
  across decision calls within a process.
- Logs all events, decisions, and portfolio snapshots to a local SQLite
  database (`rimuru_bridge.db`).

### 2.3 Qrow Orchestrator (`qrow/`)

Secondary intelligence layer focused on narrative trading, airdrop farming,
and on-chain monitoring.

- **Rimuru Intelligence** (`qrow/core/rimuru_intelligence.py`) — event risk
  scorer and action recommender. Supports graduated actions:
  `allow → flag → throttle → quarantine → freeze_sandbox → emergency_shutdown`.
- **Watchtower** — observes all bot events and delegates to Rimuru Intelligence.
- **Shadow Briefing** — daily/on-demand intelligence report aggregating
  narrative, sentiment, and clustering data.

### 2.4 Project Scanner (`backend/integrators/project_scanner.py`)

Scans configurable local directories for crypto assets (wallets, API keys,
seed phrases). All scan paths are supplied via environment variables
(`RIMURU_SCAN_PATHS`, `RIMURU_DATA_OUTPUT_DIR`) — no hardcoded paths.

### 2.5 Comprehensive Crypto Scanner (`backend/tools/full_crypto_scanner.py`)

Deep file-system scanner that writes findings to a SQLite database.
Database path: `CRYPTO_DB_PATH` env var (default: `data/crypto_findings.db`).
Base scan directory: `SCAN_BASE_DIR` env var (default: `~`).

---

## 3. Persona System

The system ships with five AI personas that can be activated per-session:

| Persona | Role |
|---------|------|
| **Rimuru** | Primary overseer — analytical, strategic |
| **Ellen Joe** | Public-facing assistant — friendly, concise |
| **Raga** | Risk manager — conservative, detail-oriented |
| **Senku** | Research analyst — data-driven, verbose |
| **Jin Wu** | Execution specialist — fast, direct |

Rimuru operates in two modes:
- **Professional mode** — standard trading intelligence and portfolio management.
- **Dark Ninja mode** — advanced threat detection and counter-intelligence
  (activated by Watchtower on high-risk events).

---

## 4. Security Design

| Concern | Approach |
|---------|----------|
| Credential storage | `DPAPI` (Windows) / `keyring` (Linux/macOS); never plaintext |
| Data at rest | AES-256-GCM encryption for sensitive JSON blobs |
| Key derivation | Argon2id for password-based keys |
| Audit logging | WORM-compliant append-only log; signed with HMAC-SHA256 |
| Import safety | All optional dependencies raise `ImportError` with install instructions — no `os.system()` calls |
| Path safety | All filesystem paths supplied via `os.getenv()` — no hardcoded OS-specific paths |

---

## 5. Ollama Integration

- Default model: `llama2` (overridable via `OLLAMA_MODEL` env var).
- Default URL: `http://localhost:11434` (overridable via `OLLAMA_URL`).
- Ollama is **optional** — the system degrades gracefully to ML-only mode.
- Prompt design: market data + technical indicators → structured analysis
  requesting a BUY/SELL/HOLD recommendation with confidence.

---

## 6. Deployment Strategies

### 6.1 ACOP (Autonomous Crypto Operations Platform)

Full Docker Compose stack (`docker-compose.team.yml`). Services:

- `price-service` (port 8100) — live price feeds.
- `wallet-service` (port 8200) — balance aggregation.
- `ai-service` (port 8300) — Rimuru AI Core REST API.
- `bot-service` (port 8400) — trading bot orchestration.
- `ollama` — local LLM inference.

### 6.2 SecureVault

Standalone credential manager service. Wraps OS keyring / DPAPI and exposes a
local REST API for other services to fetch secrets without passing them through
environment variables in production.

### 6.3 Rimuru Assistant (Deployment Checker)

Lightweight health-check script that verifies all services are reachable before
the main trading loop starts. Reports status for: Ollama, price service, wallet
service, AI service, and exchange APIs.

---

## 7. Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIR` | `data` | Root data directory |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama service URL |
| `OLLAMA_MODEL` | `llama2` | Default Ollama model |
| `PRICE_SERVICE_URL` | `http://price-service:8100` | Price engine URL |
| `WALLET_SERVICE_URL` | `http://wallet-service:8200` | Wallet service URL |
| `AI_SERVICE_URL` | `http://ai-service:8300` | AI service URL |
| `BOT_SERVICE_URL` | `http://bot-service:8400` | Bot service URL |
| `CRYPTO_DB_PATH` | `data/crypto_findings.db` | Scanner database path |
| `SCAN_BASE_DIR` | `~` | Base directory for file-system scans |
| `CDP_KEY_PATH` | `cdp_api_key.json` | Coinbase CDP key file path |
| `RIMURU_SCAN_PATHS` | _(empty)_ | Colon-separated extra scan paths |
| `RIMURU_DATA_OUTPUT_DIR` | `data/project_findings` | Output dir for project scanner |
| `KRAKEN_API_KEY` | _(required)_ | Kraken API key |
| `KRAKEN_SECRET_KEY` | _(required)_ | Kraken API secret |
