import pytest
import asyncio
from src.risk.risk_manager import RiskManager


class TestRiskManager:

    @pytest.fixture
    def risk_manager(self):
        rm = RiskManager()
        rm.current_equity = 10000.0
        rm.peak_equity = 10000.0
        return rm

    @pytest.mark.asyncio
    async def test_valid_trade_approved(self, risk_manager):
        result = await risk_manager.check_trade(
            symbol="EURUSD",
            side="buy",
            proposed_size_usd=200.0,
            entry_price=45000.0,
            stop_loss_price=44000.0,
            take_profit_price=47000.0,
            ai_confidence=0.80,
        )
        assert result.approved
        assert result.adjusted_size is not None

    @pytest.mark.asyncio
    async def test_low_ai_confidence_rejected(self, risk_manager):
        result = await risk_manager.check_trade(
            symbol="EURUSD",
            side="buy",
            proposed_size_usd=200.0,
            entry_price=45000.0,
            stop_loss_price=44000.0,
            take_profit_price=47000.0,
            ai_confidence=0.50,  # Below threshold
        )
        assert not result.approved
        assert "confidence" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_bad_rr_ratio_rejected(self, risk_manager):
        result = await risk_manager.check_trade(
            symbol="EURUSD",
            side="buy",
            proposed_size_usd=200.0,
            entry_price=45000.0,
            stop_loss_price=44500.0,  # 500 risk
            take_profit_price=45300.0,  # 300 reward — RR < 1
            ai_confidence=0.80,
        )
        assert not result.approved
        assert "R:R" in result.reason

    @pytest.mark.asyncio
    async def test_max_positions_reached(self, risk_manager):
        # Fill max positions
        for i in range(5):
            risk_manager.open_positions[f"order_{i}"] = {"symbol": "EURUSD", "size_usd": 200}

        result = await risk_manager.check_trade(
            symbol="GBPUSD",
            side="buy",
            proposed_size_usd=200.0,
            entry_price=2500.0,
            stop_loss_price=2400.0,
            take_profit_price=2800.0,
            ai_confidence=0.85,
        )
        assert not result.approved
        assert "Max open positions" in result.reason

    @pytest.mark.asyncio
    async def test_position_size_adjusted(self, risk_manager):
        result = await risk_manager.check_trade(
            symbol="EURUSD",
            side="buy",
            proposed_size_usd=5000.0,  # Way over 2%
            entry_price=45000.0,
            stop_loss_price=44000.0,
            take_profit_price=47000.0,
            ai_confidence=0.80,
        )
        assert result.approved
        assert result.adjusted_size == 200.0  # 2% of 10000

    @pytest.mark.asyncio
    async def test_circuit_breaker_daily_loss(self, risk_manager):
        risk_manager.daily_pnl = -600.0  # 6% loss (over 5% limit)
        result = await risk_manager.check_trade(
            symbol="EURUSD",
            side="buy",
            proposed_size_usd=200.0,
            entry_price=45000.0,
            stop_loss_price=44000.0,
            take_profit_price=47000.0,
            ai_confidence=0.80,
        )
        assert not result.approved
        assert "Daily loss" in result.reason

    @pytest.mark.asyncio
    async def test_circuit_breaker_drawdown(self, risk_manager):
        risk_manager.peak_equity = 10000.0
        risk_manager.current_equity = 8400.0  # 16% drawdown (over 15%)
        result = await risk_manager.check_trade(
            symbol="EURUSD",
            side="buy",
            proposed_size_usd=200.0,
            entry_price=45000.0,
            stop_loss_price=44000.0,
            take_profit_price=47000.0,
            ai_confidence=0.80,
        )
        assert not result.approved
        assert "drawdown" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_circuit_breaker_once_triggered_blocks_all(self, risk_manager):
        risk_manager._circuit_breaker_triggered = True
        result = await risk_manager.check_trade(
            symbol="EURUSD",
            side="buy",
            proposed_size_usd=200.0,
            entry_price=45000.0,
            stop_loss_price=44000.0,
            take_profit_price=47000.0,
            ai_confidence=0.95,  # Even high confidence blocked
        )
        assert not result.approved
        assert "CIRCUIT BREAKER" in result.reason

    def test_reset_daily_stats(self, risk_manager):
        risk_manager.daily_pnl = -500.0
        risk_manager._circuit_breaker_triggered = True
        risk_manager.reset_daily_stats()
        assert risk_manager.daily_pnl == 0.0
        assert not risk_manager._circuit_breaker_triggered

    @pytest.mark.asyncio
    async def test_equity_update(self, risk_manager):
        await risk_manager.update_equity(11000.0, realized_pnl=1000.0)
        assert risk_manager.current_equity == 11000.0
        assert risk_manager.daily_pnl == 1000.0
        assert risk_manager.peak_equity == 11000.0
