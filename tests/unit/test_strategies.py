import pytest
import pandas as pd
import numpy as np
from src.strategies.trend_following import TrendFollowingStrategy
from src.strategies.mean_reversion import MeanReversionStrategy
from src.strategies.ensemble_strategy import EnsembleStrategy
from src.indicators.technical import TechnicalIndicators


class TestTrendFollowingStrategy:

    @pytest.mark.asyncio
    async def test_returns_trade_signal(self, sample_ohlcv_df):
        strategy = TrendFollowingStrategy()
        df = TechnicalIndicators.add_all_indicators(sample_ohlcv_df)
        signal = await strategy.generate_signal(df, None, "BTC/USDT")
        assert signal.direction in ["BUY", "SELL", "NEUTRAL"]
        assert signal.strategy_name == "TrendFollowing"

    @pytest.mark.asyncio
    async def test_neutral_on_insufficient_data(self):
        strategy = TrendFollowingStrategy()
        tiny_df = pd.DataFrame(
            {"open": [100], "high": [110], "low": [90], "close": [105], "volume": [1000]}
        )
        signal = await strategy.generate_signal(tiny_df, None, "BTC/USDT")
        assert signal.direction == "NEUTRAL"

    @pytest.mark.asyncio
    async def test_buy_signal_has_valid_prices(self, sample_ohlcv_df):
        strategy = TrendFollowingStrategy()
        df = TechnicalIndicators.add_all_indicators(sample_ohlcv_df)
        signal = await strategy.generate_signal(df, None, "BTC/USDT")
        if signal.direction == "BUY":
            assert signal.entry_price > 0
            assert signal.stop_loss < signal.entry_price
            assert signal.take_profit > signal.entry_price


class TestMeanReversionStrategy:

    @pytest.mark.asyncio
    async def test_returns_valid_signal(self, sample_ohlcv_df):
        strategy = MeanReversionStrategy()
        df = TechnicalIndicators.add_all_indicators(sample_ohlcv_df)
        signal = await strategy.generate_signal(df, None, "ETH/USDT")
        assert signal.direction in ["BUY", "SELL", "NEUTRAL"]

    @pytest.mark.asyncio
    async def test_neutral_on_empty_df(self):
        strategy = MeanReversionStrategy()
        df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        signal = await strategy.generate_signal(df, None, "BTC/USDT")
        assert signal.direction == "NEUTRAL"


class TestEnsembleStrategy:

    @pytest.mark.asyncio
    async def test_returns_signal(self, sample_ohlcv_df):
        strategy = EnsembleStrategy()
        df = TechnicalIndicators.add_all_indicators(sample_ohlcv_df)
        signal = await strategy.generate_signal(df, df, "BTC/USDT")
        assert signal.direction in ["BUY", "SELL", "NEUTRAL"]
        assert "Ensemble" in signal.strategy_name or signal.direction == "NEUTRAL"

    @pytest.mark.asyncio
    async def test_neutral_when_strategies_disagree(self, sample_ohlcv_df, monkeypatch):
        """When strategies disagree, ensemble should return NEUTRAL."""
        from src.strategies.base_strategy import TradeSignal
        strategy = EnsembleStrategy()
        df = TechnicalIndicators.add_all_indicators(sample_ohlcv_df)

        # Force strategies to disagree
        from unittest.mock import AsyncMock
        buy_signal = TradeSignal("BUY", 45000, 44000, 47000, "A", 0.8)
        sell_signal = TradeSignal("SELL", 45000, 46000, 43000, "B", 0.8)

        strategy.strategies[0].generate_signal = AsyncMock(return_value=buy_signal)
        strategy.strategies[1].generate_signal = AsyncMock(return_value=sell_signal)

        signal = await strategy.generate_signal(df, None, "BTC/USDT")
        assert signal.direction == "NEUTRAL"
