import pytest
import pandas as pd
import numpy as np
from src.data.data_validator import DataValidator
from src.core.exceptions import DataValidationError


@pytest.fixture
def sample_df():
    rng = np.random.default_rng(42)
    n = 200
    dates = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    prices = 45000 * np.exp(np.cumsum(rng.normal(0, 0.003, n)))
    df = pd.DataFrame({
        "open": prices * 0.999, "high": prices * 1.003,
        "low":  prices * 0.997, "close": prices,
        "volume": rng.uniform(100, 1000, n),
    }, index=dates)
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"]  = df[["low",  "open", "close"]].min(axis=1)
    return df


class TestDataValidator:

    def test_valid_df_passes(self, sample_df):
        result = DataValidator().validate_and_clean(sample_df)
        assert len(result) > 0 and "close" in result.columns

    def test_missing_column_raises(self):
        df = pd.DataFrame({"open": [100, 200], "close": [110, 210]})
        with pytest.raises(DataValidationError):
            DataValidator().validate_and_clean(df)

    def test_zero_volume_removed(self, sample_df):
        df = sample_df.copy()
        df.iloc[5:10, df.columns.get_loc("volume")] = 0
        result = DataValidator().validate_and_clean(df)
        assert (result["volume"] > 0).all()

    def test_nan_values_filled(self, sample_df):
        df = sample_df.copy()
        df.iloc[5, df.columns.get_loc("close")] = np.nan
        result = DataValidator().validate_and_clean(df)
        assert not result["close"].isnull().any()

    def test_hloc_violations_fixed(self, sample_df):
        result = DataValidator().validate_and_clean(sample_df)
        assert (result["high"] >= result["low"]).all()

    def test_insufficient_rows_raises(self):
        df = pd.DataFrame({
            "open": [100.0] * 10, "high": [105.0] * 10,
            "low":  [95.0]  * 10, "close": [102.0] * 10,
            "volume": [1000.0] * 10,
        })
        with pytest.raises(DataValidationError):
            DataValidator().validate_and_clean(df)
