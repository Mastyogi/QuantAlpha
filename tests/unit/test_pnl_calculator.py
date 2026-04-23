import pytest
from src.execution.paper_trader import PaperTrader


@pytest.fixture
def trader():
    return PaperTrader()


class TestPaperTrader:

    def test_buy_order_placed_correctly(self, trader):
        r = trader.execute_order("BTC/USDT", "buy", 200.0, 45000.0, 44000.0, 47000.0)
        assert r["id"].startswith("paper_")
        assert r["amount"] > 0
        assert len(trader.open_positions) == 1

    def test_sell_order_placed_correctly(self, trader):
        r = trader.execute_order("ETH/USDT", "sell", 200.0, 2500.0, 2600.0, 2200.0)
        assert r["id"].startswith("paper_")
        assert r["side"] == "sell"

    def test_stop_loss_closes_long(self, trader):
        trader.execute_order("BTC/USDT", "buy", 200.0, 45000.0, 44000.0, 47000.0)
        closed = trader.update_positions({"BTC/USDT": 43500.0})
        assert len(closed) == 1
        assert closed[0]["exit_reason"] == "STOP_LOSS"
        assert closed[0]["pnl"] < 0

    def test_take_profit_closes_long(self, trader):
        trader.execute_order("BTC/USDT", "buy", 200.0, 45000.0, 44000.0, 47000.0)
        closed = trader.update_positions({"BTC/USDT": 47500.0})
        assert len(closed) == 1
        assert closed[0]["exit_reason"] == "TAKE_PROFIT"
        assert closed[0]["pnl"] > 0

    def test_price_in_range_keeps_position_open(self, trader):
        trader.execute_order("BTC/USDT", "buy", 200.0, 45000.0, 44000.0, 47000.0)
        closed = trader.update_positions({"BTC/USDT": 45500.0})
        assert len(closed) == 0
        assert len(trader.open_positions) == 1

    def test_stop_loss_closes_short(self, trader):
        trader.execute_order("ETH/USDT", "sell", 200.0, 2500.0, 2600.0, 2200.0)
        closed = trader.update_positions({"ETH/USDT": 2650.0})
        assert len(closed) == 1
        assert closed[0]["exit_reason"] == "STOP_LOSS"

    def test_take_profit_closes_short(self, trader):
        trader.execute_order("ETH/USDT", "sell", 200.0, 2500.0, 2600.0, 2200.0)
        closed = trader.update_positions({"ETH/USDT": 2150.0})
        assert len(closed) == 1
        assert closed[0]["exit_reason"] == "TAKE_PROFIT"
        assert closed[0]["pnl"] > 0

    def test_equity_reduced_by_fee_on_entry(self, trader):
        initial = trader.equity
        trader.execute_order("BTC/USDT", "buy", 200.0, 45000.0, 44000.0, 47000.0)
        assert trader.equity < initial

    def test_stats_after_winning_trade(self, trader):
        trader.execute_order("BTC/USDT", "buy", 200.0, 45000.0, 44000.0, 47000.0)
        trader.update_positions({"BTC/USDT": 47500.0})
        s = trader.get_stats()
        assert s["total_trades"] == 1
        assert s["winning_trades"] == 1
        assert s["win_rate"] == 100.0

    def test_multiple_positions_independent(self, trader):
        trader.execute_order("BTC/USDT", "buy", 200.0, 45000.0, 44000.0, 47000.0)
        trader.execute_order("ETH/USDT", "buy", 200.0, 2500.0,  2400.0,  2800.0)
        assert len(trader.open_positions) == 2
        closed = trader.update_positions({"BTC/USDT": 47500.0, "ETH/USDT": 2450.0})
        assert len(closed) == 1  # Only BTC hit TP
        assert closed[0]["symbol"] == "BTC/USDT"
