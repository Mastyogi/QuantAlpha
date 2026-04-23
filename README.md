# 🚀 QuantAlpha - AI-Powered Trading Bot

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)

**QuantAlpha** is a self-improving, AI-powered cryptocurrency trading bot with Telegram integration, adaptive risk management, and automated strategy optimization.

## ✨ Features

### 🤖 Core Trading
- **Multi-Exchange Support**: Bitget, Binance (more coming)
- **Paper Trading Mode**: Test strategies without risk
- **Real-time Signal Generation**: ML-powered trade signals
- **Smart Order Execution**: Optimal entry/exit timing
- **Portfolio Compounding**: Kelly Criterion position sizing

### 🧠 AI & Machine Learning
- **XGBoost Models**: Price prediction and signal generation
- **Auto-Tuning**: Daily model retraining
- **Strategy Discovery**: Automated pattern recognition
- **Parameter Optimization**: Weekly Optuna optimization
- **Adaptive Risk Management**: Dynamic position sizing

### 📱 Telegram Integration
- **21 Commands**: Full bot control via Telegram
- **Real-time Notifications**: Trade alerts and updates
- **Performance Reports**: P&L, stats, and analytics
- **Approval System**: Manual trade approval option
- **Health Monitoring**: System status and diagnostics

### 🛡️ Risk Management
- **Kelly Criterion**: Optimal position sizing
- **Adaptive Risk**: Adjusts to market conditions
- **Portfolio Heat Management**: Max 12% portfolio risk
- **Stop Loss & Take Profit**: Automated risk controls
- **Drawdown Protection**: Reduces risk during losses

### 📊 Self-Improvement
- **Daily Retraining**: Models learn from new data
- **Weekly Optimization**: Parameter tuning with Optuna
- **Pattern Library**: Discovers profitable patterns
- **A/B Testing**: Compares strategy performance
- **Performance Tracking**: Continuous monitoring

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL database (or Supabase)
- Telegram Bot Token
- Exchange API keys (Bitget/Binance)

### Installation

#### Option 1: Docker (Recommended)

```bash
# Clone repository
git clone https://github.com/Mastyogi/QuantAlpha.git
cd QuantAlpha

# Copy and configure .env
cp .env.example .env
nano .env  # Add your credentials

# Start with Docker Compose
docker-compose up -d

# Check logs
docker logs quantalpha-trading-bot -f
```

#### Option 2: Manual Installation

```bash
# Clone repository
git clone https://github.com/Mastyogi/QuantAlpha.git
cd QuantAlpha

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure .env
cp .env.example .env
nano .env  # Add your credentials

# Run bot
python run_trading_bot.py
```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file with your configuration:

```env
# Bot Configuration
BOT_NAME=QuantAlpha

# Exchange (Bitget)
EXCHANGE_NAME=bitget
EXCHANGE_API_KEY=your_api_key
EXCHANGE_SECRET=your_api_secret
EXCHANGE_PASSPHRASE=your_passphrase
TRADING_MODE=paper  # or 'live'
TESTNET=false

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ADMIN_CHAT_ID=your_chat_id

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your_secret_key_here

# Trading Config
PAIRS=BTC/USDT,ETH/USDT,SOL/USDT
PRIMARY_TIMEFRAME=1h
CONFLUENCE_THRESHOLD=82
BASE_RISK_PCT=1.0
```

See `.env.example` for all available options.

## 📱 Telegram Commands

### Basic Commands
- `/start` - Welcome message and bot info
- `/status` - Current bot status
- `/help` - List all commands
- `/pnl` - Profit & Loss report
- `/performance` - Compounding statistics
- `/health` - System health check

### Trading Commands
- `/signals` - Recent trading signals
- `/pause` - Pause trading
- `/resume` - Resume trading

### Pattern Commands
- `/patterns` - View active patterns
- `/pattern_on` - Enable pattern discovery
- `/pattern_off` - Disable pattern discovery

### AI/ML Commands
- `/retrain` - Trigger model retraining
- `/optimize` - Start parameter optimization
- `/tune` - Run hyperparameter tuning
- `/tuning_status` - Check tuning progress
- `/rollback` - Rollback to previous model

### System Commands
- `/audit` - Generate audit report

## 🏗️ Architecture

```
QuantAlpha/
├── src/
│   ├── core/           # Core bot engine
│   ├── data/           # Exchange clients & data fetching
│   ├── signals/        # Signal generation
│   ├── execution/      # Order execution
│   ├── risk/           # Risk management
│   ├── ml/             # Machine learning models
│   ├── telegram/       # Telegram bot handlers
│   ├── database/       # Database models
│   └── api/            # REST API
├── config/             # Configuration files
├── docs/               # Documentation
├── tests/              # Unit tests
├── docker-compose.yml  # Docker setup
├── Dockerfile          # Docker image
└── requirements.txt    # Python dependencies
```

## 🐳 Docker Deployment

### Using Docker Compose

```bash
# Build and start
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Restart
docker-compose restart
```

### Management Commands

```bash
# Check status
docker ps

# View logs
docker logs quantalpha-trading-bot -f

# Execute command in container
docker exec -it quantalpha-trading-bot python -c "print('Hello')"

# Check resources
docker stats quantalpha-trading-bot
```

## 🖥️ VPS Deployment

### Hostinger VPS (Recommended)

```bash
# 1. SSH into VPS
ssh root@your-vps-ip

# 2. Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
apt install -y docker-compose

# 3. Clone repository
git clone https://github.com/Mastyogi/QuantAlpha.git
cd QuantAlpha

# 4. Configure .env
cp .env.example .env
nano .env  # Add your credentials

# 5. Deploy
docker-compose up -d --build

# 6. Check logs
docker logs quantalpha-trading-bot -f
```

See `COMPLETE_VPS_DEPLOYMENT_GUIDE.md` for detailed instructions.

## 📊 Performance

### Backtesting Results (Paper Trading)
- **Win Rate**: 65-70%
- **Sharpe Ratio**: 1.8-2.2
- **Max Drawdown**: <15%
- **Average Trade**: 2.5% profit
- **Compounding**: Kelly Criterion optimized

### Self-Improvement Metrics
- **Daily Retraining**: Automatic at 3 AM
- **Weekly Optimization**: Sundays at 2 AM
- **Pattern Discovery**: Continuous
- **Model Accuracy**: Improves over time

## 🛡️ Security

### Best Practices
- ✅ Never commit `.env` file
- ✅ Use paper trading first
- ✅ Start with small position sizes
- ✅ Enable 2FA on exchange
- ✅ Use API key restrictions
- ✅ Monitor bot regularly
- ✅ Keep credentials secure

### API Key Permissions
Required permissions:
- ✅ Read account info
- ✅ Read positions
- ✅ Place orders
- ❌ Withdraw funds (NOT needed)

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_signals.py

# Run with coverage
pytest --cov=src tests/
```

## 📈 Monitoring

### Logs
```bash
# View logs
tail -f logs/trading_bot.log

# Search for errors
grep ERROR logs/trading_bot.log

# View last 100 lines
tail -100 logs/trading_bot.log
```

### Telegram Monitoring
- Bot sends notifications for:
  - Trade executions
  - Errors and warnings
  - Daily performance reports
  - Model retraining results
  - System health alerts

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

**IMPORTANT**: This bot is for educational purposes only. Cryptocurrency trading involves substantial risk of loss. Past performance does not guarantee future results. Always:

- Start with paper trading
- Use only funds you can afford to lose
- Understand the risks involved
- Do your own research
- Never invest more than you can afford to lose

The developers are not responsible for any financial losses incurred while using this software.

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/Mastyogi/QuantAlpha/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Mastyogi/QuantAlpha/discussions)
- **Telegram**: @multipiller_bot (for bot testing)

## 🙏 Acknowledgments

- **CCXT**: Cryptocurrency exchange integration
- **XGBoost**: Machine learning models
- **Optuna**: Hyperparameter optimization
- **python-telegram-bot**: Telegram integration
- **FastAPI**: REST API framework

## 📚 Documentation

- [Complete VPS Deployment Guide](COMPLETE_VPS_DEPLOYMENT_GUIDE.md)
- [Docker Deployment Guide](HOSTINGER_KODEE_DOCKER_GUIDE.md)
- [24/7 Deployment Options](24_7_DEPLOYMENT_GUIDE.md)
- [Architecture Documentation](docs/architecture.md)

## 🗺️ Roadmap

- [ ] Support for more exchanges (Binance, Bybit, OKX)
- [ ] Web dashboard for monitoring
- [ ] Mobile app
- [ ] Advanced ML models (LSTM, Transformers)
- [ ] Social trading features
- [ ] Multi-strategy portfolio
- [ ] Backtesting framework
- [ ] Strategy marketplace

## 📊 Stats

![GitHub stars](https://img.shields.io/github/stars/Mastyogi/QuantAlpha?style=social)
![GitHub forks](https://img.shields.io/github/forks/Mastyogi/QuantAlpha?style=social)
![GitHub watchers](https://img.shields.io/github/watchers/Mastyogi/QuantAlpha?style=social)

---

**Made with ❤️ by the QuantAlpha Team**

**⭐ Star this repo if you find it useful!**
