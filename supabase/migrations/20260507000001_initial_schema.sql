-- QuantAlpha Complete Database Schema
-- Migration: 20260507000001_initial_schema
-- Generated from SQLAlchemy models

-- ── Enable extensions ─────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Enums ─────────────────────────────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE tradedirection AS ENUM ('BUY', 'SELL');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE tradestatus AS ENUM ('pending', 'open', 'closed', 'cancelled', 'stopped');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE verificationstatus AS ENUM ('pending', 'verified', 'rejected');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE brokermode AS ENUM ('demo', 'real');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ── Core Trading Tables ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS trades (
    id              SERIAL PRIMARY KEY,
    symbol          VARCHAR(20)  NOT NULL,
    exchange        VARCHAR(30)  NOT NULL DEFAULT 'paper',
    order_id        VARCHAR(100) UNIQUE,
    direction       tradedirection NOT NULL,
    status          tradestatus    DEFAULT 'pending',
    entry_price     FLOAT,
    exit_price      FLOAT,
    stop_loss       FLOAT,
    take_profit     FLOAT,
    quantity        FLOAT,
    size_usd        FLOAT,
    pnl             FLOAT        DEFAULT 0.0,
    pnl_pct         FLOAT        DEFAULT 0.0,
    fees            FLOAT        DEFAULT 0.0,
    strategy_name   VARCHAR(50),
    pattern_id      VARCHAR(50),
    ai_confidence   FLOAT,
    signal_score    FLOAT,
    timeframe       VARCHAR(10),
    is_paper_trade  BOOLEAN      DEFAULT TRUE,
    metadata_json   JSONB,
    opened_at       TIMESTAMPTZ,
    closed_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_trades_symbol   ON trades(symbol);
CREATE INDEX IF NOT EXISTS ix_trades_pattern  ON trades(pattern_id);

CREATE TABLE IF NOT EXISTS signals (
    id              SERIAL PRIMARY KEY,
    symbol          VARCHAR(20),
    direction       tradedirection,
    strategy_name   VARCHAR(50),
    timeframe       VARCHAR(10),
    entry_price     FLOAT,
    stop_loss       FLOAT,
    take_profit     FLOAT,
    signal_score    FLOAT,
    ai_confidence   FLOAT,
    acted_upon      BOOLEAN      DEFAULT FALSE,
    created_at      TIMESTAMPTZ  DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_signals_symbol ON signals(symbol);

CREATE TABLE IF NOT EXISTS bot_metrics (
    id              SERIAL PRIMARY KEY,
    timestamp       TIMESTAMPTZ  DEFAULT NOW(),
    equity          FLOAT,
    daily_pnl       FLOAT,
    total_trades    INTEGER      DEFAULT 0,
    open_positions  INTEGER      DEFAULT 0,
    win_rate        FLOAT        DEFAULT 0.0,
    max_drawdown    FLOAT        DEFAULT 0.0,
    state           VARCHAR(20),
    details_json    JSONB
);

-- ── User Management ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    id                      SERIAL PRIMARY KEY,
    telegram_id             BIGINT       UNIQUE NOT NULL,
    username                VARCHAR(100),
    first_name              VARCHAR(100),
    last_name               VARCHAR(100),
    broker_account          VARCHAR(100),
    broker_mode             brokermode   DEFAULT 'demo',
    verification_status     verificationstatus DEFAULT 'pending',
    verified_at             TIMESTAMPTZ,
    mt5_login               VARCHAR(50),
    mt5_password_enc        VARCHAR(200),
    mt5_server              VARCHAR(100),
    referral_code           VARCHAR(20)  UNIQUE,
    referred_by_id          INTEGER      REFERENCES users(id),
    escrow_address          VARCHAR(100),
    escrow_balance_usdt     NUMERIC(18,8) DEFAULT 0,
    trading_balance_usdt    NUMERIC(18,8) DEFAULT 0,
    is_active               BOOLEAN      DEFAULT TRUE,
    is_admin                BOOLEAN      DEFAULT FALSE,
    trading_enabled         BOOLEAN      DEFAULT FALSE,
    current_mode            VARCHAR(10)  DEFAULT 'paper',
    settings_json           JSONB        DEFAULT '{}',
    created_at              TIMESTAMPTZ  DEFAULT NOW(),
    updated_at              TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_users_telegram_id       ON users(telegram_id);
CREATE INDEX IF NOT EXISTS ix_users_referral_code     ON users(referral_code);
CREATE INDEX IF NOT EXISTS ix_users_verification      ON users(verification_status);

-- ── Referral System ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS referrals (
    id          SERIAL PRIMARY KEY,
    referrer_id INTEGER NOT NULL REFERENCES users(id),
    referred_id INTEGER NOT NULL REFERENCES users(id),
    level       INTEGER NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_referral_referrer_level ON referrals(referrer_id, level);
CREATE INDEX IF NOT EXISTS ix_referrals_referred      ON referrals(referred_id);

CREATE TABLE IF NOT EXISTS referral_earnings (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    source_trade_id     INTEGER REFERENCES trades(id),
    level               INTEGER NOT NULL,
    amount_usdt         NUMERIC(18,8) NOT NULL,
    fee_pct             FLOAT NOT NULL,
    status              VARCHAR(20) DEFAULT 'pending',
    paid_at             TIMESTAMPTZ,
    tx_hash             VARCHAR(100),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_referral_earnings_user   ON referral_earnings(user_id);
CREATE INDEX IF NOT EXISTS ix_referral_earnings_status ON referral_earnings(status);

-- ── Escrow / Bridge ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS escrow_transactions (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    tx_type         VARCHAR(20) NOT NULL,
    amount_usdt     NUMERIC(18,8) NOT NULL,
    fee_usdt        NUMERIC(18,8) DEFAULT 0,
    net_usdt        NUMERIC(18,8) NOT NULL,
    tx_hash         VARCHAR(100) UNIQUE,
    from_address    VARCHAR(100),
    to_address      VARCHAR(100),
    block_number    BIGINT,
    confirmations   INTEGER DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'pending',
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    confirmed_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_escrow_tx_user   ON escrow_transactions(user_id);
CREATE INDEX IF NOT EXISTS ix_escrow_tx_type   ON escrow_transactions(tx_type);
CREATE INDEX IF NOT EXISTS ix_escrow_tx_hash   ON escrow_transactions(tx_hash);
CREATE INDEX IF NOT EXISTS ix_escrow_tx_status ON escrow_transactions(status);

CREATE TABLE IF NOT EXISTS profit_records (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    trade_id            INTEGER REFERENCES trades(id),
    gross_profit_usdt   NUMERIC(18,8) NOT NULL,
    service_fee_usdt    NUMERIC(18,8) NOT NULL,
    net_profit_usdt     NUMERIC(18,8) NOT NULL,
    ref_l1_fee_usdt     NUMERIC(18,8) DEFAULT 0,
    ref_l2_fee_usdt     NUMERIC(18,8) DEFAULT 0,
    ref_l3_fee_usdt     NUMERIC(18,8) DEFAULT 0,
    owner_fee_usdt      NUMERIC(18,8) DEFAULT 0,
    processed           BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_profit_records_user ON profit_records(user_id);

-- ── ML / Self-Improvement Tables ──────────────────────────────────────────

CREATE TABLE IF NOT EXISTS trading_patterns (
    id                  VARCHAR(50) PRIMARY KEY,
    name                VARCHAR(100) NOT NULL,
    symbol              VARCHAR(20)  NOT NULL,
    asset_class         VARCHAR(20),
    entry_conditions    JSONB NOT NULL,
    exit_conditions     JSONB NOT NULL,
    market_regime       VARCHAR(20),
    timeframe           VARCHAR(10),
    discovery_date      TIMESTAMPTZ NOT NULL,
    validation_metrics  JSONB NOT NULL,
    usage_count         INTEGER DEFAULT 0,
    live_win_rate       FLOAT DEFAULT 0.0,
    live_profit_factor  FLOAT DEFAULT 0.0,
    status              VARCHAR(20) DEFAULT 'active',
    deprecation_reason  TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_trading_patterns_symbol ON trading_patterns(symbol);
CREATE INDEX IF NOT EXISTS ix_trading_patterns_regime ON trading_patterns(market_regime);
CREATE INDEX IF NOT EXISTS ix_trading_patterns_status ON trading_patterns(status);

CREATE TABLE IF NOT EXISTS model_versions (
    id                  SERIAL PRIMARY KEY,
    symbol              VARCHAR(20) NOT NULL,
    version             VARCHAR(50) NOT NULL,
    model_path          VARCHAR(200) NOT NULL,
    precision           FLOAT,
    recall              FLOAT,
    accuracy            FLOAT,
    auc                 FLOAT,
    f1_score            FLOAT,
    training_samples    INTEGER,
    training_date       TIMESTAMPTZ NOT NULL,
    validation_report   JSONB,
    status              VARCHAR(20) DEFAULT 'pending',
    deployed_at         TIMESTAMPTZ,
    deprecated_at       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_model_versions_symbol ON model_versions(symbol);
CREATE INDEX IF NOT EXISTS ix_model_versions_status ON model_versions(status);

CREATE TABLE IF NOT EXISTS performance_history (
    id              SERIAL PRIMARY KEY,
    timestamp       TIMESTAMPTZ NOT NULL,
    period          VARCHAR(20) NOT NULL,
    symbol          VARCHAR(20),
    strategy_name   VARCHAR(50),
    total_trades    INTEGER DEFAULT 0,
    winning_trades  INTEGER DEFAULT 0,
    losing_trades   INTEGER DEFAULT 0,
    win_rate        FLOAT DEFAULT 0.0,
    total_pnl       FLOAT DEFAULT 0.0,
    avg_win_pct     FLOAT DEFAULT 0.0,
    avg_loss_pct    FLOAT DEFAULT 0.0,
    profit_factor   FLOAT DEFAULT 0.0,
    sharpe_ratio    FLOAT DEFAULT 0.0,
    sortino_ratio   FLOAT DEFAULT 0.0,
    max_drawdown_pct FLOAT DEFAULT 0.0,
    equity          FLOAT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_performance_history_ts     ON performance_history(timestamp);
CREATE INDEX IF NOT EXISTS ix_performance_history_symbol ON performance_history(symbol);

CREATE TABLE IF NOT EXISTS approval_history (
    id                  SERIAL PRIMARY KEY,
    proposal_id         VARCHAR(50) UNIQUE NOT NULL,
    proposal_type       VARCHAR(50) NOT NULL,
    proposal_data       JSONB NOT NULL,
    decision            VARCHAR(20),
    admin_id            VARCHAR(50),
    decision_timestamp  TIMESTAMPTZ,
    execution_status    VARCHAR(20),
    execution_timestamp TIMESTAMPTZ,
    execution_result    JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_approval_history_proposal ON approval_history(proposal_id);
CREATE INDEX IF NOT EXISTS ix_approval_history_decision ON approval_history(decision);

CREATE TABLE IF NOT EXISTS equity_history (
    id                  SERIAL PRIMARY KEY,
    timestamp           TIMESTAMPTZ NOT NULL,
    equity              FLOAT NOT NULL,
    realized_pnl        FLOAT DEFAULT 0.0,
    unrealized_pnl      FLOAT DEFAULT 0.0,
    open_positions      INTEGER DEFAULT 0,
    portfolio_heat_pct  FLOAT DEFAULT 0.0,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_equity_history_ts ON equity_history(timestamp);

CREATE TABLE IF NOT EXISTS parameter_changes (
    id              SERIAL PRIMARY KEY,
    timestamp       TIMESTAMPTZ NOT NULL,
    parameter_name  VARCHAR(100) NOT NULL,
    old_value       TEXT,
    new_value       TEXT,
    change_reason   TEXT,
    triggered_by    VARCHAR(50),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_parameter_changes_ts    ON parameter_changes(timestamp);
CREATE INDEX IF NOT EXISTS ix_parameter_changes_param ON parameter_changes(parameter_name);

CREATE TABLE IF NOT EXISTS audit_logs (
    id          SERIAL PRIMARY KEY,
    timestamp   TIMESTAMPTZ NOT NULL,
    event_type  VARCHAR(50) NOT NULL,
    component   VARCHAR(50) NOT NULL,
    severity    VARCHAR(20) NOT NULL,
    message     TEXT NOT NULL,
    details     JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_audit_logs_ts         ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS ix_audit_logs_event_type ON audit_logs(event_type);
CREATE INDEX IF NOT EXISTS ix_audit_logs_severity   ON audit_logs(severity);
