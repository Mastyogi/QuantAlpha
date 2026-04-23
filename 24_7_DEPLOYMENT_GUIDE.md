# 🚀 24/7 Self-Improving Bot Deployment Guide

## ✅ Current Status

Your bot **ALREADY has self-improvement** without any AI API!

### Self-Improving Features (Active Now)
1. ✅ **Daily Model Retraining** - Learns from past trades
2. ✅ **Weekly Parameter Optimization** - Tunes itself automatically
3. ✅ **Pattern Discovery** - Finds profitable patterns
4. ✅ **Performance Tracking** - Monitors and improves
5. ✅ **Adaptive Risk Management** - Adjusts to market conditions

**No AI API needed!** Everything runs locally using XGBoost and Optuna.

---

## 🎯 24/7 Deployment Options

### Option 1: Windows PC (Simplest)

#### Method A: Keep Terminal Open
```bash
# Start bot
python run_trading_bot.py

# Keep terminal window open
# Bot runs 24/7 as long as PC is on
```

**Pros**: 
- ✅ Works immediately
- ✅ No setup needed
- ✅ Easy to monitor

**Cons**:
- ❌ PC must stay on
- ❌ Stops if terminal closes
- ❌ No auto-restart on crash

---

#### Method B: Background Process with Auto-Restart
```bash
# Start with auto-restart
python keep_bot_running.py
```

**Features**:
- ✅ Runs in background
- ✅ Auto-restarts on crash
- ✅ Logs all activity
- ✅ Max 10 restart attempts

**Pros**:
- ✅ More reliable
- ✅ Handles crashes
- ✅ Better logging

**Cons**:
- ❌ PC must stay on
- ❌ Manual start needed

---

#### Method C: Windows Service (Best for Windows)

**Step 1**: Install NSSM (Non-Sucking Service Manager)
```powershell
# Download from: https://nssm.cc/download
# Or use Chocolatey:
choco install nssm
```

**Step 2**: Create Service
```powershell
# Open PowerShell as Administrator
cd C:\Users\rajee\trading-bot

# Create service
nssm install QuantAlpha "C:\Users\rajee\AppData\Local\Programs\Python\Python312\python.exe" "C:\Users\rajee\trading-bot\run_trading_bot.py"

# Configure service
nssm set QuantAlpha AppDirectory "C:\Users\rajee\trading-bot"
nssm set QuantAlpha DisplayName "QuantAlpha Trading Bot"
nssm set QuantAlpha Description "AI-powered trading bot with self-improvement"
nssm set QuantAlpha Start SERVICE_AUTO_START

# Start service
nssm start QuantAlpha
```

**Manage Service**:
```powershell
# Check status
nssm status QuantAlpha

# Stop service
nssm stop QuantAlpha

# Restart service
nssm restart QuantAlpha

# Remove service
nssm remove QuantAlpha confirm
```

**Pros**:
- ✅ Auto-starts on boot
- ✅ Runs as Windows service
- ✅ Survives user logout
- ✅ Professional setup

**Cons**:
- ❌ PC must stay on
- ❌ Requires NSSM installation

---

#### Method D: Task Scheduler (Built-in Windows)

**Step 1**: Run Setup Script
```powershell
# Right-click and "Run as Administrator"
setup_windows_autostart.bat
```

**Step 2**: Verify
```powershell
# Check if task created
schtasks /query /tn "QuantAlpha Trading Bot"

# Start manually
schtasks /run /tn "QuantAlpha Trading Bot"
```

**Pros**:
- ✅ Built into Windows
- ✅ Auto-starts on boot
- ✅ No extra software needed

**Cons**:
- ❌ PC must stay on
- ❌ Less flexible than NSSM

---

### Option 2: Cloud Deployment (Recommended for True 24/7)

#### AWS EC2 (Free Tier Available)

**Step 1**: Create EC2 Instance
```bash
# Instance type: t2.micro (free tier)
# OS: Ubuntu 22.04 LTS
# Storage: 20GB
```

**Step 2**: Setup Bot
```bash
# SSH into instance
ssh -i your-key.pem ubuntu@your-instance-ip

# Install dependencies
sudo apt update
sudo apt install python3-pip git -y

# Clone your bot
git clone your-repo-url
cd trading-bot

# Install requirements
pip3 install -r requirements.txt

# Copy .env file
nano .env
# Paste your configuration

# Start bot
python3 run_trading_bot.py
```

**Step 3**: Keep Running with Screen
```bash
# Install screen
sudo apt install screen -y

# Start screen session
screen -S kellyai

# Start bot
python3 run_trading_bot.py

# Detach: Press Ctrl+A then D
# Reattach: screen -r kellyai
```

**Cost**: $0/month (free tier) or ~$8/month after

---

#### DigitalOcean Droplet

**Step 1**: Create Droplet
- Size: Basic ($5/month)
- OS: Ubuntu 22.04
- Region: Closest to you

**Step 2**: Setup (Same as AWS above)

**Step 3**: Use Systemd Service
```bash
# Create service file
sudo nano /etc/systemd/system/quantalpha.service
```

```ini
[Unit]
Description=QuantAlpha Trading Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/trading-bot
ExecStart=/usr/bin/python3 /home/ubuntu/trading-bot/run_trading_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl enable quantalpha
sudo systemctl start quantalpha

# Check status
sudo systemctl status quantalpha

# View logs
sudo journalctl -u quantalpha -f
```

**Cost**: $5/month

---

#### Google Cloud Platform (Free Tier)

**Step 1**: Create VM Instance
- Machine type: e2-micro (free tier)
- OS: Ubuntu 22.04
- Region: us-central1

**Step 2**: Setup (Same as AWS)

**Cost**: $0/month (free tier) or ~$7/month after

---

#### Heroku (Easy Deployment)

**Step 1**: Create Procfile
```
worker: python run_trading_bot.py
```

**Step 2**: Deploy
```bash
# Install Heroku CLI
# Then:
heroku login
heroku create quantalpha-bot
git push heroku main
heroku ps:scale worker=1
```

**Cost**: $7/month (Eco dyno)

---

## 🔧 Self-Improvement Schedule (Already Active)

### Daily (3:00 AM)
```
✅ Model Retraining
   - Fetches last 90 days data
   - Retrains XGBoost models
   - Validates performance
   - Creates deployment proposal

✅ Performance Analysis
   - Calculates win rates
   - Identifies best patterns
   - Updates statistics

✅ Pattern Discovery
   - Scans for new patterns
   - Tests profitability
   - Adds to library
```

### Weekly (Sunday 2:00 AM)
```
✅ Parameter Optimization
   - Runs 30 Optuna trials
   - Tests parameter combinations
   - Finds best settings
   - Creates tuning proposal

✅ Strategy Evaluation
   - A/B testing results
   - Strategy comparison
   - Performance ranking

✅ Database Cleanup
   - Archives old data
   - Optimizes tables
   - Backs up critical data
```

### Real-Time (Continuous)
```
✅ Trade Monitoring
   - Checks positions every 60s
   - Profit booking
   - Stop loss management

✅ Risk Adjustment
   - Adapts to drawdown
   - Adjusts position sizes
   - Portfolio heat management

✅ Signal Generation
   - Scans market every 60s
   - Pattern matching
   - Confluence scoring
```

---

## 💡 Optional: Add AI API for Enhanced Features

### When to Add AI API?

**Current Setup (No AI API)**:
- ✅ Trading signals: XGBoost (local)
- ✅ Risk management: Kelly Criterion (math)
- ✅ Pattern recognition: Statistical analysis
- ✅ Self-improvement: ML retraining (local)
- ✅ Parameter tuning: Optuna (local)

**With AI API (Optional Enhancement)**:
- 📰 News sentiment analysis
- 📊 Market narrative understanding
- 🔍 Complex pattern explanation
- 📝 Trade reasoning documentation
- 🎯 Strategy suggestions

### How to Add (If Needed)

**Step 1**: Choose AI Provider
- OpenAI GPT-4 (~$0.03 per 1K tokens)
- Anthropic Claude (~$0.015 per 1K tokens)
- Google Gemini (Free tier available)

**Step 2**: Add to .env
```bash
# For OpenAI
OPENAI_API_KEY=sk-...

# For Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# For Google
GOOGLE_API_KEY=...
```

**Step 3**: Enable AI Features
```bash
# In .env
ENABLE_AI_SENTIMENT=true
ENABLE_AI_REASONING=true
ENABLE_AI_SUGGESTIONS=true
```

**Cost Estimate**:
- Light usage: $5-10/month
- Medium usage: $20-30/month
- Heavy usage: $50-100/month

---

## 📊 Monitoring Your 24/7 Bot

### Telegram Commands
```
/status      - Bot status
/pnl         - P&L report
/performance - Compounding stats
/health      - System health
/patterns    - Active patterns
```

### Log Files
```bash
# View logs
tail -f logs/trading_bot.log

# Search for errors
grep ERROR logs/trading_bot.log

# Check last 100 lines
tail -100 logs/trading_bot.log
```

### Database Monitoring
```sql
-- Check recent trades
SELECT * FROM trades ORDER BY created_at DESC LIMIT 10;

-- Check performance
SELECT * FROM performance_metrics ORDER BY date DESC LIMIT 7;

-- Check patterns
SELECT * FROM pattern_library WHERE is_active = true;
```

---

## 🎯 Recommended Setup

### For Testing (Now)
```bash
# Simple start
python run_trading_bot.py
```

### For 24/7 on Windows
```bash
# With auto-restart
python keep_bot_running.py

# Or setup as Windows Service (NSSM)
```

### For True 24/7 (Cloud)
```bash
# Deploy to DigitalOcean/AWS
# Use systemd service
# Monitor via Telegram
```

---

## ✅ Verification Checklist

### Bot is Running 24/7 When:
- [ ] Process is running continuously
- [ ] Responds to Telegram commands
- [ ] Generates signals regularly
- [ ] Executes trades (paper/live)
- [ ] Sends notifications
- [ ] Logs are updating
- [ ] Database is recording trades

### Self-Improvement is Active When:
- [ ] Models retrain daily (check logs)
- [ ] Parameters optimize weekly
- [ ] Patterns are discovered
- [ ] Performance improves over time
- [ ] Approval proposals are created

---

## 🚨 Troubleshooting

### Bot Stops Running
**Check**:
1. Is PC/server on?
2. Is Python process running?
3. Check logs for errors
4. Restart with auto-restart script

### No Self-Improvement
**Check**:
1. Are background tasks running?
2. Check database connection
3. Verify sufficient trade history
4. Check approval system

### High Resource Usage
**Solutions**:
1. Reduce scan frequency
2. Limit trading pairs
3. Optimize database queries
4. Use cloud with more RAM

---

## 💰 Cost Comparison

### Windows PC (24/7)
- **Cost**: Electricity (~$10-20/month)
- **Pros**: Full control, no monthly fees
- **Cons**: Must keep PC on, wear and tear

### Cloud VPS
- **DigitalOcean**: $5/month
- **AWS EC2**: $0-8/month
- **Google Cloud**: $0-7/month
- **Pros**: True 24/7, professional
- **Cons**: Monthly cost

### AI API (Optional)
- **None needed**: $0/month ✅
- **With AI features**: $5-50/month
- **Depends on**: Usage frequency

---

## 🎉 Summary

### Your Bot is ALREADY Self-Improving!
- ✅ No AI API needed
- ✅ Local ML models (XGBoost)
- ✅ Automatic retraining
- ✅ Parameter optimization
- ✅ Pattern discovery
- ✅ Performance tracking

### For 24/7 Running:
1. **Simple**: `python run_trading_bot.py` (keep terminal open)
2. **Better**: `python keep_bot_running.py` (auto-restart)
3. **Best**: Deploy to cloud (true 24/7)

### AI API Only Needed For:
- News sentiment (optional)
- Trade explanations (optional)
- Strategy suggestions (optional)

**Your bot is production-ready for 24/7 trading!** 🚀
