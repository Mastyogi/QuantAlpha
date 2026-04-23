# 🚀 Quick Start - VPS Deployment (5 Minutes)

## Choose Your Method

### 🟢 Method 1: One-Click Deploy (Easiest)
**Time**: 5 minutes  
**Best for**: Beginners, quick setup

### 🔵 Method 2: Docker (Recommended)
**Time**: 10 minutes  
**Best for**: Production, easy updates

### 🟡 Method 3: Manual (Full Control)
**Time**: 7 minutes  
**Best for**: Learning, customization

---

# 🟢 Method 1: One-Click Deploy

## Step 1: Upload Files

**Using WinSCP** (Easiest):
1. Download: https://winscp.net/
2. Connect to your VPS
3. Upload `trading-bot` folder to `/opt/kellyai/`

**Or using SCP**:
```powershell
scp -r C:\Users\rajee\trading-bot\* root@YOUR_VPS_IP:/opt/kellyai/
```

## Step 2: Run Deployment Script

```bash
# SSH into VPS
ssh root@YOUR_VPS_IP

# Go to bot directory
cd /opt/kellyai

# Make script executable
chmod +x deploy_to_vps.sh

# Run deployment
./deploy_to_vps.sh
```

## Step 3: Done!

Bot is now running! Test with:
```
/status in Telegram
```

---

# 🔵 Method 2: Docker

## Step 1: Upload Files

Same as Method 1

## Step 2: Install Docker

```bash
ssh root@YOUR_VPS_IP

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose
apt install -y docker-compose
```

## Step 3: Deploy

```bash
cd /opt/kellyai

# Create .env file
nano .env
# Paste your configuration

# Build and run
docker-compose -f docker-compose.prod.yml up -d

# Check logs
docker-compose -f docker-compose.prod.yml logs -f
```

## Step 4: Done!

Bot running in Docker! Test with:
```
/status in Telegram
```

---

# 🟡 Method 3: Manual

## Complete Steps

```bash
# 1. SSH
ssh root@YOUR_VPS_IP

# 2. Install Python
apt update && apt install -y python3 python3-pip python3-venv

# 3. Setup bot
cd /opt/kellyai
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Configure
nano .env
# Paste configuration

# 5. Create service
nano /etc/systemd/system/kellyai.service
# Paste service configuration

# 6. Start
systemctl daemon-reload
systemctl enable kellyai
systemctl start kellyai

# 7. Check
systemctl status kellyai
```

---

# 📊 Verification

## Check if Bot is Running

```bash
# Check service
systemctl status kellyai

# Should show: Active: active (running)

# Check logs
journalctl -u kellyai -f

# Should show: 🎉 BOT IS RUNNING!
```

## Test Telegram

1. Open Telegram
2. Go to @multipiller_bot
3. Send: `/status`
4. Should get bot status!

---

# 🎯 Management Commands

```bash
# Start
systemctl start kellyai

# Stop
systemctl stop kellyai

# Restart
systemctl restart kellyai

# Status
systemctl status kellyai

# Logs
journalctl -u kellyai -f
```

---

# 🐛 Troubleshooting

## Bot Not Starting

```bash
# Check logs
journalctl -u kellyai -n 50

# Check .env
cat /opt/kellyai/.env

# Test manually
cd /opt/kellyai
source venv/bin/activate
python3 run_trading_bot.py
```

## Telegram Not Working

```bash
# Verify token
grep TELEGRAM /opt/kellyai/.env

# Should show your token
```

---

# 📝 Quick Reference

## File Locations
```
Bot:     /opt/kellyai/
Config:  /opt/kellyai/.env
Service: /etc/systemd/system/kellyai.service
Logs:    /opt/kellyai/logs/
```

## Important Files
```
run_trading_bot.py       # Main bot script
.env                     # Configuration
requirements.txt         # Dependencies
docker-compose.prod.yml  # Docker config
```

---

# ✅ Success Checklist

- [ ] Files uploaded to VPS
- [ ] Dependencies installed
- [ ] .env configured
- [ ] Service created
- [ ] Bot started
- [ ] Logs show "BOT IS RUNNING"
- [ ] Telegram responds to /status

---

# 🎉 You're Done!

Your bot is now running 24/7 on VPS!

**What's working**:
- ✅ 24/7 continuous running
- ✅ Auto-restart on crash
- ✅ Auto-start on reboot
- ✅ Telegram commands
- ✅ Trading signals
- ✅ Self-improvement
- ✅ All features active

**Monitor via**:
- 📱 Telegram: /status, /health, /pnl
- 📊 Logs: journalctl -u kellyai -f
- 💻 SSH: systemctl status kellyai

**Your bot is LIVE!** 🚀

---

# 📚 Full Documentation

For detailed guides, see:
- `COMPLETE_VPS_DEPLOYMENT_GUIDE.md` - All methods explained
- `VPS_DEPLOYMENT_COMPLETE.md` - Step-by-step guide
- `24_7_DEPLOYMENT_GUIDE.md` - 24/7 running options

---

# 💡 Pro Tips

1. **Use Docker** for production (easier updates)
2. **Setup monitoring** via Telegram alerts
3. **Regular backups** of .env and database
4. **Monitor logs** daily for issues
5. **Test updates** before deploying

---

# 🆘 Need Help?

1. Check logs: `journalctl -u kellyai -f`
2. Test manually: `python3 run_trading_bot.py`
3. Verify config: `cat .env`
4. Check service: `systemctl status kellyai`

**Bot should work perfectly!** 🎊
