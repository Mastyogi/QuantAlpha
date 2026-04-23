from src.utils.math_utils import calculate_kelly_fraction
from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


class PositionSizer:
    """
    Calculates optimal position size using Kelly Criterion + fixed fraction.
    Always caps at max_position_size_pct to prevent over-sizing.
    """

    def calculate_size(
        self,
        equity: float,
        entry_price: float,
        stop_loss_price: float,
        win_rate: float = 0.55,
        avg_win_pct: float = 2.0,
        avg_loss_pct: float = 1.0,
        method: str = "fixed",
    ) -> float:
        """
        Calculate position size in USD.

        Args:
            equity: Current portfolio value
            entry_price: Planned entry price
            stop_loss_price: Stop loss price
            win_rate: Historical win rate (for Kelly)
            avg_win_pct: Average winning trade return
            avg_loss_pct: Average losing trade return
            method: "fixed" | "kelly" | "risk_based"

        Returns:
            Position size in USD
        """
        max_size = equity * (settings.max_position_size_pct / 100)

        if method == "fixed":
            return max_size

        elif method == "risk_based":
            # Size based on $ risk to stop loss
            risk_per_trade = equity * 0.01  # 1% of equity
            price_risk_pct = abs(entry_price - stop_loss_price) / entry_price
            if price_risk_pct <= 0:
                return max_size
            size = risk_per_trade / price_risk_pct
            return min(size, max_size)

        elif method == "kelly":
            kelly = calculate_kelly_fraction(win_rate, avg_win_pct, avg_loss_pct)
            size = equity * kelly
            return min(size, max_size)

        return max_size

    def calculate_quantity(self, size_usd: float, price: float) -> float:
        """Convert USD size to quantity at given price."""
        if price <= 0:
            return 0.0
        return size_usd / price
