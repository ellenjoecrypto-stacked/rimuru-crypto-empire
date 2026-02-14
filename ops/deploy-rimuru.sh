#!/bin/bash
# ============================================================
# Rimuru Crypto Empire — Deployment Script
# Deploy the full microservices trading team
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.team.yml"

# Defaults
PAPER_MODE="${PAPER_MODE:-true}"
ACTION="${1:-deploy}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════╗"
    echo "║     RIMURU CRYPTO EMPIRE — DEPLOY TEAM      ║"
    echo "║     Paper Mode: $PAPER_MODE                        ║"
    echo "╚══════════════════════════════════════════════╝"
    echo -e "${NC}"
}

health_check() {
    local name=$1
    local url=$2
    if curl -sf --connect-timeout 5 "$url" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} $name"
        return 0
    else
        echo -e "  ${RED}✗${NC} $name"
        return 1
    fi
}

deploy() {
    banner
    echo -e "${YELLOW}[1/4] Pulling latest code...${NC}"
    cd "$PROJECT_DIR"
    git pull origin master 2>/dev/null || echo "  (git pull skipped)"

    echo -e "${YELLOW}[2/4] Building Docker images...${NC}"
    PAPER_MODE=$PAPER_MODE docker compose -f "$COMPOSE_FILE" build

    echo -e "${YELLOW}[3/4] Starting services...${NC}"
    PAPER_MODE=$PAPER_MODE docker compose -f "$COMPOSE_FILE" up -d

    echo -e "${YELLOW}[4/4] Health checks (waiting 15s for startup)...${NC}"
    sleep 15

    local failed=0
    health_check "Data Ingest"      "http://localhost:8000/health" || ((failed++))
    health_check "Indicators"       "http://localhost:8001/health" || ((failed++))
    health_check "Strategy MA"      "http://localhost:8010/health" || ((failed++))
    health_check "Strategy RSI"     "http://localhost:8011/health" || ((failed++))
    health_check "Strategy Bollinger" "http://localhost:8012/health" || ((failed++))
    health_check "Strategy Momentum"  "http://localhost:8013/health" || ((failed++))
    health_check "Strategy Volume"    "http://localhost:8014/health" || ((failed++))
    health_check "Strategy LSTM"      "http://localhost:8015/health" || ((failed++))
    health_check "Executor"         "http://localhost:8020/health" || ((failed++))
    health_check "Orchestrator"     "http://localhost:8030/health" || ((failed++))
    health_check "Backtester"       "http://localhost:8040/health" || ((failed++))
    health_check "Prometheus"       "http://localhost:9090/-/healthy" || ((failed++))
    health_check "Grafana"          "http://localhost:3000/api/health" || ((failed++))

    echo ""
    if [ $failed -eq 0 ]; then
        echo -e "${GREEN}All 13 services deployed successfully!${NC}"
    else
        echo -e "${RED}$failed service(s) failed health check${NC}"
    fi
}

teardown() {
    echo -e "${YELLOW}Stopping all Rimuru services...${NC}"
    docker compose -f "$COMPOSE_FILE" down
    echo -e "${GREEN}All services stopped.${NC}"
}

status() {
    echo -e "${CYAN}=== Rimuru Team Status ===${NC}"
    docker compose -f "$COMPOSE_FILE" ps
    echo ""
    echo -e "${CYAN}=== Health Checks ===${NC}"
    health_check "Data Ingest"      "http://localhost:8000/health" || true
    health_check "Indicators"       "http://localhost:8001/health" || true
    health_check "Executor"         "http://localhost:8020/health" || true
    health_check "Orchestrator"     "http://localhost:8030/health" || true
    health_check "Backtester"       "http://localhost:8040/health" || true
    health_check "Prometheus"       "http://localhost:9090/-/healthy" || true
    health_check "Grafana"          "http://localhost:3000/api/health" || true
}

logs() {
    local service="${2:-}"
    if [ -n "$service" ]; then
        docker compose -f "$COMPOSE_FILE" logs -f "$service"
    else
        docker compose -f "$COMPOSE_FILE" logs -f --tail=50
    fi
}

case "$ACTION" in
    deploy)  deploy ;;
    stop)    teardown ;;
    status)  status ;;
    logs)    logs "$@" ;;
    restart) teardown && deploy ;;
    *)
        echo "Usage: $0 {deploy|stop|status|logs [service]|restart}"
        echo "  Environment: PAPER_MODE=true|false (default: true)"
        exit 1
        ;;
esac
