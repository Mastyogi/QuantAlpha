import asyncio
from dataclasses import dataclass
from typing import Optional, Dict
from src.utils.logger import get_logger
from src.core.exceptions import CircuitBreakerError
from config.settings import settings

logger = get_logger(__name__)


@dataclass
class RiskCheckResult:
    approved: bool
    reason: str
    adjusted_size: Optional[float] = None
    risk_score: float = 0.0


class RiskManager:
    """
    Seven-layer risk protection:
    1. Circuit breaker check
    2. AI confidence threshold
    3. Risk/Reward ratio
    4. Max open positions
    5. Position size limits
    6. Daily loss circuit breaker
    7. Drawdown halt
    """

    def __init__(self):
        self.daily_pnl: float = 0.0
        self.peak_equity: float = 0.0
        self.current_equity: float = 10000.0
        self.open_positions: Dict = {}
        self._circuit_breaker_triggered: bool = False

    async def check_trade(
        self,
        symbol: str,
        side: str,
        proposed_size_usd: float,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        ai_confidence: float,
    ) -> RiskCheckResult:
        """
        Full risk assessment before any trade.
        Returns RiskCheckResult with approved=False to block trade.
        """

        # LAYER 1: Circuit breaker check
        if self._circuit_breaker_triggered:
            return RiskCheckResult(
                approved=False,
                reason="CIRCUIT BREAKER ACTIVE: Max drawdown or daily loss exceeded",
            )

        # LAYER 2: AI confidence threshold
        if ai_confidence < settings.ai_confidence_threshold:
            return RiskCheckResult(
                approved=False,
                reason=f"AI confidence {ai_confidence:.1%} below threshold {settings.ai_confidence_threshold:.1%}",
            )

        # LAYER 3: Risk/Reward ratio check
        if side == "buy":
            reward = take_profit_price - entry_price
            risk = entry_price - stop_loss_price
        else:
            reward = entry_price - take_profit_price
            risk = stop_loss_price - entry_price

        if risk <= 0:
            return RiskCheckResult(approved=False, reason="Invalid stop loss (risk ≤ 0)")

        rr_ratio = reward / risk
        if rr_ratio < settings.risk_reward_ratio_min:
            return RiskCheckResult(
                approved=False,
                reason=f"R:R ratio {rr_ratio:.2f} below minimum {settings.risk_reward_ratio_min}",
            )

        # LAYER 4: Max open positions
        if len(self.open_positions) >= settings.max_open_positions:
            return RiskCheckResult(
                approved=False,
                reason=f"Max open positions ({settings.max_open_positions}) reached",
            )

        # LAYER 5: Position size limits
        max_size_usd = self.current_equity * (settings.max_position_size_pct / 100)
        adjusted_size = min(proposed_size_usd, max_size_usd)

        if adjusted_size < proposed_size_usd:
            logger.info(
                f"Position size adjusted: ${proposed_size_usd:.2f} → ${adjusted_size:.2f}"
            )

        # LAYER 6: Daily loss check
        if self.current_equity > 0:
            daily_loss_pct = abs(self.daily_pnl) / self.current_equity * 100
        else:
            daily_loss_pct = 0
        if self.daily_pnl < 0 and daily_loss_pct >= settings.max_daily_loss_pct:
            self._circuit_breaker_triggered = True
            return RiskCheckResult(
                approved=False,
                reason=f"Daily loss limit {settings.max_daily_loss_pct}% hit. Trading halted.",
            )

        # LAYER 7: Drawdown check
        if self.peak_equity > 0:
            drawdown_pct = (self.peak_equity - self.current_equity) / self.peak_equity * 100
            if drawdown_pct >= settings.max_drawdown_pct:
                self._circuit_breaker_triggered = True
                return RiskCheckResult(
                    approved=False,
                    reason=f"Max drawdown {settings.max_drawdown_pct}% breached. TRADING HALTED.",
                )

        return RiskCheckResult(
            approved=True,
            reason="All risk checks passed",
            adjusted_size=adjusted_size,
            risk_score=self._calculate_risk_score(ai_confidence, rr_ratio, adjusted_size),
        )

    def _calculate_risk_score(self, confidence: float, rr: float, size: float) -> float:
        """Composite risk score 0-10 (lower = safer)."""
        size_pct = size / max(self.current_equity, 1) * 100
        return round(
            (1 - confidence) * 3
            + (1 / max(rr, 0.1)) * 3
            + (size_pct / 2),
            2,
        )

    def register_open_position(self, order_id: str, symbol: str, size_usd: float):
        """Track a newly opened position."""
        self.open_positions[order_id] = {"symbol": symbol, "size_usd": size_usd}

    def remove_position(self, order_id: str):
        """Remove a closed position."""
        self.open_positions.pop(order_id, None)

    async def update_equity(self, new_equity: float, realized_pnl: float = 0):
        """Update equity tracking and drawdown monitor."""
        self.current_equity = new_equity
        self.daily_pnl += realized_pnl
        if new_equity > self.peak_equity:
            self.peak_equity = new_equity
        logger.debug(
            f"Equity updated: ${new_equity:.2f}, Daily PnL: ${self.daily_pnl:.2f}"
        )

    def reset_daily_stats(self):
        """Call this at 00:00 UTC every day."""
        self.daily_pnl = 0.0
        self._circuit_breaker_triggered = False
        logger.info("Daily risk stats reset")

    @property
    def circuit_breaker_active(self) -> bool:
        return self._circuit_breaker_triggered
