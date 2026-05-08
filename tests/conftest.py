import pytest
import asyncio
import pandas as pd
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_ohlcv_df():
    """Generate realistic OHLCV test data (300 candles)."""
    np.random.seed(42)
    n = 300
    dates = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    base_price = 45000.0

    # Simulate price walk
    returns = np.random.normal(0.0001, 0.005, n)
    prices = base_price * np.exp(np.cumsum(returns))

    high = prices * (1 + np.abs(np.random.normal(0, 0.002, n)))
    low = prices * (1 - np.abs(np.random.normal(0, 0.002, n)))
    open_ = prices * (1 + np.random.normal(0, 0.001, n))

    df = pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": prices,
            "volume": np.random.uniform(100, 1000, n) * prices / 1000,
        },
        index=dates,
    )
    # Ensure high >= close,open and low <= close,open
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"] = df[["low", "open", "close"]].min(axis=1)
    return df


@pytest.fixture
def sample_ohlcv_df_small():
    """Small 100-candle dataset for fast tests."""
    np.random.seed(7)
    n = 100
    dates = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    prices = 2000.0 * np.exp(np.cumsum(np.random.normal(0, 0.003, n)))
    df = pd.DataFrame(
        {
            "open": prices * 0.999,
            "high": prices * 1.003,
            "low": prices * 0.997,
            "close": prices,
            "volume": np.random.uniform(50, 500, n),
        },
        index=dates,
    )
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"] = df[["low", "open", "close"]].min(axis=1)
    return df


@pytest.fixture
def mock_broker():
    """Mock BrokerClient for unit tests."""
    broker = AsyncMock()
    broker.fetch_ohlcv.return_value = pd.DataFrame(
        [
            [45000.0, 45500.0, 44500.0, 45200.0, 100.0]
            for _ in range(200)
        ],
        columns=["open", "high", "low", "close", "volume"],
        index=pd.date_range("2024-01-01", periods=200, freq="1h", tz="UTC")
    )
    broker.get_account_info.return_value = {
        "equity": 10000.0, "balance": 10000.0, "currency": "USD"
    }
    broker.fetch_tick.return_value = {"last": 45200.0, "bid": 45195.0, "ask": 45205.0}
    broker.initialize = AsyncMock()
    broker.close = AsyncMock()
    return broker


@pytest.fixture
def mock_settings(monkeypatch):
    """Patch settings for tests."""
    monkeypatch.setattr("config.settings.settings.trading_mode", "paper")
    monkeypatch.setattr("config.settings.settings.ai_confidence_threshold", 0.70)
    monkeypatch.setattr("config.settings.settings.max_position_size_pct", 2.0)
    monkeypatch.setattr("config.settings.settings.max_daily_loss_pct", 5.0)
    monkeypatch.setattr("config.settings.settings.max_drawdown_pct", 15.0)
    monkeypatch.setattr("config.settings.settings.max_open_positions", 5)
    monkeypatch.setattr("config.settings.settings.risk_reward_ratio_min", 1.5)
