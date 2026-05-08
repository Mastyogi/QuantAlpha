#!/usr/bin/env python3
"""
QuantAlpha — 24/7 Continuous Self-Improvement System
======================================================
Runs forever. No external AI APIs needed.

Loop (every 5 min):
  1. Fetch fresh market data
  2. Retrain models every 6 hours with latest data
  3. Generate signals via full ML pipeline
  4. Execute paper trades
  5. Monitor positions (SL/TP)
  6. Track win rate & PnL
  7. Auto-adjust thresholds based on performance

All filters ENABLED (production-grade):
  - Regime filter (TRENDING / RANGING / VOLATILE / DEAD)
  - Consensus check (2/3 models must agree)
  - Confluence scoring (0-100)
  - ATR-based SL/TP
  - Risk management (max 2% per trade)
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

# ── Bootstrap path ────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# Load .env before any imports that need settings
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from config.settings import settings
from src.data.exchange_client import ExchangeClient
from src.data.data_fetcher import DataFetcher
from src.signals.signal_engine import FineTunedSignalEngine
from src.execution.order_manager import OrderManager
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ── Force console output (override JSON logger for CI system) ─────────────────
import logging
_console = logging.StreamHandler(sys.stdout)
_console.setLevel(logging.DEBUG)
_console.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s", "%H:%M:%S"))
logging.getLogger().addHandler(_console)
logging.getLogger().setLevel(logging.INFO)

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
SCAN_INTERVAL_SEC   = 300   # 5 minutes between scans
RETRAIN_INTERVAL_H  = 6     # retrain every 6 hours
DATA_CANDLES        = 1000  # candles to fetch for training (~41 days of 1h)
SCAN_CANDLES        = 200   # candles for signal generation
INITIAL_EQUITY      = 10_000.0
MIN_WIN_RATE        = 0.55  # below this → tighten threshold
TARGET_WIN_RATE     = 0.72  # above this → can loosen threshold
CONFLUENCE_START    = 60    # starting confluence threshold (tightens/loosens auto)
CONFLUENCE_MIN      = 45
CONFLUENCE_MAX      = 85
REPORT_FILE         = ROOT / "ci_report.json"


# ─────────────────────────────────────────────────────────────────────────────
# Main system
# ─────────────────────────────────────────────────────────────────────────────
class ContinuousImprovementSystem:
    """24/7 self-training, self-validating trading system."""

    def __init__(self):
        self.exchange   = ExchangeClient()
        self.fetcher    = DataFetcher(self.exchange)
        self.engine     = FineTunedSignalEngine(
            model_dir="models",
            confluence_threshold=CONFLUENCE_START,
            max_risk_pct=2.0,
            account_equity=INITIAL_EQUITY,
            use_pattern_library=False,   # skip DB pattern library for standalone run
        )
        self.order_mgr  = OrderManager(self.exchange, initial_equity=INITIAL_EQUITY)

        # State
        self.equity          = INITIAL_EQUITY
        self.peak_equity     = INITIAL_EQUITY
        self.iteration       = 0
        self.last_retrain    = None          # datetime | None
        self.perf_history: List[Dict] = []  # rolling performance snapshots
        self.model_trained   = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def run(self):
        """Entry point — runs forever."""
        await self.exchange.initialize()
        self._banner("24/7 Continuous Improvement System STARTED")

        # Phase 1 — initial training
        await self._train_all(force=True)
        self.model_trained = True
        self.last_retrain  = datetime.now(timezone.utc)

        # Phase 2 — continuous loop
        while True:
            self.iteration += 1
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            logger.info(f"\n{'─'*70}")
            logger.info(f"🔄  Iteration #{self.iteration}  |  {ts}")
            logger.info(f"{'─'*70}")

            try:
                # Retrain if due
                if self._retrain_due():
                    await self._train_all(force=True)
                    self.last_retrain = datetime.now(timezone.utc)

                # Signal scan + paper trade
                await self._scan_and_trade()

                # Monitor open positions
                await self._monitor_positions()

                # Evaluate & adjust
                self._evaluate()
                self._auto_adjust()

                # Persist report
                self._save_report()

            except Exception as exc:
                logger.error(f"❌  Iteration error: {exc}", exc_info=True)

            next_in = SCAN_INTERVAL_SEC
            logger.info(f"\n⏳  Next scan in {next_in//60} min …")
            await asyncio.sleep(next_in)

    # ── Training ──────────────────────────────────────────────────────────────

    async def _train_all(self, force: bool = False):
        logger.info("\n📚  Training models …")
        for symbol in settings.trading_pairs:
            await self._train_symbol(symbol, force=force)

    async def _train_symbol(self, symbol: str, force: bool = False):
        try:
            df = await self.fetcher.get_dataframe(symbol, "1h", limit=DATA_CANDLES)
            if df is None or len(df) < 200:
                logger.warning(f"   ⚠️  {symbol}: only {len(df) if df is not None else 0} candles — skip")
                return

            logger.info(f"   🔄  {symbol}: {len(df)} candles  ({df.index[0].date()} → {df.index[-1].date()})")
            metrics = self.engine.train_model(
                symbol=symbol,
                df=df,
                asset_class="crypto" if "/" in symbol else "forex",
                force_retrain=force,
            )
            if "error" not in metrics:
                logger.info(
                    f"   ✅  {symbol}  precision={metrics.get('precision',0):.1%}"
                    f"  recall={metrics.get('recall',0):.1%}"
                    f"  auc={metrics.get('auc',0):.3f}"
                    f"  n={metrics.get('n_samples',0)}"
                )
            else:
                logger.error(f"   ❌  {symbol}: {metrics['error']}")
        except Exception as exc:
            logger.error(f"   ❌  {symbol} training error: {exc}")

    def _retrain_due(self) -> bool:
        if self.last_retrain is None:
            return True
        hours = (datetime.now(timezone.utc) - self.last_retrain).total_seconds() / 3600
        if hours >= RETRAIN_INTERVAL_H:
            logger.info(f"⏰  {hours:.1f}h since last retrain — retraining now")
            return True
        return False

    # ── Signal scan ───────────────────────────────────────────────────────────

    async def _scan_and_trade(self):
        logger.info("\n📡  Scanning markets …")
        approved = 0

        for symbol in settings.trading_pairs:
            try:
                df_1h = await self.fetcher.get_dataframe(symbol, "1h", limit=SCAN_CANDLES)
                df_4h = await self.fetcher.get_dataframe(symbol, "4h", limit=100)

                if df_1h is None or len(df_1h) < 100:
                    logger.debug(f"   {symbol}: insufficient data")
                    continue

                signal = await self.engine.analyze(
                    symbol=symbol,
                    df_1h=df_1h,
                    df_4h=df_4h,
                )

                price = df_1h["close"].iloc[-1]
                status = "✅ APPROVED" if signal.approved else f"⛔ {signal.rejection_reason[:40]}"
                logger.info(
                    f"   {symbol}  ${price:,.2f}  "
                    f"dir={signal.direction}  "
                    f"conf={signal.ai_confidence:.0%}  "
                    f"score={signal.confluence_score:.0f}  "
                    f"{status}"
                )

                if signal.approved:
                    approved += 1
                    await self._execute_paper_trade(signal)

            except Exception as exc:
                logger.debug(f"   {symbol} scan error: {exc}")

        logger.info(f"   📊  Approved signals this cycle: {approved}")

    async def _execute_paper_trade(self, signal):
        """Execute a paper trade for an approved signal."""
        try:
            setup = signal.trade_setup
            # Use 1% of equity per trade (conservative)
            size_usd = max(50.0, self.equity * 0.01)

            result = await self.order_mgr.place_trade(
                symbol=signal.symbol,
                side=signal.direction.lower(),
                size_usd=size_usd,
                entry_price=setup.entry_price,
                stop_loss=setup.stop_loss,
                take_profit=setup.take_profit_2,
                confidence=signal.ai_confidence,
                strategy_name="CI_System",
                use_kelly_sizing=False,
            )
            logger.info(
                f"   📝  Trade opened: {signal.symbol} {signal.direction}"
                f"  entry={setup.entry_price:.4g}"
                f"  sl={setup.stop_loss:.4g}"
                f"  tp={setup.take_profit_2:.4g}"
                f"  size=${size_usd:.0f}"
                f"  id={result.get('id','?')}"
            )
        except Exception as exc:
            logger.warning(f"   ⚠️  Trade execution skipped (DB offline or error): {exc}")

    # ── Position monitoring ───────────────────────────────────────────────────

    async def _monitor_positions(self):
        positions = self.order_mgr.paper_trader.open_positions
        if not positions:
            return

        logger.info(f"\n📋  Monitoring {len(positions)} open position(s) …")

        # Fetch current prices
        prices: Dict[str, float] = {}
        for pos in positions.values():
            sym = pos["symbol"]
            if sym not in prices:
                try:
                    ticker = await self.exchange.fetch_ticker(sym)
                    prices[sym] = float(ticker.get("last", 0.0))
                except Exception:
                    pass

        # Check SL/TP
        closed = await self.order_mgr.check_and_close_positions(prices)
        for trade in closed:
            pnl = trade.get("pnl", 0.0)
            self.equity += pnl
            if self.equity > self.peak_equity:
                self.peak_equity = self.equity
            icon = "✅" if pnl > 0 else "❌"
            logger.info(
                f"   {icon}  {trade.get('symbol','?')} closed"
                f"  reason={trade.get('exit_reason','?')}"
                f"  pnl=${pnl:+.2f}"
                f"  equity=${self.equity:,.2f}"
            )

    # ── Performance evaluation ────────────────────────────────────────────────

    def _evaluate(self):
        history = self.order_mgr.paper_trader.trade_history
        if len(history) < 5:
            logger.info(f"\n📊  Trades so far: {len(history)} (need 5+ for stats)")
            return

        recent = history[-20:]
        wins   = [t for t in recent if t.get("pnl", 0) > 0]
        losses = [t for t in recent if t.get("pnl", 0) <= 0]
        wr     = len(wins) / len(recent)
        total_pnl = sum(t.get("pnl", 0) for t in recent)
        avg_win   = float(np.mean([t["pnl"] for t in wins]))   if wins   else 0.0
        avg_loss  = float(np.mean([t["pnl"] for t in losses])) if losses else 0.0
        pf = abs(avg_win * len(wins) / (avg_loss * len(losses))) if losses and avg_loss != 0 else 0.0

        logger.info(f"\n📊  Performance (last {len(recent)} trades):")
        logger.info(f"   Win Rate:      {wr:.1%}  ({len(wins)}W / {len(losses)}L)")
        logger.info(f"   Total PnL:     ${total_pnl:+.2f}")
        logger.info(f"   Avg Win:       ${avg_win:+.2f}")
        logger.info(f"   Avg Loss:      ${avg_loss:+.2f}")
        logger.info(f"   Profit Factor: {pf:.2f}")
        logger.info(f"   Equity:        ${self.equity:,.2f}  (peak ${self.peak_equity:,.2f})")
        logger.info(f"   Confluence:    {self.engine.confluence_threshold:.0f}/100")

        self.perf_history.append({
            "ts":           datetime.now(timezone.utc).isoformat(),
            "trades":       len(recent),
            "win_rate":     round(wr, 4),
            "total_pnl":    round(total_pnl, 4),
            "profit_factor":round(pf, 4),
            "equity":       round(self.equity, 2),
            "threshold":    self.engine.confluence_threshold,
        })

    # ── Auto-adjustment ───────────────────────────────────────────────────────

    def _auto_adjust(self):
        if len(self.perf_history) < 3:
            return

        recent_wr = float(np.mean([p["win_rate"] for p in self.perf_history[-5:]]))
        cur = self.engine.confluence_threshold

        if recent_wr < MIN_WIN_RATE:
            new = min(CONFLUENCE_MAX, cur + 5)
            logger.info(f"⚙️   Win rate {recent_wr:.1%} < {MIN_WIN_RATE:.0%} → tighten threshold {cur:.0f}→{new:.0f}")
            self.engine.confluence_threshold = new
            self.engine._confluence.min_score = new

        elif recent_wr > TARGET_WIN_RATE:
            new = max(CONFLUENCE_MIN, cur - 3)
            logger.info(f"⚙️   Win rate {recent_wr:.1%} > {TARGET_WIN_RATE:.0%} → loosen threshold {cur:.0f}→{new:.0f}")
            self.engine.confluence_threshold = new
            self.engine._confluence.min_score = new

        else:
            logger.info(f"⚙️   Threshold {cur:.0f} optimal (win rate {recent_wr:.1%})")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _save_report(self):
        """Persist performance history to JSON for external monitoring."""
        try:
            stats = self.order_mgr.paper_trader.get_stats()
            report = {
                "updated_at":   datetime.now(timezone.utc).isoformat(),
                "iteration":    self.iteration,
                "equity":       round(self.equity, 2),
                "peak_equity":  round(self.peak_equity, 2),
                "threshold":    self.engine.confluence_threshold,
                "paper_stats":  stats,
                "history":      self.perf_history[-50:],   # last 50 snapshots
            }
            REPORT_FILE.write_text(json.dumps(report, indent=2))
        except Exception:
            pass

    @staticmethod
    def _banner(msg: str):
        line = "=" * 70
        print(f"\n{line}\n  {msg}\n{line}", flush=True)
        logger.info(f"{msg}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
async def main():
    system = ContinuousImprovementSystem()
    await system.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑  Stopped by user. Final report saved to ci_report.json")
    except Exception as exc:
        print(f"\n\n❌  Fatal: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
