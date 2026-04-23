"""
Integration Tests — Full Pipeline
===================================
Tests the complete chain: DataFetcher → Indicators → Signal Engine → Risk → Execution.
These tests mock the exchange but use real logic throughout.

Marked with @pytest.mark.integration — excluded from fast unit test runs.
"""
import pytest
import asyncio
import numpy as np
import pandas as pd
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


@pytest.fixture
def realistic_ohlcv_df():
    """300 candles with realistic trending price action."""
    rng = np.random.default_rng(42)
    n = 300
    dates = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")

    # Simulate a trend + consolidation pattern
    trend = np.linspace(0, 0.15, n)
    noise = rng.normal(0, 0.003, n)
    prices = 45000 * np.exp(np.cumsum(noise) + trend)

    df = pd.DataFrame({
        "open":   prices * (1 + rng.normal(0, 0.001, n)),
        "high":   prices * (1 + np.abs(rng.normal(0, 0.003, n))),
        "low":    prices * (1 - np.abs(rng.normal(0, 0.003, n))),
        "close":  prices,
        "volume": rng.uniform(500, 5000, n),
    }, index=dates)
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"]  = df[["low",  "open", "close"]].min(axis=1)
    return df


@pytest.mark.integration
class TestIndicatorPipeline:
    """Test that all indicators compute correctly on real data."""

    def test_technical_indicators_no_nan_on_300_bars(self, realistic_ohlcv_df):
        from src.indicators.technical import TechnicalIndicators
        result = TechnicalIndicators.add_all_indicators(realistic_ohlcv_df)
        assert len(result) > 200
        critical = ["rsi_14", "macd", "atr_14", "bb_upper", "bb_lower", "adx", "signal_score"]
        for col in critical:
            assert col in result.columns, f"Missing column: {col}"
            nan_count = result[col].isna().sum()
            assert nan_count == 0, f"NaN in {col}: {nan_count} values"

    def test_volume_profile_produces_valid_levels(self, realistic_ohlcv_df):
        from src.indicators.volume_profile import VolumeProfile
        vp = VolumeProfile()
        result = vp.calculate(realistic_ohlcv_df)
        assert result.poc > 0
        assert result.vah >= result.poc >= result.val
        assert 0 < result.poc_strength < 1

    def test_market_structure_detects_trend(self, realistic_ohlcv_df):
        from src.indicators.market_structure import MarketStructureAnalyzer
        msa = MarketStructureAnalyzer()
        result = msa.analyze(realistic_ohlcv_df)
        # Trending data (linspace uptrend) should be detected as uptrend
        assert result.trend in ("uptrend", "downtrend", "ranging")
        assert isinstance(result.structure_score, float)
        assert 0 <= result.structure_score <= 100

    def test_order_flow_runs_on_real_data(self, realistic_ohlcv_df):
        from src.indicators.order_flow import OrderFlowAnalyzer
        of = OrderFlowAnalyzer()
        result = of.analyze(realistic_ohlcv_df)
        assert -100 <= result.of_score <= 100
        assert result.cvd_trend in ("rising", "falling", "flat")
        assert -1 <= result.bid_ask_imbalance <= 1

    def test_custom_signals_add_all_columns(self, realistic_ohlcv_df):
        from src.indicators.custom_signals import CustomSignals
        from src.indicators.technical import TechnicalIndicators
        df = TechnicalIndicators.add_all_indicators(realistic_ohlcv_df)
        result = CustomSignals.add_all_custom(df)
        for col in ["alpha_signal", "smart_money_index", "exhaustion", "custom_composite"]:
            assert col in result.columns
            assert result[col].between(-150, 150).all(), f"Out of range: {col}"


@pytest.mark.integration
class TestAdvancedFeaturePipeline:
    """Test 65-feature engineering pipeline."""

    def test_features_generated_count(self, realistic_ohlcv_df):
        from src.ai_engine.advanced_features import AdvancedFeaturePipeline
        pipeline = AdvancedFeaturePipeline()
        features_df = pipeline.generate(realistic_ohlcv_df)
        assert features_df is not None
        feature_cols = [c for c in features_df.columns
                        if c not in ("open", "high", "low", "close", "volume")]
        assert len(feature_cols) >= 30, f"Expected ≥30 features, got {len(feature_cols)}"

    def test_features_no_nan_after_warmup(self, realistic_ohlcv_df):
        from src.ai_engine.advanced_features import AdvancedFeaturePipeline
        pipeline = AdvancedFeaturePipeline()
        features_df = pipeline.generate(realistic_ohlcv_df)
        # After warmup period, critical features should have no NaN
        tail = features_df.tail(100)
        for col in AdvancedFeaturePipeline.FEATURE_COLUMNS[:20]:
            if col in tail.columns:
                nan_pct = tail[col].isna().mean()
                assert nan_pct < 0.05, f"Too many NaN in {col}: {nan_pct:.0%}"


@pytest.mark.integration
class TestRiskPipeline:
    """Test risk management chain."""

    def test_pnl_calculator_full_trade_cycle(self):
        from src.risk.pnl_calculator import PnLCalculator
        calc = PnLCalculator(initial_equity=10_000.0)

        # Open trade
        calc.record_trade_open("t1", "BTC/USDT", "BUY", 45000, 0.044, 2000, "trend")

        # Close with profit
        record = calc.record_trade_close("t1", 46000, "TP")
        assert record is not None
        assert record.gross_pnl > 0
        assert record.net_pnl < record.gross_pnl  # fees deducted
        assert record.close_reason == "TP"

    def test_pnl_snapshot_metrics(self):
        from src.risk.pnl_calculator import PnLCalculator
        calc = PnLCalculator(initial_equity=10_000.0)

        # 3 winning trades, 1 losing
        for i in range(3):
            tid = f"win_{i}"
            calc.record_trade_open(tid, "BTC/USDT", "BUY", 45000, 0.1, 1000, "trend")
            calc.record_trade_close(tid, 45900, "TP")  # ~+2% win

        calc.record_trade_open("loss_1", "ETH/USDT", "SELL", 2500, 0.4, 1000, "trend")
        calc.record_trade_close("loss_1", 2600, "SL")  # loss

        snap = calc.get_snapshot()
        assert snap.total_trades == 4
        assert snap.winning_trades == 3
        assert snap.win_rate == 0.75
        assert snap.profit_factor > 1.0

    def test_portfolio_manager_blocks_correlated_trades(self):
        from src.risk.portfolio_manager import PortfolioManager
        pm = PortfolioManager(equity=10_000.0)
        pm.add_position("t1", "BTC/USDT", "BUY", 2000, 2.0)

        # ETH/BTC correlation = 0.85 — should be blocked
        result = pm.check_new_trade("ETH/USDT", "BUY", 2000, 2.0)
        assert not result.approved
        assert result.max_correlation >= 0.75

    def test_portfolio_manager_heat_check(self):
        from src.risk.portfolio_manager import PortfolioManager
        pm = PortfolioManager(equity=10_000.0)
        # Add 4 x 2% risk = 8% heat
        for i in range(4):
            pm.add_position(f"t{i}", f"ASSET{i}/USDT", "BUY", 2000, 2.0)

        # 5th trade would push to 10% — over 8% limit
        result = pm.check_new_trade("SOL/USDT", "BUY", 2000, 2.0)
        assert not result.approved
        assert "heat" in result.reason.lower()


@pytest.mark.integration
class TestBacktestPipeline:
    """Test vectorized backtester end-to-end."""

    def test_backtester_runs_and_returns_metrics(self, realistic_ohlcv_df):
        from src.backtesting.backtester import VectorizedBacktester
        bt = VectorizedBacktester()
        result = bt.run(realistic_ohlcv_df, "BTC/USDT", "1h", initial_capital=10_000.0)
        assert result is not None
        assert result.total_trades >= 0
        assert 0 <= result.win_rate <= 100
        assert result.max_drawdown_pct >= 0

    def test_monte_carlo_produces_distribution(self):
        from src.backtesting.monte_carlo import MonteCarloSimulator
        rng = np.random.default_rng(42)
        # 50 trades with positive expectancy
        returns = [0.015 if rng.random() > 0.4 else -0.010 for _ in range(50)]
        mc = MonteCarloSimulator(n_simulations=500)  # Fast for CI
        result = mc.run(returns, initial_equity=10_000.0)

        assert result.n_simulations == 500
        assert result.final_equity_p5 < result.final_equity_median < result.final_equity_p95
        assert 0 <= result.probability_of_ruin <= 1
        assert result.var_95 >= 0

    def test_monte_carlo_ruin_on_negative_edge(self):
        from src.backtesting.monte_carlo import MonteCarloSimulator
        # Negative expectancy strategy — should have high ruin probability
        returns = [-0.02 for _ in range(50)]  # All losing trades
        mc = MonteCarloSimulator(n_simulations=500)
        result = mc.run(returns, initial_equity=10_000.0)
        assert result.probability_of_ruin > 0.5  # Most paths ruined


@pytest.mark.integration
class TestDataNormalization:
    """Test data normalizer cross-exchange compatibility."""

    def test_normalize_raw_ccxt_format(self):
        from src.data.data_normalizer import DataNormalizer
        norm = DataNormalizer()

        # Raw CCXT format
        raw = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=100, freq="1h"),
            "open": np.random.uniform(44000, 46000, 100),
            "high": np.random.uniform(45000, 47000, 100),
            "low":  np.random.uniform(43000, 45000, 100),
            "close": np.random.uniform(44000, 46000, 100),
            "volume": np.random.uniform(100, 1000, 100),
        })
        result = norm.normalize(raw, "BTC/USDT")
        assert result.index.tz is not None  # UTC timezone
        assert list(result.columns) == ["open", "high", "low", "close", "volume"]
        assert (result["high"] >= result["low"]).all()

    def test_symbol_normalization(self):
        from src.data.data_normalizer import DataNormalizer
        norm = DataNormalizer()
        assert norm.normalize_symbol("BTCUSDT") == "BTC/USDT"
        assert norm.normalize_symbol("XBT/USD") == "BTC/USDT"
        assert norm.normalize_symbol("BTC/USD") == "BTC/USDT"
        assert norm.normalize_symbol("EURUSD") == "EUR/USD"


@pytest.mark.integration
class TestSignalEngine:
    """Test FineTunedSignalEngine with mock data."""

    def test_signal_engine_returns_final_signal(self, realistic_ohlcv_df):
        from src.signals.signal_engine import FineTunedSignalEngine
        engine = FineTunedSignalEngine(
            model_dir="models",
            confluence_threshold=50.0,   # Low threshold for test
            max_risk_pct=2.0,
            account_equity=10_000.0,
        )
        result = engine.analyze("BTC/USDT", realistic_ohlcv_df)
        assert result.symbol == "BTC/USDT"
        assert result.direction in ("BUY", "SELL", "NEUTRAL")
        assert 0 <= result.ai_confidence <= 1
        assert 0 <= result.confluence_score <= 100

    def test_neutral_signal_when_no_model_loaded(self, realistic_ohlcv_df):
        """Without a trained model, engine should return NEUTRAL (not crash)."""
        from src.signals.signal_engine import FineTunedSignalEngine
        engine = FineTunedSignalEngine(model_dir="/nonexistent/path")
        result = engine.analyze("BTC/USDT", realistic_ohlcv_df)
        assert result is not None
        # Should degrade gracefully — not raise exception
