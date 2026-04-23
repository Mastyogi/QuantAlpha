# 🐳 Hostinger Kodee - Complete Docker Package

## 📦 Kodee Ko Ye Files Chahiye

### ✅ Already Ready:
1. **docker-compose.yml** - Main compose file (root folder mein)
2. **Dockerfile** - Image build file (root folder mein)
3. **.env** - Configuration with credentials (root folder mein)
4. **requirements.txt** - Python dependencies
5. **src/** - All source code
6. **config/** - Configuration files
7. **run_trading_bot.py** - Main entry point

---

## 🎯 Kodee Deployment (3 Steps Only!)

### Step 1: Upload Files

**Using FileZilla**:
```
Host: srv1565491.hstgr.cloud
Username: root
Password: Your Hostinger password
Port: 22

Upload entire folder to: /opt/quantalpha/
```

**Files structure on VPS**:
```
/opt/quantalpha/
├── docker-compose.yml
├── Dockerfile
├── .env
├── requirements.txt
├── run_trading_bot.py
├── src/
│   ├── main.py
│   ├── core/
│   ├── data/
│   ├── signals/
│   ├── execution/
│   ├── risk/
│   ├── ml/
│   ├── telegram/
│   └── ...
└── config/
    ├── settings.py
    └── ...
```

---

### Step 2: Tell Kodee (Prompt 1)

```
Install Docker and Docker Compose:

curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh && apt install -y docker-compose && docker --version && docker-compose --version
```

**Wait for**: Docker version output (e.g., Docker version 24.0.x)

---

### Step 3: Tell Kodee (Prompt 2)

```
Build and start QuantAlpha bot:

cd /opt/quantalpha && docker-compose up -d --build && sleep 10 && docker ps && docker logs quantalpha-trading-bot --tail 50
```

**Wait for**: 
- Container building (2-3 minutes)
- Container starting
- Logs showing "BOT IS RUNNING!"

---

### Step 4: Verify

**In Telegram**:
- Open @multipiller_bot
- Send: `/status`
- Should get reply!

**Done!** ✅ Bot is running 24/7 in Docker!

---

## 📋 What Kodee Will Do

### Prompt 1 (Install Docker):
```
✅ Download Docker installation script
✅ Install Docker engine
✅ Install Docker Compose
✅ Verify installation
```

### Prompt 2 (Deploy Bot):
```
✅ Go to bot directory
✅ Build Docker image from Dockerfile
✅ Create container from image
✅ Start container in background
✅ Show container status
✅ Show bot logs
```

---

## 🎮 Management Commands

### Check Status
```bash
docker ps
docker-compose ps
```

### View Logs
```bash
docker logs quantalpha-trading-bot -f
docker-compose logs -f
```

### Restart Bot
```bash
docker-compose restart
```

### Stop Bot
```bash
docker-compose down
```

### Update Bot
```bash
# Upload new files
docker-compose down
docker-compose up -d --build
```

### Check Resources
```bash
docker stats quantalpha-trading-bot
```

---

## 📊 Files Explanation

### 1. docker-compose.yml
```yaml
# Main orchestration file
# Defines:
# - Service name: quantalpha-bot
# - Container name: quantalpha-trading-bot
# - Build context: current directory
# - Volumes: logs, models, reports
# - Network: quantalpha-network
# - Restart policy: unless-stopped
# - Health check: every 60 seconds
```

### 2. Dockerfile
```dockerfile
# Image build instructions
# Steps:
# 1. Use Python 3.11 slim base
# 2. Install system dependencies
# 3. Install Python packages
# 4. Copy application code
# 5. Set working directory
# 6. Expose ports (8000, 8080)
# 7. Run bot
```

### 3. .env
```env
# Configuration file
# Contains:
# - Bot name: QuantAlpha
# - Exchange credentials (Bitget)
# - Telegram bot token
# - Database URL (Supabase)
# - Trading pairs
# - Risk parameters
# - All sensitive data
```

---

## ✅ Success Indicators

### 1. Docker Installed
```bash
$ docker --version
Docker version 24.0.7, build afdd53b
```

### 2. Container Running
```bash
$ docker ps
CONTAINER ID   IMAGE                  STATUS
abc123def456   quantalpha-bot:latest  Up 2 minutes
```

### 3. Logs Show Success
```bash
$ docker logs quantalpha-trading-bot --tail 20
✅ Loaded .env
✅ Telegram token loaded
🤖 QuantAlpha Trading Bot
INFO: QuantAlpha Trading Bot — Starting Up
✅ Telegram polling started
🎉 BOT IS RUNNING!
```

### 4. Telegram Working
```
/status → Bot replies with status
```

---

## 🐛 Troubleshooting

### Issue: Container Not Starting

**Check logs**:
```bash
docker logs quantalpha-trading-bot --tail 100
```

**Common causes**:
- Missing .env file
- Wrong credentials in .env
- Port 8000 already in use
- Out of memory

**Solution**:
```bash
# Check .env exists
ls -la /opt/quantalpha/.env

# Check .env content
cat /opt/quantalpha/.env | head -10

# Check memory
free -h

# Restart container
docker-compose restart
```

---

### Issue: Build Fails

**Error**: `failed to build`

**Solution**:
```bash
# Check Dockerfile
cat /opt/quantalpha/Dockerfile

# Check requirements.txt
cat /opt/quantalpha/requirements.txt

# Try manual build
cd /opt/quantalpha
docker build -t quantalpha-bot:latest .

# Check for errors in output
```

---

### Issue: Telegram Not Working

**Check**:
```bash
# Verify token in .env
grep TELEGRAM /opt/quantalpha/.env

# Check bot logs
docker logs quantalpha-trading-bot | grep -i telegram

# Test token manually
docker exec -it quantalpha-trading-bot python -c "from telegram import Bot; import asyncio; bot = Bot('YOUR_TOKEN'); print(asyncio.run(bot.get_me()))"
```

---

## 💡 Pro Tips

### 1. Keep Images Clean
```bash
# Remove old images
docker image prune -a

# Remove unused volumes
docker volume prune
```

### 2. Monitor Resources
```bash
# Real-time stats
docker stats quantalpha-trading-bot

# Check disk usage
docker system df
```

### 3. Backup Data
```bash
# Backup volumes
docker run --rm -v quantalpha_logs:/data -v $(pwd):/backup alpine tar czf /backup/logs-backup.tar.gz /data

# Backup .env
cp /opt/quantalpha/.env /root/backups/.env.backup
```

### 4. Update Bot
```bash
# Stop bot
docker-compose down

# Upload new files via FileZilla

# Rebuild and start
docker-compose up -d --build

# Check logs
docker logs quantalpha-trading-bot -f
```

---

## 📞 Quick Reference Card

```
═══════════════════════════════════════════════
HOSTINGER KODEE - DOCKER QUICK REFERENCE
═══════════════════════════════════════════════

VPS: srv1565491.hstgr.cloud
Directory: /opt/quantalpha
Container: quantalpha-trading-bot
Image: quantalpha-bot:latest

INSTALL:
curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh && apt install -y docker-compose

DEPLOY:
cd /opt/quantalpha && docker-compose up -d --build

STATUS:
docker ps

LOGS:
docker logs quantalpha-trading-bot -f

RESTART:
docker-compose restart

STOP:
docker-compose down

UPDATE:
docker-compose down && docker-compose up -d --build

STATS:
docker stats quantalpha-trading-bot

═══════════════════════════════════════════════
```

---

## 🎉 Summary

**Files Ready**:
- ✅ docker-compose.yml (root folder)
- ✅ Dockerfile (root folder)
- ✅ .env (root folder)
- ✅ All source code

**Kodee Prompts**: Only 2!
1. Install Docker
2. Deploy bot

**Time**: 10-15 minutes

**Result**: Professional Docker deployment! 🚀

---

## 🚀 Ready to Deploy!

1. **Upload files** to `/opt/quantalpha/` via FileZilla
2. **Copy Prompt 1** from `KODEE_DOCKER_PROMPTS.txt`
3. **Paste to Kodee** and wait
4. **Copy Prompt 2** and paste
5. **Test in Telegram**: `/status`

**Done!** ✅

---

**Docker deployment is professional and reliable!**  
**Kodee will handle everything automatically!** 💪

**Happy Trading!** 📈
