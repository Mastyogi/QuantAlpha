"""
CCXT-based exchange client with paper-trading fallback.
When CCXT is not installed, falls back to built-in price simulator.
"""
try:
    import ccxt.async_support as ccxt
    _CCXT_AVAILABLE = True
except ImportError:
    ccxt = None          # type: ignore
    _CCXT_AVAILABLE = False

import asyncio
import random
import uuid
from typing import Dict, List, Optional

from src.utils.retry import async_retry
from src.utils.logger import get_logger
from src.core.exceptions import ExchangeError, ExchangeNotAvailableError
from config.settings import settings

logger = get_logger(__name__)


# ── Built-in price simulator (used when CCXT unavailable) ─────────────────────
_CRYPTO_BASE = {"BTC/USDT": 43500.0, "ETH/USDT": 2318.0, "SOL/USDT": 98.0,
                "BNB/USDT": 310.0, "XRP/USDT": 0.52, "ADA/USDT": 0.45}


class _PriceSimulator:
    def __init__(self):
        self._prices = {k: v for k, v in _CRYPTO_BASE.items()}
        self._rng = random.Random(0)

    def step(self, symbol: str) -> float:
        p = self._prices.get(symbol, 100.0)
        p *= 1 + self._rng.gauss(0, 0.003)
        self._prices[symbol] = max(p, 0.001)
        return self._prices[symbol]

    def fetch_ohlcv(self, symbol: str, tf_hours: int = 1, limit: int = 200) -> List:
        import time, math
        now_ms = int(time.time() * 1000)
        dt = tf_hours * 3600 * 1000
        price = _CRYPTO_BASE.get(symbol, 100.0)
        rng = random.Random(hash(symbol) % 2**32)
        candles = []
        for i in range(limit):
            ts = now_ms - (limit - i) * dt
            o = price
            c = o * (1 + rng.gauss(0, 0.012))
            h = max(o, c) * (1 + abs(rng.gauss(0, 0.004)))
            l = min(o, c) * (1 - abs(rng.gauss(0, 0.004)))
            v = rng.uniform(500, 5000)
            candles.append([ts, o, h, l, c, v])
            price = c
        return candles

    def fetch_ticker(self, symbol: str) -> Dict:
        p = self._prices.get(symbol, _CRYPTO_BASE.get(symbol, 100.0))
        spread = p * 0.0002
        return {"symbol": symbol, "bid": p - spread, "ask": p + spread,
                "last": p, "close": p}

    def place_order(self, symbol: str, side: str, amount: float) -> Dict:
        p = self._prices.get(symbol, 100.0)
        fill = p * (1.001 if side == "buy" else 0.999)
        return {"id": f"sim_{uuid.uuid4().hex[:8]}", "symbol": symbol,
                "side": side, "amount": amount, "price": fill,
                "status": "closed", "filled": amount, "cost": fill * amount}


_SIMULATOR = _PriceSimulator()


# ── ExchangeClient ─────────────────────────────────────────────────────────────
class ExchangeClient:
    """
    CCXT wrapper with built-in paper trading simulation.
    If CCXT is not installed, routes all requests through _PriceSimulator.
    """

    def __init__(self):
        self.exchange_name = settings.exchange_name
        self._exchange = None
        self._initialized = False

    async def initialize(self):
        if not _CCXT_AVAILABLE:
            logger.info("CCXT not installed — using built-in price simulator")
            self._initialized = True
            return

        if settings.trading_mode == "paper" or settings.exchange_name == "paper":
            logger.info("Initializing PAPER TRADING mode")
            try:
                # Use configured exchange even in paper mode
                exchange_name = settings.exchange_name if settings.exchange_name != "paper" else "bitget"
                exchange_class = getattr(ccxt, exchange_name, ccxt.bitget)
                
                self._exchange = exchange_class({
                    "apiKey": settings.exchange_api_key or "paper_key",
                    "secret": settings.exchange_api_secret or "paper_secret",
                    "password": getattr(settings, "exchange_passphrase", None),  # For Bitget
                    "sandbox": False, # Use real market data even for paper trading 
                    "enableRateLimit": True,
                    "options": {"defaultType": "spot"},
                })
                
                if not settings.exchange_api_key or settings.exchange_api_key == "paper_key":
                    if settings.trading_mode == "live":
                        raise ExchangeError("Real API key required for LIVE mode")
            except Exception as e:
                if settings.trading_mode in ["live", "paper"]:
                    raise ExchangeError(f"Critical exchange initialization failure: {e}")
                logger.warning(f"Exchange initialization failed: {e}")
                self._exchange = None
        else:
            # Other modes (mock/sim)
            self._exchange = None

        if self._exchange:
            try:
                await self._exchange.load_markets()
                logger.info(f"Exchange markets loaded: {settings.exchange_name}")
            except Exception as e:
                if settings.trading_mode in ["live", "paper"]:
                    raise ExchangeError(f"Exchange offline - critical failure in {settings.trading_mode} mode: {e}")
                logger.warning(f"Exchange offline (using simulator): {e}")
                self._exchange = None  # fall back to simulator

        self._initialized = True

    @async_retry(max_attempts=3, exceptions=(Exception,))
    async def fetch_ohlcv(self, symbol: str, timeframe: str = "1h",
                          limit: int = 200, since: Optional[int] = None) -> List:
        if not self._initialized:
            await self.initialize()
        if self._exchange is None:
            tf_hours = {"1m": 1/60, "5m": 5/60, "15m": 0.25, "30m": 0.5,
                        "1h": 1, "4h": 4, "1d": 24}.get(timeframe, 1)
            return _SIMULATOR.fetch_ohlcv(symbol, int(tf_hours) or 1, limit)
        try:
            return await self._exchange.fetch_ohlcv(symbol, timeframe, limit=limit, since=since)
        except Exception as e:
            logger.warning(f"fetch_ohlcv failed ({e}), using simulator")
            return _SIMULATOR.fetch_ohlcv(symbol, 1, limit)

    @async_retry(max_attempts=3, exceptions=(Exception,))
    async def fetch_balance(self) -> Dict:
        if not self._initialized:
            await self.initialize()
        if self._exchange is None or settings.trading_mode == "paper":
            return {"USDT": {"total": 10000.0, "free": 10000.0, "used": 0.0}}
        try:
            return await self._exchange.fetch_balance()
        except Exception as e:
            logger.warning(f"fetch_balance failed: {e}")
            return {"USDT": {"total": 10000.0, "free": 10000.0, "used": 0.0}}

    @async_retry(max_attempts=3, exceptions=(Exception,))
    async def fetch_ticker(self, symbol: str) -> Dict:
        if not self._initialized:
            await self.initialize()
        if self._exchange is None:
            return _SIMULATOR.fetch_ticker(symbol)
        try:
            return await self._exchange.fetch_ticker(symbol)
        except Exception as e:
            raise ExchangeError(f"fetch_ticker failed for {symbol}: {e}")

    async def place_order(self, symbol: str, side: str, notional_usd: float,
                          stop_loss: float = 0.0, take_profit: float = 0.0) -> Dict:
        """Paper order — returns simulated fill using REAL market price."""
        if settings.trading_mode == "paper":
            ticker = await self.fetch_ticker(symbol)
            price = ticker["ask"] if side == "buy" else ticker["bid"]
            amount = notional_usd / price if price > 0 else 0
            
            from src.utils.time_utils import utcnow
            logger.info(f"✨ [PAPER ORDER] {side.upper()} {amount:.6f} {symbol} at ${price:,.2f}")
            
            return {
                "id": f"paper_{uuid.uuid4().hex[:8]}",
                "symbol": symbol,
                "side": side,
                "amount": amount,
                "price": price,
                "status": "closed",
                "timestamp": int(utcnow().timestamp() * 1000),
                "type": "market",
                "filled": amount,
                "cost": notional_usd,
                "stop_loss": stop_loss,
                "take_profit": take_profit
            }
        
        if self._exchange is None:
            ticker = _SIMULATOR.fetch_ticker(symbol)
            price = ticker["ask"] if side == "buy" else ticker["bid"]
            amount = notional_usd / price if price > 0 else 0
            return _SIMULATOR.place_order(symbol, side, amount)
            
        return self._simulate_order(symbol, side, notional_usd)

    async def create_market_order(self, symbol: str, side: str,
                                  amount: float, params: dict = None) -> Dict:
        if settings.trading_mode == "paper":
            ticker = await self.fetch_ticker(symbol)
            price = ticker["last"]
            from src.utils.time_utils import utcnow
            
            logger.info(f"✨ [PAPER MARKET ORDER] {side.upper()} {amount:.6f} {symbol} at ${price:,.2f}")
            
            return {
                "id": f"paper_{uuid.uuid4().hex[:8]}",
                "symbol": symbol,
                "side": side,
                "amount": amount,
                "price": price,
                "status": "closed",
                "timestamp": int(utcnow().timestamp() * 1000),
                "type": "market",
                "filled": amount,
                "cost": amount * price
            }
            
        if self._exchange is None:
            return self._simulate_order_sync(symbol, side, amount)
            
        try:
            return await self._exchange.create_market_order(
                symbol, side, amount, params=params or {}
            )
        except Exception as e:
            raise ExchangeError(f"create_market_order failed: {e}")

    def _simulate_order_sync(self, symbol: str, side: str, amount: float) -> Dict:
        from src.utils.time_utils import utcnow
        return {"id": f"paper_{uuid.uuid4().hex[:8]}", "symbol": symbol,
                "side": side, "amount": amount, "price": 0.0,
                "status": "closed", "timestamp": int(utcnow().timestamp() * 1000),
                "type": "market", "filled": amount, "cost": 0.0}

    async def fetch_order(self, order_id: str, symbol: str) -> Dict:
        if settings.trading_mode == "paper" or self._exchange is None:
            return {"id": order_id, "status": "closed"}
        return await self._exchange.fetch_order(order_id, symbol)

    async def ping(self) -> bool:
        try:
            if self._exchange:
                await self._exchange.fetch_time()
            return True
        except Exception:
            return False

    async def close(self):
        if self._exchange:
            try:
                await self._exchange.close()
            except Exception:
                pass
