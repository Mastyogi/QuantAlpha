# 🚀 Hostinger VPS - Quick Start Guide

## 📋 Aapke Paas Kya Hai

✅ **VPS**: `srv1565491.hstgr.cloud`  
✅ **Bot Name**: QuantAlpha  
✅ **Telegram**: @multipiller_bot  
✅ **Mode**: Paper Trading (Safe)  
✅ **Exchange**: Bitget  

---

## 🎯 3 Files Banaye Gaye Hain

### 1. **HOSTINGER_AI_DEPLOYMENT_PROMPT.md** (Full Detail)
- Complete step-by-step prompt
- Hostinger AI ko copy-paste karne ke liye
- Sabse detailed guide
- **Use**: Agar AI se pura deployment karwana hai

### 2. **HOSTINGER_AI_SIMPLE_PROMPT.txt** (Short Version)
- Quick prompt for AI
- Sirf commands
- **Use**: Agar AI ko seedha commands dene hain

### 3. **HOSTINGER_DEPLOYMENT_STEPS.md** (Manual Guide)
- Step-by-step manual process
- Screenshots ke saath samjhaya
- **Use**: Agar khud deploy karna hai

---

## 🚀 Sabse Aasan Tarika (Recommended)

### Step 1: Hostinger Panel Kholo
```
https://hpanel.hostinger.com
Login karo
VPS select karo: srv1565491.hstgr.cloud
```

### Step 2: AI Assistant Kholo
- Panel mein "AI Assistant" ya "Kodee" dhundo
- Click karo

### Step 3: Ye Prompt Copy-Paste Karo

```
I need to deploy a Python trading bot. Please execute:

1. Update system:
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv git build-essential libssl-dev libffi-dev python3-dev htop curl

2. Create directories:
mkdir -p /opt/quantalpha/logs /opt/quantalpha/models /opt/quantalpha/reports

3. Verify Python:
python3 --version

Confirm when done.
```

### Step 4: Files Upload Karo

**FileZilla Use Karo** (Sabse Aasan):
1. Download: https://filezilla-project.org/
2. Connect:
   - Host: `srv1565491.hstgr.cloud`
   - Username: `root`
   - Password: Hostinger ka password
   - Port: `22`
3. Right side mein `/opt/quantalpha/` pe jao
4. Left side se apne PC ka `C:\Users\rajee\trading-bot` folder kholo
5. Sab files drag-drop karo

### Step 5: AI Ko Bolo Setup Kare

```
Files uploaded. Please setup:

cd /opt/quantalpha
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

Wait for completion (3-5 minutes).
```

### Step 6: .env File Banwao

```
Create /opt/quantalpha/.env with:

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

### Step 7: Service Banwao

```
Create /etc/systemd/system/quantalpha.service:

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

Then:
systemctl daemon-reload
systemctl enable quantalpha
systemctl start quantalpha
systemctl status quantalpha
```

### Step 8: Logs Dekho

```
Show logs:
journalctl -u quantalpha -n 30
```

**Dekhna Chahiye**:
```
✅ BOT IS RUNNING!
✅ Telegram polling started
```

### Step 9: Telegram Test Karo

1. Telegram kholo
2. @multipiller_bot pe jao
3. Send karo: `/status`
4. Bot reply karega!

**Done!** ✅ Bot 24/7 chal raha hai!

---

## 🎮 Bot Manage Kaise Kare

### Status Check Karo
```bash
ssh root@srv1565491.hstgr.cloud
systemctl status quantalpha
```

### Logs Dekho
```bash
ssh root@srv1565491.hstgr.cloud
journalctl -u quantalpha -f
```

### Restart Karo
```bash
ssh root@srv1565491.hstgr.cloud
systemctl restart quantalpha
```

### Stop Karo
```bash
ssh root@srv1565491.hstgr.cloud
systemctl stop quantalpha
```

---

## 📱 Telegram Commands

Bot test karne ke liye:

```
/start       - Welcome message
/status      - Bot ka status (turant kaam karega)
/pnl         - Profit/Loss report
/performance - Stats
/health      - System health
/patterns    - Active patterns
/signals     - Recent signals
/help        - Sab commands
```

---

## ✅ Success Kaise Pata Chalega

Bot chal raha hai jab:

✅ `systemctl status quantalpha` → "active (running)"  
✅ Logs mein → "BOT IS RUNNING!"  
✅ Logs mein → "Telegram polling started"  
✅ Koi error nahi  
✅ Telegram `/status` kaam kar raha  

---

## 🐛 Agar Problem Aaye

### Problem 1: Files upload nahi ho rahe
**Solution**: FileZilla use karo, SCP se aasan hai

### Problem 2: Python purana version hai
**Solution**: AI se bolo:
```
apt install -y python3.11 python3.11-venv python3.11-dev
```

### Problem 3: Memory kam hai
**Solution**: VPS upgrade karo 2GB RAM pe

### Problem 4: Telegram kaam nahi kar raha
**Solution**: Token check karo .env file mein

---

## 💰 Hostinger VPS Plans

| Plan | RAM | CPU | Price | Suitable? |
|------|-----|-----|-------|-----------|
| KVM 1 | 1GB | 1 | ₹299/mo | ⚠️ Minimum |
| KVM 2 | 2GB | 2 | ₹599/mo | ✅ **Best** |
| KVM 4 | 4GB | 2 | ₹999/mo | ✅ Overkill |

**Recommendation**: KVM 2 (2GB RAM) - ₹599/month

---

## 📞 Quick Commands

```bash
# Connect
ssh root@srv1565491.hstgr.cloud

# Status
systemctl status quantalpha

# Logs
journalctl -u quantalpha -f

# Restart
systemctl restart quantalpha
```

---

## 🎯 Files Ka Use Kaise Kare

### Agar AI Se Deploy Karwana Hai:
1. `HOSTINGER_AI_DEPLOYMENT_PROMPT.md` kholo
2. Pura content copy karo
3. Hostinger AI mein paste karo
4. AI sab kar dega

### Agar Khud Deploy Karna Hai:
1. `HOSTINGER_DEPLOYMENT_STEPS.md` kholo
2. Step-by-step follow karo
3. Commands manually run karo

### Agar Quick Commands Chahiye:
1. `HOSTINGER_AI_SIMPLE_PROMPT.txt` kholo
2. Commands copy karo
3. AI ko de do

---

## 🎉 Summary

**Kya Karna Hai**:
1. Hostinger panel kholo
2. AI assistant use karo
3. Prompts copy-paste karo
4. Files upload karo
5. Bot test karo Telegram mein

**Kitna Time Lagega**: 15-20 minutes

**Kitna Cost**: ₹599/month (recommended)

**Result**: 24/7 running trading bot! 🚀

---

## 📚 Help Files

- **Full Guide**: `HOSTINGER_AI_DEPLOYMENT_PROMPT.md`
- **Quick Prompt**: `HOSTINGER_AI_SIMPLE_PROMPT.txt`
- **Manual Steps**: `HOSTINGER_DEPLOYMENT_STEPS.md`
- **This File**: Quick reference

---

## ✅ Final Checklist

- [ ] Hostinger VPS active
- [ ] Root password ready
- [ ] FileZilla installed
- [ ] Bot files ready on PC
- [ ] AI prompt copied
- [ ] Files uploaded
- [ ] Service created
- [ ] Bot started
- [ ] Telegram tested
- [ ] Logs checked

**Sab green ho jaye to bot ready hai!** ✅

---

**Hostinger VPS perfect hai aapke bot ke liye!**  
**Ab deploy karo aur 24/7 trading shuru karo!** 🚀

**Questions?** Check detailed guides in other files!
