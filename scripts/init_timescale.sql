-- AI Trading Platform — TimescaleDB Initialization
-- Run automatically on first postgres startup via docker-entrypoint-initdb.d

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Enable pg_stat_statements for query monitoring
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Create hypertable for OHLCV time-series data (after ORM creates the table)
-- This is called from application startup via:
--   SELECT create_hypertable('ohlcv_data', 'timestamp', if_not_exists => TRUE);

-- Performance: create index on common query patterns
-- These are created after tables exist via Alembic migrations

-- Set timezone to UTC
SET timezone = 'UTC';
