import pytest
import pandas as pd
import numpy as np
from src.data.data_validator import DataValidator
from src.core.exceptions import DataValidationError
from src.utils.validators import validate_trade_params, validate_symbol


class TestInvalidData:

    def test_empty_dataframe_raises(self):
        validator = DataValidator()
        df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        with pytest.raises(DataValidationError):
            validator.validate_and_clean(df)

    def test_all_nan_raises(self):
        validator = DataValidator()
        df = pd.DataFrame({
            "open": [np.nan] * 100,
            "high": [np.nan] * 100,
            "low": [np.nan] * 100,
            "close": [np.nan] * 100,
            "volume": [np.nan] * 100,
        })
        with pytest.raises((DataValidationError, Exception)):
            validator.validate_and_clean(df)

    def test_invalid_symbol_rejected(self):
        assert not validate_symbol("BTCUSDT")  # Missing slash
        assert not validate_symbol("")
        assert not validate_symbol("BT/")
        assert validate_symbol("BTC/USDT")

    def test_invalid_trade_buy_sl_above_entry(self):
        valid, msg = validate_trade_params(
            "BTC/USDT", "buy", 200, 45000, 46000, 47000
        )
        assert not valid

    def test_invalid_trade_sell_tp_above_entry(self):
        valid, msg = validate_trade_params(
            "BTC/USDT", "sell", 200, 45000, 46000, 46000
        )
        assert not valid

    def test_invalid_side(self):
        valid, msg = validate_trade_params(
            "BTC/USDT", "long", 200, 45000, 44000, 47000
        )
        assert not valid

    def test_negative_size_rejected(self):
        valid, msg = validate_trade_params(
            "BTC/USDT", "buy", -100, 45000, 44000, 47000
        )
        assert not valid

    def test_valid_buy_trade_accepted(self):
        valid, msg = validate_trade_params(
            "BTC/USDT", "buy", 200, 45000, 44000, 47000
        )
        assert valid

    def test_valid_sell_trade_accepted(self):
        valid, msg = validate_trade_params(
            "ETH/USDT", "sell", 100, 2500, 2600, 2200
        )
        assert valid
