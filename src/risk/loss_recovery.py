"""Loss Recovery State Machine"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from src.utils.logger import get_logger
logger = get_logger(__name__)

class RecoveryPhase(str, Enum):
    NORMAL="NORMAL"; ALERT="ALERT"; RECOVERY="RECOVERY"; PAUSED="PAUSED"; RESET="RESET"

@dataclass
class RecoveryEvent:
    timestamp: str; symbol: str; event_type: str
    old_phase: str; new_phase: str; pnl_usd: float

class LossRecoveryManager:
    MAX_CONSECUTIVE_LOSSES = 5

    def __init__(self, dynamic_sizer=None):
        self._sizer = dynamic_sizer
        self._phases: Dict[str, RecoveryPhase] = {}
        self._events: List[RecoveryEvent] = []
        self._consec_losses: Dict[str, int] = {}
        self._consec_wins: Dict[str, int] = {}

    def on_trade_result(self, symbol, won, pnl_usd=0.0) -> RecoveryPhase:
        current = self._phases.get(symbol, RecoveryPhase.NORMAL)
        cons_l = self._consec_losses.get(symbol, 0)
        if won:
            self._consec_wins[symbol] = self._consec_wins.get(symbol, 0) + 1
            self._consec_losses[symbol] = 0
            if current in (RecoveryPhase.ALERT, RecoveryPhase.RECOVERY):
                new_phase = RecoveryPhase.RESET
                if self._sizer: self._sizer.record_win(symbol, pnl_usd)
            elif current == RecoveryPhase.PAUSED:
                new_phase = RecoveryPhase.NORMAL
                if self._sizer: self._sizer.record_win(symbol, pnl_usd)
            elif current == RecoveryPhase.RESET:
                new_phase = RecoveryPhase.NORMAL
            else:
                new_phase = RecoveryPhase.NORMAL
                if self._sizer: self._sizer.record_win(symbol, pnl_usd)
        else:
            self._consec_losses[symbol] = cons_l + 1
            self._consec_wins[symbol] = 0
            new_cons = self._consec_losses[symbol]
            if new_cons >= self.MAX_CONSECUTIVE_LOSSES:
                new_phase = RecoveryPhase.PAUSED
                logger.warning(f"PAUSED [{symbol}]: {new_cons} consecutive losses")
            elif new_cons >= 3:
                new_phase = RecoveryPhase.RECOVERY
                if self._sizer: self._sizer.record_loss(symbol, pnl_usd)
            elif new_cons >= 1:
                new_phase = RecoveryPhase.ALERT
                if self._sizer: self._sizer.record_loss(symbol, pnl_usd)
            else:
                new_phase = RecoveryPhase.NORMAL
        self._events.append(RecoveryEvent(
            datetime.now(timezone.utc).isoformat(), symbol,
            "WIN" if won else "LOSS", str(current), str(new_phase), pnl_usd))
        self._phases[symbol] = new_phase
        return new_phase

    def get_phase(self, symbol): return self._phases.get(symbol, RecoveryPhase.NORMAL)
    def is_trading_allowed(self, symbol): return self.get_phase(symbol) != RecoveryPhase.PAUSED

    def manual_resume(self, symbol):
        self._phases[symbol] = RecoveryPhase.NORMAL
        self._consec_losses[symbol] = 0
        if self._sizer: self._sizer.reset_symbol(symbol, "manual_resume")
        return f"Resumed {symbol}"

    def get_status_all(self):
        return {sym: {"phase": str(phase), "cons_losses": self._consec_losses.get(sym,0),
                      "trading_ok": self.is_trading_allowed(sym)}
                for sym, phase in self._phases.items()}
