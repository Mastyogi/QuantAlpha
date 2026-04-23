"""Mock Notifier — console + HTML fallback when no Telegram token"""
from __future__ import annotations
import json, os, time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
from src.utils.logger import get_logger
logger = get_logger(__name__)

EVENTS_FILE = "/tmp/paper_report_events.jsonl"

@dataclass
class NotifyEvent:
    ts:str; level:str; symbol:str; message:str; data:Dict=field(default_factory=dict)

class MockNotifier:
    COLORS = {"SIGNAL":"\033[92m","TRADE":"\033[94m","INFO":"\033[96m",
              "WARNING":"\033[93m","CRITICAL":"\033[91m","RESET":"\033[0m"}
    EMOJI  = {"SIGNAL":"📈","TRADE":"💼","INFO":"ℹ️","WARNING":"⚠️","CRITICAL":"🚨"}

    def __init__(self):
        self._events:List[NotifyEvent]=[]
        with open(EVENTS_FILE,"w") as f: f.write("")

    async def start(self): self._print("INFO","SYS","🤖 MockNotifier active (no Telegram token)")
    async def stop(self): pass

    async def send_alert(self, level, message, symbol="SYS", dedup_key=None):
        self._emit(level, symbol, message)

    async def send_signal(self, symbol, direction, entry_price, stop_loss,
                          take_profit, confidence, timeframe, strategy_name,
                          signal_score, additional_info=None):
        msg = (f"{'📈' if direction=='BUY' else '📉'} {direction} {symbol} | "
               f"entry={entry_price:.4g} sl={stop_loss:.4g} tp={take_profit:.4g} | "
               f"conf={confidence:.1%} score={signal_score:.0f}/100")
        self._emit("SIGNAL", symbol, msg,
                   {"direction":direction,"entry":entry_price,"score":signal_score})

    async def send_trade_closed(self, symbol, side, entry, exit_p, pnl, pnl_pct, reason):
        icon = "✅" if pnl>0 else "❌"
        self._emit("TRADE", symbol,
                   f"{icon} {side} {symbol} | {entry:.4g}→{exit_p:.4g} | P&L={pnl:+.4f} ({pnl_pct:+.2f}%) | {reason}")

    async def send_pnl_report(self, equity, daily_pnl, win_rate, pf, max_dd, total_trades, day):
        self._emit("INFO","SYS",
            f"📊 Day {day} Report | Equity=${equity:.4f} | WR={win_rate:.1%} | PF={pf:.2f} | DD={max_dd:.2f}%")

    def get_stats(self):
        by = {}
        for e in self._events: by[e.level]=by.get(e.level,0)+1
        return {"mode":"CONSOLE_FALLBACK","total":len(self._events),"by_level":by}

    def _emit(self, level, symbol, message, data=None):
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        ev = NotifyEvent(ts,level,symbol,message,data or {})
        self._events.append(ev)
        try:
            with open(EVENTS_FILE,"a") as f:
                f.write(json.dumps({"ts":ts,"level":level,"symbol":symbol,"message":message})+"\n")
        except Exception: pass
        self._print(level, symbol, message)

    def _print(self, level, symbol, message):
        color = self.COLORS.get(level,""); reset = self.COLORS["RESET"]
        emoji = self.EMOJI.get(level,"•")
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"{color}[{ts}] {emoji} [{level}] [{symbol}] {message[:200]}{reset}")
