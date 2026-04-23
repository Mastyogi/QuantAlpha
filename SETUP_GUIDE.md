# 🚀 KellyAI - Complete Setup Guide

## 📋 Table of Contents
1. [Bot Name & Branding](#bot-name--branding)
2. [Prerequisites](#prerequisites)
3. [Telegram Bot Setup](#telegram-bot-setup)
4. [Bitget Exchange Setup](#bitget-exchange-setup)
5. [MT5 Forex Setup](#mt5-forex-setup)
6. [Database Setup](#database-setup)
7. [Configuration](#configuration)
8. [Testing Modes](#testing-modes)
9. [Deployment](#deployment)
10. [Monitoring & Logs](#monitoring--logs)

---

## 🎯 Bot Name & Branding

### Recommended Name: **"KellyAI"** 🏆

**Why KellyAI?**
- ✅ Reflects Kelly Criterion (core compounding strategy)
- ✅ AI component is clear
- ✅ Short, memorable, professional
- ✅ Perfect for Telegram bot username: `@KellyAI_Bot`

**Alternative Names**:
- CompoundX
- AutoGrow
- QuantumFund
- AlphaBot

---

## 📦 Prerequisites

### System Requirements
```bash
# Operating System
- Linux (Ubuntu 20.04+ recommended)
- Windows 10/11 with WSL2
- macOS 11+

# Software
- Python 3.9+
- PostgreSQL 14+ or TimescaleDB
- Redis (optional, for caching)
- Git

# Hardware (Minimum)
- 2 CPU cores
- 4GB RAM
- 20GB storage

# Hardware (Recommended)
- 4+ CPU cores
- 8GB+ RAM
- 50GB+ SSD storage
```

### Install Dependencies
```bash
# Clone repository
git clone <your-repo-url>
cd trading-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install Python packages
pip install -r requirements.txt

# Install additional packages for Bitget & MT5
pip install ccxt MetaTrader5
```

---

## 📱 Telegram Bot Setup

### Step 1: Create Bot with BotFather

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Choose bot name: **KellyAI** (or your preferred name)
4. Choose username: `@KellyAI_Bot` (must end with 'bot')
5. Copy the **Bot Token** (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Step 2: Configure Bot Settings

```bash
# Send these commands to @BotFather:

# Set bot description
/setdescription
# Then paste:
"KellyAI - Self-Improving Portfolio Fund Compounder
Autonomous trading with Kelly Criterion position sizing, pattern discovery, and adaptive risk management."

# Set bot about text
/setabouttext
# Then paste:
"AI-powered trading bot with autonomous learning and compounding growth"

# Set bot commands
/setcommands
# Then paste:
start - Main menu
status - Bot & system status
health - System health check
signals - Recent trade signals
pnl - P&L summary
pause - Pause trading
resume - Resume trading
performance - Compounding stats
patterns - Active trading patterns
audit - Generate audit report
retrain - Trigger model retraining
optimize - Trigger parameter optimization
rollback - Emergency model rollback
help - Command list
```

### Step 3: Get Your Chat ID

1. Search for `@userinfobot` on Telegram
2. Send `/start` to the bot
3. Copy your **Chat ID** (e.g., `123456789`)
4. This will be your admin ID

### Step 4: Add to .env File

```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_ADMIN_CHAT_IDS=123456789
BOT_NAME=KellyAI
```

---

## 💱 Bitget Exchange Setup

### Step 1: Create Bitget Account

1. Go to [Bitget.com](https://www.bitget.com)
2. Sign up for an account
3. Complete KYC verification (required for API access)

### Step 2: Create API Keys

1. Login to Bitget
2. Go to **Account** → **API Management**
3. Click **Create API Key**
4. Set permissions:
   - ✅ **Read** (required)
   - ✅ **Trade** (required for live trading)
   - ❌ **Withdraw** (NOT recommended for security)
5. Set IP whitelist (optional but recommended)
6. Copy:
   - API Key
   - API Secret
   - Passphrase

### Step 3: Test with Demo Account (Recommended)

```bash
# Bitget offers demo trading
# Use demo credentials first to test the bot
BITGET_API_KEY=demo_api_key
BITGET_API_SECRET=demo_api_secret
BITGET_PASSPHRASE=demo_passphrase
```

### Step 4: Add to .env File

```bash
BITGET_API_KEY=your_actual_api_key
BITGET_API_SECRET=your_actual_api_secret
BITGET_PASSPHRASE=your_actual_passphrase
BITGET_API_URL=https://api.bitget.com
BITGET_WS_URL=wss://ws.bitget.com/mix/v1/stream
ENABLE_BITGET=true
```

### Step 5: Verify Connection

```python
# Test script: test_bitget.py
import ccxt

exchange = ccxt.bitget({
    'apiKey': 'your_api_key',
    'secret': 'your_api_secret',
    'password': 'your_passphrase',
})

# Test connection
try:
    balance = exchange.fetch_balance()
    print("✅ Bitget connection successful!")
    print(f"USDT Balance: {balance['USDT']['free']}")
except Exception as e:
    print(f"❌ Connection failed: {e}")
```

---

## 📊 MT5 Forex Setup

### Step 1: Choose Forex Broker

**Recommended Brokers**:
- **IC Markets** (low spreads, good for algo trading)
- **FTMO** (prop trading, demo accounts)
- **Pepperstone** (reliable, MT5 support)
- **XM** (beginner-friendly)

### Step 2: Download MT5

1. Download MetaTrader 5 from your broker's website
2. Install MT5 on your computer
3. Login with your broker credentials

### Step 3: Enable Algo Trading

1. Open MT5
2. Go to **Tools** → **Options** → **Expert Advisors**
3. Enable:
   - ✅ Allow automated trading
   - ✅ Allow DLL imports
   - ✅ Allow WebRequest for listed URL

### Step 4: Get MT5 Credentials

```bash
# From your broker account:
MT5_ACCOUNT=12345678  # Your account number
MT5_PASSWORD=YourPassword123
MT5_SERVER=ICMarkets-Demo  # Server name from MT5
MT5_BROKER=ICMarkets-Demo
```

### Step 5: Install MT5 Python Package

```bash
pip install MetaTrader5
```

### Step 6: Test Connection

```python
# Test script: test_mt5.py
import MetaTrader5 as mt5

# Initialize MT5
if not mt5.initialize():
    print("❌ MT5 initialization failed")
    quit()

# Login
account = 12345678
password = "YourPassword123"
server = "ICMarkets-Demo"

if mt5.login(account, password=password, server=server):
    print("✅ MT5 connection successful!")
    account_info = mt5.account_info()
    print(f"Balance: ${account_info.balance}")
    print(f"Equity: ${account_info.equity}")
else:
    print("❌ MT5 login failed")

mt5.shutdown()
```

### Step 7: Add to .env File

```bash
MT5_ACCOUNT=12345678
MT5_PASSWORD=YourPassword123
MT5_SERVER=ICMarkets-Demo
MT5_BROKER=ICMarkets-Demo
ENABLE_MT5=true
```

---

## 🗄️ Database Setup

### Option 1: PostgreSQL (Recommended)

```bash
# Install PostgreSQL
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# Create database
sudo -u postgres psql
CREATE DATABASE trading_bot;
CREATE USER trading_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE trading_bot TO trading_user;
\q

# Add to .env
DATABASE_URL=postgresql://trading_user:secure_password@localhost:5432/trading_bot
```

### Option 2: TimescaleDB (Best for Time-Series Data)

```bash
# Install TimescaleDB
sudo add-apt-repository ppa:timescale/timescaledb-ppa
sudo apt-get update
sudo apt-get install timescaledb-postgresql-14

# Enable TimescaleDB
sudo timescaledb-tune
sudo systemctl restart postgresql

# Create database with TimescaleDB
sudo -u postgres psql
CREATE DATABASE trading_bot;
\c trading_bot
CREATE EXTENSION IF NOT EXISTS timescaledb;
\q
```

### Apply Database Migrations

```bash
# Initialize Alembic (if not already done)
alembic init alembic

# Apply migrations
alembic upgrade head

# Verify tables created
psql -U trading_user -d trading_bot -c "\dt"
```

---

## ⚙️ Configuration

### Step 1: Copy Environment Template

```bash
cp .env.example .env
```

### Step 2: Edit Configuration

```bash
nano .env  # or use your preferred editor
```

### Step 3: Essential Settings

```bash
# MUST CONFIGURE:
TRADING_MODE=paper  # Start with paper trading!
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_ADMIN_CHAT_IDS=your_chat_id
BITGET_API_KEY=your_key
BITGET_API_SECRET=your_secret
BITGET_PASSPHRASE=your_passphrase
MT5_ACCOUNT=your_account
MT5_PASSWORD=your_password
MT5_SERVER=your_server
DATABASE_URL=postgresql://user:pass@localhost:5432/trading_bot
INITIAL_EQUITY=10000.00

# RECOMMENDED SETTINGS:
ENABLE_COMPOUNDING=true
ENABLE_PROFIT_BOOKING=true
USE_PATTERN_LIBRARY=true
ENABLE_SELF_IMPROVEMENT=true
REQUIRE_APPROVAL=true
```

---

## 🧪 Testing Modes

### 1. Paper Trading Mode (Recommended First)

```bash
# .env configuration
TRADING_MODE=paper
INITIAL_EQUITY=10000.00

# Run bot
python src/main.py
```

**Features**:
- ✅ Uses real market data
- ✅ Simulates trades without real money
- ✅ Tests all bot features
- ✅ Generates real logs and metrics
- ✅ Safe for testing strategies

**Duration**: Run for **48 hours minimum** before live trading

### 2. Backtesting Mode

```bash
# .env configuration
BACKTEST_MODE=true
BACKTEST_START_DATE=2024-01-01
BACKTEST_END_DATE=2024-12-31
BACKTEST_INITIAL_CAPITAL=10000.00

# Run backtest
python scripts/run_backtest.py
```

**Features**:
- ✅ Tests on historical data
- ✅ Fast execution (months in minutes)
- ✅ Generates performance reports
- ✅ Validates strategies

### 3. A/B Testing Mode

```bash
# .env configuration
ENABLE_AB_TESTING=true
AB_TEST_DURATION=30
AB_TEST_MIN_TRADES=50

# Run A/B test
python src/ml/ab_testing.py
```

**Features**:
- ✅ Compares two strategies
- ✅ Statistical significance testing
- ✅ Automatic winner selection
- ✅ Minimum sample size enforcement

---

## 🚀 Deployment

### Development Mode

```bash
# Run locally
python src/main.py
```

### Production Mode (Docker)

```bash
# Build Docker image
docker build -t kellyai:latest .

# Run container
docker-compose up -d

# View logs
docker-compose logs -f
```

### Production Mode (Systemd Service)

```bash
# Create service file
sudo nano /etc/systemd/system/kellyai.service

# Add content:
[Unit]
Description=KellyAI Trading Bot
After=network.target postgresql.service

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/trading-bot
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

# Enable and start service
sudo systemctl enable kellyai
sudo systemctl start kellyai
sudo systemctl status kellyai
```

---

## 📊 Monitoring & Logs

### Real-Time Monitoring

```bash
# Telegram commands
/status      # Bot status
/health      # System health
/performance # Compounding stats
/pnl         # Profit/Loss

# API endpoints
curl http://localhost:8000/health
curl http://localhost:8000/health/detailed
curl http://localhost:8000/api/status
```

### Log Files

```bash
# View logs
tail -f logs/trading_bot.log

# View audit logs
tail -f logs/audit.log

# Export audit logs to CSV
python -c "
from src.utils.logger import get_audit_logger
import asyncio
audit = get_audit_logger()
asyncio.run(audit.export_logs_to_csv('audit_export.csv'))
"
```

### Database Queries

```sql
-- Recent trades
SELECT * FROM trades ORDER BY opened_at DESC LIMIT 10;

-- Performance metrics
SELECT * FROM performance_history ORDER BY timestamp DESC LIMIT 5;

-- Active patterns
SELECT * FROM trading_patterns WHERE is_active = true ORDER BY win_rate DESC;

-- Equity history
SELECT * FROM equity_history ORDER BY timestamp DESC LIMIT 20;

-- Audit logs
SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 50;
```

---

## 🎯 Maximum Compounding Recommendations

### 1. **Start Conservative**
```bash
INITIAL_EQUITY=10000.00
KELLY_FRACTION=0.25  # 25% of Kelly (safe)
MAX_POSITION_PCT=5.0
MAX_PORTFOLIO_HEAT=12.0
```

### 2. **Gradually Increase After Proven Performance**
```bash
# After 3 months with >60% win rate:
KELLY_FRACTION=0.35  # 35% of Kelly
MAX_POSITION_PCT=7.0
MAX_PORTFOLIO_HEAT=15.0
```

### 3. **Enable All Compounding Features**
```bash
ENABLE_COMPOUNDING=true
ENABLE_PROFIT_BOOKING=true
USE_PATTERN_LIBRARY=true
ENABLE_SELF_IMPROVEMENT=true
ADAPTIVE_RISK_ENABLED=true
```

### 4. **Optimize for High-Confluence Signals**
```bash
MIN_CONFLUENCE_SCORE=80.0  # Higher threshold
MIN_AI_CONFIDENCE=0.75
MIN_PATTERN_WIN_RATE=0.65
```

### 5. **Aggressive Profit Booking**
```bash
TP1_MULTIPLIER=1.5
TP2_MULTIPLIER=2.5  # Closer targets
TP3_MULTIPLIER=4.0
TRAILING_STOP_LOCK_PCT=60  # Lock 60% of gains
```

### 6. **Diversification**
```bash
# Trade multiple pairs
CRYPTO_PAIRS=BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,AVAX/USDT
FOREX_PAIRS=EURUSD,GBPUSD,USDJPY,AUDUSD,USDCAD

# Enable both markets
ENABLE_CRYPTO=true
ENABLE_FOREX=true
```

### 7. **Reinvest Profits**
- Don't withdraw profits for first 6 months
- Let compounding work its magic
- Withdraw only excess above target equity

### 8. **Monitor & Adjust**
- Review performance weekly
- Adjust Kelly fraction based on win rate
- Increase position sizes gradually
- Never exceed 10% per position

---

## ⚠️ Important Warnings

### Security
- ❌ **NEVER** share your API keys
- ❌ **NEVER** enable withdraw permissions
- ✅ Use IP whitelist on exchange
- ✅ Enable 2FA on all accounts
- ✅ Store .env file securely (add to .gitignore)

### Risk Management
- ⚠️ Start with paper trading (48 hours minimum)
- ⚠️ Start with small capital ($100-$1000)
- ⚠️ Never risk more than 2% per trade
- ⚠️ Set stop losses on all trades
- ⚠️ Monitor bot daily for first month

### Legal
- 📋 Check local regulations for algo trading
- 📋 Understand tax implications
- 📋 Keep detailed records (audit logs)
- 📋 Consult financial advisor if needed

---

## 🆘 Troubleshooting

### Bot Not Starting
```bash
# Check logs
tail -f logs/trading_bot.log

# Verify database connection
psql -U trading_user -d trading_bot -c "SELECT 1"

# Test Telegram bot
python -c "from telegram import Bot; bot = Bot('YOUR_TOKEN'); print(bot.get_me())"
```

### No Signals Generated
- Check confluence threshold (try lowering to 70)
- Verify market data is being fetched
- Check signal engine logs
- Ensure patterns are discovered (wait 30 days)

### Trades Not Executing
- Verify API keys are correct
- Check exchange balance
- Ensure trading mode is set correctly
- Check order manager logs

---

## 📞 Support

### Documentation
- `README.md` - Project overview
- `IMPLEMENTATION_COMPLETE.md` - Feature documentation
- `docs/` - Additional documentation

### Logs
- `logs/trading_bot.log` - Main application log
- `logs/audit.log` - Audit trail
- Database audit_logs table

### Telegram
- Use `/help` command for bot commands
- Use `/health` to check system status
- Use `/audit` to generate reports

---

## 🎉 You're Ready!

Your **KellyAI** bot is now configured and ready to trade!

**Next Steps**:
1. ✅ Start in paper trading mode
2. ✅ Monitor for 48 hours
3. ✅ Review performance metrics
4. ✅ Adjust settings if needed
5. ✅ Switch to live trading (with small capital)
6. ✅ Scale up gradually

**Good luck with your compounding journey!** 🚀💰

---

**Bot Name**: KellyAI  
**Version**: 1.0.0  
**Last Updated**: April 22, 2026
