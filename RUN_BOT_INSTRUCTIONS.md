# 🚀 How to Run KellyAI Trading Bot

## ✅ Test Successful!

Your bot just sent you a test message in Telegram! Check @multipiller_bot chat.

---

## 🎯 Why /start Didn't Work Before

**Problem**: You sent `/start` command but bot was not running  
**Solution**: Bot needs to be running continuously to respond to commands

---

## 🚀 Start Bot (3 Methods)

### Method 1: Direct Run (Recommended for Testing)
```bash
python src/main.py
```

**What happens**:
- Bot starts and runs continuously
- Listens for Telegram commands
- Generates trading signals
- Executes paper trades
- Sends notifications

**To stop**: Press `Ctrl+C`

---

### Method 2: Background Run (Windows)
```powershell
# Start in background
Start-Process python -ArgumentList "src/main.py" -WindowStyle Hidden

# Check if running
Get-Process python

# Stop
Stop-Process -Name python
```

---

### Method 3: Keep Terminal Open
```bash
# Start bot
python src/main.py

# Keep this terminal window open
# Bot will run until you close it or press Ctrl+C
```

---

## 📱 Using Telegram Commands

### Step 1: Start Bot
```bash
python src/main.py
```

**Leave this running!** Don't close the terminal.

### Step 2: Open Telegram
- Open @multipiller_bot chat
- You should see the test message we just sent

### Step 3: Send Commands
Now try these commands:
```
/start    - Welcome message
/status   - Bot status
/help     - All commands
/pnl      - P&L report
```

**Bot will respond immediately!**

---

## 🔍 What You'll See

### In Terminal (Bot Running)
```
============================================================
  AI Trading Bot — Starting Up
  Mode: PAPER
  Pairs: BTC/USDT, ETH/USDT
============================================================
INFO: Adaptive Risk Manager initialized
INFO: Portfolio Compounder initialized
INFO: Starting BotEngineV2...
INFO: EventBus started
[TELEGRAM] ✅ Bot @multipiller_bot connected!
INFO: BotEngineV2 ready. Equity=$10,000.00
```

### In Telegram (When You Send /status)
```
🟢 BOT STATUS

State: READY
Mode: PAPER
Uptime: 00:05:23
Equity: $10,000.00
Daily PnL: $0.00
Open Positions: 0
Pairs: BTC/USDT, ETH/USDT
```

---

## ⚠️ Important Notes

### Bot Must Be Running
- ❌ Bot not running = Commands don't work
- ✅ Bot running = Commands work instantly

### Keep Terminal Open
- Don't close the terminal where bot is running
- Bot stops if you close terminal
- Use background method for permanent running

### Test Message Received?
- Check @multipiller_bot in Telegram
- You should have received: "🧪 Bot Test Message"
- If yes, bot is working perfectly!

---

## 🎯 Quick Start Guide

### 1. Start Bot
```bash
python src/main.py
```

### 2. Wait for Startup (10 seconds)
Look for this line:
```
[TELEGRAM] ✅ Bot @multipiller_bot connected!
```

### 3. Test in Telegram
Send to @multipiller_bot:
```
/status
```

### 4. You Should Get Response
```
🟢 BOT STATUS
State: READY
...
```

---

## 🐛 Troubleshooting

### Bot Not Responding to Commands

**Check 1**: Is bot running?
```bash
# Check if Python process is running
Get-Process python
```

**Check 2**: Did you see startup message?
```
[TELEGRAM] ✅ Bot @multipiller_bot connected!
```

**Check 3**: Did you click START in Telegram?
- Open @multipiller_bot
- Click START button
- Then send commands

### "Flood Control" Error

**What it means**: Too many API calls  
**Solution**: Wait 5-10 minutes  
**Note**: This doesn't affect bot operation, only testing

### Bot Stops Immediately

**Cause**: Error in startup  
**Solution**: Check error message in terminal  
**Common issues**:
- Database connection failed
- .env file not found
- Missing dependencies

---

## 📊 Expected Behavior

### First 5 Minutes
- Bot initializes all components
- Connects to Telegram
- Starts market scanning
- No signals yet (normal)

### After 15-30 Minutes
- First signals generated
- Telegram notifications sent
- Trades executed (paper mode)
- P&L tracking starts

### Continuous Operation
- Scans market every 60 seconds
- Generates signals when conditions met
- Executes trades automatically
- Sends notifications for all events
- Responds to Telegram commands instantly

---

## 🎉 Success Checklist

- [x] Test message received in Telegram ✅
- [ ] Bot started with `python src/main.py`
- [ ] Saw "[TELEGRAM] ✅ Bot connected!" message
- [ ] Sent /status command
- [ ] Received bot status response
- [ ] Bot running continuously

---

## 🚀 Ready to Go!

**Your bot is working!** Just:

1. **Start bot**: `python src/main.py`
2. **Keep terminal open**
3. **Send /status in Telegram**
4. **Enjoy automated trading!**

---

**Pro Tip**: Open two terminals:
- Terminal 1: Run bot (`python src/main.py`)
- Terminal 2: Monitor logs (`Get-Content logs/trading_bot.log -Tail 50 -Wait`)

This way you can see everything happening in real-time! 📊
