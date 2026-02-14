# 🚀 RIMURU CRYPTO EMPIRE - QUICK START GUIDE

Get up and running in 5 minutes!

---

## ⚡ FASTEST WAY TO START

### 1. Deploy (One Command)

```bash
cd rimuru_empire
./deploy.sh
```

That's it! The script will:
- ✅ Set up Docker containers
- ✅ Pull Ollama AI model
- ✅ Start all services
- ✅ Create necessary directories

### 2. Access Dashboard

Open your browser and go to:
```
http://localhost:3000
```

### 3. Configure Exchange

1. Go to **Security** section
2. Click **Add Exchange**
3. Enter your exchange API keys
4. Enable **Sandbox Mode** for testing
5. Click **Add**

**⚠️ IMPORTANT**: Never enable withdrawal permissions!

### 4. Create Your First Bot

1. Go to **Bots** section
2. Click **Create Bot**
3. Fill in:
   - Name: `my_first_bot`
   - Exchange: (your exchange)
   - Symbol: `BTC/USDT`
   - Strategy: `RSI Reversal`
   - Paper Trading: ✅ Enabled
4. Click **Create Bot**

### 5. Start Trading

1. Find your bot in the list
2. Click **Start**
3. Watch it trade in the Dashboard!

---

## 📱 ACCESS POINTS

- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **Ollama AI**: http://localhost:11434

---

## 🛡️ SAFETY FIRST

### Before You Start Real Trading

1. ✅ Test with **Paper Trading** for 1-2 weeks
2. ✅ Verify all strategies work correctly
3. ✅ Monitor performance closely
4. ✅ Use small amounts (start with $100-500)
5. ✅ Set strict loss limits

### Security Checklist

- ✅ Strong vault password
- ✅ API keys without withdrawal permissions
- ✅ IP whitelisting enabled
- ✅ 2FA enabled on exchanges
- ✅ Emergency stop tested

---

## 🎯 TRADING STRATEGIES

Available strategies:

1. **MA Crossover** - Trend following
2. **RSI Reversal** - Mean reversion
3. **MACD Momentum** - Momentum trading
4. **Bollinger Breakout** - Breakout trading
5. **Grid Trading** - Range trading

Start with RSI Reversal - it's beginner-friendly!

---

## 📊 DASHBOARD OVERVIEW

### Main Sections

1. **Dashboard** - Overview of everything
   - Portfolio value
   - Daily P&L
   - Active bots
   - Open positions

2. **Trading** - Manual trading interface
   - Live charts
   - Order entry
   - Market data

3. **Bots** - Bot management
   - Create bots
   - Start/stop bots
   - Monitor performance

4. **Security** - Credential management
   - Add exchanges
   - View audit logs
   - Security settings

---

## 🆘 TROUBLESHOOTING

### Dashboard not loading?
```bash
docker-compose restart frontend
```

### Bots not starting?
```bash
docker-compose logs backend
```

### Ollama not working?
```bash
docker-compose restart ollama
```

### Reset everything?
```bash
docker-compose down -v
docker-compose up -d
```

---

## 📚 LEARN MORE

- **Full Documentation**: README.md
- **Deployment Guide**: DEPLOYMENT_GUIDE.md
- **Project Status**: PROJECT_COMPLETION.md
- **API Reference**: http://localhost:8000/docs

---

## ⚠️ IMPORTANT REMINDERS

1. **Start with paper trading** - no real money at risk
2. **Use small amounts** - never trade more than you can afford to lose
3. **Never enable withdrawal permissions** - security first!
4. **Monitor closely** - watch your bots at first
5. **Set loss limits** - protect your capital

---

## 🎉 YOU'RE READY!

Your Rimuru Crypto Empire is now running!

**Next Steps:**
1. Test with paper trading
2. Learn the strategies
3. Monitor performance
4. Gradually increase position sizes
5. Start real trading (when ready)

---

**Need Help?**
- Check logs: `docker-compose logs -f`
- Read documentation: README.md
- Review API docs: http://localhost:8000/docs

**Happy Trading! 🚀📈**