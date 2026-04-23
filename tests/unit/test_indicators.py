import pytest
import pandas as pd
import numpy as np
from src.indicators.technical import TechnicalIndicators


@pytest.fixture
def sample_df():
    rng = np.random.default_rng(42)
    n = 300
    dates = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    prices = 45000 * np.exp(np.cumsum(rng.normal(0, 0.003, n)))
    df = pd.DataFrame({
        "open": prices * 0.999, "high": prices * 1.003,
        "low": prices * 0.997, "close": prices,
        "volume": rng.uniform(100, 1000, n),
    }, index=dates)
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"]  = df[["low",  "open", "close"]].min(axis=1)
    return df


class TestTechnicalIndicators:

    def test_all_required_columns_present(self, sample_df):
        r = TechnicalIndicators.add_all_indicators(sample_df)
        for col in ["ema_9", "ema_21", "ema_50", "rsi_14", "macd", "macd_signal",
                    "bb_upper", "bb_lower", "atr_14", "vwap", "signal_score",
                    "adx", "volume_ratio", "obv"]:
            assert col in r.columns, f"Missing: {col}"

    def test_rsi_in_valid_range(self, sample_df):
        r = TechnicalIndicators.add_all_indicators(sample_df)
        assert (r["rsi_14"] >= 0).all() and (r["rsi_14"] <= 100).all()

    def test_signal_score_in_valid_range(self, sample_df):
        r = TechnicalIndicators.add_all_indicators(sample_df)
        assert (r["signal_score"] >= -100).all() and (r["signal_score"] <= 100).all()

    def test_no_nan_in_core_indicators(self, sample_df):
        r = TechnicalIndicators.add_all_indicators(sample_df)
        for col in ["rsi_14", "macd", "atr_14", "signal_score"]:
            assert not r[col].isnull().any(), f"NaN in {col}"

    def test_bollinger_bands_ordering(self, sample_df):
        r = TechnicalIndicators.add_all_indicators(sample_df)
        tol = 1e-8
        assert (r["bb_upper"] >= r["bb_middle"] - tol).all()
        assert (r["bb_middle"] >= r["bb_lower"] - tol).all()

    def test_atr_positive(self, sample_df):
        r = TechnicalIndicators.add_all_indicators(sample_df)
        assert (r["atr_14"] > 0).all()

    def test_support_resistance_ordering(self, sample_df):
        support, resistance = TechnicalIndicators.calculate_support_resistance(sample_df)
        assert isinstance(support, float) and isinstance(resistance, float)
        assert resistance >= support

    def test_output_rows_reduced_but_substantial(self, sample_df):
        r = TechnicalIndicators.add_all_indicators(sample_df)
        assert 100 < len(r) < len(sample_df)

    def test_volume_ratio_non_negative(self, sample_df):
        r = TechnicalIndicators.add_all_indicators(sample_df)
        assert (r["volume_ratio"] >= 0).all()

    def test_ema_9_not_equal_ema_200(self, sample_df):
        """Fast and slow EMAs should diverge on trending data."""
        r = TechnicalIndicators.add_all_indicators(sample_df)
        assert not (r["ema_9"] == r["ema_200"]).all()
