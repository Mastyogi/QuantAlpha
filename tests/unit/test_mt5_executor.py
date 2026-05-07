"""
Unit tests for MT5Executor — mock mode (no real MT5 terminal needed).
"""
import pytest
from unittest.mock import MagicMock, patch


class TestMT5ExecutorStubMode:
    """Tests that run when MetaTrader5 package is not installed."""

    def setup_method(self):
        from src.execution.mt5_executor import MT5Executor
        self.executor = MT5Executor(login=12345, password="test", server="FxPro-Demo")

    def test_connect_fails_gracefully_without_mt5(self):
        with patch("src.execution.mt5_executor.MT5_AVAILABLE", False):
            from src.execution.mt5_executor import MT5Executor
            ex = MT5Executor(login=12345, password="test", server="FxPro-Demo")
            result = ex.connect()
            assert result is False

    def test_place_order_fails_gracefully_without_mt5(self):
        with patch("src.execution.mt5_executor.MT5_AVAILABLE", False):
            from src.execution.mt5_executor import MT5Executor
            ex = MT5Executor()
            result = ex.place_order("EURUSD", "buy", 0.01)
            assert result.success is False
            assert "not installed" in result.error.lower() or "not connected" in result.error.lower()

    def test_get_positions_returns_empty_without_mt5(self):
        with patch("src.execution.mt5_executor.MT5_AVAILABLE", False):
            from src.execution.mt5_executor import MT5Executor
            ex = MT5Executor()
            positions = ex.get_positions()
            assert positions == []

    def test_get_account_info_returns_none_without_mt5(self):
        with patch("src.execution.mt5_executor.MT5_AVAILABLE", False):
            from src.execution.mt5_executor import MT5Executor
            ex = MT5Executor()
            info = ex.get_account_info()
            assert info is None


class TestMT5ExecutorWithMockMT5:
    """Tests using a mocked MetaTrader5 module."""

    def _make_mock_mt5(self):
        mt5 = MagicMock()
        mt5.TRADE_RETCODE_DONE = 10009
        mt5.ORDER_TYPE_BUY = 0
        mt5.ORDER_TYPE_SELL = 1
        mt5.TRADE_ACTION_DEAL = 1
        mt5.TRADE_ACTION_SLTP = 6
        mt5.ORDER_FILLING_IOC = 1
        mt5.ORDER_FILLING_FOK = 0
        mt5.ORDER_TIME_GTC = 0
        mt5.initialize.return_value = True
        mt5.login.return_value = True

        # Account info mock
        account = MagicMock()
        account.login = 12345
        account.server = "FxPro-Demo"
        account.balance = 10000.0
        account.equity = 10000.0
        account.margin = 0.0
        account.margin_free = 10000.0
        account.margin_level = 0.0
        account.profit = 0.0
        account.currency = "USD"
        account.leverage = 100
        account.trade_allowed = True
        mt5.account_info.return_value = account

        # Tick mock
        tick = MagicMock()
        tick.bid = 1.0850
        tick.ask = 1.0852
        mt5.symbol_info_tick.return_value = tick

        # Symbol info mock
        sym_info = MagicMock()
        sym_info.filling_mode = 0
        mt5.symbol_info.return_value = sym_info

        # Order result mock
        order_result = MagicMock()
        order_result.retcode = 10009
        order_result.order = 12345678
        order_result.price = 1.0852
        order_result.volume = 0.01
        order_result.comment = "Request executed"
        mt5.order_send.return_value = order_result

        return mt5

    def test_connect_success(self):
        mock_mt5 = self._make_mock_mt5()
        with patch("src.execution.mt5_executor.MT5_AVAILABLE", True), \
             patch("src.execution.mt5_executor.mt5", mock_mt5):
            from src.execution.mt5_executor import MT5Executor
            ex = MT5Executor(login=12345, password="test", server="FxPro-Demo")
            result = ex.connect()
            assert result is True
            assert ex._connected is True

    def test_place_buy_order(self):
        mock_mt5 = self._make_mock_mt5()
        with patch("src.execution.mt5_executor.MT5_AVAILABLE", True), \
             patch("src.execution.mt5_executor.mt5", mock_mt5):
            from src.execution.mt5_executor import MT5Executor
            ex = MT5Executor(login=12345, password="test", server="FxPro-Demo")
            ex._connected = True
            result = ex.place_order("EURUSD", "buy", 0.01, stop_loss=1.0800, take_profit=1.0950)
            assert result.success is True
            assert result.ticket == 12345678
            assert result.price == 1.0852

    def test_place_sell_order(self):
        mock_mt5 = self._make_mock_mt5()
        with patch("src.execution.mt5_executor.MT5_AVAILABLE", True), \
             patch("src.execution.mt5_executor.mt5", mock_mt5):
            from src.execution.mt5_executor import MT5Executor
            ex = MT5Executor(login=12345, password="test", server="FxPro-Demo")
            ex._connected = True
            result = ex.place_order("EURUSD", "sell", 0.01, stop_loss=1.0900, take_profit=1.0750)
            assert result.success is True

    def test_get_account_info(self):
        mock_mt5 = self._make_mock_mt5()
        with patch("src.execution.mt5_executor.MT5_AVAILABLE", True), \
             patch("src.execution.mt5_executor.mt5", mock_mt5):
            from src.execution.mt5_executor import MT5Executor
            ex = MT5Executor(login=12345, password="test", server="FxPro-Demo")
            ex._connected = True
            info = ex.get_account_info()
            assert info is not None
            assert info.balance == 10000.0
            assert info.leverage == 100

    def test_order_failure_returns_error(self):
        mock_mt5 = self._make_mock_mt5()
        mock_mt5.order_send.return_value.retcode = 10004  # Requote
        mock_mt5.order_send.return_value.comment = "Requote"
        with patch("src.execution.mt5_executor.MT5_AVAILABLE", True), \
             patch("src.execution.mt5_executor.mt5", mock_mt5):
            from src.execution.mt5_executor import MT5Executor
            ex = MT5Executor(login=12345, password="test", server="FxPro-Demo")
            ex._connected = True
            result = ex.place_order("EURUSD", "buy", 0.01)
            assert result.success is False


class TestOrderManagerLotSizing:
    """Test USD → lot size conversion."""

    def test_forex_lot_sizing(self):
        from src.execution.order_manager import OrderManager
        # EURUSD at 1.085: $1000 / (100000 * 1.085) ≈ 0.01 lots
        lot = OrderManager._usd_to_lots("EURUSD", 1000.0, 1.085)
        assert 0.005 <= lot <= 0.02

    def test_crypto_lot_sizing(self):
        from src.execution.order_manager import OrderManager
        # BTC at 50000: $1000 / 50000 = 0.02 BTC
        lot = OrderManager._usd_to_lots("BTC/USDT", 1000.0, 50000.0)
        assert abs(lot - 0.02) < 0.001

    def test_minimum_lot_enforced(self):
        from src.execution.order_manager import OrderManager
        # Very small amount should still give minimum 0.01 lots for forex
        lot = OrderManager._usd_to_lots("EURUSD", 1.0, 1.085)
        assert lot >= 0.01
