# 🐳 Hostinger Kodee - Docker Deployment Guide

## 📋 Files Ready for Kodee

Aapke paas ye files hain:

✅ **docker-compose.yml** - Main compose file  
✅ **Dockerfile** - Image build instructions  
✅ **.env** - Configuration (credentials)  
✅ **docker-compose.prod.yml** - Production version (alternative)  

---

## 🎯 Kodee Ko Kya Chahiye

Hostinger Kodee ko ye chahiye:

1. ✅ `docker-compose.yml` file
2. ✅ `.env` file (with all credentials)
3. ✅ `Dockerfile` (already hai)
4. ✅ All source code files

---

## 🚀 Method 1: Direct Docker Compose (Recommended)

### Step 1: Upload Files to VPS

**Using FileZilla**:
```
Host: srv1565491.hstgr.cloud
Username: root
Password: Your Hostinger password
Port: 22

Upload to: /opt/quantalpha/
```

**Files to upload**:
- docker-compose.yml
- Dockerfile
- .env
- requirements.txt
- All src/ folder
- All config/ folder
- run_trading_bot.py

### Step 2: Tell Kodee to Deploy

```
Deploy my Docker app:

cd /opt/quantalpha
docker-compose up -d --build

Show me the status and logs.
```

**Kodee will**:
- Build Docker image
- Start container
- Show status
- Show logs

### Step 3: Verify

```
Check Docker status:

docker ps
docker logs quantalpha-trading-bot --tail 50
```

**Expected output**:
```
✅ BOT IS RUNNING!
✅ Telegram polling started
```

### Step 4: Test Telegram

- Open @multipiller_bot
- Send: `/status`
- Should get reply!

**Done!** ✅

---

## 🚀 Method 2: Using GitHub (If You Have Repo)

### Step 1: Create GitHub Repo

```powershell
# On your PC
cd C:\Users\rajee\trading-bot

git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/quantalpha-bot.git
git push -u origin main
```

### Step 2: Tell Kodee to Clone and Deploy

```
Clone and deploy from GitHub:

cd /opt
git clone https://github.com/YOUR_USERNAME/quantalpha-bot.git quantalpha
cd quantalpha
docker-compose up -d --build

Show status and logs.
```

---

## 🚀 Method 3: Pre-built Image (Fastest)

### Step 1: Build Image Locally (Optional)

```powershell
# On your PC
cd C:\Users\rajee\trading-bot
docker build -t quantalpha-bot:latest .
docker save quantalpha-bot:latest | gzip > quantalpha-bot.tar.gz
```

### Step 2: Upload and Load on VPS

```bash
# Upload quantalpha-bot.tar.gz to VPS
# Then on VPS:
docker load < quantalpha-bot.tar.gz
docker-compose up -d
```

---

## 📝 docker-compose.yml Explanation

```yaml
version: '3.8'

services:
  quantalpha-bot:
    build:
      context: .              # Build from current directory
      dockerfile: Dockerfile  # Use this Dockerfile
    container_name: quantalpha-trading-bot
    restart: unless-stopped   # Auto-restart on crash
    env_file:
      - .env                  # Load environment variables
    volumes:
      - ./logs:/app/logs      # Persist logs
      - ./models:/app/models  # Persist ML models
      - ./reports:/app/reports # Persist reports
    networks:
      - quantalpha-network
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 60s           # Check every 60 seconds
      timeout: 10s
      retries: 3
      start_period: 30s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"       # Max 10MB per log file
        max-file: "3"         # Keep 3 log files

networks:
  quantalpha-network:
    driver: bridge

volumes:
  logs:
  models:
  reports:
```

---

## 🎮 Docker Management Commands

### Start Bot
```bash
docker-compose up -d
```

### Stop Bot
```bash
docker-compose down
```

### Restart Bot
```bash
docker-compose restart
```

### View Logs
```bash
docker-compose logs -f
# Or
docker logs quantalpha-trading-bot -f
```

### Check Status
```bash
docker ps
docker-compose ps
```

### Rebuild Image
```bash
docker-compose up -d --build
```

### Remove Everything
```bash
docker-compose down -v
```

---

## 🐛 Troubleshooting

### Issue 1: Port Already in Use

**Error**: `port is already allocated`

**Solution**:
```bash
# Find process using port
lsof -i :8000
# Kill it
kill -9 <PID>
# Or change port in .env
echo "API_PORT=8001" >> .env
```

### Issue 2: Build Fails

**Error**: `failed to build`

**Solution**:
```bash
# Check Dockerfile
cat Dockerfile

# Try building manually
docker build -t quantalpha-bot:latest .

# Check logs
docker-compose logs
```

### Issue 3: Container Keeps Restarting

**Error**: Container status shows "Restarting"

**Solution**:
```bash
# Check logs
docker logs quantalpha-trading-bot --tail 100

# Check .env file
cat .env

# Test manually
docker run -it --rm quantalpha-bot:latest python run_trading_bot.py
```

### Issue 4: Out of Memory

**Error**: `OOMKilled`

**Solution**:
```bash
# Check memory
free -h

# Upgrade VPS to 2GB RAM
# Or reduce trading pairs in .env
```

---

## 📊 Resource Monitoring

### Check Container Resources
```bash
docker stats quantalpha-trading-bot
```

### Check Disk Usage
```bash
docker system df
```

### Clean Up Unused Images
```bash
docker system prune -a
```

---

## 🔒 Security Best Practices

### 1. Secure .env File
```bash
chmod 600 .env
```

### 2. Don't Commit .env to Git
```bash
echo ".env" >> .gitignore
```

### 3. Use Docker Secrets (Advanced)
```yaml
# In docker-compose.yml
secrets:
  telegram_token:
    file: ./secrets/telegram_token.txt
```

---

## 🎯 Kodee Prompts for Docker

### Prompt 1: Install Docker
```
Install Docker and Docker Compose:

curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
apt install -y docker-compose
docker --version
docker-compose --version
```

### Prompt 2: Deploy Bot
```
Deploy QuantAlpha bot:

cd /opt/quantalpha
docker-compose up -d --build
docker ps
docker logs quantalpha-trading-bot --tail 30
```

### Prompt 3: Check Status
```
Check bot status:

docker ps | grep quantalpha
docker logs quantalpha-trading-bot --tail 50 | grep -i "running\|error"
```

### Prompt 4: Restart Bot
```
Restart bot:

cd /opt/quantalpha
docker-compose restart
docker logs quantalpha-trading-bot --tail 20
```

---

## 📱 Verification Steps

### 1. Container Running
```bash
docker ps
```
**Should show**: `quantalpha-trading-bot` with status "Up"

### 2. Logs Show Success
```bash
docker logs quantalpha-trading-bot --tail 30
```
**Should show**:
- ✅ BOT IS RUNNING!
- ✅ Telegram polling started

### 3. Telegram Working
- Send `/status` to @multipiller_bot
- Should get reply

### 4. Auto-restart Working
```bash
docker restart quantalpha-trading-bot
# Wait 30 seconds
docker ps
```
**Should show**: Container is "Up" again

---

## 🎉 Advantages of Docker Deployment

✅ **Isolated Environment** - No dependency conflicts  
✅ **Easy Updates** - Just rebuild image  
✅ **Portable** - Works on any VPS  
✅ **Resource Control** - Limit CPU/RAM  
✅ **Easy Rollback** - Keep old images  
✅ **Professional** - Industry standard  

---

## 📊 Comparison: Docker vs Direct

| Feature | Docker | Direct |
|---------|--------|--------|
| **Setup Time** | 10 min | 15 min |
| **Isolation** | ✅ Yes | ❌ No |
| **Updates** | Easy | Manual |
| **Rollback** | Easy | Hard |
| **Resource Control** | ✅ Yes | ❌ No |
| **Portability** | ✅ High | ❌ Low |
| **Complexity** | Medium | Low |

**Recommendation**: Use Docker for production!

---

## 🚀 Quick Start with Kodee

### Complete Deployment (3 Prompts)

**Prompt 1**:
```
Install Docker:
curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh && apt install -y docker-compose && docker --version
```

**Prompt 2** (after uploading files):
```
Deploy bot:
cd /opt/quantalpha && docker-compose up -d --build && docker ps
```

**Prompt 3**:
```
Show logs:
docker logs quantalpha-trading-bot --tail 50
```

**Done!** ✅

---

## 📞 Quick Reference

```
VPS: srv1565491.hstgr.cloud
Directory: /opt/quantalpha
Container: quantalpha-trading-bot
Image: quantalpha-bot:latest
Network: quantalpha-network

Start: docker-compose up -d
Stop: docker-compose down
Logs: docker logs quantalpha-trading-bot -f
Status: docker ps
Restart: docker-compose restart
```

---

## ✅ Final Checklist

- [ ] Docker installed on VPS
- [ ] Files uploaded to /opt/quantalpha/
- [ ] .env file configured
- [ ] docker-compose.yml present
- [ ] Dockerfile present
- [ ] Image built successfully
- [ ] Container running
- [ ] Logs show "BOT IS RUNNING!"
- [ ] Telegram responds to /status
- [ ] Auto-restart enabled

**Sab ✅ ho jaye to Docker deployment complete!** 🚀

---

**Docker deployment professional aur reliable hai!**  
**Hostinger Kodee easily handle kar lega!** 💪
