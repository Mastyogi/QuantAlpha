"""
Drawdown Monitor
=================
Real-time equity tracking + 7-layer circuit breaker system.

Triggers:
  Layer 1 — Warning:        Drawdown > 7.5%   → Alert sent
  Layer 2 — Reduce Size:    Drawdown > 10%    → Position size halved
  Layer 3 — Pause New:      Drawdown > 12.5%  → No new trades opened
  Layer 4 — Circuit Break:  Drawdown > 15%    → ALL trading stopped
  Layer 5 — Daily Limit:    Daily loss > 5%   → Paused until next day
  Layer 6 — Loss Streak:    5 consecutive L   → Size reduced 50%
  Layer 7 — Win Rate Drop:  Last 10 < 40% WR  → Review mode

Circuit break requires MANUAL restart — safety feature.
"""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Deque, Dict, List, Optional, Tuple

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EquitySnapshot:
    equity:    float
    timestamp: str
    pnl:       float = 0.0


@dataclass
class RiskState:
    """Current risk assessment."""
    drawdown_pct:       float = 0.0   # Current DD from peak
    daily_loss_pct:     float = 0.0
    loss_streak:        int   = 0
    win_streak:         int   = 0
    recent_win_rate:    float = 1.0   # Last 10 trades
    size_multiplier:    float = 1.0   # 1.0 = full size, 0.5 = half
    circuit_broken:     bool  = False
    daily_paused:       bool  = False
    reduce_size:        bool  = False
    pause_new_trades:   bool  = False
    active_warnings:    List[str] = field(default_factory=list)

    @property
    def trading_allowed(self) -> bool:
        return not self.circuit_broken and not self.daily_paused and not self.pause_new_trades

    @property
    def effective_risk_pct(self) -> float:
        """Actual risk per trade after multiplier."""
        return 2.0 * self.size_multiplier

    def status_line(self) -> str:
        icons = []
        if self.circuit_broken:    icons.append("🔴 CIRCUIT BREAK")
        elif self.daily_paused:    icons.append("🟡 DAILY LIMIT HIT")
        elif self.pause_new_trades: icons.append("🟠 PAUSED NEW TRADES")
        elif self.reduce_size:     icons.append("🟡 SIZE REDUCED")
        else:                      icons.append("🟢 TRADING OK")
        return f"{' | '.join(icons)} | DD={self.drawdown_pct:.1f}% | Daily={self.daily_loss_pct:.1f}%"


class DrawdownMonitor:
    """
    Tracks equity in real-time and enforces circuit breakers.
    Integrates with EventBus to broadcast risk state changes.
    """

    # ── Thresholds ────────────────────────────────────────────────────────────
    DD_WARNING     = 7.5
    DD_REDUCE_SIZE = 10.0
    DD_PAUSE_NEW   = 12.5
    DD_CIRCUIT     = 15.0
    DAILY_LIMIT    = 5.0
    STREAK_LIMIT   = 5
    RECENT_WR_MIN  = 0.40

    def __init__(self, initial_equity: float = 10_000.0):
        self.initial_equity   = initial_equity
        self.peak_equity      = initial_equity
        self._equity          = initial_equity
        self._daily_start_eq  = initial_equity
        self._last_reset_date = date.today()

        self._equity_history: List[EquitySnapshot] = [
            EquitySnapshot(equity=initial_equity, timestamp=self._now())
        ]
        self._trade_results: Deque[bool] = deque(maxlen=20)  # True=win, False=loss
        self._daily_trades:  Deque[float] = deque(maxlen=100)

        self.state = RiskState()
        self._circuit_break_time: Optional[str] = None

        # EventBus integration (optional — won't crash if not available)
        try:
            from src.core.event_bus import bus
            self._bus = bus
        except ImportError:
            self._bus = None

    # ── Equity updates ────────────────────────────────────────────────────────

    async def update_equity(self, new_equity: float, realized_pnl: float = 0.0) -> RiskState:
        """
        Call after every trade close or mark-to-market.
        Returns updated RiskState.
        """
        self._check_date_reset()

        prev_equity  = self._equity
        self._equity = new_equity
        self.peak_equity = max(self.peak_equity, new_equity)

        snapshot = EquitySnapshot(equity=new_equity, timestamp=self._now(), pnl=realized_pnl)
        self._equity_history.append(snapshot)
        if len(self._equity_history) > 500:
            self._equity_history = self._equity_history[-500:]

        if realized_pnl != 0.0:
            self._daily_trades.append(realized_pnl)
            is_win = realized_pnl > 0
            self._trade_results.append(is_win)
            if is_win:
                self.state.win_streak += 1
                self.state.loss_streak = 0
            else:
                self.state.loss_streak += 1
                self.state.win_streak  = 0

        await self._evaluate_risk()
        return self.state

    async def _evaluate_risk(self) -> None:
        """Re-evaluate all risk layers and emit events if state changes."""
        prev_state = RiskState(
            circuit_broken=self.state.circuit_broken,
            daily_paused=self.state.daily_paused,
        )
        warnings = []

        # ── Calculate metrics ─────────────────────────────────────────────────
        dd = (self.peak_equity - self._equity) / self.peak_equity * 100
        daily_loss = (self._daily_start_eq - self._equity) / self._daily_start_eq * 100
        daily_loss = max(daily_loss, 0.0)
        recent_wr = (
            sum(self._trade_results) / len(self._trade_results)
            if self._trade_results else 1.0
        )

        self.state.drawdown_pct    = round(dd, 2)
        self.state.daily_loss_pct  = round(daily_loss, 2)
        self.state.recent_win_rate = round(recent_wr, 3)

        # ── Layer 4: Circuit Breaker (max drawdown) ───────────────────────────
        if dd >= self.DD_CIRCUIT and not self.state.circuit_broken:
            self.state.circuit_broken = True
            self._circuit_break_time  = self._now()
            msg = f"🔴 CIRCUIT BREAKER TRIGGERED: Drawdown {dd:.1f}% ≥ {self.DD_CIRCUIT}%"
            logger.critical(msg)
            warnings.append(msg)
            if self._bus:
                await self._bus.emit_circuit_break(msg, dd)

        # ── Layer 5: Daily limit ──────────────────────────────────────────────
        elif daily_loss >= self.DAILY_LIMIT and not self.state.daily_paused:
            self.state.daily_paused = True
            msg = f"🟡 DAILY LIMIT: Loss {daily_loss:.1f}% ≥ {self.DAILY_LIMIT}%"
            logger.warning(msg)
            warnings.append(msg)
            if self._bus:
                await self._bus.publish(
                    __import__('src.core.event_bus', fromlist=['Event', 'EventType']).Event(
                        type=__import__('src.core.event_bus', fromlist=['EventType']).EventType.DAILY_LIMIT_HIT,
                        data={"daily_loss_pct": daily_loss}, source="drawdown_monitor"
                    )
                )

        # ── Layer 3: Pause new trades ─────────────────────────────────────────
        self.state.pause_new_trades = (dd >= self.DD_PAUSE_NEW and not self.state.circuit_broken)
        if dd >= self.DD_PAUSE_NEW:
            warnings.append(f"🟠 Pausing new trades: DD={dd:.1f}%")

        # ── Layer 2: Reduce size ──────────────────────────────────────────────
        if dd >= self.DD_REDUCE_SIZE or self.state.loss_streak >= self.STREAK_LIMIT:
            self.state.reduce_size      = True
            self.state.size_multiplier  = 0.5
            warnings.append(f"📉 Size halved: DD={dd:.1f}%, streak={self.state.loss_streak}")
        elif dd >= self.DD_WARNING:
            self.state.size_multiplier = 0.75
            warnings.append(f"⚠️  Size reduced 25%: DD={dd:.1f}%")
        else:
            self.state.reduce_size     = False
            self.state.size_multiplier = 1.0

        # ── Layer 1: Warning ─────────────────────────────────────────────────
        if dd >= self.DD_WARNING:
            warnings.append(f"⚠️  Drawdown warning: {dd:.1f}%")

        # ── Layer 7: Win rate drop ────────────────────────────────────────────
        if len(self._trade_results) >= 5 and recent_wr < self.RECENT_WR_MIN:
            warnings.append(f"📊 Low win rate: {recent_wr:.0%} (last {len(self._trade_results)} trades)")
            self.state.size_multiplier = min(self.state.size_multiplier, 0.5)

        self.state.active_warnings = warnings
        if warnings:
            for w in warnings[:2]:  # Log first 2
                logger.warning(w)

    # ── Manual controls ───────────────────────────────────────────────────────

    def reset_circuit_breaker(self, admin_confirmed: bool = True) -> bool:
        """Manual reset — requires explicit admin confirmation."""
        if not admin_confirmed:
            return False
        logger.warning("Circuit breaker MANUALLY RESET by admin")
        self.state.circuit_broken  = False
        self.state.pause_new_trades = False
        self._circuit_break_time   = None
        return True

    def reset_daily(self) -> None:
        """Called at start of new trading day."""
        self._daily_start_eq  = self._equity
        self.state.daily_paused = False
        self._daily_trades.clear()
        logger.info("Daily limits reset")

    # ── Position size helper ──────────────────────────────────────────────────

    def get_adjusted_risk_pct(self, base_risk_pct: float = 2.0) -> float:
        """Return risk % adjusted for current drawdown state."""
        if not self.state.trading_allowed:
            return 0.0
        return round(base_risk_pct * self.state.size_multiplier, 2)

    # ── Analytics ─────────────────────────────────────────────────────────────

    def get_equity_curve(self, last_n: int = 100) -> List[Dict]:
        snaps = self._equity_history[-last_n:]
        return [{"t": s.timestamp, "equity": s.equity, "pnl": s.pnl} for s in snaps]

    def get_summary(self) -> Dict:
        total_return = (self._equity - self.initial_equity) / self.initial_equity * 100
        max_dd = 0.0
        peak = self.initial_equity
        for snap in self._equity_history:
            peak = max(peak, snap.equity)
            dd = (peak - snap.equity) / peak * 100
            max_dd = max(max_dd, dd)

        return {
            "current_equity":   round(self._equity, 2),
            "peak_equity":      round(self.peak_equity, 2),
            "initial_equity":   self.initial_equity,
            "total_return_pct": round(total_return, 2),
            "current_dd_pct":   self.state.drawdown_pct,
            "max_dd_pct":       round(max_dd, 2),
            "daily_loss_pct":   self.state.daily_loss_pct,
            "loss_streak":      self.state.loss_streak,
            "win_streak":       self.state.win_streak,
            "recent_win_rate":  self.state.recent_win_rate,
            "size_multiplier":  self.state.size_multiplier,
            "circuit_broken":   self.state.circuit_broken,
            "trading_allowed":  self.state.trading_allowed,
            "status":           self.state.status_line(),
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _check_date_reset(self) -> None:
        today = date.today()
        if today != self._last_reset_date:
            self.reset_daily()
            self._last_reset_date = today

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @property
    def current_equity(self) -> float:
        return self._equity

    @property
    def trading_allowed(self) -> bool:
        return self.state.trading_allowed
