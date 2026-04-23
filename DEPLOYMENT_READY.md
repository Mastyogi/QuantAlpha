# 🚀 QuantAlpha - Ready for VPS Deployment

## ✅ Renaming Complete

All "KellyAI" references have been successfully renamed to "QuantAlpha"!

---

## 📦 What's Ready

### ✅ Core Files Updated
- `run_trading_bot.py` - Main bot starter
- `.env` - Configuration with `BOT_NAME=QuantAlpha`
- `.env.example` - Template configuration

### ✅ Deployment Scripts Ready
- `deploy_quantalpha.sh` - **Recommended** one-click VPS deployment
- `deploy_to_vps.sh` - Alternative deployment script
- `vps_deploy.sh` - Legacy deployment script
- `setup_windows_autostart.bat` - Windows auto-start

### ✅ Documentation Updated
- `COMPLETE_VPS_DEPLOYMENT_GUIDE.md` - All 3 deployment methods
- `VPS_DEPLOYMENT_COMPLETE.md` - Quick VPS guide
- `24_7_DEPLOYMENT_GUIDE.md` - 24/7 running options
- `RENAMING_COMPLETE.md` - Detailed renaming report

### ✅ Docker Configuration
- `docker-compose.prod.yml` - Production Docker setup
- `Dockerfile` - Container build configuration
- `.dockerignore` - Docker optimization

---

## 🎯 Your Bot Details

**Bot Name**: QuantAlpha  
**Telegram Bot**: @multipiller_bot  
**Bot Username**: QuantAlpha  
**Admin Chat ID**: 7263314996  
**Trading Mode**: PAPER  
**Exchange**: Bitget  

---

## 🚀 Quick Deployment Guide

### Option 1: One-Click Deployment (Recommended) ⭐

**Step 1**: Upload files to VPS
```bash
# From your Windows PC
scp -r C:\Users\rajee\trading-bot\* root@YOUR_VPS_IP:/opt/quantalpha/
```

**Step 2**: Upload and run deployment script
```bash
# Upload script
scp deploy_quantalpha.sh root@YOUR_VPS_IP:/root/

# SSH into VPS
ssh root@YOUR_VPS_IP

# Run deployment
chmod +x /root/deploy_quantalpha.sh
/root/deploy_quantalpha.sh
```

**Step 3**: Create .env file on VPS
```bash
nano /opt/quantalpha/.env
```

Paste your configuration:
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

# Database
DATABASE_URL=postgresql+asyncpg://postgres:Rahul%40639228@db.ycmhzbctijkgpwjfloxk.supabase.co:5432/postgres
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=Hf8R2LSsIrdNtVm0uPiaq1wEg6CUkMDGABKO9YeJvzZy35lQhp4oX7njcTFbxW
LOG_LEVEL=INFO

# Trading Config
PAIRS=BTC/USDT,ETH/USDT,SOL/USDT
PRIMARY_TIMEFRAME=1h
CONFLUENCE_THRESHOLD=82
BASE_RISK_PCT=1.0
```

Save: `Ctrl+X`, `Y`, `Enter`

**Step 4**: Start the bot
```bash
systemctl start quantalpha
systemctl status quantalpha
journalctl -u quantalpha -f
```

**Step 5**: Test in Telegram
```
Open @multipiller_bot
Send: /status
```

**Done!** ✅ Bot is running 24/7!

---

### Option 2: Docker Deployment 🐳

**Step 1**: Upload files
```bash
scp -r C:\Users\rajee\trading-bot\* root@YOUR_VPS_IP:/opt/quantalpha/
```

**Step 2**: SSH and install Docker
```bash
ssh root@YOUR_VPS_IP
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
apt install -y docker-compose
```

**Step 3**: Create .env file
```bash
cd /opt/quantalpha
nano .env
# Paste configuration (same as above)
```

**Step 4**: Build and run
```bash
docker build -t quantalpha-bot:latest .
docker-compose -f docker-compose.prod.yml up -d
```

**Step 5**: Check logs
```bash
docker-compose -f docker-compose.prod.yml logs -f
```

**Done!** ✅ Bot running in Docker!

---

## 🎮 Management Commands

### Systemd Service (Option 1)
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
```

### Docker (Option 2)
```bash
# Start
docker-compose -f docker-compose.prod.yml up -d

# Stop
docker-compose -f docker-compose.prod.yml down

# Restart
docker-compose -f docker-compose.prod.yml restart

# Logs
docker-compose -f docker-compose.prod.yml logs -f

# Status
docker ps | grep quantalpha
```

---

## 📱 Telegram Commands

Once bot is running, test these commands:

```
/start       - Welcome message
/status      - Bot status
/pnl         - Profit & Loss report
/performance - Compounding stats
/health      - System health
/patterns    - Active patterns
/signals     - Recent signals
/help        - All commands
```

---

## ✅ Verification Checklist

After deployment, verify:

- [ ] Bot uploaded to `/opt/quantalpha/` (not `/opt/kellyai/`)
- [ ] Service created as `quantalpha.service`
- [ ] `.env` file configured with all credentials
- [ ] Service started: `systemctl status quantalpha` shows "active (running)"
- [ ] Logs show: "🎉 BOT IS RUNNING!"
- [ ] Logs show: "✅ Telegram polling started"
- [ ] Telegram responds to `/status` command
- [ ] No errors in logs: `journalctl -u quantalpha -n 50`

---

## 🐛 Troubleshooting

### Bot Not Starting
```bash
# Check logs
journalctl -u quantalpha -n 50

# Check .env file
cat /opt/quantalpha/.env

# Test manually
cd /opt/quantalpha
source venv/bin/activate
python3 run_trading_bot.py
```

### Telegram Not Responding
```bash
# Verify token
grep TELEGRAM /opt/quantalpha/.env

# Test token
python3 -c "from telegram import Bot; import asyncio; bot = Bot('8619104592:AAEjVGp9eRpphPoP9bhqxMboVf_A-UdXX_M'); print(asyncio.run(bot.get_me()))"
```

### Port 8000 Already in Use
```bash
# Find process using port 8000
lsof -i :8000

# Kill process
kill -9 <PID>

# Or change port in .env
echo "API_PORT=8001" >> /opt/quantalpha/.env
```

---

## 📊 Expected Output

When bot starts successfully, you should see:

```
✅ Loaded .env from: /opt/quantalpha/.env
✅ Telegram token loaded: 8619104592:AAEjVGp9e...
🤖 QuantAlpha Trading Bot
============================================================
INFO: QuantAlpha Trading Bot — Starting Up
INFO: Mode: PAPER
INFO: Pairs: BTC/USDT, ETH/USDT, SOL/USDT
============================================================
INFO: Adaptive Risk Manager initialized
INFO: Portfolio Compounder initialized
INFO: AutoTuningSystem initialized
INFO: Health Check System initialized
INFO: Profit Booking Engine initialized
✅ Telegram app created successfully
✅ Telegram app initialized
✅ Telegram app started
✅ Telegram polling started
🎉 BOT IS RUNNING!
============================================================
📱 Test in Telegram:
   1. Open @multipiller_bot
   2. Send: /status
   3. You should get bot status!
⏹  Press Ctrl+C to stop (on VPS, it runs as service)
```

---

## 🎉 Success Indicators

Your bot is working when:

✅ Service shows "active (running)"  
✅ Logs show "BOT IS RUNNING!"  
✅ Logs show "Telegram polling started"  
✅ Telegram bot responds to `/status`  
✅ No errors in last 50 log lines  
✅ Bot sends startup notification to Telegram  

---

## 📝 Important Notes

### Directory Structure
```
/opt/quantalpha/              # Bot directory
/opt/quantalpha/venv/         # Virtual environment
/opt/quantalpha/.env          # Configuration
/opt/quantalpha/logs/         # Log files
/opt/quantalpha/models/       # ML models
/opt/quantalpha/reports/      # Reports
```

### Service Files
```
/etc/systemd/system/quantalpha.service    # Service definition
```

### Log Locations
```
# Systemd logs
journalctl -u quantalpha -f

# File logs
tail -f /opt/quantalpha/logs/bot.log
tail -f /opt/quantalpha/logs/bot_error.log
```

---

## 🔒 Security Reminders

- ✅ `.env` file contains sensitive credentials
- ✅ Never commit `.env` to git
- ✅ Keep API keys secure
- ✅ Use strong SECRET_KEY
- ✅ Restrict SSH access to VPS
- ✅ Enable firewall on VPS

---

## 📞 Quick Reference

### VPS Connection
```bash
ssh root@YOUR_VPS_IP
```

### Check Bot Status
```bash
systemctl status quantalpha
```

### View Live Logs
```bash
journalctl -u quantalpha -f
```

### Restart Bot
```bash
systemctl restart quantalpha
```

### Stop Bot
```bash
systemctl stop quantalpha
```

### Update Bot
```bash
systemctl stop quantalpha
cd /opt/quantalpha
# Upload new files
systemctl start quantalpha
```

---

## 🎯 Next Steps

1. **Deploy to VPS** using Option 1 or 2 above
2. **Verify** bot is running with checklist
3. **Test** Telegram commands
4. **Monitor** logs for first few hours
5. **Enjoy** 24/7 automated trading!

---

## 📚 Additional Resources

- **Full VPS Guide**: `COMPLETE_VPS_DEPLOYMENT_GUIDE.md`
- **24/7 Options**: `24_7_DEPLOYMENT_GUIDE.md`
- **Renaming Details**: `RENAMING_COMPLETE.md`
- **Docker Setup**: `docker-compose.prod.yml`

---

## 🎉 You're Ready!

**QuantAlpha** is fully configured and ready for VPS deployment!

**Bot Name**: QuantAlpha  
**Status**: ✅ Production Ready  
**Mode**: Paper Trading  
**Exchange**: Bitget  
**Telegram**: @multipiller_bot  

**Deploy now and start trading 24/7!** 🚀

---

**Last Updated**: April 23, 2026  
**Version**: 1.0.0  
**Deployment**: VPS Ready
