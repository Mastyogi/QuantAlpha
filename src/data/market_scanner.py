"""
Market Scanner
===============
Concurrently scans all symbols (crypto + forex + commodities).
Priority queue — high-volatility / high-ADX pairs scanned first.
Rate-limit aware — never hammers the exchange.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Set

import numpy as np
import pandas as pd

from src.utils.logger import get_logger
from src.indicators.technical import TechnicalIndicators

logger = get_logger(__name__)


@dataclass
class ScanResult:
    symbol:         str
    priority_score: float       # Higher = scan more often
    adx:            float = 0.0
    atr_pct:        float = 0.0
    volume_ratio:   float = 1.0
    last_price:     float = 0.0
    trend_aligned:  bool = False
    scan_time_ms:   float = 0.0
    error:          Optional[str] = None

    @property
    def is_scannable(self) -> bool:
        return self.error is None and self.adx > 15


@dataclass
class ScannerConfig:
    symbols:          List[str]         # All symbols to scan
    concurrency:      int  = 5          # Max concurrent fetches
    scan_interval_s:  int  = 60         # Base interval between full sweeps
    fast_interval_s:  int  = 15         # Interval for high-priority symbols
    min_adx:          float = 18.0      # Skip symbols below this ADX
    min_volume_ratio: float = 0.8       # Skip low-volume periods


class MarketScanner:
    """
    Manages concurrent scanning of all instruments.
    Calls on_signal_cb when a high-confluence signal is found.
    """

    def __init__(
        self,
        config: ScannerConfig,
        data_fetcher,           # DataFetcher instance
        signal_engine,          # FineTunedSignalEngine instance
        on_signal_cb: Optional[Callable] = None,
    ):
        self.config   = config
        self.fetcher  = data_fetcher
        self.engine   = signal_engine
        self.on_signal_cb = on_signal_cb

        self._sem     = asyncio.Semaphore(config.concurrency)
        self._running = False
        self._scan_results: Dict[str, ScanResult] = {}
        self._priority_queue: List[str] = list(config.symbols)
        self._scan_count = 0
        self._signals_found = 0
        self._errors: Dict[str, int] = {}

    # ── Main loop ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        self._running = True
        logger.info(f"MarketScanner started: {len(self.config.symbols)} symbols, "
                    f"concurrency={self.config.concurrency}")
        # Initial priority sort
        await self._initial_priority_scan()
        # Main scan loop
        while self._running:
            await self._scan_cycle()
            await asyncio.sleep(self.config.scan_interval_s)

    async def stop(self) -> None:
        self._running = False
        logger.info(f"MarketScanner stopped. Scans: {self._scan_count}, "
                    f"Signals: {self._signals_found}")

    # ── Scan cycle ────────────────────────────────────────────────────────────

    async def _initial_priority_scan(self) -> None:
        """Quick scan to rank symbols by activity before main loop."""
        logger.info("Initial priority scan...")
        tasks = [self._quick_priority_check(s) for s in self.config.symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid = [r for r in results if isinstance(r, ScanResult) and r.is_scannable]
        # Sort by ADX × volume_ratio
        valid.sort(key=lambda x: x.priority_score, reverse=True)
        self._priority_queue = [r.symbol for r in valid]
        # Add any symbols that failed to back of queue
        scanned = {r.symbol for r in valid}
        for s in self.config.symbols:
            if s not in scanned:
                self._priority_queue.append(s)
        logger.info(f"Priority order: {self._priority_queue[:5]}...")

    async def _scan_cycle(self) -> None:
        """Full scan cycle — all symbols in priority order."""
        self._scan_count += 1
        t0 = asyncio.get_event_loop().time()

        # Scan in batches to respect concurrency limit
        batch_size = self.config.concurrency * 2
        for i in range(0, len(self._priority_queue), batch_size):
            batch = self._priority_queue[i:i + batch_size]
            tasks = [self._scan_symbol(s) for s in batch]
            await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = asyncio.get_event_loop().time() - t0
        logger.info(
            f"Scan #{self._scan_count} complete: {len(self._priority_queue)} symbols, "
            f"{elapsed:.1f}s, {self._signals_found} signals total"
        )

        # Re-sort priority queue based on fresh ADX data
        self._resort_priority()

    async def _scan_symbol(self, symbol: str) -> Optional[object]:
        """Full signal analysis for one symbol."""
        async with self._sem:
            t0 = asyncio.get_event_loop().time()
            try:
                # Fetch primary + higher TF
                df_1h = await self._fetch_df(symbol, "1h", 200)
                if df_1h is None or len(df_1h) < 100:
                    return None

                df_4h = await self._fetch_df(symbol, "4h", 100)

                # Quick pre-filter: skip low-activity symbols
                df_1h = TechnicalIndicators.add_all_indicators(df_1h)
                adx = df_1h.get("adx", pd.Series([0])).iloc[-1]
                vol_ratio = df_1h.get("volume_ratio", pd.Series([1])).iloc[-1]

                scan_ms = (asyncio.get_event_loop().time() - t0) * 1000
                self._scan_results[symbol] = ScanResult(
                    symbol=symbol,
                    priority_score=adx * vol_ratio,
                    adx=float(adx),
                    atr_pct=float(df_1h.get("atr_pct", pd.Series([0])).iloc[-1]),
                    volume_ratio=float(vol_ratio),
                    last_price=float(df_1h["close"].iloc[-1]),
                    scan_time_ms=round(scan_ms, 1),
                )

                if adx < self.config.min_adx:
                    logger.debug(f"{symbol}: ADX={adx:.1f} < {self.config.min_adx} — skip")
                    return None

                if vol_ratio < self.config.min_volume_ratio:
                    logger.debug(f"{symbol}: vol_ratio={vol_ratio:.2f} — skip")
                    return None

                # ── Run signal engine ─────────────────────────────────────────
                signal = await self.engine.analyze(
                    symbol=symbol,
                    df_1h=df_1h,
                    df_4h=df_4h,
                )

                if signal.approved:
                    self._signals_found += 1
                    logger.info(
                        f"🎯 SIGNAL [{symbol}] {signal.direction} "
                        f"score={signal.confluence_score:.0f} "
                        f"conf={signal.ai_confidence:.0%}"
                    )
                    if self.on_signal_cb:
                        await self.on_signal_cb(signal)

                    # Boost priority for symbol with active signals
                    self._scan_results[symbol].priority_score *= 1.5

                return signal

            except Exception as e:
                self._errors[symbol] = self._errors.get(symbol, 0) + 1
                logger.debug(f"Scan error {symbol}: {e}")
                return None

    async def _quick_priority_check(self, symbol: str) -> ScanResult:
        """Fast ADX + volume check to rank symbol priority."""
        try:
            df = await self._fetch_df(symbol, "1h", 50)
            if df is None or len(df) < 30:
                return ScanResult(symbol=symbol, priority_score=0, error="insufficient_data")
            df = TechnicalIndicators.add_all_indicators(df)
            adx = float(df.get("adx", pd.Series([0])).iloc[-1])
            vol = float(df.get("volume_ratio", pd.Series([1])).iloc[-1])
            return ScanResult(
                symbol=symbol, priority_score=adx * vol,
                adx=adx, volume_ratio=vol,
                last_price=float(df["close"].iloc[-1]),
            )
        except Exception as e:
            return ScanResult(symbol=symbol, priority_score=0, error=str(e))

    async def _fetch_df(
        self, symbol: str, timeframe: str, limit: int
    ) -> Optional[pd.DataFrame]:
        """Fetch OHLCV with fallback to simulator."""
        try:
            return await self.fetcher.get_dataframe(symbol, timeframe, limit=limit)
        except Exception:
            return self._simulate_df(symbol, limit)

    @staticmethod
    def _simulate_df(symbol: str, n: int) -> pd.DataFrame:
        """Fallback simulator for testing without exchange."""
        base_prices = {
            "BTC/USDT": 43000, "ETH/USDT": 2300, "SOL/USDT": 95,
            "EURUSD": 1.084, "XAUUSD": 1950,
        }
        base = base_prices.get(symbol, 100)
        rng  = np.random.default_rng(abs(hash(symbol)) % 2**32)
        dates = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
        prices = base * np.exp(np.cumsum(rng.normal(0, 0.003, n)))
        df = pd.DataFrame({
            "open": prices * 0.999, "high": prices * 1.003,
            "low": prices * 0.997,  "close": prices,
            "volume": 500 + rng.uniform(0, 1, n) * 500,
        }, index=dates)
        df["high"] = df[["high","open","close"]].max(axis=1)
        df["low"]  = df[["low","open","close"]].min(axis=1)
        return df

    def _resort_priority(self) -> None:
        """Re-sort symbols by current priority score."""
        scored = [
            (s, self._scan_results.get(s, ScanResult(s, 0)).priority_score)
            for s in self.config.symbols
        ]
        scored.sort(key=lambda x: -x[1])
        self._priority_queue = [s for s, _ in scored]

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> Dict:
        return {
            "symbols_tracked": len(self.config.symbols),
            "scan_count": self._scan_count,
            "signals_found": self._signals_found,
            "errors": sum(self._errors.values()),
            "top_symbols": [
                {"symbol": s, **vars(self._scan_results[s])}
                for s in self._priority_queue[:5]
                if s in self._scan_results
            ],
        }
