# Rimuru Crypto Empire — Operations Runbook

## Quick Reference

| Service | Port | Endpoint |
|---------|------|----------|
| Data Ingest | 8000 | http://localhost:8000/health |
| Indicators | 8001 | http://localhost:8001/health |
| Strategy MA | 8010 | http://localhost:8010/health |
| Strategy RSI | 8011 | http://localhost:8011/health |
| Strategy Bollinger | 8012 | http://localhost:8012/health |
| Strategy Momentum | 8013 | http://localhost:8013/health |
| Strategy Volume | 8014 | http://localhost:8014/health |
| Strategy LSTM | 8015 | http://localhost:8015/health |
| Executor | 8020 | http://localhost:8020/health |
| Orchestrator | 8030 | http://localhost:8030/health |
| Backtester | 8040 | http://localhost:8040/health |
| Prometheus | 9090 | http://localhost:9090 |
| Grafana | 3000 | http://localhost:3000 (admin/rimuru2024) |

---

## Deploy Commands (Docker Compose)

```bash
# Deploy full team (paper mode — default)
PAPER_MODE=true docker compose -f docker-compose.team.yml up -d

# Deploy with live trading (CAUTION)
PAPER_MODE=false docker compose -f docker-compose.team.yml up -d

# Stop everything
docker compose -f docker-compose.team.yml down

# View logs
docker compose -f docker-compose.team.yml logs -f orchestrator
docker compose -f docker-compose.team.yml logs -f executor

# Rebuild specific service
docker compose -f docker-compose.team.yml build data-ingest
docker compose -f docker-compose.team.yml up -d data-ingest
```

## Deploy via Script

```bash
# Full deploy
./ops/deploy-rimuru.sh deploy

# Status check
./ops/deploy-rimuru.sh status

# Tail logs
./ops/deploy-rimuru.sh logs orchestrator

# Full restart
./ops/deploy-rimuru.sh restart

# Stop all
./ops/deploy-rimuru.sh stop
```

---

## Kubernetes Deploy

```bash
# Apply all K8s manifests
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/secrets.yaml      # Edit with real keys first!
kubectl apply -f infra/k8s/configmap.yaml
kubectl apply -f infra/k8s/deployments.yaml
kubectl apply -f infra/k8s/strategies.yaml
kubectl apply -f infra/k8s/monitoring.yaml

# Check pods
kubectl get pods -n rimuru-trading

# Logs
kubectl logs -f deployment/orchestrator -n rimuru-trading
```

---

## Emergency Procedures

### Emergency Stop (halt all trading)
```bash
curl -X POST http://localhost:8020/emergency-stop
```
This immediately stops the executor from placing any new orders.

### Check if Paper Mode is Active
```bash
curl http://localhost:8020/health | python -m json.tool
```
Look for `"paper_mode": true` in the response.

### Switch to Paper Mode
```bash
curl -X POST http://localhost:8020/paper-mode/true
```

### Kill the Orchestrator Scan Loop
```bash
curl -X POST http://localhost:8030/stop
```

### Full System Kill
```bash
docker compose -f docker-compose.team.yml down
# or
docker stop $(docker ps -q --filter "label=com.docker.compose.project=rimuru_empire")
```

---

## Monitoring

### Grafana Dashboard
- URL: http://localhost:3000
- Login: admin / rimuru2024
- Dashboard: Rimuru Trading Dashboard (auto-provisioned)

### Prometheus Queries
```promql
# Active trades today
rimuru_executor_daily_trades

# Current P&L
rimuru_executor_daily_pnl

# Service uptime
rimuru_orchestrator_uptime

# API call rate
rate(rimuru_data_ingest_kraken_calls[5m])
```

---

## Trading Configuration

### Strategy Weights (env vars)
```
WEIGHT_MA_CROSSOVER=0.20
WEIGHT_RSI=0.18
WEIGHT_BOLLINGER=0.15
WEIGHT_MOMENTUM=0.17
WEIGHT_VOLUME=0.12
WEIGHT_LSTM=0.18
```

### Risk Parameters
```
PAPER_MODE=true          # Paper trading (no real orders)
MAX_POSITION_PCT=0.80    # Max 80% of balance per position
DAILY_LOSS_LIMIT=10.0    # Stop trading after $10 daily loss
MAX_OPEN_POSITIONS=5     # Max concurrent positions
```

### Tradeable Pairs
Default: XXBTZUSD, XETHZUSD, SOLUSD, XDGUSD, PEPEUSD

---

## Architecture

```
                    ┌─────────────┐
                    │ Orchestrator│  (THE BRAIN)
                    │   :8030     │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────┴─────┐ ┌───┴───┐  ┌─────┴─────┐
        │Data Ingest│ │Indicat│  │  Executor  │
        │  :8000    │ │ :8001 │  │   :8020    │
        └─────┬─────┘ └───────┘  └────────────┘
              │
        ┌─────┴─────────────────────────────┐
        │         6 Strategy Services        │
        │ MA:8010  RSI:8011  BB:8012        │
        │ MOM:8013 VOL:8014  LSTM:8015      │
        └───────────────────────────────────┘
```

The Orchestrator fetches market data, computes indicators, fans out to all 6 strategies, aggregates signals with weighted ensemble + Kelly sizing, and executes via the Executor service.
