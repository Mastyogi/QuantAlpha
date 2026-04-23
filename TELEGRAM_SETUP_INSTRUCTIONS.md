# 🤖 Telegram Bot Setup Instructions

## ✅ Current Status
- **Bot Token**: Valid ✅
- **Bot Username**: @multipiller_bot
- **Bot Name**: QuantAlpha
- **Bot ID**: 8619104592

## 🔧 Setup Steps

### Step 1: Start Chat with Bot
1. Open Telegram app
2. Search for: `@multipiller_bot`
3. Click "START" button
4. You should see a welcome message

### Step 2: Get Your Chat ID
Your configured admin chat ID is: `7263314996`

To verify this is correct:
1. Send any message to @multipiller_bot
2. The bot will respond with your chat ID
3. Make sure it matches: `7263314996`

### Step 3: Test Bot Commands
Once you've started the chat, try these commands:
- `/start` - Main menu
- `/status` - Bot status
- `/help` - List all commands
- `/pnl` - P&L report

## 🐛 Troubleshooting

### Error: "Not Found"
**Cause**: You haven't started a chat with the bot yet

**Solution**:
1. Open Telegram
2. Search: @multipiller_bot
3. Click START
4. Send /start command

### Error: "Forbidden: bot was blocked by the user"
**Cause**: You blocked the bot

**Solution**:
1. Unblock @multipiller_bot in Telegram
2. Send /start again

### Wrong Chat ID
If the bot doesn't respond to your commands:
1. Send a message to @userinfobot in Telegram
2. It will show your chat ID
3. Update `.env` file with correct `TELEGRAM_ADMIN_CHAT_ID`

## 📱 Available Commands

### Basic Commands
- `/start` - Main menu
- `/status` - Bot & system status
- `/health` - System health check
- `/signals` - Recent trade signals
- `/pnl` - P&L summary
- `/pause` - Pause trading
- `/resume` - Resume trading

### Performance & Analytics
- `/performance` - Compounding stats
- `/patterns` - Active trading patterns
- `/audit` - Generate audit report
- `/regime` - Market regime detection

### Advanced Commands
- `/retrain <symbol>` - Trigger model retraining
- `/optimize` - Trigger parameter optimization
- `/rollback <symbol>` - Emergency model rollback
- `/tune` - Manual parameter tuning
- `/tuning_status` - Auto-tuning status
- `/pattern_off <id>` - Disable pattern
- `/pattern_on <id>` - Enable pattern

## 🎯 Next Steps

1. **Start the bot**:
   ```bash
   python src/main.py
   ```

2. **Open Telegram** and send `/start` to @multipiller_bot

3. **Monitor logs**:
   ```bash
   tail -f logs/trading_bot.log
   ```

4. **Test a command**:
   - Send `/status` in Telegram
   - You should get bot status report

## 🔐 Security Notes

- Never share your bot token
- Only admin chat ID can execute commands
- Bot runs in PAPER TRADING mode by default
- All trades are simulated until you switch to LIVE mode

## 📊 Expected Behavior

Once bot is running and Telegram is connected:
- You'll receive signal notifications
- Trade open/close alerts
- Daily P&L reports
- System health alerts
- Circuit breaker notifications

## ✅ Verification Checklist

- [ ] Bot token is valid (8619104592:AAHKWfsoyliH-DMyllrS1FZVXNW3nqcZLXQ)
- [ ] Started chat with @multipiller_bot
- [ ] Sent /start command
- [ ] Received welcome message
- [ ] Admin chat ID is correct (7263314996)
- [ ] Bot is running (python src/main.py)
- [ ] /status command works
- [ ] Receiving notifications

---

**Bot is ready!** Just start a chat with @multipiller_bot and send /start 🚀
