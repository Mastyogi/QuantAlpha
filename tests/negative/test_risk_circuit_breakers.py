import pytest
from src.risk.risk_manager import RiskManager


class TestCircuitBreakers:

    @pytest.fixture
    def risk_manager(self):
        rm = RiskManager()
        rm.current_equity = 10000.0
        rm.peak_equity = 10000.0
        return rm

    @pytest.mark.asyncio
    async def test_daily_loss_circuit_breaker_blocks_all_trades(self, risk_manager):
        """Once daily loss limit hit, ALL trades should be rejected."""
        risk_manager.daily_pnl = -600.0  # 6% loss
        for _ in range(3):
            result = await risk_manager.check_trade(
                "BTC/USDT", "buy", 200, 45000, 44000, 47000, 0.95
            )
            assert not result.approved

    @pytest.mark.asyncio
    async def test_drawdown_circuit_breaker(self, risk_manager):
        """Max drawdown circuit breaker should trigger."""
        risk_manager.peak_equity = 10000.0
        risk_manager.current_equity = 8400.0  # 16% drawdown
        result = await risk_manager.check_trade(
            "BTC/USDT", "buy", 200, 45000, 44000, 47000, 0.95
        )
        assert not result.approved
        assert risk_manager.circuit_breaker_active

    @pytest.mark.asyncio
    async def test_circuit_breaker_resets_daily(self, risk_manager):
        """Circuit breaker must reset at midnight."""
        risk_manager._circuit_breaker_triggered = True
        risk_manager.daily_pnl = -1000.0
        risk_manager.reset_daily_stats()
        assert not risk_manager.circuit_breaker_active
        assert risk_manager.daily_pnl == 0.0

    @pytest.mark.asyncio
    async def test_invalid_stop_loss_rejected(self, risk_manager):
        """Stop loss on wrong side of entry must be rejected."""
        result = await risk_manager.check_trade(
            "BTC/USDT", "buy",
            200,
            45000,
            46000,   # SL above entry for BUY — invalid
            47000,
            0.85,
        )
        assert not result.approved

    @pytest.mark.asyncio
    async def test_zero_confidence_rejected(self, risk_manager):
        result = await risk_manager.check_trade(
            "BTC/USDT", "buy", 200, 45000, 44000, 47000, ai_confidence=0.0
        )
        assert not result.approved
