## 🚀 Complete VPS Deployment Guide

## ❌ Vercel: NOT Suitable

**Why Vercel Won't Work**:
- ❌ Serverless only (10-60 sec timeout)
- ❌ No long-running processes
- ❌ No persistent connections
- ❌ Bot needs 24/7 continuous running

**Vercel is for**: Static sites, API endpoints, short functions  
**Your bot needs**: Continuous process, Telegram polling, market scanning

---

## ✅ VPS: PERFECT Choice!

**Why VPS is Best**:
- ✅ 24/7 continuous running
- ✅ Full control over resources
- ✅ Persistent connections
- ✅ No timeouts
- ✅ Can run ML models
- ✅ Cost-effective ($5/month)

---

## 🎯 Quick VPS Deployment (5 Minutes)

### Method 1: Automated Script

**On your VPS**:
```bash
# 1. Upload deployment script
scp vps_deploy.sh root@your-vps-ip:/root/

# 2. SSH into VPS
ssh root@your-vps-ip

# 3. Run deployment script
chmod +x vps_deploy.sh
./vps_deploy.sh

# 4. Upload bot files
# From your PC:
scp -r C:\Users\rajee\trading-bot/* root@your-vps-ip:/opt/quantalpha/

# 5. Create .env file on VPS
nano /opt/quantalpha/.env
# Paste your configuration

# 6. Start bot
systemctl start quantalpha

# 7. Check status
systemctl status quantalpha

# 8. View logs
journalctl -u quantalpha -f
```

---

### Method 2: Manual Step-by-Step

#### Step 1: Connect to VPS
```bash
ssh root@your-vps-ip
```

#### Step 2: Install Dependencies
```bash
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv git
```

#### Step 3: Setup Bot
```bash
# Create directory
mkdir -p /opt/quantalpha
cd /opt/quantalpha

# Upload files (from your PC)
# scp -r C:\Users\rajee\trading-bot/* root@your-vps-ip:/opt/quantalpha/

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

#### Step 4: Configure
```bash
# Create .env
nano .env
# Paste your configuration
# Save: Ctrl+X, Y, Enter
```

#### Step 5: Create Service
```bash
nano /etc/systemd/system/quantalpha.service
```

Paste:
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

#### Step 6: Start Bot
```bash
# Create logs directory
mkdir -p /opt/quantalpha/logs

# Enable and start
systemctl daemon-reload
systemctl enable quantalpha
systemctl start quantalpha

# Check status
systemctl status quantalpha
```

---

## 📊 Verification

### 1. Check Service Status
```bash
systemctl status quantalpha
```

**Should show**:
```
● quantalpha.service - QuantAlpha Trading Bot
   Active: active (running)
```

### 2. Check Logs
```bash
journalctl -u quantalpha -f
```

**Should show**:
```
✅ Loaded .env
✅ Telegram token loaded
✅ Telegram app created successfully
✅ Telegram polling started
🎉 BOT IS RUNNING!
```

### 3. Test Telegram
Open Telegram → @multipiller_bot → Send:
```
/status
```

**Should get**:
```
🟢 BOT STATUS
State: READY
Mode: PAPER
...
```

---

## 🔧 Management Commands

### Service Control
```bash
# Start
systemctl start quantalpha

# Stop
systemctl stop quantalpha

# Restart
systemctl restart quantalpha

# Status
systemctl status quantalpha

# Enable auto-start
systemctl enable quantalpha
```

### View Logs
```bash
# Live logs
journalctl -u quantalpha -f

# Last 100 lines
journalctl -u quantalpha -n 100

# Today's logs
journalctl -u quantalpha --since today

# Errors only
journalctl -u quantalpha -p err
```

### Update Bot
```bash
# Stop bot
systemctl stop quantalpha

# Update files
cd /opt/quantalpha
# Upload new files or git pull

# Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# Restart
systemctl start quantalpha
```

---

## 💰 VPS Providers (Recommended)

### 1. DigitalOcean ($5/month)
- **Specs**: 1GB RAM, 1 CPU, 25GB SSD
- **Setup**: 55 seconds
- **Pros**: Easy, reliable, good docs
- **Link**: digitalocean.com

### 2. Vultr ($5/month)
- **Specs**: 1GB RAM, 1 CPU, 25GB SSD
- **Setup**: 1 minute
- **Pros**: Fast, many locations
- **Link**: vultr.com

### 3. Hetzner (€4/month)
- **Specs**: 2GB RAM, 1 CPU, 20GB SSD
- **Setup**: 2 minutes
- **Pros**: Best value, EU-based
- **Link**: hetzner.com

### 4. Oracle Cloud (FREE Forever!)
- **Specs**: 1GB RAM, 1 CPU, 50GB storage
- **Setup**: 5 minutes
- **Pros**: Actually free, no credit card after trial
- **Link**: oracle.com/cloud/free

---

## 🔒 Security Setup

### 1. Firewall
```bash
# Install UFW
apt install ufw -y

# Allow SSH
ufw allow 22/tcp

# Enable
ufw enable

# Check
ufw status
```

### 2. Secure .env
```bash
chmod 600 /opt/quantalpha/.env
chown root:root /opt/quantalpha/.env
```

### 3. SSH Key (Recommended)
```bash
# On your PC, generate key
ssh-keygen -t rsa -b 4096

# Copy to VPS
ssh-copy-id root@your-vps-ip

# Disable password login
nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no
systemctl restart sshd
```

---

## 📊 Monitoring

### Resource Usage
```bash
# CPU and Memory
htop

# Disk
df -h

# Bot process
ps aux | grep python
```

### Bot Health
```bash
# Via Telegram
/health
/status
/pnl

# Via logs
journalctl -u quantalpha -f
```

### Alerts
Bot automatically sends Telegram alerts for:
- ✅ Bot started
- ✅ Signals generated
- ✅ Trades executed
- ✅ Errors occurred
- ✅ System health issues

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

### Telegram Not Working
```bash
# Check token in .env
grep TELEGRAM /opt/quantalpha/.env

# Test token
python3 -c "from telegram import Bot; import asyncio; bot = Bot('YOUR_TOKEN'); print(asyncio.run(bot.get_me()))"
```

### High Memory Usage
```bash
# Check memory
free -h

# Restart bot
systemctl restart quantalpha

# Upgrade VPS if needed
```

---

## 🎯 Post-Deployment Checklist

- [ ] VPS created and accessible
- [ ] Bot files uploaded
- [ ] .env file configured
- [ ] Dependencies installed
- [ ] Service created and enabled
- [ ] Bot started successfully
- [ ] Logs show "BOT IS RUNNING"
- [ ] Telegram responds to /status
- [ ] Firewall configured
- [ ] Auto-start enabled
- [ ] Monitoring setup

---

## 📝 Quick Reference

### File Locations
```
Bot directory:    /opt/quantalpha/
Virtual env:      /opt/quantalpha/venv/
Config file:      /opt/quantalpha/.env
Service file:     /etc/systemd/system/quantalpha.service
Logs:             /opt/quantalpha/logs/
```

### Important Commands
```bash
# Service
systemctl start quantalpha
systemctl stop quantalpha
systemctl restart quantalpha
systemctl status quantalpha

# Logs
journalctl -u quantalpha -f
tail -f /opt/quantalpha/logs/bot.log

# Update
cd /opt/quantalpha && git pull
systemctl restart quantalpha
```

---

## 🎉 Success!

Your bot is now running 24/7 on VPS!

**What's happening**:
- ✅ Bot runs continuously
- ✅ Auto-restarts on crash
- ✅ Auto-starts on VPS reboot
- ✅ Telegram commands work
- ✅ Trading signals generated
- ✅ Self-improvement active
- ✅ All systems operational

**Monitor via**:
- 📱 Telegram: /status, /health, /pnl
- 📊 Logs: journalctl -u quantalpha -f
- 💻 SSH: systemctl status quantalpha

**Your bot is LIVE!** 🚀
