# 🚀 RIMURU CRYPTO EMPIRE

A comprehensive, production-ready cryptocurrency automation platform with AI-powered trading, DeFi farming, and multi-exchange support.

## ✨ Features

### 🤖 Multi-Strategy Trading Bots
- **Spot Trading Bot** with 5 strategies (MA Crossover, RSI Reversal, MACD Momentum, Bollinger Breakout, Grid Trading)
- **DeFi Farming Bot** for yield farming across protocols (Uniswap, Aave, Curve)
- **Arbitrage Bot** for cross-exchange arbitrage opportunities
- **Staking Bot** for automated staking management

### 🧠 AI-Powered Intelligence
- **Rimuru AI Core** with machine learning for signal generation
- **Ollama Integration** for advanced AI reasoning
- **Self-Learning System** that improves from trade outcomes
- **Pattern Recognition** in market data
- **Strategy Optimization** based on performance

### 🛡️ Military-Grade Security
- **AES-256-GCM Encryption** for all credentials
- **Secure Credential Vault** with audit logging
- **2FA Support** for enhanced security
- **Rate Limiting** and brute force protection
- **Emergency Stop** mechanism for immediate halting

### 📊 Modern Dashboard
- **Real-Time Updates** via WebSocket
- **Interactive Charts** with TradingView integration
- **Portfolio Tracking** with P&L visualization
- **Bot Status Monitoring** with live metrics
- **Risk Management Center** with alerts

### 🔗 Multi-Exchange Support
- Binance, Kraken, Coinbase, Bybit, OKX
- Unified API interface
- Connection pooling and retry logic
- Rate limiting and error handling

## 📋 Prerequisites

- Docker & Docker Compose
- 4GB+ RAM
- 20GB+ Storage
- Stable internet connection
- (Optional) GPU for AI training

## 🚀 Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd rimuru_empire

# Copy environment file
cp .env.example .env

# Edit .env with your configuration
nano .env
```

### 2. Configure Security

Edit `.env` and set a strong vault password:

```bash
VAULT_MASTER_PASSWORD=your_super_secure_password_here
```

### 3. Deploy with Docker

```bash
# Build and start all services
docker-compose up -d

# Check service status
docker-compose ps
```

### 4. Access the Dashboard

- **Frontend Dashboard**: http://localhost:3000
- **API Gateway**: http://localhost:5000/docs
- **Price Service**: http://localhost:8100/docs
- **Wallet Service**: http://localhost:8200/docs
- **AI Service**: http://localhost:8300/docs
- **Bot Service**: http://localhost:8400/docs
- **Ollama AI**: http://localhost:11434

## 🧱 Microservice Architecture

Each service runs in its own Docker container. Mix and match based on your needs:

| Service | Port | Dockerfile | Description |
|---------|------|-----------|-------------|
| **Price Service** | 8100 | `Dockerfile.price` | Live prices from CoinGecko, CoinCap, Kraken, Etherscan |
| **Wallet Service** | 8200 | `Dockerfile.wallet` | Multi-chain balance tracker (ETH, BTC, SOL + ERC-20) |
| **AI Service** | 8300 | `Dockerfile.ai` | Rimuru AI Core + Ollama LLM trading decisions |
| **Bot Service** | 8400 | `Dockerfile.bot` | Trading, farming, collection bots with approval workflow |
| **API Gateway** | 5000 | `Dockerfile.api` | Unified REST API + WebSocket gateway |
| **Asset Scanner** | — | `Dockerfile.scanner` | File scanner for wallets, API keys, seeds |
| **Pipeline** | — | `Dockerfile.pipeline` | Scanner ↔ Price enrichment bridge |
| **Frontend** | 3000 | `frontend/Dockerfile` | React dashboard |
| **Ollama** | 11434 | (official image) | Local LLM for AI analysis |
| **PostgreSQL** | 5432 | (official image) | Persistent data store |
| **Redis** | 6379 | (official image) | Caching layer |

### Run Individual Services

```bash
# Just the price engine
docker-compose up -d price-service

# Price + Wallet tracking
docker-compose up -d price-service wallet-service

# Full AI trading stack
docker-compose up -d price-service ai-service bot-service ollama

# Everything
docker-compose up -d
```

## 📁 Project Structure

```
rimuru_empire/
├── backend/
│   ├── api/              # FastAPI endpoints
│   │   ├── gateway.py        # Unified API gateway
│   │   ├── price_service.py  # Price REST + WebSocket (port 8100)
│   │   ├── ai_service.py     # AI decision API (port 8300)
│   │   └── main.py           # Legacy API
│   ├── bots/             # Trading bot implementations
│   │   ├── bot_service.py    # Bot management API (port 8400)
│   │   ├── base_bot.py       # Base bot class
│   │   └── spot_trader.py    # Spot trading strategies
│   ├── core/             # Core functionality
│   │   ├── rimuru_ai.py      # AI core with ML + Ollama
│   │   ├── exchange_manager.py # Multi-exchange connector
│   │   └── risk_manager.py   # Risk assessment engine
│   ├── services/         # Standalone services
│   │   ├── price_engine.py   # Multi-source price engine
│   │   └── wallet_service.py # Multi-chain wallet tracker
│   ├── integrators/      # Data bridges
│   │   ├── rimuru_bridge.py      # Central nervous system
│   │   ├── scanner_price_pipeline.py # Scanner ↔ Price
│   │   └── project_scanner.py    # Project directory scanner
│   ├── tools/            # Utility tools
│   │   ├── full_crypto_scanner.py  # File-level crypto scanner
│   │   ├── check_balances.py      # Balance checker
│   │   └── generate_report.py     # Report generator
│   ├── security/         # Security modules
│   │   ├── credential_vault.py     # Encrypted credential storage
│   │   ├── credential_vault_hardened.py
│   │   └── secrets_manager.py      # Secrets management
│   ├── database/         # Database models
│   ├── Dockerfile.price     # Price service container
│   ├── Dockerfile.wallet    # Wallet service container
│   ├── Dockerfile.ai        # AI service container
│   ├── Dockerfile.bot       # Bot service container
│   ├── Dockerfile.scanner   # Asset scanner container
│   ├── Dockerfile.pipeline  # Pipeline container
│   └── Dockerfile.api       # API gateway container
├── frontend/
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── services/     # API services & WebSocket
│   │   ├── hooks/        # Custom React hooks
│   │   └── utils/        # Frontend utilities
│   └── public/           # Static assets
├── config/               # Configuration files
├── data/                 # Data storage (gitignored)
├── logs/                 # Application logs
├── docker-compose.yml    # Full orchestration
└── .gitignore            # Security-first gitignore
```

## 🔧 Configuration

### Exchange Setup

1. Navigate to the Dashboard
2. Go to **Security** → **Add Exchange**
3. Enter your exchange API keys
4. **IMPORTANT**: Never enable withdrawal permissions
5. Enable IP whitelisting on the exchange

### Bot Configuration

1. Go to **Bots** → **Create Bot**
2. Select bot type (Spot, DeFi, Arbitrage, Staking)
3. Configure trading parameters:
   - Trading pair (e.g., BTC/USDT)
   - Strategy selection
   - Risk parameters
   - Position sizing
4. Start with **Paper Trading** mode first

### Risk Management

Configure risk limits in the **Security** section:

```yaml
max_position_size: 10%      # Maximum position size
max_daily_loss: 2%          # Maximum daily loss
stop_loss: 5%               # Stop loss percentage
take_profit: 10%            # Take profit percentage
emergency_stop: enabled     # Enable emergency stop
```

## 🤖 Using the AI Core

### Ollama Setup

The system includes Ollama for local AI processing:

```bash
# Pull a model
docker-compose exec ollama ollama pull llama2

# Test the connection
docker-compose exec backend python -c "
import asyncio
from backend.core.rimuru_ai import RimuruAICore
ai = RimuruAICore()
print(asyncio.run(ai.check_ollama_connection()))
"
```

### AI Features

- **Market Analysis**: AI analyzes market conditions and provides recommendations
- **Signal Generation**: ML models generate trading signals with confidence scores
- **Pattern Recognition**: Identifies trading patterns in historical data
- **Continuous Learning**: System learns from trade outcomes

## 📊 Monitoring

### Dashboard Metrics

- Portfolio value and P&L
- Active bot status
- Open positions
- Risk indicators
- Performance charts

### Logs

View application logs:

```bash
# Backend logs
docker-compose logs -f backend

# Frontend logs
docker-compose logs -f frontend

# All services
docker-compose logs -f
```

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Bot status
curl http://localhost:8000/api/bots

# Risk summary
curl http://localhost:8000/api/risk/summary
```

## 🛡️ Security Best Practices

1. **NEVER enable withdrawal permissions** on API keys
2. **Use IP whitelisting** on your exchange accounts
3. **Enable 2FA** everywhere possible
4. **Rotate API keys** regularly (every 90 days)
5. **Monitor audit logs** for suspicious activity
6. **Keep the vault password** secure and backed up
7. **Start with paper trading** before using real funds
8. **Set strict loss limits** and respect them

## ⚠️ Warnings

### Financial Risk
- Cryptocurrency trading is highly volatile
- You can lose your entire investment
- Past performance ≠ future results
- Only trade what you can afford to lose

### Technical Risks
- Internet connectivity issues
- Exchange API downtime
- Software bugs
- Market manipulation

### Legal & Compliance
- Understand your local regulations
- Comply with exchange terms of service
- Keep records for tax purposes
- Consider professional advice

## 🐛 Troubleshooting

### Common Issues

**1. Bots not starting**
```bash
# Check backend logs
docker-compose logs backend

# Verify exchange connections
curl http://localhost:8000/api/exchanges
```

**2. WebSocket not connecting**
```bash
# Check firewall settings
# Ensure port 8000 is accessible
# Verify CORS configuration
```

**3. Ollama not responding**
```bash
# Restart Ollama service
docker-compose restart ollama

# Check if model is pulled
docker-compose exec ollama ollama list
```

**4. Database errors**
```bash
# Reset database (WARNING: deletes all data)
docker-compose down -v
docker-compose up -d
```

## 📈 Performance Optimization

### For High-Frequency Trading

1. Use dedicated server with low latency
2. Deploy closer to exchange servers
3. Use Redis for caching
4. Optimize database queries
5. Monitor resource usage

### For Large Portfolios

1. Use PostgreSQL instead of SQLite
2. Increase Redis memory allocation
3. Use multiple bot instances
4. Implement position diversification
5. Monitor risk levels closely

## 🔄 Updates & Maintenance

### Update System

```bash
# Pull latest changes
git pull origin main

# Rebuild containers
docker-compose build

# Restart services
docker-compose up -d
```

### Backup Data

```bash
# Backup data directory
tar -czf backup_$(date +%Y%m%d).tar.gz data/

# Backup database
docker-compose exec postgres pg_dump rimuru_db > backup.sql
```

## 📞 Support

### Documentation

- API Documentation: http://localhost:8000/docs
- User Manual: See `docs/USER_MANUAL.md`
- Deployment Guide: See `docs/DEPLOYMENT.md`

### Community

- GitHub Issues: Report bugs and feature requests
- Discord: Join our community for real-time support

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- CCXT for exchange integration
- Ollama for AI capabilities
- FastAPI for the backend framework
- React & Material-UI for the frontend

---

**⚠️ DISCLAIMER**: This software is provided for educational purposes only. Cryptocurrency trading involves substantial risk of loss. Use at your own risk.

**🚀 Start Building Your Crypto Empire Today!**