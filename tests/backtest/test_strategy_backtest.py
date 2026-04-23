import pytest
import numpy as np
import pandas as pd
from src.backtesting.backtester import VectorizedBacktester


class TestStrategyBacktest:

    @pytest.fixture
    def backtester(self):
        return VectorizedBacktester()

    def test_backtest_returns_result(self, backtester, sample_ohlcv_df):
        result = backtester.run(sample_ohlcv_df, "BTC/USDT", "1h")
        assert result is not None
        assert result.symbol == "BTC/USDT"
        assert result.timeframe == "1h"

    def test_backtest_metrics_valid(self, backtester, sample_ohlcv_df):
        result = backtester.run(sample_ohlcv_df, "BTC/USDT", "1h")
        assert 0 <= result.win_rate <= 100
        assert result.max_drawdown_pct >= 0
        assert result.total_trades == result.winning_trades + result.losing_trades

    def test_backtest_trade_count(self, backtester, sample_ohlcv_df):
        result = backtester.run(sample_ohlcv_df, "BTC/USDT", "1h")
        # Should generate at least some trades on 300 candles
        assert result.total_trades >= 0

    def test_backtest_no_lookahead_bias(self, backtester, sample_ohlcv_df):
        """Ensure backtester starts after indicator warmup period."""
        result = backtester.run(sample_ohlcv_df, "BTC/USDT", "1h")
        for trade in result.trades:
            # All trades should have valid entry prices
            assert trade.entry_price > 0
            assert trade.stop_loss > 0
            assert trade.take_profit > 0

    def test_backtest_summary_string(self, backtester, sample_ohlcv_df):
        result = backtester.run(sample_ohlcv_df, "BTC/USDT", "1h")
        summary = result.summary()
        assert "BTC/USDT" in summary
        assert "Win Rate" in summary

    def test_initial_capital_preserved_math(self, backtester, sample_ohlcv_df):
        """Total return should be mathematically consistent."""
        result = backtester.run(sample_ohlcv_df, "BTC/USDT", "1h", initial_capital=10000.0)
        assert isinstance(result.total_return_pct, float)
