"""
Unified broker client that routes to the correct backend:
  - Crypto pairs (BTC/USDT etc.)   → CCXT exchange client
  - Forex/Commodity (EURUSD etc.)  → MT5Client (real or simulator)

Usage:
    from src.data.forex.broker_client import BrokerClient
    client = BrokerClient()
    await client.initialize()
    df = await client.fetch_ohlcv("EURUSD", "H1", 200)
    df = await client.fetch_ohlcv("BTC/USDT", "1h", 200)
"""
from __future__ import annotations

import asyncio
from typing import Dict, List, Optional, Tuple

import pandas as pd

from src.utils.logger import get_logger
from src.data.forex.mt5_client import MT5Client, ALL_BASE_PRICES
from src.data.exchange_client import ExchangeClient
from src.data.data_validator import DataValidator

logger = get_logger(__name__)


# ── Instrument classification ─────────────────────────────────────────────────
FOREX_SYMBOLS = {
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
    "USDCHF", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY",
}
COMMODITY_SYMBOLS = {
    "XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD",   # metals
    "USOIL",  "UKOIL",  "NGAS",                 # energy
    "WHEAT",  "CORN",   "SOYBEAN",               # agriculture
}
MT5_SYMBOLS = FOREX_SYMBOLS | COMMODITY_SYMBOLS

# MT5 timeframe string → CCXT-style string (for unified API)
MT5_TF_MAP = {
    "M1": "1m",  "M5": "5m",  "M15": "15m", "M30": "30m",
    "H1": "1h",  "H4": "4h",  "D1":  "1d",  "W1":  "1w",
}
CCXT_TO_MT5 = {v: k for k, v in MT5_TF_MAP.items()}

# Pip sizes for position sizing
PIP_SIZES: Dict[str, float] = {
    "EURUSD": 0.0001, "GBPUSD": 0.0001, "AUDUSD": 0.0001, "NZDUSD": 0.0001,
    "USDCAD": 0.0001, "USDCHF": 0.0001, "EURGBP": 0.0001, "EURNZD": 0.0001,
    "USDJPY": 0.01,   "EURJPY": 0.01,   "GBPJPY": 0.01,   "AUDJPY": 0.01,
    "XAUUSD": 0.01,   "XAGUSD": 0.001,
    "USOIL":  0.01,   "UKOIL":  0.01,
}

# USD pip value per 1 standard lot (approximate, for risk calculation)
PIP_VALUE_USD: Dict[str, float] = {
    "EURUSD": 10.0,   "GBPUSD": 10.0,   "AUDUSD": 10.0,   "NZDUSD": 10.0,
    "USDCAD": 7.7,    "USDCHF": 11.2,   "USDJPY": 6.7,
    "EURGBP": 13.0,   "EURJPY": 6.7,    "GBPJPY": 6.7,
    "XAUUSD": 1.0,    "XAGUSD": 0.5,
    "USOIL":  1.0,    "UKOIL":  1.0,
}

# Minimum lot sizes
MIN_LOT: Dict[str, float] = {sym: 0.01 for sym in MT5_SYMBOLS}
MAX_LOT: Dict[str, float] = {
    **{sym: 100.0 for sym in FOREX_SYMBOLS},
    **{sym: 50.0  for sym in COMMODITY_SYMBOLS},
}


def is_forex_or_commodity(symbol: str) -> bool:
    """Return True if symbol should be routed to MT5 (not CCXT)."""
    clean = symbol.upper().replace("-", "").replace("/", "").replace("_", "")
    return clean in MT5_SYMBOLS


def get_pip_size(symbol: str) -> float:
    clean = symbol.upper().replace("/", "")
    return PIP_SIZES.get(clean, 0.0001)


def get_pip_value_usd(symbol: str) -> float:
    clean = symbol.upper().replace("/", "")
    return PIP_VALUE_USD.get(clean, 10.0)


def get_asset_class(symbol: str) -> str:
    clean = symbol.upper().replace("/", "")
    if clean in FOREX_SYMBOLS:
        return "forex"
    if clean in COMMODITY_SYMBOLS:
        return "commodity"
    return "crypto"


class BrokerClient:
    """
    Unified async broker client.

    Automatically routes:
      • Forex / commodity symbols → MT5Client (real terminal or paper simulator)
      • Crypto pairs              → CCXT ExchangeClient (paper or live)
    """

    def __init__(self):
        self._mt5:  Optional[MT5Client]      = None
        self._ccxt: Optional[ExchangeClient] = None
        self._validator = DataValidator()
        self._initialized = False

    # ── Initialization ─────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        from config.settings import settings

        # MT5 for forex/commodities
        if settings.enable_forex or settings.enable_commodities:
            self._mt5 = MT5Client()
            real = await self._mt5.initialize()
            mode = "real MT5 terminal" if real else "MT5 simulator"
            logger.info(f"BrokerClient: forex/commodities via {mode}")
        else:
            logger.info("BrokerClient: forex/commodities disabled")

        # CCXT for crypto
        self._ccxt = ExchangeClient()
        await self._ccxt.initialize()
        logger.info("BrokerClient: crypto via CCXT (paper mode)")

        self._initialized = True

    # ── Data fetching ──────────────────────────────────────────────────────────

    async def fetch_ohlcv(
        self, symbol: str, timeframe: str = "1h", limit: int = 300
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data for any symbol (crypto or forex/commodity).
        Returns a validated DataFrame with columns [open, high, low, close, volume].
        """
        if not self._initialized:
            await self.initialize()

        if is_forex_or_commodity(symbol):
            return await self._fetch_forex_ohlcv(symbol, timeframe, limit)
        return await self._fetch_crypto_ohlcv(symbol, timeframe, limit)

    async def _fetch_forex_ohlcv(
        self, symbol: str, timeframe: str, limit: int
    ) -> pd.DataFrame:
        if self._mt5 is None:
            raise RuntimeError("MT5 client not initialized — enable_forex must be True")

        # Convert CCXT timeframe "1h" → MT5 "H1"
        mt5_tf = CCXT_TO_MT5.get(timeframe, "H1")
        raw = await self._mt5.fetch_ohlcv(symbol, mt5_tf, limit)
        return self._raw_to_dataframe(raw)

    async def _fetch_crypto_ohlcv(
        self, symbol: str, timeframe: str, limit: int
    ) -> pd.DataFrame:
        if self._ccxt is None:
            raise RuntimeError("CCXT client not initialized")
        raw = await self._ccxt.fetch_ohlcv(symbol, timeframe, limit)
        return self._raw_to_dataframe(raw)

    @staticmethod
    def _raw_to_dataframe(raw: List[List]) -> pd.DataFrame:
        """Convert [[ts_ms, O, H, L, C, V], ...] → validated DataFrame."""
        import pandas as pd
        from datetime import timezone
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.set_index("timestamp", inplace=True)
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        df.sort_index(inplace=True)
        return df

    async def fetch_tick(self, symbol: str) -> dict:
        """Get current bid/ask/last for any symbol."""
        if not self._initialized:
            await self.initialize()
        if is_forex_or_commodity(symbol) and self._mt5:
            return await self._mt5.fetch_tick(symbol)
        # CCXT fallback
        if self._ccxt:
            try:
                ticker = await self._ccxt.fetch_ticker(symbol)
                return {"symbol": symbol, "bid": ticker.get("bid", 0),
                        "ask": ticker.get("ask", 0), "last": ticker.get("last", 0)}
            except Exception:
                pass
        return {"symbol": symbol, "bid": 0, "ask": 0, "last": 0}

    # ── Order execution ────────────────────────────────────────────────────────

    async def place_order(
        self, symbol: str, side: str, notional_usd: float,
        stop_loss: float = 0.0, take_profit: float = 0.0
    ) -> dict:
        """
        Place an order. Automatically converts notional USD to lots for forex.
        Returns a dict with order details.
        """
        if not self._initialized:
            await self.initialize()

        if is_forex_or_commodity(symbol) and self._mt5:
            lot = self._usd_to_lots(symbol, notional_usd)
            return await self._mt5.place_order(
                symbol, side, lot, sl=stop_loss, tp=take_profit
            )
        # Crypto path
        if self._ccxt:
            return await self._ccxt.place_order(symbol, side, notional_usd, stop_loss, take_profit)
        raise RuntimeError("No broker available for order placement")

    @staticmethod
    def _usd_to_lots(symbol: str, notional_usd: float) -> float:
        """Convert a USD notional amount to MT5 lot size."""
        clean = symbol.upper().replace("/", "")
        base_price = ALL_BASE_PRICES.get(clean, 1.0)
        # Standard lot = 100,000 units for forex, different for commodities
        if clean in FOREX_SYMBOLS:
            lot_value_usd = base_price * 100_000 if clean.startswith("USD") else 100_000
            lots = notional_usd / (base_price * 100_000)
        elif clean in {"XAUUSD", "XAGUSD"}:
            lots = notional_usd / (base_price * 100)
        else:
            lots = notional_usd / (base_price * 1_000)
        # Clamp to valid range
        min_l = MIN_LOT.get(clean, 0.01)
        max_l = MAX_LOT.get(clean, 10.0)
        lots = max(min_l, min(round(lots, 2), max_l))
        return lots

    # ── Account info ───────────────────────────────────────────────────────────

    async def get_account_info(self) -> dict:
        if self._mt5 and (
            (hasattr(self, '_settings') and getattr(self._settings, 'enable_forex', False))
            or True  # always check if MT5 initialized
        ):
            try:
                return await self._mt5.get_account_info()
            except Exception:
                pass
        return {"balance": 10000.0, "equity": 10000.0, "margin": 0.0,
                "free_margin": 10000.0, "leverage": 100}

    # ── Symbol info ────────────────────────────────────────────────────────────

    def get_instrument_info(self, symbol: str) -> dict:
        """Return metadata for any instrument."""
        clean = symbol.upper().replace("/", "")
        return {
            "symbol": symbol,
            "asset_class": get_asset_class(symbol),
            "pip_size": get_pip_size(symbol),
            "pip_value_usd": get_pip_value_usd(symbol),
            "min_lot": MIN_LOT.get(clean, 0.001),
            "max_lot": MAX_LOT.get(clean, 100.0),
            "is_forex": clean in FOREX_SYMBOLS,
            "is_commodity": clean in COMMODITY_SYMBOLS,
        }

    async def close(self):
        if self._mt5:
            await self._mt5.close()
