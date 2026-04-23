# 🤖 Telegram Bot Creation Guide

## ⚠️ Current Issue
Your bot token `8619104592:AAHKWfsoyliH-DMyllrS1FZVXNW3nqcZLXQ` is returning "Not Found" error.

This means:
- Bot was deleted from BotFather
- Token was revoked
- Bot doesn't exist anymore

## 🔧 Solution: Create New Bot

### Step 1: Open BotFather
1. Open Telegram
2. Search for: `@BotFather`
3. Start chat with BotFather

### Step 2: Create New Bot
Send this command to BotFather:
```
/newbot
```

### Step 3: Choose Bot Name
BotFather will ask for a name. Choose something like:
```
KellyAI Trading Bot
```
or
```
QuantAlpha Bot
```

### Step 4: Choose Username
BotFather will ask for username. Must end with "bot":
```
kellyai_trading_bot
```
or
```
quantalpha_trading_bot
```

### Step 5: Get Your Token
BotFather will give you a token like:
```
1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567
```

### Step 6: Update .env File
Copy the new token and update your `.env` file:
```bash
TELEGRAM_BOT_TOKEN=YOUR_NEW_TOKEN_HERE
```

### Step 7: Get Your Chat ID
1. Search for `@userinfobot` in Telegram
2. Start chat and send any message
3. Bot will reply with your chat ID
4. Update `.env` with your chat ID:
```bash
TELEGRAM_ADMIN_CHAT_ID=YOUR_CHAT_ID_HERE
```

### Step 8: Configure Bot Settings (Optional)
Send these commands to @BotFather:

**Set Description**:
```
/setdescription
```
Then select your bot and send:
```
AI-powered trading bot with self-learning capabilities. Supports crypto and forex markets with automated risk management.
```

**Set About Text**:
```
/setabouttext
```
Then:
```
KellyAI - Hedge Fund Grade Trading Bot
```

**Set Commands**:
```
/setcommands
```
Then paste this:
```
start - Main menu
status - Bot status
health - System health
signals - Recent signals
pnl - P&L report
pause - Pause trading
resume - Resume trading
performance - Compounding stats
patterns - Active patterns
regime - Market regimes
help - Show all commands
```

### Step 9: Test New Bot
Run this command to test:
```bash
python quick_test.py
```

### Step 10: Start Bot
```bash
python src/main.py
```

## 🎯 Quick Setup Commands

```bash
# 1. Update .env with new token
# TELEGRAM_BOT_TOKEN=your_new_token

# 2. Test connection
python quick_test.py

# 3. Start bot
python src/main.py

# 4. Open Telegram and send /start to your bot
```

## 📱 Alternative: Use Existing Bot

If you already have a bot:
1. Open @BotFather
2. Send `/mybots`
3. Select your bot
4. Click "API Token"
5. Copy the token
6. Update `.env` file

## 🔐 Security Tips

- Never share your bot token publicly
- Don't commit `.env` file to git
- Regenerate token if compromised:
  - Send `/revoke` to @BotFather
  - Select your bot
  - Get new token

## ✅ Verification

After creating new bot, you should see:
```
✅ Bot connected: @your_bot_username (Your Bot Name)
```

## 🐛 Troubleshooting

### "Not Found" Error
- Token is invalid or revoked
- Create new bot with /newbot

### "Unauthorized" Error
- Token format is wrong
- Check for extra spaces in .env

### "Forbidden" Error
- You blocked the bot
- Unblock and send /start

---

**Need Help?** 
1. Make sure you're talking to the real @BotFather (verified account)
2. Token should be in format: `123456789:ABCdefGHI...`
3. No spaces before or after token in .env file
