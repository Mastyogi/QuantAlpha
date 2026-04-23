# 🤖 Hostinger AI - Complete Deployment Prompt

Copy and paste this entire prompt to Hostinger AI Assistant:

---

## DEPLOYMENT REQUEST

I need to deploy a Python trading bot called "QuantAlpha" on this Hostinger VPS. Please help me with complete setup.

### Bot Details:
- **Name**: QuantAlpha Trading Bot
- **Type**: Python 3.11 application
- **Purpose**: Automated cryptocurrency trading with Telegram integration
- **Mode**: Paper trading (no real money)
- **Exchange**: Bitget
- **Telegram Bot**: @multipiller_bot

### Requirements:
1. Python 3.11 or higher
2. Virtual environment
3. Systemd service for 24/7 running
4. Auto-start on VPS reboot
5. Proper logging

---

## STEP-BY-STEP DEPLOYMENT

### Step 1: System Update and Dependencies

Please run these commands:

```bash
# Update system
apt update && apt upgrade -y

# Install required packages
apt install -y python3 python3-pip python3-venv git build-essential \
    libssl-dev libffi-dev python3-dev htop curl wget nano

# Verify Python version
python3 --version
```

**Expected**: Python 3.10 or higher

---

### Step 2: Create Bot Directory

```bash
# Create directory structure
mkdir -p /opt/quantalpha
mkdir -p /opt/quantalpha/logs
mkdir -p /opt/quantalpha/models
mkdir -p /opt/quantalpha/reports

# Set permissions
chmod 755 /opt/quantalpha
```

---

### Step 3: Upload Bot Files

I will upload my bot files to `/opt/quantalpha/` using SCP or FileZilla.

**Files to upload**:
- All Python source files (src/ directory)
- Configuration files (config/ directory)
- requirements.txt
- run_trading_bot.py
- .env file (with credentials)

**Please confirm directory is ready for upload.**

---

### Step 4: Setup Virtual Environment

After I upload files, please run:

```bash
# Go to bot directory
cd /opt/quantalpha

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt
```

**This will take 3-5 minutes. Please wait for completion.**

---

### Step 5: Create .env Configuration File

Please create file `/opt/quantalpha/.env` with this content:

```env
# Bot Configuration
BOT_NAME=QuantAlpha

# Exchange (Bitget)
EXCHANGE_NAME=bitget
EXCHANGE_API_KEY=bg_24b5d72feb434de76d28b3b97b0a6b52
EXCHANGE_SECRET=53caeab8cb8733c84e7c29075911176d32468edf1593505c741412cb8332c30b
EXCHANGE_PASSPHRASE=fixswingproduceclevererasesucces
TRADING_MODE=paper
TESTNET=false

# Telegram
TELEGRAM_BOT_TOKEN=8619104592:AAEjVGp9eRpphPoP9bhqxMboVf_A-UdXX_M
TELEGRAM_ADMIN_CHAT_ID=7263314996

# MT5 / Forex Broker
MT5_LOGIN=mq99344
MT5_PASSWORD=X9TxNfZV
MT5_SERVER=MetaQuotes-Demo
MT5_PATH=
BROKER_MODE=paper
ENABLE_FOREX=false
ENABLE_COMMODITIES=false

# Trading Config
PAIRS=BTC/USDT,ETH/USDT,SOL/USDT
PRIMARY_TIMEFRAME=1h
CONFLUENCE_THRESHOLD=82
MIN_WALLET_START_USD=10.0
BASE_RISK_PCT=1.0

# Dynamic Sizing
DYNAMIC_SIZING_AFTER_LOSS_PCT=15
DYNAMIC_MAX_MULTIPLIER=2.0
DYNAMIC_MAX_CONSECUTIVE_INCR=3
RECOVERY_RESET_TO_BASE=true

# Execution
EXECUTION_LATENCY_TARGET_MS=50
USE_WEBSOCKET=true

# AI Fine-Tuning
ENABLE_FINE_TUNING=true
OPTUNA_TRIALS=30
AB_TEST_MIN_IMPROVEMENT=0.02

# Database
DATABASE_URL=postgresql+asyncpg://postgres:Rahul%40639228@db.ycmhzbctijkgpwjfloxk.supabase.co:5432/postgres
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=Hf8R2LSsIrdNtVm0uPiaq1wEg6CUkMDGABKO9YeJvzZy35lQhp4oX7njcTFbxW
FLASK_ENV=production
LOG_LEVEL=INFO
```

**Command to create file**:
```bash
nano /opt/quantalpha/.env
# Paste content above
# Save: Ctrl+X, Y, Enter
```

---

### Step 6: Test Bot Manually

Before creating service, please test bot:

```bash
cd /opt/quantalpha
source venv/bin/activate
python3 run_trading_bot.py
```

**Expected output**:
```
✅ Loaded .env from: /opt/quantalpha/.env
✅ Telegram token loaded: 8619104592:AAEjVGp9e...
🤖 QuantAlpha Trading Bot
============================================================
INFO: QuantAlpha Trading Bot — Starting Up
INFO: Mode: PAPER
INFO: Pairs: BTC/USDT, ETH/USDT, SOL/USDT
============================================================
✅ Telegram app created successfully
✅ Telegram app initialized
✅ Telegram app started
✅ Telegram polling started
🎉 BOT IS RUNNING!
```

**If you see this, press Ctrl+C to stop and proceed to next step.**

**If errors occur, please share the error message.**

---

### Step 7: Create Systemd Service

Please create service file `/etc/systemd/system/quantalpha.service`:

```bash
nano /etc/systemd/system/quantalpha.service
```

**Paste this content**:

```ini
[Unit]
Description=QuantAlpha Trading Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/quantalpha
Environment="PATH=/opt/quantalpha/venv/bin"
ExecStart=/opt/quantalpha/venv/bin/python3 /opt/quantalpha/run_trading_bot.py
Restart=always
RestartSec=10
StandardOutput=append:/opt/quantalpha/logs/bot.log
StandardError=append:/opt/quantalpha/logs/bot_error.log

[Install]
WantedBy=multi-user.target
```

**Save**: Ctrl+X, Y, Enter

---

### Step 8: Enable and Start Service

```bash
# Reload systemd
systemctl daemon-reload

# Enable auto-start on boot
systemctl enable quantalpha

# Start the service
systemctl start quantalpha

# Check status
systemctl status quantalpha
```

**Expected status**: `active (running)`

---

### Step 9: Verify Logs

```bash
# View live logs
journalctl -u quantalpha -f

# Or view file logs
tail -f /opt/quantalpha/logs/bot.log
```

**Should show**:
- ✅ Bot starting up
- ✅ Telegram connected
- ✅ "BOT IS RUNNING!"

**Press Ctrl+C to exit log view (bot keeps running)**

---

### Step 10: Test Telegram Integration

Please confirm:
1. Bot service is running: `systemctl status quantalpha`
2. No errors in logs: `journalctl -u quantalpha -n 50`
3. I can test Telegram by sending `/status` to @multipiller_bot

---

## VERIFICATION CHECKLIST

Please verify these items:

- [ ] Python 3.11+ installed
- [ ] Bot directory created: `/opt/quantalpha/`
- [ ] Virtual environment created: `/opt/quantalpha/venv/`
- [ ] All dependencies installed from requirements.txt
- [ ] .env file created with all credentials
- [ ] Bot tested manually (no errors)
- [ ] Systemd service created: `/etc/systemd/system/quantalpha.service`
- [ ] Service enabled for auto-start
- [ ] Service started successfully
- [ ] Service status shows "active (running)"
- [ ] Logs show "BOT IS RUNNING!"
- [ ] No errors in last 50 log lines

---

## MANAGEMENT COMMANDS

After deployment, I can manage bot with:

```bash
# Start bot
systemctl start quantalpha

# Stop bot
systemctl stop quantalpha

# Restart bot
systemctl restart quantalpha

# Check status
systemctl status quantalpha

# View logs
journalctl -u quantalpha -f

# View last 100 lines
journalctl -u quantalpha -n 100

# View errors only
journalctl -u quantalpha -p err
```

---

## TROUBLESHOOTING

If any issues occur, please check:

### Issue 1: Service fails to start
```bash
# Check logs
journalctl -u quantalpha -n 50

# Check .env file exists
ls -la /opt/quantalpha/.env

# Check Python path
which python3
```

### Issue 2: Import errors
```bash
# Reinstall requirements
cd /opt/quantalpha
source venv/bin/activate
pip install -r requirements.txt --force-reinstall
```

### Issue 3: Port 8000 already in use
```bash
# Find process using port
lsof -i :8000

# Kill process if needed
kill -9 <PID>
```

### Issue 4: Permission errors
```bash
# Fix permissions
chown -R root:root /opt/quantalpha
chmod -R 755 /opt/quantalpha
chmod 600 /opt/quantalpha/.env
```

---

## MONITORING SETUP (Optional)

Please also setup monitoring:

### 1. Auto-restart on failure
Already configured in service file with `Restart=always`

### 2. Health check script
```bash
# Create health check
nano /root/check_quantalpha.sh
```

Paste:
```bash
#!/bin/bash
if ! systemctl is-active --quiet quantalpha; then
    systemctl start quantalpha
    echo "Bot restarted at $(date)" >> /root/bot_restarts.log
fi
```

```bash
# Make executable
chmod +x /root/check_quantalpha.sh

# Add to crontab (check every 5 minutes)
crontab -e
# Add line:
*/5 * * * * /root/check_quantalpha.sh
```

### 3. Daily backup
```bash
# Create backup script
nano /root/backup_quantalpha.sh
```

Paste:
```bash
#!/bin/bash
mkdir -p /root/backups
tar -czf /root/backups/quantalpha_$(date +%Y%m%d).tar.gz /opt/quantalpha
find /root/backups -name "quantalpha_*.tar.gz" -mtime +7 -delete
```

```bash
# Make executable
chmod +x /root/backup_quantalpha.sh

# Add to crontab (daily at 3 AM)
crontab -e
# Add line:
0 3 * * * /root/backup_quantalpha.sh
```

---

## RESOURCE MONITORING

Please also check system resources:

```bash
# Check RAM usage
free -h

# Check disk space
df -h

# Check CPU usage
top

# Check bot process
ps aux | grep python
```

**Recommended VPS specs**:
- Minimum: 1GB RAM, 1 CPU core
- Recommended: 2GB RAM, 2 CPU cores
- Optimal: 4GB RAM, 2 CPU cores

---

## FIREWALL CONFIGURATION

Please configure firewall:

```bash
# Install UFW if not installed
apt install -y ufw

# Allow SSH
ufw allow 22/tcp

# Enable firewall
ufw enable

# Check status
ufw status
```

---

## FINAL VERIFICATION

After all steps, please confirm:

1. **Service Status**:
   ```bash
   systemctl status quantalpha
   ```
   Should show: `active (running)`

2. **Recent Logs**:
   ```bash
   journalctl -u quantalpha -n 20
   ```
   Should show: "BOT IS RUNNING!" and no errors

3. **Auto-start Enabled**:
   ```bash
   systemctl is-enabled quantalpha
   ```
   Should show: `enabled`

4. **Process Running**:
   ```bash
   ps aux | grep run_trading_bot.py
   ```
   Should show Python process

5. **Telegram Working**:
   I will test by sending `/status` to @multipiller_bot

---

## SUCCESS CRITERIA

Deployment is successful when:

✅ Service shows "active (running)"  
✅ Logs show "BOT IS RUNNING!"  
✅ Logs show "Telegram polling started"  
✅ No errors in recent logs  
✅ Auto-start is enabled  
✅ Telegram bot responds to commands  
✅ Bot survives VPS reboot  

---

## ADDITIONAL INFORMATION

**Bot Architecture**:
- Main entry: `run_trading_bot.py`
- Source code: `src/` directory
- Configuration: `config/` directory
- Logs: `/opt/quantalpha/logs/`
- Models: `/opt/quantalpha/models/`

**Key Features**:
- Telegram bot integration (@multipiller_bot)
- Bitget exchange connection (paper trading)
- XGBoost ML models for predictions
- Kelly Criterion position sizing
- Adaptive risk management
- Pattern discovery
- Auto-tuning with Optuna
- PostgreSQL database (Supabase)

**Important Notes**:
- Bot runs in PAPER mode (no real money)
- All trades are simulated
- Telegram admin chat ID: 7263314996
- Bot will send notifications to Telegram
- Self-improvement runs daily at 3 AM
- Parameter optimization runs weekly

---

## SUPPORT INFORMATION

If you encounter any issues during deployment:

1. **Check Python version**: Must be 3.10+
2. **Check disk space**: Need at least 2GB free
3. **Check RAM**: Need at least 512MB available
4. **Check internet**: Bot needs internet for exchange/Telegram
5. **Check logs**: Always check logs first for errors

**Common Issues**:
- Missing dependencies → Reinstall requirements.txt
- Port conflicts → Change API_PORT in .env
- Memory issues → Reduce trading pairs or upgrade VPS
- Telegram errors → Verify bot token is correct

---

## COMPLETION

Once deployment is complete, please provide:

1. Service status output
2. Last 20 lines of logs
3. Confirmation that auto-start is enabled
4. Any warnings or errors encountered

I will then test the Telegram bot to confirm everything is working.

Thank you for your help with deploying QuantAlpha Trading Bot!

---

**Deployment Date**: April 23, 2026  
**Bot Version**: 1.0.0  
**VPS**: Hostinger (srv1565491.hstgr.cloud)  
**Service Name**: quantalpha  
**Directory**: /opt/quantalpha  
