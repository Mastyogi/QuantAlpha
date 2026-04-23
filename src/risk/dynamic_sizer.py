"""Dynamic Position Sizer with loss-recovery logic. $10 min wallet."""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from src.utils.logger import get_logger
logger = get_logger(__name__)

@dataclass
class SizingState:
    symbol: str; base_risk_pct: float
    current_multiplier: float = 1.0; consecutive_losses: int = 0
    in_recovery: bool = False; total_loss_usd: float = 0.0
    @property
    def current_risk_pct(self): return min(self.base_risk_pct*self.current_multiplier, 2.0)
    def status_line(self):
        if self.in_recovery:
            return f"RECOVERY | risk={self.current_risk_pct:.2f}% mult={self.current_multiplier:.2f}x losses={self.consecutive_losses}"
        return f"NORMAL | risk={self.current_risk_pct:.1f}%"

@dataclass
class SizingHistory:
    trade_id: str; symbol: str; equity: float; size_usd: float
    multiplier: float; in_recovery: bool; timestamp: str = ""

class DynamicPositionSizer:
    MAX_RISK_PCT = 2.0; MAX_MULTIPLIER = 2.0; MAX_CONSEC = 3

    def __init__(self, base_risk_pct=1.0, increase_pct=0.15, max_multiplier=2.0,
                 min_trade_usd=1.0, min_wallet_usd=10.0, history_dir="logs"):
        self.base_risk_pct = base_risk_pct; self.increase_pct = increase_pct
        self.max_multiplier = min(max_multiplier, self.MAX_MULTIPLIER)
        self.min_trade_usd = max(min_trade_usd, 1.0); self.min_wallet_usd = min_wallet_usd
        self._states: Dict[str, SizingState] = {}
        self._history: List[SizingHistory] = []
        os.makedirs(history_dir, exist_ok=True)
        logger.info(f"DynamicPositionSizer: base={base_risk_pct}% increase={increase_pct*100:.0f}%/loss min_wallet=${min_wallet_usd}")

    def get_position_size(self, symbol, equity, entry_price, stop_loss,
                          ai_confidence=0.75, trade_id="") -> Tuple[float, SizingState]:
        state = self._get_or_create(symbol)
        if equity < self.min_wallet_usd:
            logger.warning(f"Equity ${equity:.2f} < min ${self.min_wallet_usd}")
            return 0.0, state
        conf_mult = max(0.7, min(1.3, 0.9 + (ai_confidence - 0.70) * 1.5))
        stop_dist = abs(entry_price - stop_loss) / max(entry_price, 1e-10)
        if stop_dist <= 0: stop_dist = 0.02
        risk_pct = min(state.current_risk_pct * conf_mult, self.MAX_RISK_PCT)
        risk_usd = equity * risk_pct / 100
        size_usd = risk_usd / max(stop_dist, 0.005)
        size_usd = max(size_usd, self.min_trade_usd)
        size_usd = min(size_usd, equity * 0.5)
        self._history.append(SizingHistory(trade_id, symbol, equity, round(size_usd,2),
            state.current_multiplier, state.in_recovery, datetime.now(timezone.utc).isoformat()))
        return round(size_usd, 2), state

    def record_win(self, symbol, pnl_usd=0.0) -> SizingState:
        state = self._get_or_create(symbol)
        if state.in_recovery:
            state.current_multiplier = 1.0; state.consecutive_losses = 0
            state.in_recovery = False
            logger.info(f"RECOVERY COMPLETE [{symbol}] — reset to base")
        else:
            state.consecutive_losses = 0
        return state

    def record_loss(self, symbol, loss_usd=0.0) -> SizingState:
        state = self._get_or_create(symbol)
        state.consecutive_losses += 1; state.total_loss_usd += abs(loss_usd)
        if not state.in_recovery: state.in_recovery = True
        if state.consecutive_losses <= self.MAX_CONSEC:
            new_m = 1.0 + self.increase_pct * state.consecutive_losses
            state.current_multiplier = min(new_m, self.max_multiplier)
            logger.info(f"Loss #{state.consecutive_losses} [{symbol}] mult={state.current_multiplier:.2f}x")
        return state

    def reset_symbol(self, symbol, reason="manual"):
        state = self._get_or_create(symbol)
        state.current_multiplier = 1.0; state.consecutive_losses = 0; state.in_recovery = False

    def get_state(self, symbol): return self._get_or_create(symbol)
    def get_all_states(self): return dict(self._states)
    def get_metrics(self):
        in_rec = sum(1 for s in self._states.values() if s.in_recovery)
        return {"base_risk_pct": self.base_risk_pct, "symbols_tracked": len(self._states),
                "symbols_in_recovery": in_rec}

    def _get_or_create(self, symbol):
        if symbol not in self._states:
            self._states[symbol] = SizingState(symbol, self.base_risk_pct)
        return self._states[symbol]
