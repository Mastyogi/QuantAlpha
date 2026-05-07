import os
from pathlib import Path
from typing import List, Optional

# Load .env file
try:
    from dotenv import load_dotenv
    # Load from project root
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass  # python-dotenv not installed


def _env(key, default=None):
    return os.environ.get(key, default)

def _env_bool(key, default=False):
    val = os.environ.get(key, str(default)).lower()
    return val in ("true", "1", "yes")

def _env_float(key, default=0.0):
    try:
        return float(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default

def _env_int(key, default=0):
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default

def _env_list(key, default=""):
    val = os.environ.get(key, default)
    if not val:
        return []
    return [p.strip() for p in val.split(",") if p.strip()]


class TradingBotSettings:
    def __init__(self):
        # ── Exchange (Crypto) ──────────────────────────────────────────────────
        self.exchange_name          = _env("EXCHANGE_NAME", "paper")
        self.exchange_api_key       = _env("EXCHANGE_API_KEY", "")
        self.exchange_secret        = _env("EXCHANGE_SECRET", "")          # Bitget uses EXCHANGE_SECRET
        self.exchange_api_secret    = _env("EXCHANGE_API_SECRET", self.exchange_secret)
        self.exchange_passphrase    = _env("EXCHANGE_PASSPHRASE", "")
        self.exchange_testnet       = _env_bool("EXCHANGE_TESTNET", False)
        self.trading_mode           = _env("TRADING_MODE", "paper")
        self.primary_timeframe      = _env("PRIMARY_TIMEFRAME", "1h")

        # ── Phase 5-6 Trading Config ─────────────────────────────────────────
        self.confluence_threshold   = _env_int("CONFLUENCE_THRESHOLD", 82)
        self.min_wallet_start_usd   = float(_env("MIN_WALLET_START_USD", "10.0"))
        self.base_risk_pct          = float(_env("BASE_RISK_PCT", "1.0"))
        self.dynamic_sizing_loss_pct= float(_env("DYNAMIC_SIZING_AFTER_LOSS_PCT", "15.0")) / 100
        self.dynamic_max_multiplier = float(_env("DYNAMIC_MAX_MULTIPLIER", "2.0"))
        self.recovery_reset_to_base = _env("RECOVERY_RESET_TO_BASE", "true").lower() == "true"
        self.execution_latency_target = _env_int("EXECUTION_LATENCY_TARGET_MS", 50)
        self.enable_fine_tuning     = _env("ENABLE_FINE_TUNING", "true").lower() == "true"
        self.optuna_trials          = _env_int("OPTUNA_TRIALS", 30)
        self.ab_test_min_improvement= float(_env("AB_TEST_MIN_IMPROVEMENT", "0.02"))

        # ── MT5 / Forex Broker ────────────────────────────────────────────────
        self.broker_mode            = _env("BROKER_MODE", "paper")   # paper|mt5
        self.mt5_login              = _env_int("MT5_LOGIN", 0)
        self.mt5_password           = _env("MT5_PASSWORD", "")
        self.mt5_server             = _env("MT5_SERVER", "MetaQuotes-Demo")
        self.mt5_path               = _env("MT5_PATH", "")

        # ── Escrow / Bridge ───────────────────────────────────────────────────
        self.bsc_rpc_url            = _env("BSC_RPC_URL", "https://bsc-dataseed.binance.org/")
        self.bsc_network            = _env("BSC_NETWORK", "mainnet")
        self.escrow_contract_address= _env("ESCROW_CONTRACT_ADDRESS", "")
        self.usdt_contract_address  = _env("USDT_CONTRACT_ADDRESS", "0x55d398326f99059fF775485246999027B3197955")
        self.bot_wallet_private_key = _env("BOT_WALLET_PRIVATE_KEY", "")
        self.service_wallet_address = _env("SERVICE_WALLET_ADDRESS", "")
        self.owner_wallet_address   = _env("OWNER_WALLET_ADDRESS", "")
        self.secret_key             = _env("SECRET_KEY", "quantalpha-default-secret-key-32b")

        # ── Instrument Lists ──────────────────────────────────────────────────
        self.trading_pairs          = _env_list("TRADING_PAIRS", "BTC/USDT,ETH/USDT")
        self.forex_pairs            = _env_list("FOREX_PAIRS",   "EURUSD,GBPUSD,USDJPY")
        self.commodity_pairs        = _env_list("COMMODITY_PAIRS","XAUUSD,XAGUSD,USOIL")
        self.enable_forex           = _env_bool("ENABLE_FOREX", False)
        self.enable_commodities     = _env_bool("ENABLE_COMMODITIES", False)

        # ── Telegram ─────────────────────────────────────────────────────────
        self.telegram_bot_token     = _env("TELEGRAM_BOT_TOKEN", "placeholder_token")
        self.telegram_admin_chat_id = _env_int("TELEGRAM_ADMIN_CHAT_ID", 0)
        self.telegram_channel_id    = None
        self.telegram_alert_level   = _env("TELEGRAM_ALERT_LEVEL", "INFO")

        # ── Database ─────────────────────────────────────────────────────────
        self.database_url           = _env("DATABASE_URL", "postgresql+asyncpg://bot:pass@localhost:5432/trading_bot")
        self.redis_url              = _env("REDIS_URL", "redis://localhost:6379/0")

        # ── Risk ─────────────────────────────────────────────────────────────
        self.max_position_size_pct  = _env_float("MAX_POSITION_SIZE_PCT", 2.0)
        self.max_daily_loss_pct     = _env_float("MAX_DAILY_LOSS_PCT", 5.0)
        self.max_drawdown_pct       = _env_float("MAX_DRAWDOWN_PCT", 15.0)
        self.max_open_positions     = _env_int("MAX_OPEN_POSITIONS", 5)
        self.risk_reward_ratio_min  = _env_float("RISK_REWARD_RATIO_MIN", 1.5)
        self.slippage_pct           = _env_float("SLIPPAGE_PCT", 0.1)
        self.max_lot_size           = _env_float("MAX_LOT_SIZE", 0.5)
        self.risk_per_trade_pct     = _env_float("RISK_PER_TRADE_PCT", 1.0)

        # ── Strategy ─────────────────────────────────────────────────────────
        self.primary_timeframe      = _env("PRIMARY_TIMEFRAME", "1h")
        self.secondary_timeframe    = _env("SECONDARY_TIMEFRAME", "4h")
        self.confirmation_timeframe = _env("CONFIRMATION_TIMEFRAME", "15m")
        self.strategy_mode          = _env("STRATEGY_MODE", "ensemble")

        # ── AI ────────────────────────────────────────────────────────────────
        self.ai_confidence_threshold    = _env_float("AI_CONFIDENCE_THRESHOLD", 0.70)
        self.model_retrain_interval_hours = _env_int("MODEL_RETRAIN_INTERVAL_HOURS", 24)
        self.feature_lookback_periods   = _env_int("FEATURE_LOOKBACK_PERIODS", 100)
        self.mlflow_tracking_uri        = _env("MLFLOW_TRACKING_URI", "http://localhost:5000")

        # ── Logging ───────────────────────────────────────────────────────────
        self.log_level              = _env("LOG_LEVEL", "INFO")
        self.log_format             = _env("LOG_FORMAT", "json")

        # ── Servers ───────────────────────────────────────────────────────────
        self.api_port               = _env_int("API_PORT", 8000)
        self.web_port               = _env_int("WEB_PORT", 8080)
        self.prometheus_port        = _env_int("PROMETHEUS_PORT", 9090)

        # ── OAuth / Web Auth ─────────────────────────────────────────────────
        self.google_client_id       = _env("GOOGLE_CLIENT_ID", "")
        self.google_client_secret   = _env("GOOGLE_CLIENT_SECRET", "")
        self.github_client_id       = _env("GITHUB_CLIENT_ID", "")
        self.github_client_secret   = _env("GITHUB_CLIENT_SECRET", "")
        self.oauth_redirect_base    = _env("OAUTH_REDIRECT_BASE", "http://localhost:8080")
        self.jwt_secret_key         = _env("JWT_SECRET_KEY", "change-me-32-char-secret-key!!!")
        self.jwt_expire_hours       = _env_int("JWT_EXPIRE_HOURS", 24)
        self.allowed_emails         = _env_list("ALLOWED_EMAILS", "")  # empty = allow all

        # ── Validations ──────────────────────────────────────────────────────
        if self.trading_mode not in ("paper", "live"):
            raise ValueError("trading_mode must be paper or live")
        if not self.trading_pairs:
            self.trading_pairs = ["BTC/USDT", "ETH/USDT"]

    @property
    def all_instruments(self):
        """All active instruments across asset classes."""
        instruments = list(self.trading_pairs)
        if self.enable_forex:
            instruments.extend(self.forex_pairs)
        if self.enable_commodities:
            instruments.extend(self.commodity_pairs)
        return instruments


settings = TradingBotSettings()
