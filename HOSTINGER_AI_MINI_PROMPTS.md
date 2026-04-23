# 🤖 Hostinger AI - Mini Prompts (Step by Step)

Hostinger AI ko ek-ek prompt dena hai. Har step ke baad wait karo aur next prompt do.

---

## 📋 PROMPT 1: System Setup

```
Update system and install Python:
apt update && apt upgrade -y && apt install -y python3 python3-pip python3-venv git build-essential libssl-dev libffi-dev python3-dev htop curl && python3 --version
```

**Wait for**: Completion message and Python version (should be 3.10+)

---

## 📋 PROMPT 2: Create Directories

```
Create bot directories:
mkdir -p /opt/quantalpha/logs /opt/quantalpha/models /opt/quantalpha/reports && chmod 755 /opt/quantalpha && ls -la /opt/quantalpha
```

**Wait for**: Directory listing showing logs, models, reports folders

---

## 📋 PROMPT 3: Setup Virtual Environment

**⚠️ IMPORTANT**: Upload your bot files to `/opt/quantalpha/` using FileZilla BEFORE this step!

```
Setup Python environment:
cd /opt/quantalpha && python3 -m venv venv && source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt
```

**Wait for**: "Successfully installed..." message (takes 3-5 minutes)

---

## 📋 PROMPT 4: Create .env File (Part 1)

```
Create config file part 1:
cat > /opt/quantalpha/.env << 'EOF'
BOT_NAME=QuantAlpha
EXCHANGE_NAME=bitget
EXCHANGE_API_KEY=bg_24b5d72feb434de76d28b3b97b0a6b52
EXCHANGE_SECRET=53caeab8cb8733c84e7c29075911176d32468edf1593505c741412cb8332c30b
EXCHANGE_PASSPHRASE=fixswingproduceclevererasesucces
TRADING_MODE=paper
TESTNET=false
EOF
```

**Wait for**: Confirmation

---

## 📋 PROMPT 5: Create .env File (Part 2)

```
Add config part 2:
cat >> /opt/quantalpha/.env << 'EOF'
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
EOF
```

**Wait for**: Confirmation

---

## 📋 PROMPT 6: Verify .env File

```
Check config file:
cat /opt/quantalpha/.env | head -20
```

**Wait for**: File content display (verify BOT_NAME=QuantAlpha is there)

---

## 📋 PROMPT 7: Test Bot

```
Test bot manually:
cd /opt/quantalpha && source venv/bin/activate && timeout 15 python3 run_trading_bot.py || true
```

**Wait for**: Should see "BOT IS RUNNING!" and "Telegram polling started"

---

## 📋 PROMPT 8: Create Service File (Part 1)

```
Create systemd service:
cat > /etc/systemd/system/quantalpha.service << 'EOF'
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
EOF
```

**Wait for**: Confirmation

---

## 📋 PROMPT 9: Create Service File (Part 2)

```
Complete service file:
cat >> /etc/systemd/system/quantalpha.service << 'EOF'
StandardOutput=append:/opt/quantalpha/logs/bot.log
StandardError=append:/opt/quantalpha/logs/bot_error.log

[Install]
WantedBy=multi-user.target
EOF
```

**Wait for**: Confirmation

---

## 📋 PROMPT 10: Start Service

```
Enable and start bot:
systemctl daemon-reload && systemctl enable quantalpha && systemctl start quantalpha && sleep 5 && systemctl status quantalpha
```

**Wait for**: Status showing "active (running)"

---

## 📋 PROMPT 11: Check Logs

```
Show bot logs:
journalctl -u quantalpha -n 30 --no-pager
```

**Wait for**: Logs showing "BOT IS RUNNING!" and "Telegram polling started"

---

## 📋 PROMPT 12: Final Verification

```
Final check:
systemctl is-active quantalpha && systemctl is-enabled quantalpha && ps aux | grep run_trading_bot.py | grep -v grep
```

**Wait for**: "active", "enabled", and process details

---

## ✅ Success!

If all prompts completed successfully:
- ✅ Bot is running
- ✅ Auto-starts on reboot
- ✅ Logs are working

**Test in Telegram**: Send `/status` to @multipiller_bot

---

## 🎮 Management Commands (After Deployment)

### Check Status
```
systemctl status quantalpha
```

### View Logs
```
journalctl -u quantalpha -f
```

### Restart Bot
```
systemctl restart quantalpha
```

### Stop Bot
```
systemctl stop quantalpha
```

---

## 🐛 If Something Fails

### Check Logs for Errors
```
journalctl -u quantalpha -n 50 --no-pager | grep -i error
```

### Restart Service
```
systemctl restart quantalpha && systemctl status quantalpha
```

### Check .env File
```
cat /opt/quantalpha/.env
```

### Test Manually
```
cd /opt/quantalpha && source venv/bin/activate && python3 run_trading_bot.py
```

---

## 📝 Notes

- **Total Prompts**: 12
- **Time**: 15-20 minutes
- **Each prompt**: Wait for completion before next
- **File Upload**: Do between Prompt 2 and 3
- **Testing**: After Prompt 12, test in Telegram

---

## 🎯 Quick Reference

```
VPS: srv1565491.hstgr.cloud
Directory: /opt/quantalpha
Service: quantalpha
Telegram: @multipiller_bot
```

**Deployment complete!** 🚀
