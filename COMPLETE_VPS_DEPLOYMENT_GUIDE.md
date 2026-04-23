## 🚀 Complete VPS Deployment Guide - All Methods

# Table of Contents
1. [Method 1: Direct Upload (Easiest)](#method-1-direct-upload)
2. [Method 2: Docker (Recommended)](#method-2-docker)
3. [Method 3: Git Deploy](#method-3-git-deploy)

---

# Method 1: Direct Upload (Easiest - 5 Minutes) ⭐

Best for: Quick start, testing, small deployments

## Step-by-Step Guide

### Step 1: Upload Files to VPS

**Option A: Using SCP (Command Line)**

```powershell
# From your Windows PC (PowerShell)
cd C:\Users\rajee\trading-bot

# Upload entire directory
scp -r * root@YOUR_VPS_IP:/opt/quantalpha/

# Example:
# scp -r * root@192.168.1.100:/opt/quantalpha/
```

**Option B: Using WinSCP (GUI - Easier)**

1. Download WinSCP: https://winscp.net/eng/download.php
2. Install and open WinSCP
3. Create new connection:
   - File protocol: SCP
   - Host name: YOUR_VPS_IP
   - Port: 22
   - User name: root
   - Password: YOUR_PASSWORD
4. Click "Login"
5. Navigate to `/opt/` on VPS (right panel)
6. Create folder `quantalpha`
7. Drag and drop all files from `C:\Users\rajee\trading-bot` to `/opt/quantalpha/`

---

### Step 2: SSH into VPS

```bash
# From PowerShell or CMD
ssh root@YOUR_VPS_IP

# Enter password when prompted
```

---

### Step 3: Install Dependencies

```bash
# Update system
apt update && apt upgrade -y

# Install Python 3.11
apt install -y python3 python3-pip python3-venv git build-essential

# Verify Python version
python3 --version  # Should be 3.10 or higher
```

---

### Step 4: Setup Bot

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

# This will take 2-3 minutes
```

---

### Step 5: Configure Environment

```bash
# Create .env file
nano .env
```

**Paste this** (update with your values):

```env
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

**Save**: Press `Ctrl+X`, then `Y`, then `Enter`

---

### Step 6: Test Bot

```bash
# Test run (should see bot starting)
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
INFO: Pairs: BTC/USDT, ETH/USDT
...
✅ Telegram app created successfully
✅ Telegram app initialized
✅ Telegram app started
✅ Telegram polling started
🎉 BOT IS RUNNING!
```

**Press `Ctrl+C` to stop** (we'll setup service next)

---

### Step 7: Create Systemd Service

```bash
# Create service file
nano /etc/systemd/system/quantalpha.service
```

**Paste this**:

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

**Save**: `Ctrl+X`, `Y`, `Enter`

---

### Step 8: Start Service

```bash
# Create logs directory
mkdir -p /opt/quantalpha/logs

# Reload systemd
systemctl daemon-reload

# Enable auto-start on boot
systemctl enable quantalpha

# Start the service
systemctl start quantalpha

# Check status
systemctl status quantalpha
```

**Should show**:
```
● quantalpha.service - QuantAlpha Trading Bot
   Loaded: loaded (/etc/systemd/system/quantalpha.service; enabled)
   Active: active (running) since ...
```

---

### Step 9: Verify Everything Works

```bash
# View live logs
journalctl -u quantalpha -f

# Should show:
# ✅ Telegram app created successfully
# ✅ Telegram polling started
# 🎉 BOT IS RUNNING!
```

**Press `Ctrl+C` to exit logs**

---

### Step 10: Test Telegram

1. Open Telegram on your phone
2. Go to @multipiller_bot
3. Send: `/status`
4. You should get bot status!

**Success!** ✅ Bot is running 24/7 on VPS!

---

## Management Commands

```bash
# Start bot
systemctl start quantalpha

# Stop bot
systemctl stop quantalpha

# Restart bot
systemctl restart quantalpha

# Check status
systemctl status quantalpha

# View logs (live)
journalctl -u quantalpha -f

# View last 100 lines
journalctl -u quantalpha -n 100
```

---

# Method 2: Docker (Recommended for Production) ⭐⭐

Best for: Production, easy updates, isolation

## Why Docker?

- ✅ Isolated environment
- ✅ Easy to update
- ✅ Consistent across systems
- ✅ Easy rollback
- ✅ Better resource management

## Step-by-Step Guide

### Step 1: Upload Files to VPS

Same as Method 1 - use SCP or WinSCP to upload files to `/opt/quantalpha/`

---

### Step 2: SSH into VPS

```bash
ssh root@YOUR_VPS_IP
```

---

### Step 3: Install Docker

```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt install -y docker-compose

# Verify installation
docker --version
docker-compose --version

# Start Docker
systemctl start docker
systemctl enable docker
```

---

### Step 4: Prepare Bot

```bash
# Go to bot directory
cd /opt/quantalpha

# Create .env file
nano .env
```

**Paste your configuration** (same as Method 1)

**Save**: `Ctrl+X`, `Y`, `Enter`

---

### Step 5: Build Docker Image

```bash
# Build image
docker build -t quantalpha-bot:latest .

# This will take 3-5 minutes
```

**Expected output**:
```
Successfully built abc123def456
Successfully tagged quantalpha-bot:latest
```

---

### Step 6: Run with Docker Compose

```bash
# Start bot
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

**Should show**:
```
✅ Loaded .env
✅ Telegram app created successfully
🎉 BOT IS RUNNING!
```

**Press `Ctrl+C` to exit logs** (bot keeps running)

---

### Step 7: Verify

```bash
# Check container status
docker ps

# Should show quantalpha-trading-bot running

# Test Telegram
# Send /status to @multipiller_bot
```

**Success!** ✅ Bot running in Docker!

---

## Docker Management Commands

```bash
# Start bot
docker-compose -f docker-compose.prod.yml up -d

# Stop bot
docker-compose -f docker-compose.prod.yml down

# Restart bot
docker-compose -f docker-compose.prod.yml restart

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Update bot
docker-compose -f docker-compose.prod.yml down
docker build -t quantalpha-bot:latest .
docker-compose -f docker-compose.prod.yml up -d

# Check resource usage
docker stats quantalpha-trading-bot
```

---

## Auto-Start Docker on Boot

```bash
# Create systemd service for Docker Compose
nano /etc/systemd/system/quantalpha-docker.service
```

**Paste**:
```ini
[Unit]
Description=QuantAlpha Trading Bot (Docker)
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/quantalpha
ExecStart=/usr/bin/docker-compose -f docker-compose.prod.yml up -d
ExecStop=/usr/bin/docker-compose -f docker-compose.prod.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

**Enable**:
```bash
systemctl daemon-reload
systemctl enable quantalpha-docker
systemctl start quantalpha-docker
```

---

# Method 3: Git Deploy (Best for Updates) ⭐

Best for: Frequent updates, version control, team collaboration

## Step-by-Step Guide

### Step 1: Create Git Repository

**On your PC**:

```powershell
cd C:\Users\rajee\trading-bot

# Initialize git (if not already)
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit"

# Create repository on GitHub/GitLab
# Then push
git remote add origin https://github.com/YOUR_USERNAME/quantalpha-bot.git
git push -u origin main
```

---

### Step 2: Clone on VPS

```bash
# SSH into VPS
ssh root@YOUR_VPS_IP

# Install git
apt update && apt install -y git python3 python3-pip python3-venv

# Clone repository
cd /opt
git clone https://github.com/YOUR_USERNAME/quantalpha-bot.git quantalpha

# Go to directory
cd /opt/quantalpha
```

---

### Step 3: Setup (Same as Method 1)

```bash
# Create venv
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Create .env
nano .env
# Paste configuration

# Test
python3 run_trading_bot.py
```

---

### Step 4: Create Service (Same as Method 1)

Follow Step 7-8 from Method 1

---

### Step 5: Update Bot (Easy!)

```bash
# Stop bot
systemctl stop quantalpha

# Pull latest changes
cd /opt/quantalpha
git pull origin main

# Update dependencies (if changed)
source venv/bin/activate
pip install -r requirements.txt

# Restart bot
systemctl start quantalpha

# Check logs
journalctl -u quantalpha -f
```

---

# 📊 Comparison Summary

| Feature | Direct | Docker | Git |
|---------|--------|--------|-----|
| **Setup Time** | 5 min | 10 min | 7 min |
| **Difficulty** | Easy | Medium | Easy |
| **Updates** | Manual | Rebuild | `git pull` |
| **Isolation** | No | Yes | No |
| **Rollback** | Hard | Easy | Easy |
| **Best For** | Testing | Production | Development |

---

# 🎯 Recommendations

## For Beginners
**Use Method 1 (Direct Upload)**
- Easiest to understand
- Quick to setup
- Good for learning

## For Production
**Use Method 2 (Docker)**
- Professional setup
- Easy to manage
- Better isolation
- Easy updates

## For Development
**Use Method 3 (Git)**
- Easy updates
- Version control
- Team collaboration

---

# 🔧 Post-Deployment Checklist

- [ ] Bot uploaded to VPS
- [ ] Dependencies installed
- [ ] .env file configured
- [ ] Bot tested manually
- [ ] Service created
- [ ] Service started
- [ ] Auto-start enabled
- [ ] Logs show "BOT IS RUNNING"
- [ ] Telegram responds to /status
- [ ] Firewall configured (optional)

---

# 🐛 Troubleshooting

## Bot Not Starting

```bash
# Check logs
journalctl -u kellyai -n 50

# Or for Docker
docker-compose -f docker-compose.prod.yml logs

# Common issues:
# 1. Missing .env file
# 2. Wrong Python version
# 3. Missing dependencies
# 4. Port already in use
```

## Telegram Not Working

```bash
# Check token
grep TELEGRAM /opt/kellyai/.env

# Test token manually
python3 -c "from telegram import Bot; import asyncio; bot = Bot('YOUR_TOKEN'); print(asyncio.run(bot.get_me()))"
```

## High Memory Usage

```bash
# Check memory
free -h

# Check bot memory
ps aux | grep python

# Restart if needed
systemctl restart kellyai
```

---

# 📝 Quick Reference

## File Locations
```
Bot directory:    /opt/kellyai/
Virtual env:      /opt/kellyai/venv/
Config file:      /opt/kellyai/.env
Service file:     /etc/systemd/system/kellyai.service
Logs:             /opt/kellyai/logs/
```

## Important Commands
```bash
# Service
systemctl start kellyai
systemctl stop kellyai
systemctl restart kellyai
systemctl status kellyai

# Logs
journalctl -u kellyai -f
tail -f /opt/kellyai/logs/bot.log

# Docker
docker-compose -f docker-compose.prod.yml up -d
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml logs -f
```

---

# 🎉 Success!

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

**Your bot is LIVE and trading 24/7!** 🚀
