import pytest
from src.risk.position_sizer import PositionSizer


class TestPositionSizer:

    @pytest.fixture
    def sizer(self):
        return PositionSizer()

    def test_fixed_method_returns_max_pct(self, sizer):
        size = sizer.calculate_size(
            equity=10000.0,
            entry_price=45000.0,
            stop_loss_price=44000.0,
            method="fixed",
        )
        assert size == 200.0  # 2% of 10000

    def test_risk_based_sizing(self, sizer):
        # 1% risk, SL is 2% away from entry
        size = sizer.calculate_size(
            equity=10000.0,
            entry_price=45000.0,
            stop_loss_price=44100.0,  # 2% away
            method="risk_based",
        )
        assert size > 0
        assert size <= 200.0  # Never exceeds max

    def test_kelly_sizing(self, sizer):
        size = sizer.calculate_size(
            equity=10000.0,
            entry_price=45000.0,
            stop_loss_price=44000.0,
            win_rate=0.55,
            avg_win_pct=2.0,
            avg_loss_pct=1.0,
            method="kelly",
        )
        assert size > 0
        assert size <= 200.0

    def test_calculate_quantity(self, sizer):
        qty = sizer.calculate_quantity(200.0, 45000.0)
        assert abs(qty - 200.0 / 45000.0) < 1e-10

    def test_zero_price_returns_zero(self, sizer):
        qty = sizer.calculate_quantity(200.0, 0.0)
        assert qty == 0.0

    def test_size_never_exceeds_max(self, sizer):
        # Try to get a huge Kelly allocation
        size = sizer.calculate_size(
            equity=10000.0,
            entry_price=45000.0,
            stop_loss_price=44000.0,
            win_rate=0.95,
            avg_win_pct=10.0,
            avg_loss_pct=1.0,
            method="kelly",
        )
        assert size <= 200.0  # Always capped at max_position_size_pct
