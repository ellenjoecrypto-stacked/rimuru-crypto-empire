# 🚀 RIMURU CRYPTO EMPIRE - Deployment Guide

Complete guide for deploying and running the Rimuru Crypto Empire system.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Manual Installation](#manual-installation)
4. [Docker Deployment](#docker-deployment)
5. [Configuration](#configuration)
6. [First Run Setup](#first-run-setup)
7. [Production Deployment](#production-deployment)
8. [Monitoring & Maintenance](#monitoring--maintenance)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Hardware Requirements
- **Minimum**: 4GB RAM, 20GB Storage, 2 CPU cores
- **Recommended**: 8GB RAM, 50GB Storage, 4 CPU cores
- **Optional**: GPU for AI training (NVIDIA with CUDA)

### Software Requirements
- **Docker**: 20.10+ 
- **Docker Compose**: 2.0+
- **Operating System**: Linux, macOS, or Windows with WSL2
- **Browser**: Chrome, Firefox, or Edge (for dashboard)

### Network Requirements
- Stable internet connection
- Open ports: 3000 (frontend), 8000 (backend), 11434 (Ollama)
- No strict firewall blocking outgoing connections

---

## Quick Start

### Automated Setup (Recommended)

```bash
# 1. Clone the repository
git clone <repository-url>
cd rimuru_empire

# 2. Run the deployment script
chmod +x deploy.sh
./deploy.sh

# 3. Access the dashboard
# Open http://localhost:3000 in your browser
```

That's it! The system will:
- Set up Docker containers
- Pull Ollama AI model
- Start all services
- Create necessary directories

---

## Manual Installation

### Step 1: Clone and Prepare

```bash
# Clone repository
git clone <repository-url>
cd rimuru_empire

# Copy environment template
cp .env.example .env

# Create directories
mkdir -p data/bot_states data/ai_models logs
```

### Step 2: Configure Environment

Edit `.env` file:

```bash
nano .env
```

**Critical Settings** (change these!):
```bash
# Security - USE STRONG PASSWORDS!
VAULT_MASTER_PASSWORD=your_super_secure_vault_password_here

# Database
DB_PASSWORD=your_database_password_here

# Trading defaults
PAPER_TRADING=true  # Start with paper trading
DEFAULT_MAX_POSITION_PCT=0.10
DEFAULT_MAX_DAILY_LOSS_PCT=0.02
```

### Step 3: Docker Deployment

```bash
# Build and start all services
docker-compose up -d --build

# Check service status
docker-compose ps

# View logs
docker-compose logs -f
```

### Step 4: Verify Installation

```bash
# Check API health
curl http://localhost:8000/health

# Check frontend
curl http://localhost:3000

# Check Ollama
curl http://localhost:11434/api/tags
```

---

## Docker Deployment

### Services Overview

| Service | Port | Purpose | Status |
|---------|------|---------|--------|
| frontend | 3000 | Web dashboard | ✅ Required |
| backend | 8000 | API server | ✅ Required |
| redis | 6379 | Caching | ✅ Required |
| ollama | 11434 | AI processing | ✅ Optional |
| postgres | 5432 | Database | ⚪ Optional (SQLite default) |

### Docker Commands

```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d backend

# Stop all services
docker-compose down

# Restart service
docker-compose restart backend

# View logs
docker-compose logs -f backend

# Scale services
docker-compose up -d --scale backend=2

# Update and rebuild
docker-compose pull
docker-compose up -d --build
```

### Resource Limits

Edit `docker-compose.yml` to add resource limits:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

---

## Configuration

### Exchange API Keys

1. **Get API Keys from Exchange**:
   - Binance: https://www.binance.com/en/my/settings/api-management
   - Kraken: https://www.kraken.com/u/settings/api
   - Coinbase: https://www.coinbase.com/settings/api

2. **Configure Permissions** (CRITICAL):
   - ✅ Read Account Info
   - ✅ Spot Trading
   - ✅ Futures Trading (if needed)
   - ❌ Withdrawals (NEVER enable)
   - ✅ IP Whitelist (recommended)

3. **Add Keys to Rimuru**:
   - Go to Dashboard → Security
   - Click "Add Exchange"
   - Enter exchange name and API keys
   - Enable sandbox mode for testing

### Risk Management

Edit risk parameters in `.env`:

```bash
# Position sizing
DEFAULT_MAX_POSITION_PCT=0.10        # 10% of portfolio per trade

# Loss limits
DEFAULT_MAX_DAILY_LOSS_PCT=0.02      # 2% daily loss limit
DEFAULT_STOP_LOSS_PCT=0.05           # 5% stop loss
DEFAULT_TAKE_PROFIT_PCT=0.10        # 10% take profit

# Bot limits
MAX_CONCURRENT_BOTS=10
MAX_OPEN_POSITIONS=5
```

### AI Configuration

```bash
# Ollama model
OLLAMA_MODEL=llama2

# AI confidence threshold
AI_MIN_CONFIDENCE=0.7

# Learning parameters
AI_LEARNING_RATE=0.01
AI_RETRAIN_INTERVAL=100  # trades
```

---

## First Run Setup

### 1. Access Dashboard

```
http://localhost:3000
```

### 2. Security Setup

1. Go to **Security** section
2. Add your first exchange:
   - Name: `test_binance`
   - Type: `Binance`
   - API Key: [Your API key]
   - Secret Key: [Your secret key]
   - Sandbox Mode: ✅ Enable
3. Test connection

### 3. Create First Bot

1. Go to **Bots** section
2. Click "Create Bot"
3. Configure:
   - Name: `test_spot_bot`
   - Exchange: `test_binance`
   - Symbol: `BTC/USDT`
   - Strategy: `RSI Reversal`
   - Paper Trading: ✅ Enable
4. Click "Create Bot"
5. Start the bot

### 4. Monitor Performance

- Dashboard: Overview of all activity
- Trading: Live price charts and order entry
- Bots: Individual bot status and performance
- Security: Credential management and audit logs

---

## Production Deployment

### Security Hardening

1. **Environment Variables**:
```bash
# Use strong passwords
VAULT_MASTER_PASSWORD=$(openssl rand -base64 32)
DB_PASSWORD=$(openssl rand -base64 32)

# Enable production mode
DEBUG=false
PAPER_TRADING=false
```

2. **Firewall Configuration**:
```bash
# Only allow necessary ports
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw allow 22/tcp    # SSH
ufw enable
```

3. **SSL/TLS Setup** (using Nginx):
```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:3000;
    }
}
```

4. **Database Migration** (SQLite → PostgreSQL):

```yaml
# docker-compose.yml
postgres:
  image: postgres:15-alpine
  environment:
    POSTGRES_DB: rimuru_db
    POSTGRES_USER: rimuru_user
    POSTGRES_PASSWORD: ${DB_PASSWORD}
  volumes:
    - postgres-data:/var/lib/postgresql/data
```

### Backup Strategy

```bash
# Automated backup script
#!/bin/bash
BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup data
tar -czf $BACKUP_DIR/data_$DATE.tar.gz data/

# Backup database
docker-compose exec -T postgres pg_dump rimuru_db > $BACKUP_DIR/db_$DATE.sql

# Keep last 7 days
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
```

### Monitoring Setup

```bash
# Install monitoring tools
pip install prometheus-client
pip install sentry-sdk

# Configure health checks
curl http://localhost:8000/health
```

---

## Monitoring & Maintenance

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Bot status
curl http://localhost:8000/api/bots

# Risk summary
curl http://localhost:8000/api/risk/summary

# Exchange connections
curl http://localhost:8000/api/exchanges
```

### Log Management

```bash
# View logs
docker-compose logs -f backend

# Export logs
docker-compose logs backend > logs/backend.log

# Rotate logs (add to docker-compose.yml)
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

### Performance Monitoring

Monitor these metrics:
- CPU usage < 80%
- Memory usage < 80%
- API response time < 100ms
- Bot execution frequency
- Trade success rate

### Regular Maintenance

**Daily**:
- Check dashboard for errors
- Review bot performance
- Monitor P&L

**Weekly**:
- Review audit logs
- Check API key usage
- Backup data

**Monthly**:
- Rotate API keys
- Update dependencies
- Review risk parameters
- Performance analysis

**Quarterly**:
- Security audit
- Disaster recovery test
- System optimization

---

## Troubleshooting

### Common Issues

#### 1. Docker Containers Won't Start

```bash
# Check logs
docker-compose logs

# Restart containers
docker-compose restart

# Rebuild containers
docker-compose down
docker-compose up -d --build
```

#### 2. Frontend Not Loading

```bash
# Check if backend is running
curl http://localhost:8000/health

# Check nginx configuration
docker-compose logs frontend

# Rebuild frontend
docker-compose up -d --build frontend
```

#### 3. Bots Not Starting

```bash
# Check exchange connection
curl http://localhost:8000/api/exchanges

# Check bot logs
docker-compose logs backend | grep -i bot

# Verify API keys
# Go to Security → Check exchange connection
```

#### 4. Ollama Not Responding

```bash
# Restart Ollama
docker-compose restart ollama

# Pull model manually
docker-compose exec ollama ollama pull llama2

# Check Ollama logs
docker-compose logs ollama
```

#### 5. Database Errors

```bash
# Reset database (WARNING: deletes all data)
docker-compose down -v
docker-compose up -d

# Backup first!
tar -czf backup.tar.gz data/
```

### Getting Help

1. **Check Logs**:
   ```bash
   docker-compose logs -f
   ```

2. **Review Documentation**:
   - README.md
   - API docs: http://localhost:8000/docs

3. **GitHub Issues**:
   - Report bugs
   - Feature requests

4. **Community Support**:
   - Discord channel
   - Forum discussions

---

## Next Steps

After deployment:

1. ✅ Test with paper trading mode
2. ✅ Configure exchange API keys
3. ✅ Create and test trading bots
4. ✅ Monitor performance for 1-2 weeks
5. ✅ Gradually increase position sizes
6. ✅ Enable real trading (when ready)

---

## Support & Resources

- **Documentation**: See README.md
- **API Reference**: http://localhost:8000/docs
- **Troubleshooting**: See section above
- **Community**: Join our Discord

---

**⚠️ IMPORTANT**: Always start with paper trading and small amounts. Never trade more than you can afford to lose.

**🚀 Ready to build your crypto empire? Start trading today!**