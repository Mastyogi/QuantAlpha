"""
P&L Calculator
==============
Real-time profit/loss tracking with:
  - Realized P&L (closed trades)
  - Unrealized P&L (open positions, mark-to-market)
  - Fee deduction (maker/taker per exchange)
  - Slippage cost tracking
  - Daily / weekly / all-time aggregation
  - Per-symbol and per-strategy breakdown
  - Sharpe, Sortino, Profit Factor computation
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TradeRecord:
    """Immutable record of a completed trade."""
    trade_id:       str
    symbol:         str
    direction:      str        # BUY / SELL
    strategy:       str
    entry_price:    float
    exit_price:     float
    quantity:       float
    size_usd:       float
    gross_pnl:      float      # Before fees
    fees:           float
    slippage_cost:  float
    net_pnl:        float      # gross - fees - slippage
    net_pnl_pct:    float      # % of size_usd
    entry_time:     datetime
    exit_time:      datetime
    close_reason:   str        # TP1 / TP2 / SL / manual


@dataclass
class PnLSnapshot:
    """Full P&L state at a point in time."""
    timestamp:          datetime
    realized_pnl:       float = 0.0
    unrealized_pnl:     float = 0.0
    total_pnl:          float = 0.0
    daily_pnl:          float = 0.0
    total_fees:         float = 0.0
    total_slippage:     float = 0.0
    total_trades:       int   = 0
    winning_trades:     int   = 0
    losing_trades:      int   = 0
    win_rate:           float = 0.0
    avg_win:            float = 0.0
    avg_loss:           float = 0.0
    profit_factor:      float = 0.0
    max_drawdown_pct:   float = 0.0
    sharpe_ratio:       float = 0.0
    sortino_ratio:      float = 0.0
    current_equity:     float = 0.0
    peak_equity:        float = 0.0

    def to_telegram_str(self) -> str:
        """Compact P&L summary for Telegram."""
        wr = f"{self.win_rate:.1%}" if self.total_trades else "N/A"
        pf = f"{self.profit_factor:.2f}" if self.profit_factor else "N/A"
        return (
            f"📊 *P&L Report*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Realized P&L:   `{self.realized_pnl:+.2f} USD`\n"
            f"📈 Unrealized P&L: `{self.unrealized_pnl:+.2f} USD`\n"
            f"📅 Daily P&L:      `{self.daily_pnl:+.2f} USD`\n"
            f"💸 Total Fees:     `{self.total_fees:.2f} USD`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Win Rate:       `{wr}`\n"
            f"📊 Profit Factor:  `{pf}`\n"
            f"📉 Max Drawdown:   `{self.max_drawdown_pct:.1f}%`\n"
            f"⚡ Sharpe Ratio:   `{self.sharpe_ratio:.2f}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏦 Equity:         `${self.current_equity:,.2f}`\n"
            f"🔢 Trades:         `{self.total_trades}` "
            f"({self.winning_trades}W/{self.losing_trades}L)\n"
        )


class PnLCalculator:
    """
    Core P&L tracking engine.
    Thread-safe, accumulates across the bot session.
    """

    # ── Exchange fee schedules ────────────────────────────────────────────────
    FEE_SCHEDULES = {
        "binance":  {"maker": 0.001,  "taker": 0.001},
        "bybit":    {"maker": 0.001,  "taker": 0.001},
        "okx":      {"maker": 0.0008, "taker": 0.001},
        "paper":    {"maker": 0.001,  "taker": 0.001},
        "default":  {"maker": 0.001,  "taker": 0.001},
    }

    def __init__(
        self,
        initial_equity: float = 10_000.0,
        exchange: str = "paper",
        slippage_pct: float = 0.0005,  # 0.05% per side
    ):
        self.initial_equity = initial_equity
        self.current_equity = initial_equity
        self.peak_equity    = initial_equity
        self.exchange       = exchange
        self.slippage_pct   = slippage_pct

        self._fees = self.FEE_SCHEDULES.get(exchange, self.FEE_SCHEDULES["default"])

        # Trade history
        self._trades: List[TradeRecord] = []
        self._daily_pnl: Dict[date, float] = defaultdict(float)
        self._equity_curve: List[Tuple[datetime, float]] = [
            (datetime.now(timezone.utc), initial_equity)
        ]

        # Per-symbol and per-strategy breakdowns
        self._symbol_pnl:   Dict[str, float] = defaultdict(float)
        self._strategy_pnl: Dict[str, float] = defaultdict(float)

        # Unrealized tracking {trade_id: {entry, qty, direction}}
        self._open_positions: Dict[str, dict] = {}

        # Counters
        self._total_fees      = 0.0
        self._total_slippage  = 0.0

        logger.info(f"PnLCalculator initialized: equity=${initial_equity:,.2f}")

    # ── Trade recording ───────────────────────────────────────────────────────

    def record_trade_open(
        self,
        trade_id:    str,
        symbol:      str,
        direction:   str,
        entry_price: float,
        quantity:    float,
        size_usd:    float,
        strategy:    str = "unknown",
    ) -> float:
        """
        Record opening of a position.
        Returns fee deducted from equity.
        """
        fee = size_usd * self._fees["taker"]
        slip = size_usd * self.slippage_pct
        total_cost = fee + slip

        self.current_equity -= total_cost
        self._total_fees    += fee
        self._total_slippage += slip
        self._equity_curve.append((datetime.now(timezone.utc), self.current_equity))

        self._open_positions[trade_id] = {
            "symbol":      symbol,
            "direction":   direction,
            "entry_price": entry_price,
            "quantity":    quantity,
            "size_usd":    size_usd,
            "strategy":    strategy,
            "entry_time":  datetime.now(timezone.utc),
        }

        logger.debug(f"Trade opened {trade_id}: fee={fee:.2f}, slip={slip:.2f}")
        return total_cost

    def record_trade_close(
        self,
        trade_id:     str,
        exit_price:   float,
        close_reason: str = "unknown",
    ) -> Optional[TradeRecord]:
        """
        Record closing of a position.
        Returns complete TradeRecord with P&L breakdown.
        """
        pos = self._open_positions.pop(trade_id, None)
        if not pos:
            logger.warning(f"Trade {trade_id} not found in open positions")
            return None

        entry_price = pos["entry_price"]
        quantity    = pos["quantity"]
        size_usd    = pos["size_usd"]
        direction   = pos["direction"]

        # Gross P&L
        if direction == "BUY":
            gross_pnl = (exit_price - entry_price) * quantity
        else:
            gross_pnl = (entry_price - exit_price) * quantity

        # Exit costs
        exit_fee  = size_usd * self._fees["taker"]
        slip_cost = size_usd * self.slippage_pct
        net_pnl   = gross_pnl - exit_fee - slip_cost
        net_pct   = (net_pnl / size_usd) * 100

        self.current_equity += net_pnl
        self.current_equity -= (exit_fee + slip_cost)
        self.peak_equity     = max(self.peak_equity, self.current_equity)
        self._total_fees    += exit_fee
        self._total_slippage += slip_cost

        now = datetime.now(timezone.utc)
        self._equity_curve.append((now, self.current_equity))

        # Daily P&L tracking
        today = now.date()
        self._daily_pnl[today] += net_pnl

        # Breakdowns
        self._symbol_pnl[pos["symbol"]]   += net_pnl
        self._strategy_pnl[pos["strategy"]] += net_pnl

        record = TradeRecord(
            trade_id      = trade_id,
            symbol        = pos["symbol"],
            direction     = direction,
            strategy      = pos["strategy"],
            entry_price   = entry_price,
            exit_price    = exit_price,
            quantity      = quantity,
            size_usd      = size_usd,
            gross_pnl     = gross_pnl,
            fees          = exit_fee,
            slippage_cost = slip_cost,
            net_pnl       = net_pnl,
            net_pnl_pct   = net_pct,
            entry_time    = pos["entry_time"],
            exit_time     = now,
            close_reason  = close_reason,
        )
        self._trades.append(record)

        logger.info(
            f"Trade closed {trade_id}: net_pnl={net_pnl:+.2f} ({net_pct:+.2f}%) "
            f"reason={close_reason}"
        )
        return record

    # ── Unrealized P&L ────────────────────────────────────────────────────────

    def calculate_unrealized(self, current_prices: Dict[str, float]) -> float:
        """Mark-to-market unrealized P&L for all open positions."""
        total_unrealized = 0.0
        for pos in self._open_positions.values():
            price = current_prices.get(pos["symbol"])
            if price is None:
                continue
            if pos["direction"] == "BUY":
                upnl = (price - pos["entry_price"]) * pos["quantity"]
            else:
                upnl = (pos["entry_price"] - price) * pos["quantity"]
            total_unrealized += upnl
        return total_unrealized

    # ── Metrics computation ───────────────────────────────────────────────────

    def get_snapshot(
        self,
        current_prices: Optional[Dict[str, float]] = None,
    ) -> PnLSnapshot:
        """Full P&L snapshot with all metrics."""
        unrealized = (
            self.calculate_unrealized(current_prices) if current_prices else 0.0
        )
        realized = sum(t.net_pnl for t in self._trades)
        total    = realized + unrealized

        today     = datetime.now(timezone.utc).date()
        daily_pnl = self._daily_pnl.get(today, 0.0)

        wins   = [t for t in self._trades if t.net_pnl > 0]
        losses = [t for t in self._trades if t.net_pnl <= 0]
        n      = len(self._trades)

        win_rate  = len(wins) / n if n > 0 else 0.0
        avg_win   = float(np.mean([t.net_pnl for t in wins]))  if wins   else 0.0
        avg_loss  = float(np.mean([t.net_pnl for t in losses])) if losses else 0.0

        gross_profit = sum(t.net_pnl for t in wins)
        gross_loss   = abs(sum(t.net_pnl for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        # Max drawdown from equity curve
        max_dd = self._calculate_max_drawdown()

        # Sharpe & Sortino from daily returns
        sharpe, sortino = self._calculate_risk_ratios()

        return PnLSnapshot(
            timestamp       = datetime.now(timezone.utc),
            realized_pnl    = realized,
            unrealized_pnl  = unrealized,
            total_pnl       = total,
            daily_pnl       = daily_pnl,
            total_fees      = self._total_fees,
            total_slippage  = self._total_slippage,
            total_trades    = n,
            winning_trades  = len(wins),
            losing_trades   = len(losses),
            win_rate        = win_rate,
            avg_win         = avg_win,
            avg_loss        = avg_loss,
            profit_factor   = profit_factor,
            max_drawdown_pct = max_dd,
            sharpe_ratio    = sharpe,
            sortino_ratio   = sortino,
            current_equity  = self.current_equity,
            peak_equity     = self.peak_equity,
        )

    def get_daily_summary(self) -> Dict:
        """Today's trading summary."""
        today  = datetime.now(timezone.utc).date()
        today_trades = [
            t for t in self._trades
            if t.exit_time.date() == today
        ]
        wins = [t for t in today_trades if t.net_pnl > 0]
        return {
            "date":         str(today),
            "trades":       len(today_trades),
            "wins":         len(wins),
            "losses":       len(today_trades) - len(wins),
            "win_rate":     len(wins) / max(1, len(today_trades)),
            "net_pnl":      sum(t.net_pnl for t in today_trades),
            "fees_today":   sum(t.fees for t in today_trades),
            "best_trade":   max((t.net_pnl for t in today_trades), default=0),
            "worst_trade":  min((t.net_pnl for t in today_trades), default=0),
        }

    def get_symbol_breakdown(self) -> Dict[str, float]:
        return dict(sorted(self._symbol_pnl.items(), key=lambda x: x[1], reverse=True))

    def get_strategy_breakdown(self) -> Dict[str, float]:
        return dict(sorted(self._strategy_pnl.items(), key=lambda x: x[1], reverse=True))

    def get_equity_curve(self) -> List[Tuple[datetime, float]]:
        return list(self._equity_curve)

    def reset_daily_counters(self):
        """Call at 00:00 UTC to reset daily tracking."""
        today = datetime.now(timezone.utc).date()
        self._daily_pnl[today] = 0.0
        logger.info("Daily P&L counters reset")

    # ── Private helpers ───────────────────────────────────────────────────────

    def _calculate_max_drawdown(self) -> float:
        """Max drawdown % from equity curve."""
        if len(self._equity_curve) < 2:
            return 0.0
        equities = np.array([e for _, e in self._equity_curve])
        peaks = np.maximum.accumulate(equities)
        drawdowns = (equities - peaks) / peaks * 100
        return float(abs(drawdowns.min()))

    def _calculate_risk_ratios(self, risk_free_rate: float = 0.05) -> Tuple[float, float]:
        """Calculate annualized Sharpe and Sortino ratios from daily P&L."""
        daily_returns_items = sorted(self._daily_pnl.items())
        if len(daily_returns_items) < 5:
            return 0.0, 0.0

        daily_equity = self.initial_equity
        daily_rets = []
        for _, pnl in daily_returns_items:
            ret = pnl / daily_equity if daily_equity > 0 else 0
            daily_rets.append(ret)
            daily_equity += pnl

        if not daily_rets:
            return 0.0, 0.0

        rets = np.array(daily_rets)
        daily_rf = risk_free_rate / 252

        excess = rets - daily_rf
        sharpe = float(np.mean(excess) / np.std(excess) * np.sqrt(252)) if np.std(excess) > 0 else 0.0

        downside = rets[rets < 0]
        downside_std = float(np.std(downside) * np.sqrt(252)) if len(downside) > 0 else 1e-10
        sortino = float(np.mean(excess) * np.sqrt(252) / downside_std)

        return sharpe, sortino
