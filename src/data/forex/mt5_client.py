"""
MetaTrader 5 client wrapper.

Real MT5:   Requires MetaTrader5 Python package + terminal installed on Windows.
Simulator:  Full OHLCV + order simulation when MT5 is unavailable (paper trading,
            Linux CI, unit tests).  The simulator generates realistic tick data
            so the rest of the pipeline works identically.
"""
import asyncio
import random
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from src.utils.logger import get_logger
from src.core.exceptions import ExchangeError, ExchangeNotAvailableError

logger = get_logger(__name__)

# ── Instrument definitions ─────────────────────────────────────────────────────
FOREX_BASE_PRICES: Dict[str, float] = {
    "EURUSD": 1.0850, "GBPUSD": 1.2650, "USDJPY": 149.50,
    "AUDUSD": 0.6520, "USDCAD": 1.3580, "USDCHF": 0.8950,
    "NZDUSD": 0.5980, "EURGBP": 0.8580,
}
COMMODITY_BASE_PRICES: Dict[str, float] = {
    "XAUUSD": 2030.50, "XAGUSD": 22.85,
    "USOIL":   78.40,  "UKOIL":  83.20,
}
ALL_BASE_PRICES = {**FOREX_BASE_PRICES, **COMMODITY_BASE_PRICES}

# Typical daily volatility as fraction of price
DAILY_VOL: Dict[str, float] = {
    "EURUSD": 0.0050, "GBPUSD": 0.0065, "USDJPY": 0.0055,
    "AUDUSD": 0.0060, "USDCAD": 0.0045, "XAUUSD": 0.0080,
    "XAGUSD": 0.0120, "USOIL":  0.0200, "UKOIL":  0.0180,
}


class MT5Simulator:
    """
    Stateful OHLCV + order book simulator for forex/commodity instruments.
    Produces realistic candle data based on GBM price process.
    """

    def __init__(self):
        self._prices: Dict[str, float] = {k: v for k, v in ALL_BASE_PRICES.items()}
        self._orders: Dict[str, dict] = {}
        self._order_counter = 1
        self._equity = 10_000.0
        self._balance = 10_000.0
        self._rng = random.Random(42)

    def _step_price(self, symbol: str, dt_seconds: float = 3600.0) -> float:
        """Advance price by one time step using GBM."""
        sigma = DAILY_VOL.get(symbol, 0.005)
        dt_frac = dt_seconds / 86400.0
        drift = 0.0
        shock = self._rng.gauss(0, 1)
        prev = self._prices[symbol]
        new_price = prev * (1 + drift * dt_frac + sigma * (dt_frac ** 0.5) * shock)
        self._prices[symbol] = max(new_price, prev * 0.80)  # floor at -20%
        return self._prices[symbol]

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe_minutes: int = 60,
        count: int = 200,
    ) -> List[List]:
        """Return list of [timestamp_ms, open, high, low, close, volume]."""
        if symbol not in self._prices:
            raise ExchangeNotAvailableError(f"Unknown symbol: {symbol}")

        dt_seconds = timeframe_minutes * 60
        candles = []
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        start_ms = now_ms - count * dt_seconds * 1000

        # Reset price to base for reproducibility
        price = ALL_BASE_PRICES.get(symbol, 1.0)
        sigma = DAILY_VOL.get(symbol, 0.005)
        dt_frac = dt_seconds / 86400.0
        rng = random.Random(hash(symbol) % 2**32)

        for i in range(count):
            ts_ms = start_ms + i * dt_seconds * 1000
            open_ = price
            # Simulate intra-candle walk
            high = open_
            low = open_
            close = open_
            for _ in range(4):
                close = close * (1 + rng.gauss(0, sigma * (dt_frac ** 0.5)))
                high = max(high, close)
                low = min(low, close)
            high *= (1 + abs(rng.gauss(0, sigma * 0.3 * dt_frac**0.5)))
            low  *= (1 - abs(rng.gauss(0, sigma * 0.3 * dt_frac**0.5)))
            high = max(high, open_, close)
            low  = min(low,  open_, close)
            volume = rng.uniform(500, 5000)
            candles.append([ts_ms, open_, high, low, close, volume])
            price = close

        return candles

    def fetch_tick(self, symbol: str) -> dict:
        price = self._prices.get(symbol, ALL_BASE_PRICES.get(symbol, 1.0))
        spread = price * 0.0001
        return {
            "symbol": symbol, "bid": price - spread / 2,
            "ask": price + spread / 2, "last": price,
            "time": datetime.now(timezone.utc),
        }

    def place_order(
        self,
        symbol: str,
        order_type: str,   # "buy" | "sell"
        volume: float,
        price: float = 0.0,
        sl: float = 0.0,
        tp: float = 0.0,
        comment: str = "",
    ) -> dict:
        tick = self.fetch_tick(symbol)
        fill_price = tick["ask"] if order_type == "buy" else tick["bid"]
        ticket = self._order_counter
        self._order_counter += 1
        self._orders[str(ticket)] = {
            "ticket": ticket, "symbol": symbol, "type": order_type,
            "volume": volume, "open_price": fill_price,
            "sl": sl, "tp": tp, "comment": comment,
            "open_time": datetime.now(timezone.utc),
            "profit": 0.0,
        }
        logger.info(f"[MT5-SIM] {order_type.upper()} {symbol} vol={volume} @ {fill_price:.5f}")
        return {"retcode": 10009, "order": ticket, "price": fill_price,
                "volume": volume, "comment": "Simulated fill"}

    def close_order(self, ticket: int) -> dict:
        key = str(ticket)
        if key not in self._orders:
            return {"retcode": 10004, "comment": "Order not found"}
        order = self._orders.pop(key)
        tick = self.fetch_tick(order["symbol"])
        close_price = tick["bid"] if order["type"] == "buy" else tick["ask"]
        if order["type"] == "buy":
            profit = (close_price - order["open_price"]) * order["volume"] * 100000
        else:
            profit = (order["open_price"] - close_price) * order["volume"] * 100000
        self._balance += profit
        logger.info(f"[MT5-SIM] CLOSE ticket={ticket} profit={profit:.2f}")
        return {"retcode": 10009, "profit": profit, "close_price": close_price}

    def get_account_info(self) -> dict:
        floating = sum(o.get("profit", 0) for o in self._orders.values())
        return {
            "balance": self._balance, "equity": self._balance + floating,
            "margin": len(self._orders) * 100.0,
            "free_margin": self._balance + floating - len(self._orders) * 100.0,
            "leverage": 100,
        }


class MT5Client:
    """
    Async wrapper around MT5 (real or simulated).

    Usage:
        client = MT5Client()
        await client.initialize()
        df = await client.fetch_ohlcv("EURUSD", "H1", limit=200)
    """

    # MT5 timeframe string → minutes
    TIMEFRAME_MINUTES = {
        "M1": 1, "M5": 5, "M15": 15, "M30": 30,
        "H1": 60, "H4": 240, "D1": 1440, "W1": 10080,
    }

    def __init__(self):
        self._sim = MT5Simulator()
        self._mt5 = None            # real MT5 module if available
        self._use_real = False
        self._initialized = False

    async def initialize(self) -> bool:
        """Try to connect to real MT5; fall back to simulator."""
        from config.settings import settings
        if settings.broker_mode == "mt5" and settings.mt5_login:
            try:
                import MetaTrader5 as mt5
                path = settings.mt5_path or None
                ok = mt5.initialize(path=path) if path else mt5.initialize()
                if ok:
                    auth = mt5.login(
                        settings.mt5_login,
                        password=settings.mt5_password,
                        server=settings.mt5_server,
                    )
                    if auth:
                        self._mt5 = mt5
                        self._use_real = True
                        info = mt5.account_info()
                        logger.info(f"MT5 connected: account={info.login} balance={info.balance}")
                        self._initialized = True
                        return True
                    else:
                        logger.warning(f"MT5 login failed: {mt5.last_error()}")
                        mt5.shutdown()
            except ImportError:
                logger.info("MetaTrader5 package not installed — using simulator")
            except Exception as e:
                logger.warning(f"MT5 init failed: {e} — using simulator")

        logger.info("MT5Client: using built-in price simulator (paper mode)")
        self._initialized = True
        return False

    async def fetch_ohlcv(
        self, symbol: str, timeframe: str = "H1", limit: int = 200
    ) -> List[List]:
        """Return [[timestamp_ms, O, H, L, C, V], ...] — same format as CCXT."""
        if not self._initialized:
            await self.initialize()

        tf_minutes = self.TIMEFRAME_MINUTES.get(timeframe.upper(), 60)

        if self._use_real and self._mt5:
            return await asyncio.get_event_loop().run_in_executor(
                None, self._fetch_real_ohlcv, symbol, timeframe, limit
            )
        return self._sim.fetch_ohlcv(symbol, tf_minutes, limit)

    def _fetch_real_ohlcv(self, symbol: str, timeframe: str, limit: int) -> List[List]:
        import MetaTrader5 as mt5
        tf_map = {
            "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }
        tf = tf_map.get(timeframe.upper(), mt5.TIMEFRAME_H1)
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, limit)
        if rates is None:
            raise ExchangeError(f"MT5 fetch_ohlcv failed for {symbol}: {mt5.last_error()}")
        result = []
        for r in rates:
            ts_ms = int(r["time"]) * 1000
            result.append([ts_ms, r["open"], r["high"], r["low"], r["close"], r["tick_volume"]])
        return result

    async def fetch_tick(self, symbol: str) -> dict:
        if self._use_real and self._mt5:
            return await asyncio.get_event_loop().run_in_executor(
                None, self._fetch_real_tick, symbol
            )
        return self._sim.fetch_tick(symbol)

    def _fetch_real_tick(self, symbol: str) -> dict:
        tick = self._mt5.symbol_info_tick(symbol)
        if not tick:
            raise ExchangeError(f"MT5 tick fetch failed for {symbol}")
        return {"symbol": symbol, "bid": tick.bid, "ask": tick.ask,
                "last": tick.last, "time": datetime.fromtimestamp(tick.time, tz=timezone.utc)}

    async def place_order(
        self, symbol: str, order_type: str, volume: float,
        sl: float = 0.0, tp: float = 0.0, comment: str = "bot"
    ) -> dict:
        if self._use_real and self._mt5:
            return await asyncio.get_event_loop().run_in_executor(
                None, self._place_real_order, symbol, order_type, volume, sl, tp, comment
            )
        return self._sim.place_order(symbol, order_type, volume, sl=sl, tp=tp, comment=comment)

    def _place_real_order(self, symbol, order_type, volume, sl, tp, comment):
        import MetaTrader5 as mt5
        tick = mt5.symbol_info_tick(symbol)
        price = tick.ask if order_type == "buy" else tick.bid
        otype = mt5.ORDER_TYPE_BUY if order_type == "buy" else mt5.ORDER_TYPE_SELL
        req = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol,
            "volume": volume, "type": otype, "price": price,
            "sl": sl, "tp": tp, "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(req)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            raise ExchangeError(f"MT5 order failed: {result.comment}")
        return {"retcode": result.retcode, "order": result.order,
                "price": result.price, "volume": result.volume}

    async def get_account_info(self) -> dict:
        if self._use_real and self._mt5:
            info = await asyncio.get_event_loop().run_in_executor(
                None, self._mt5.account_info
            )
            return {
                "balance": info.balance, "equity": info.equity,
                "margin": info.margin, "free_margin": info.margin_free,
                "leverage": info.leverage,
            }
        return self._sim.get_account_info()

    async def close(self):
        if self._use_real and self._mt5:
            self._mt5.shutdown()
