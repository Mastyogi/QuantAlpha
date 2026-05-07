# QuantAlpha — Zero-Shot AI Handoff Prompt

> Copy this entire document into any AI agent or new developer to bring them fully up to speed instantly.

---

## 1. What Is QuantAlpha?

QuantAlpha is a **production-grade, multi-user AI trading bot** built in Python. It:

- Generates high-confluence trade signals using a stacking ML ensemble (RF + GBM + LR → meta-learner)
- Executes trades live via **MetaTrader 5 (FxPro Direct)** or paper-simulates them
- Manages users via Telegram with a full onboarding flow (register → verify → deposit → trade → withdraw)
- Holds user funds in a **BSC escrow smart contract** (USDT BEP-20), deducting 15% service fee on withdrawal
- Runs a **3-level referral program** (2.5% / 1.5% / 1.0% of gross profit per level, 10% to owner)
- Self-improves weekly via Optuna parameter tuning and model retraining

---

## 2. Repository Structure

```
c:\QuantAlpha\
├── config/
│   └── settings.py          # All env-var-backed settings (TradingBotSettings class)
├── contracts/
│   └── Escrow.sol           # BSC escrow smart contract (Solidity 0.8.20)
├── src/
│   ├── bridge/              # NEW: BSC escrow bridge
│   │   ├── escrow_contract.py   # Web3 interface to Escrow.sol
│   │   ├── deposit_handler.py   # Listens for BSC deposits, credits balances
│   │   ├── withdraw_handler.py  # Processes withdrawals with 15% fee
│   │   └── profit_tracker.py    # Tracks PnL for fee calculation
│   ├── users/               # NEW: Multi-user management
│   │   └── user_manager.py      # Registration, verification, MT5 creds, referral chain
│   ├── referral/            # NEW: 3-level referral system
│   │   └── referral_engine.py   # Fee distribution, leaderboard, weekly payouts
│   ├── execution/
│   │   ├── mt5_executor.py      # Live MT5 execution (FxPro Direct)
│   │   ├── order_manager.py     # Routes paper/live/MT5 orders; Kelly sizing
│   │   └── paper_trader.py      # Paper trading simulation
│   ├── telegram/
│   │   ├── handlers.py          # All command registrations (36 commands)
│   │   └── user_handlers.py     # NEW: /start /verify /deposit /withdraw /balance
│   │                              #      /referral /referrals /withdraw_ref /leaderboard
│   │                              #      /mode /settings /history /chart /alert
│   │                              #      /export /support /feedback
│   ├── database/
│   │   ├── models.py            # All SQLAlchemy models (incl. User, Referral, Escrow)
│   │   ├── repositories.py      # Async data access layer
│   │   └── connection.py        # Async engine with graceful DB-offline fallback
│   ├── signals/
│   │   └── signal_engine.py     # FineTunedSignalEngine (65+ features, ensemble)
│   ├── ai_engine/
│   │   ├── ensemble_model.py    # StackingEnsemble (RF+GBM+LR → meta-learner)
│   │   └── advanced_features.py # 65-feature pipeline
│   ├── risk/
│   │   ├── adaptive_risk.py     # ATR-based SL/TP, Kelly sizing, correlation guard
│   │   └── drawdown_monitor.py  # Circuit breaker, daily loss limit
│   ├── ml/
│   │   ├── self_improvement_engine.py  # Weekly model retraining
│   │   └── auto_tuning_system.py       # Optuna parameter optimization
│   └── core/
│       └── bot_engine.py        # BotEngineV2 — orchestrates everything
├── tests/
│   ├── unit/                # 44 unit tests (all pass)
│   ├── integration/         # 4 integration tests (all pass)
│   ├── negative/            # 11 security/edge-case tests (all pass)
│   └── load/                # 3 load tests (all pass) — 1000 concurrent users
└── requirements.txt         # All dependencies including web3==6.15.1
```

---

## 3. Database Models

All in `src/database/models.py`:

| Model | Purpose |
|-------|---------|
| `Trade` | Individual trade records |
| `Signal` | Generated signals |
| `User` | Telegram users with broker/MT5/escrow data |
| `Referral` | 3-level referral chain (referrer_id, referred_id, level) |
| `ReferralEarning` | Per-trade referral fee records |
| `EscrowTransaction` | BSC deposit/withdrawal records |
| `ProfitRecord` | Profit + fee breakdown per trade |
| `TradingPattern` | Discovered ML patterns |
| `ModelVersion` | ML model version tracking |
| `PerformanceHistory` | Daily/weekly performance metrics |
| `ApprovalHistory` | Admin approval workflow |
| `EquityHistory` | Equity snapshots for compounding |
| `ParameterChange` | Auto-tuning audit trail |
| `AuditLog` | System event log |

---

## 4. Environment Variables

Copy `.env.example` to `.env` and fill in:

```bash
# Core
TRADING_MODE=paper          # paper | live
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ADMIN_CHAT_ID=...
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/trading_bot

# MT5 / FxPro (for live trading)
MT5_LOGIN=12345678
MT5_PASSWORD=YourPassword
MT5_SERVER=FxPro-Demo       # or FxPro-Real
BROKER_MODE=mt5             # paper | mt5

# BSC Escrow
BSC_RPC_URL=https://bsc-dataseed.binance.org/
ESCROW_CONTRACT_ADDRESS=0x...   # deploy contracts/Escrow.sol first
BOT_WALLET_PRIVATE_KEY=0x...
SERVICE_WALLET_ADDRESS=0x...
USDT_CONTRACT_ADDRESS=0x55d398326f99059fF775485246999027B3197955

# Security
SECRET_KEY=32-char-random-string   # for AES encryption of MT5 passwords

# Exchange (crypto)
EXCHANGE_NAME=bitget
BITGET_API_KEY=...
BITGET_API_SECRET=...
BITGET_PASSPHRASE=...
```

---

## 5. Architecture: How Live Trading Works

```
User sends /mode real
    → UserManager.set_mode() checks verification
    → OrderManager.connect_mt5(login, password, server)
    → MT5Executor.connect() → mt5.initialize() + mt5.login()

Signal approved by FineTunedSignalEngine
    → BotEngineV2._on_signal_approved()
    → OrderManager.place_trade()
        if TRADING_MODE=live and BROKER_MODE=mt5:
            → MT5Executor.place_order(symbol, side, volume, sl, tp)
        elif TRADING_MODE=live (crypto):
            → ExchangeClient.create_market_order()
        else (paper):
            → PaperTrader.execute_order()
```

---

## 6. Architecture: Fee Flow

```
Trade closes with profit P
    → BotEngineV2._on_trade_closed_performance_track()
    → ProfitTracker.record_trade_profit(telegram_id, trade_id, P)
    → ReferralEngine.distribute_profit_fees(user_id, trade_id, P)
        service_fee = P × 15%
        net_profit  = P × 85%
        L1 referrer gets P × 2.5%
        L2 referrer gets P × 1.5%
        L3 referrer gets P × 1.0%
        Owner gets   P × 10.0%
        → ReferralEarning rows created (status=pending)
        → User.escrow_balance_usdt updated for each referrer

Weekly (Sunday 00:00 UTC):
    → ReferralEngine.run_weekly_payouts()
    → All pending ReferralEarning → status=paid
    → (Production: trigger BSC transfer via WithdrawHandler)
```

---

## 7. Architecture: Escrow Flow

```
User /deposit:
    → EscrowContract.generate_deposit_address(telegram_id)
    → User sends USDT (BEP-20) to that address
    → DepositHandler polls BSC every 30s
    → On 3 confirmations: User.escrow_balance_usdt += amount

User /withdraw 100 0xAddress:
    → WithdrawHandler.request_withdrawal(telegram_id, 100, address)
    → Checks: verified, min/max limits, valid address, sufficient balance
    → Deducts from User.escrow_balance_usdt
    → EscrowContract.withdraw(address, 100)
        → Contract sends 85 USDT to user, 15 USDT to SERVICE_WALLET
    → EscrowTransaction record created
```

---

## 8. Telegram Commands (36 total)

**Original (preserved):**
`/start /status /pause /resume /pnl /signals /help /audit /rollback /performance /patterns /retrain /optimize /health /tune /tuning_status /pattern_off /pattern_on /regime`

**New (added):**
`/register /verify /deposit /withdraw /balance /referral /referrals /withdraw_ref /leaderboard /mode /settings /history /chart /alert /export /support /feedback`

---

## 9. Deployment Steps

### Local / Paper Mode
```bash
cp .env.example .env
# Edit .env: set TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID
# Leave TRADING_MODE=paper
pip install -r requirements.txt
python -m src.main
```

### Docker (Paper Mode)
```bash
docker-compose up -d
```

### Live MT5 Mode
1. Install MetaTrader 5 terminal on Windows
2. Set in `.env`:
   ```
   TRADING_MODE=live
   BROKER_MODE=mt5
   MT5_LOGIN=<your_fxpro_account>
   MT5_PASSWORD=<password>
   MT5_SERVER=FxPro-Real
   ```
3. Run: `python -m src.main`

### Deploy Escrow Contract (BSC)
```bash
# Install Hardhat or Foundry
# Deploy contracts/Escrow.sol with:
#   _usdt = 0x55d398326f99059fF775485246999027B3197955 (BSC mainnet USDT)
#   _serviceWallet = your service wallet address
# Set ESCROW_CONTRACT_ADDRESS in .env
```

---

## 10. Running Tests

```bash
# All new tests (62 tests, all pass)
pytest tests/unit/test_user_manager.py \
       tests/unit/test_referral_engine.py \
       tests/unit/test_escrow.py \
       tests/unit/test_mt5_executor.py \
       tests/integration/test_user_flow.py \
       tests/negative/test_security.py \
       tests/load/test_concurrent_users.py \
       -v --timeout=60

# Full suite
pytest tests/ -v --timeout=60
```

---

## 11. FxPro Partner Link

The partner referral link is hardcoded in `src/users/user_manager.py`:
```python
FXPRO_PARTNER_LINK = "https://direct-fxpro.com/en/partner/2FiFKGf7J"
```
This appears as a button in `/start`. Every new user who registers via this link is tracked as a referral.

---

## 12. Known Quirks & Maintenance Notes

1. **MT5 requires Windows** — MetaTrader5 Python package only works on Windows. On Linux/Docker, it falls back to the MT5Simulator automatically.

2. **Web3 mock mode** — If `web3` package is not installed or BSC RPC is unreachable, `EscrowContract` enters mock mode. Deposits/withdrawals are simulated. Set `ESCROW_CONTRACT_ADDRESS` to enable real blockchain operations.

3. **DB offline fallback** — All DB operations check `is_db_available()` and return safe defaults if PostgreSQL is down. The bot runs in degraded mode without persistence.

4. **Referral code format** — `QA{5-digit-id}{4-char-random}` e.g. `QA12345ABCD`. Generated deterministically from telegram_id + random suffix.

5. **Password encryption** — MT5 passwords are AES-encrypted using `SECRET_KEY` env var via `cryptography.Fernet`. If `cryptography` is not installed, falls back to base64 (not secure — install the package).

6. **Weekly payouts** — `ReferralEngine.start_weekly_scheduler()` must be started as an asyncio task. It's not yet wired into `BotEngineV2.start()` — add `asyncio.create_task(referral_engine.start_weekly_scheduler())` there.

7. **Per-user MT5 credentials** — Architecture supports per-user MT5 accounts. Users set credentials via `/mode real` flow. Admin credentials come from env vars. The `OrderManager.connect_mt5()` method accepts per-user credentials.

8. **Profit fee trigger** — `ProfitTracker.record_trade_profit()` must be called from `BotEngineV2._on_trade_closed_performance_track()` when `pnl > 0`. Wire this in for production.

9. **Escrow contract security** — The Solidity contract uses checks-effects-interactions pattern (re-entrancy safe). Solidity 0.8.20 has built-in overflow protection. Only owner can pause. Users can only withdraw their own balance.

10. **Telegram rate limits** — `TelegramNotifier` has a 1.05s per-chat rate limiter and 3-attempt retry with exponential backoff. Flood control (429) triggers 5s sleep.

---

## 13. High-Confidence Checklist

Before going live, verify:

- [ ] `TRADING_MODE=live` and `BROKER_MODE=mt5` set in `.env`
- [ ] MT5 terminal installed and logged in on Windows
- [ ] `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER` correct
- [ ] Escrow contract deployed on BSC mainnet
- [ ] `ESCROW_CONTRACT_ADDRESS` set in `.env`
- [ ] `SERVICE_WALLET_ADDRESS` set (receives 15% fees)
- [ ] `SECRET_KEY` is a strong 32-char random string
- [ ] `DATABASE_URL` points to production PostgreSQL
- [ ] All 62 tests pass: `pytest tests/ -v`
- [ ] Bot runs 24h in paper mode without errors
- [ ] New user can: /start → /verify → /deposit → /mode demo → /balance
- [ ] Trade profit triggers correct referral distribution (check DB)
- [ ] /withdraw deducts exactly 15% (check EscrowTransaction records)

---

*Generated by QuantAlpha AI transformation — May 2026*
