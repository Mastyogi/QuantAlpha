# 🚀 KellyAI Deployment Checklist

## Pre-Deployment Checklist

### ✅ Configuration
- [x] `.env` file created from `.env.example`
- [ ] Telegram bot token configured
- [ ] Telegram admin chat ID configured
- [ ] Bitget API keys configured (for crypto)
- [ ] MT5 credentials configured (for forex, optional)
- [ ] Database URL configured
- [ ] Redis URL configured
- [ ] Initial equity set
- [ ] Risk parameters configured
- [ ] Trading pairs selected
- [ ] Trading mode set (paper/live)

### ✅ Database Setup
- [ ] PostgreSQL/TimescaleDB installed and running
- [ ] Database created
- [ ] Database migration applied: `alembic upgrade head`
- [ ] Database connection tested

### ✅ Redis Setup
- [ ] Redis installed and running
- [ ] Redis connection tested
- [ ] Redis URL configured in `.env`

### ✅ Dependencies
- [ ] Python 3.9+ installed
- [ ] All pip dependencies installed: `pip install -r requirements.txt`
- [ ] MetaTrader5 package installed (if using MT5): `pip install MetaTrader5`

### ✅ Testing
- [ ] Unit tests passed: `pytest tests/unit/`
- [ ] Integration tests passed: `pytest tests/integration/`
- [ ] All 31 tests passing

### ✅ Exchange Setup
- [ ] Bitget account created (for crypto)
- [ ] Bitget API keys generated
- [ ] API keys have trading permissions
- [ ] MT5 account created (for forex, optional)
- [ ] MT5 terminal installed (Windows only)

### ✅ Telegram Setup
- [ ] Telegram bot created via @BotFather
- [ ] Bot token obtained
- [ ] Admin chat ID obtained (via @userinfobot)
- [ ] Bot tested with `/start` command

---

## Deployment Steps

### Step 1: Environment Setup
```bash
# Clone repository
git clone <repo_url>
cd trading-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit configuration
nano .env  # or use your preferred editor
```

### Step 2: Database Setup
```bash
# Start PostgreSQL (if not running)
sudo systemctl start postgresql  # Linux
# or
brew services start postgresql  # Mac

# Create database
createdb trading_bot

# Apply migrations
alembic upgrade head

# Verify tables created
psql trading_bot -c "\dt"
```

### Step 3: Redis Setup
```bash
# Start Redis (if not running)
sudo systemctl start redis  # Linux
# or
brew services start redis  # Mac

# Test Redis connection
redis-cli ping
# Should return: PONG
```

### Step 4: Configuration
Edit `.env` file with your settings:

```bash
# Required Settings
TRADING_MODE=paper
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_ADMIN_CHAT_ID=your_chat_id_here
BITGET_API_KEY=your_key_here
BITGET_API_SECRET=your_secret_here
BITGET_PASSPHRASE=your_passphrase_here
DATABASE_URL=postgresql://user:pass@localhost:5432/trading_bot
REDIS_URL=redis://localhost:6379/0
INITIAL_EQUITY=10000.00

# Optional MT5 Settings (for forex)
MT5_LOGIN=your_account
MT5_PASSWORD=your_password
MT5_SERVER=your_server
ENABLE_FOREX=false
```

### Step 5: Run Tests
```bash
# Run all tests
pytest tests/ -v

# Run specific test suites
pytest tests/unit/ -v
pytest tests/integration/ -v

# Check test coverage
pytest tests/ --cov=src --cov-report=html
```

### Step 6: Start Bot
```bash
# Start in paper trading mode
python src/main.py

# Or use screen/tmux for background execution
screen -S kellyai
python src/main.py
# Ctrl+A, D to detach

# Or use systemd service (Linux)
sudo systemctl start kellyai
```

### Step 7: Verify Deployment
```bash
# Check bot status via Telegram
/start
/status
/health

# Check logs
tail -f logs/trading_bot.log

# Check database
psql trading_bot -c "SELECT * FROM trades LIMIT 5;"

# Check Redis
redis-cli GET "regime:BTC/USDT"
```

---

## Post-Deployment Monitoring

### First Hour
- [ ] Bot started successfully
- [ ] Telegram bot responding to commands
- [ ] Health check passing: `/health`
- [ ] No errors in logs
- [ ] Database connection working
- [ ] Redis connection working
- [ ] Exchange connection working

### First Day
- [ ] Signals being generated
- [ ] Regime detection working
- [ ] Pattern library loading
- [ ] No circuit breaker activations
- [ ] Health checks passing
- [ ] Performance tracking working

### First Week
- [ ] Trades executed successfully
- [ ] Profit booking working
- [ ] Trailing stops working
- [ ] Pattern updates working
- [ ] Daily analysis running
- [ ] Weekly retraining scheduled

### First Month
- [ ] Compounding working (10% equity change)
- [ ] Auto-tuning running weekly
- [ ] Pattern discovery working
- [ ] Model retraining working
- [ ] Approval workflow working
- [ ] Performance meeting expectations

---

## Monitoring Commands

### Telegram Commands
```bash
/status         # Bot status
/health         # System health
/performance    # Compounding stats
/patterns       # Active patterns
/regime         # Market regimes
/pnl            # P&L report
/signals        # Recent signals
/tuning_status  # Auto-tuning status
```

### System Commands
```bash
# Check bot process
ps aux | grep python

# Check logs
tail -f logs/trading_bot.log

# Check database
psql trading_bot -c "SELECT COUNT(*) FROM trades;"

# Check Redis
redis-cli INFO stats

# Check disk space
df -h

# Check memory
free -h
```

---

## Troubleshooting

### Bot Not Starting
1. Check logs: `tail -f logs/trading_bot.log`
2. Verify database connection: `psql trading_bot`
3. Verify Redis connection: `redis-cli ping`
4. Check `.env` configuration
5. Verify all dependencies installed: `pip list`

### Telegram Not Responding
1. Verify bot token in `.env`
2. Check Telegram bot status: `curl https://api.telegram.org/bot<TOKEN>/getMe`
3. Verify admin chat ID
4. Check network connectivity
5. Check logs for Telegram errors

### Database Errors
1. Verify database running: `sudo systemctl status postgresql`
2. Check database connection: `psql trading_bot`
3. Verify migrations applied: `alembic current`
4. Check database logs: `sudo journalctl -u postgresql`

### Exchange Errors
1. Verify API keys in `.env`
2. Check API key permissions
3. Test API connection: `curl https://api.bitget.com/api/spot/v1/public/time`
4. Check rate limits
5. Verify network connectivity

### Redis Errors
1. Verify Redis running: `sudo systemctl status redis`
2. Check Redis connection: `redis-cli ping`
3. Check Redis logs: `sudo journalctl -u redis`
4. Verify Redis URL in `.env`

---

## Performance Optimization

### Database
- [ ] Enable connection pooling (already configured)
- [ ] Create indexes on frequently queried columns
- [ ] Regular VACUUM and ANALYZE
- [ ] Monitor query performance

### Redis
- [ ] Set appropriate TTL for cached data (15 min for regimes)
- [ ] Monitor memory usage
- [ ] Enable persistence if needed
- [ ] Regular monitoring

### Bot
- [ ] Monitor CPU usage
- [ ] Monitor memory usage
- [ ] Monitor network I/O
- [ ] Optimize logging level (INFO in production)

---

## Security Checklist

### API Keys
- [ ] API keys stored in `.env` (not in code)
- [ ] `.env` file in `.gitignore`
- [ ] API keys have minimum required permissions
- [ ] API keys rotated regularly

### Database
- [ ] Strong database password
- [ ] Database not exposed to internet
- [ ] Regular backups configured
- [ ] SSL/TLS enabled for connections

### Telegram
- [ ] Admin chat ID verified
- [ ] Bot token kept secret
- [ ] Admin-only commands protected
- [ ] Rate limiting enabled

### Server
- [ ] Firewall configured
- [ ] SSH key authentication
- [ ] Regular security updates
- [ ] Monitoring and alerting

---

## Backup Strategy

### Database Backups
```bash
# Daily backup
pg_dump trading_bot > backup_$(date +%Y%m%d).sql

# Automated backup script
0 2 * * * pg_dump trading_bot > /backups/trading_bot_$(date +\%Y\%m\%d).sql
```

### Configuration Backups
```bash
# Backup .env file
cp .env .env.backup

# Backup models
tar -czf models_backup.tar.gz models/
```

### Redis Backups
```bash
# Enable Redis persistence in redis.conf
save 900 1
save 300 10
save 60 10000

# Manual backup
redis-cli SAVE
```

---

## Scaling Considerations

### Horizontal Scaling
- [ ] Multiple bot instances for different pairs
- [ ] Load balancer for API endpoints
- [ ] Distributed Redis cluster
- [ ] Database read replicas

### Vertical Scaling
- [ ] Increase server resources (CPU, RAM)
- [ ] Optimize database queries
- [ ] Increase connection pool size
- [ ] Optimize Redis memory

---

## Maintenance Schedule

### Daily
- [ ] Check bot status: `/status`
- [ ] Review health checks: `/health`
- [ ] Monitor performance: `/performance`
- [ ] Check logs for errors
- [ ] Verify trades executing

### Weekly
- [ ] Review pattern performance: `/patterns`
- [ ] Check auto-tuning results: `/tuning_status`
- [ ] Verify model versions
- [ ] Analyze compounding rate
- [ ] Review audit logs

### Monthly
- [ ] Full system audit: `/audit`
- [ ] Pattern library cleanup
- [ ] Performance analysis
- [ ] Parameter adjustments
- [ ] Security review
- [ ] Backup verification

---

## Emergency Procedures

### Circuit Breaker Activated
1. Check reason: `/health`
2. Review recent trades: `/pnl`
3. Check logs for errors
4. Verify market conditions
5. Reset if safe: `/resume`

### Database Failure
1. Check database status
2. Restore from backup if needed
3. Verify data integrity
4. Restart bot

### Exchange API Failure
1. Check exchange status
2. Verify API keys
3. Check rate limits
4. Wait for recovery
5. Bot will auto-retry

### Model Performance Degradation
1. Check win rate: `/performance`
2. Review recent trades
3. Trigger retraining: `/retrain <symbol>`
4. Or rollback: `/rollback <symbol>`

---

## Success Metrics

### Week 1
- [ ] Bot running 24/7
- [ ] No critical errors
- [ ] Health checks passing
- [ ] Signals generating
- [ ] Trades executing

### Month 1
- [ ] Win rate > 55%
- [ ] Compounding working
- [ ] Pattern discovery working
- [ ] Auto-tuning running
- [ ] No major issues

### Month 3
- [ ] Win rate > 60%
- [ ] Positive returns
- [ ] Patterns improving
- [ ] Models retraining
- [ ] System stable

### Month 6
- [ ] Win rate > 65%
- [ ] Consistent returns
- [ ] Multiple patterns active
- [ ] Models optimized
- [ ] Ready for scaling

---

## Contact & Support

### Documentation
- `README.md` - Main documentation
- `IMPLEMENTATION_COMPLETE_FINAL.md` - Complete feature list
- `FINAL_SUMMARY_HINDI.md` - Hindi summary
- `MAXIMUM_COMPOUNDING_STRATEGY.md` - Compounding strategy
- `SETUP_GUIDE.md` - Setup guide

### Logs
- `logs/trading_bot.log` - Main log file
- `logs/audit.log` - Audit log
- `logs/error.log` - Error log

### Telegram
- `/help` - Show all commands
- Admin chat for support

---

## Final Checklist

Before going live:
- [ ] All configuration verified
- [ ] All tests passing
- [ ] Database migration applied
- [ ] Redis running
- [ ] Telegram bot responding
- [ ] Exchange connection working
- [ ] 48 hours paper trading successful
- [ ] Performance meeting expectations
- [ ] Backups configured
- [ ] Monitoring setup
- [ ] Emergency procedures documented

---

**Status**: Ready for Deployment ✅  
**Last Updated**: April 23, 2026  
**Version**: 1.0.0  

🚀 **READY TO LAUNCH!** 🚀
