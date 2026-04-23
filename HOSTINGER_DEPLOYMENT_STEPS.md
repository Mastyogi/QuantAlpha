# 🚀 Hostinger VPS - Step-by-Step Deployment Guide

## 📋 Pre-Deployment Checklist

- [ ] Hostinger VPS active: `srv1565491.hstgr.cloud`
- [ ] Root password available
- [ ] Bot files ready on Windows PC: `C:\Users\rajee\trading-bot`
- [ ] Telegram bot token: `8619104592:AAEjVGp9eRpphPoP9bhqxMboVf_A-UdXX_M`
- [ ] FileZilla or WinSCP installed (for file upload)

---

## 🎯 Deployment Process

### Method 1: Using Hostinger AI (Recommended) ⭐

**Step 1**: Login to Hostinger Control Panel
- Go to: https://hpanel.hostinger.com
- Login with your credentials
- Select your VPS: `srv1565491.hstgr.cloud`

**Step 2**: Open AI Assistant
- Look for "AI Assistant" or "Kodee" in Hostinger panel
- Click to open chat

**Step 3**: Copy and Paste This Prompt

```
I need to deploy a Python trading bot. Please execute these commands:

1. Update system:
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv git build-essential libssl-dev libffi-dev python3-dev htop curl

2. Create directories:
mkdir -p /opt/quantalpha/logs /opt/quantalpha/models /opt/quantalpha/reports
chmod 755 /opt/quantalpha

3. Verify Python version:
python3 --version

Please confirm when done, then I'll upload my bot files.
```

**Step 4**: Wait for AI to Complete
- AI will execute commands
- Verify no errors
- Confirm Python 3.10+ is installed

**Step 5**: Upload Bot Files

**Option A: Using FileZilla (GUI - Easier)**
1. Open FileZilla
2. Connect:
   - Host: `srv1565491.hstgr.cloud`
   - Username: `root`
   - Password: Your Hostinger password
   - Port: `22`
3. Navigate to `/opt/quantalpha/` on right panel
4. Drag all files from `C:\Users\rajee\trading-bot` to VPS

**Option B: Using WinSCP**
1. Open WinSCP
2. New Session:
   - File protocol: SCP
   - Host: `srv1565491.hstgr.cloud`
   - Port: 22
   - Username: root
   - Password: Your password
3. Login and upload files to `/opt/quantalpha/`

**Option C: Using SCP Command (PowerShell)**
```powershell
cd C:\Users\rajee\trading-bot
scp -r * root@srv1565491.hstgr.cloud:/opt/quantalpha/
```

**Step 6**: Tell AI to Setup Virtual Environment

```
Files uploaded. Please setup virtual environment:

cd /opt/quantalpha
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

This will take 3-5 minutes. Please wait for completion.
```

**Step 7**: Tell AI to Create .env File

```
Please create file /opt/quantalpha/.env with this content:

BOT_NAME=QuantAlpha
EXCHANGE_NAME=bitget
EXCHANGE_API_KEY=bg_24b5d72feb434de76d28b3b97b0a6b52
EXCHANGE_SECRET=53caeab8cb8733c84e7c29075911176d32468edf1593505c741412cb8332c30b
EXCHANGE_PASSPHRASE=fixswingproduceclevererasesucces
TRADING_MODE=paper
TESTNET=false
TELEGRAM_BOT_TOKEN=8619104592:AAEjVGp9eRpphPoP9bhqxMboVf_A-UdXX_M
TELEGRAM_ADMIN_CHAT_ID=7263314996
DATABASE_URL=postgresql+asyncpg://postgres:Rahul%40639228@db.ycmhzbctijkgpwjfloxk.supabase.co:5432/postgres
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=Hf8R2LSsIrdNtVm0uPiaq1wEg6CUkMDGABKO9YeJvzZy35lQhp4oX7njcTFbxW
LOG_LEVEL=INFO
PAIRS=BTC/USDT,ETH/USDT,SOL/USDT
PRIMARY_TIMEFRAME=1h
CONFLUENCE_THRESHOLD=82
BASE_RISK_PCT=1.0
```

**Step 8**: Tell AI to Test Bot

```
Please test bot manually:

cd /opt/quantalpha
source venv/bin/activate
python3 run_trading_bot.py

Let it run for 10 seconds, then press Ctrl+C to stop.
Share the output with me.
```

**Expected Output**:
```
✅ Loaded .env
✅ Telegram token loaded
🤖 QuantAlpha Trading Bot
INFO: QuantAlpha Trading Bot — Starting Up
✅ Telegram polling started
🎉 BOT IS RUNNING!
```

**Step 9**: Tell AI to Create Service

```
Bot test successful. Please create systemd service:

Create file /etc/systemd/system/quantalpha.service with this content:

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

Then run:
systemctl daemon-reload
systemctl enable quantalpha
systemctl start quantalpha
systemctl status quantalpha
```

**Step 10**: Tell AI to Show Logs

```
Please show me the logs:

journalctl -u quantalpha -n 30
```

**Step 11**: Verify in Telegram
- Open Telegram
- Go to @multipiller_bot
- Send: `/status`
- You should get bot status!

**Done!** ✅ Bot is running 24/7!

---

### Method 2: Manual SSH Deployment

**Step 1**: Connect via SSH
```bash
ssh root@srv1565491.hstgr.cloud
```

**Step 2**: Run All Commands Manually
```bash
# Update system
apt update && apt upgrade -y

# Install dependencies
apt install -y python3 python3-pip python3-venv git build-essential \
    libssl-dev libffi-dev python3-dev htop curl

# Create directories
mkdir -p /opt/quantalpha/{logs,models,reports}
chmod 755 /opt/quantalpha

# Exit SSH
exit
```

**Step 3**: Upload Files (from Windows)
```powershell
scp -r C:\Users\rajee\trading-bot\* root@srv1565491.hstgr.cloud:/opt/quantalpha/
```

**Step 4**: SSH Back and Setup
```bash
ssh root@srv1565491.hstgr.cloud

# Setup virtual environment
cd /opt/quantalpha
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file
nano .env
# Paste configuration (see above)
# Save: Ctrl+X, Y, Enter

# Test bot
python3 run_trading_bot.py
# Press Ctrl+C after 10 seconds

# Create service
nano /etc/systemd/system/quantalpha.service
# Paste service configuration (see above)
# Save: Ctrl+X, Y, Enter

# Start service
systemctl daemon-reload
systemctl enable quantalpha
systemctl start quantalpha
systemctl status quantalpha

# View logs
journalctl -u quantalpha -f
```

---

## 🎮 Post-Deployment Management

### Check Bot Status
```bash
ssh root@srv1565491.hstgr.cloud
systemctl status quantalpha
```

### View Logs
```bash
ssh root@srv1565491.hstgr.cloud
journalctl -u quantalpha -f
```

### Restart Bot
```bash
ssh root@srv1565491.hstgr.cloud
systemctl restart quantalpha
```

### Stop Bot
```bash
ssh root@srv1565491.hstgr.cloud
systemctl stop quantalpha
```

### Update Bot
```bash
# Stop bot
ssh root@srv1565491.hstgr.cloud
systemctl stop quantalpha

# Upload new files from Windows
scp -r C:\Users\rajee\trading-bot\* root@srv1565491.hstgr.cloud:/opt/quantalpha/

# Restart bot
ssh root@srv1565491.hstgr.cloud
systemctl start quantalpha
```

---

## 📱 Telegram Commands to Test

After deployment, test these:

```
/start       - Welcome message
/status      - Bot status (should work immediately)
/pnl         - Profit & Loss
/performance - Compounding stats
/health      - System health
/patterns    - Active patterns
/signals     - Recent signals
/help        - All commands
```

---

## ✅ Success Indicators

Your bot is working when:

✅ `systemctl status quantalpha` shows "active (running)"  
✅ Logs show "BOT IS RUNNING!"  
✅ Logs show "Telegram polling started"  
✅ No errors in logs  
✅ Telegram `/status` command works  
✅ Bot sends startup notification  

---

## 🐛 Common Issues & Solutions

### Issue 1: "Permission Denied" during SCP
**Solution**: Check password, or use FileZilla instead

### Issue 2: Python version too old
**Solution**: 
```bash
apt install -y software-properties-common
add-apt-repository ppa:deadsnakes/ppa
apt update
apt install -y python3.11 python3.11-venv python3.11-dev
```

### Issue 3: Port 8000 already in use
**Solution**: 
```bash
# Find process
lsof -i :8000
# Kill it
kill -9 <PID>
```

### Issue 4: Out of memory
**Solution**: Upgrade VPS plan to 2GB RAM

### Issue 5: Telegram not working
**Solution**: 
```bash
# Test token
cd /opt/quantalpha
source venv/bin/activate
python3 -c "from telegram import Bot; import asyncio; bot = Bot('8619104592:AAEjVGp9eRpphPoP9bhqxMboVf_A-UdXX_M'); print(asyncio.run(bot.get_me()))"
```

---

## 📊 Resource Monitoring

### Check RAM Usage
```bash
free -h
```

### Check Disk Space
```bash
df -h
```

### Check CPU Usage
```bash
top
# Press 'q' to exit
```

### Check Bot Process
```bash
ps aux | grep python
```

---

## 🔒 Security Best Practices

### 1. Change Root Password
```bash
passwd
```

### 2. Setup Firewall
```bash
apt install -y ufw
ufw allow 22/tcp
ufw enable
ufw status
```

### 3. Secure .env File
```bash
chmod 600 /opt/quantalpha/.env
```

### 4. Setup SSH Key (Optional)
```powershell
# On Windows, generate key
ssh-keygen -t rsa -b 4096

# Copy to VPS
scp ~/.ssh/id_rsa.pub root@srv1565491.hstgr.cloud:~/.ssh/authorized_keys
```

---

## 📞 Quick Reference Card

```
VPS: srv1565491.hstgr.cloud
Bot Directory: /opt/quantalpha
Service: quantalpha
Telegram: @multipiller_bot

Connect:
ssh root@srv1565491.hstgr.cloud

Status:
systemctl status quantalpha

Logs:
journalctl -u quantalpha -f

Restart:
systemctl restart quantalpha

Stop:
systemctl stop quantalpha
```

---

## 🎉 Deployment Complete!

Once you see:
- ✅ Service running
- ✅ Logs show "BOT IS RUNNING!"
- ✅ Telegram responds to `/status`

**Your QuantAlpha bot is LIVE and trading 24/7!** 🚀

---

**Need Help?**
- Check logs first: `journalctl -u quantalpha -n 50`
- Test manually: `cd /opt/quantalpha && source venv/bin/activate && python3 run_trading_bot.py`
- Verify .env file: `cat /opt/quantalpha/.env`
- Check service file: `cat /etc/systemd/system/quantalpha.service`

**Happy Trading!** 📈
