"""
MT5 Executor — Live trading bridge for MetaTrader 5 (FxPro Direct).

Connects to FxPro server using env vars MT5_LOGIN, MT5_PASSWORD, MT5_SERVER.
Implements place_order, close_order, modify_order, get_positions, get_account_info.
Falls back gracefully when MetaTrader5 package is not installed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from src.utils.logger import get_logger

logger = get_logger(__name__)

#  Try importing MetaTrader5 
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None  # type: ignore
    MT5_AVAILABLE = False
    logger.warning("MetaTrader5 package not installed — MT5Executor in stub mode")


@dataclass
class MT5Position:
    """Represents an open MT5 position."""
    ticket: int
    symbol: str
    direction: str          # "buy" | "sell"
    volume: float
    open_price: float
    current_price: float
    stop_loss: float
    take_profit: float
    profit: float
    swap: float
    comment: str
    open_time: int


@dataclass
class MT5AccountInfo:
    """MT5 account snapshot."""
    login: int
    server: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    profit: float
    currency: str
    leverage: int
    trade_allowed: bool


@dataclass
class MT5OrderResult:
    """Result of an MT5 order operation."""
    success: bool
    ticket: int = 0
    order_id: str = ""
    retcode: int = 0
    comment: str = ""
    price: float = 0.0
    volume: float = 0.0
    symbol: str = ""
    error: str = ""


class MT5Executor:
    """
    Live trading executor for MetaTrader 5 via FxPro Direct.

    Architecture:
    - Each user has their own MT5 credentials stored in the User model.
    - The executor is instantiated per-user with their credentials.
    - For the bot owner / admin, credentials come from env vars.
    - Supports both demo and real account modes.

    Usage:
        executor = MT5Executor(login=12345, password="pass", server="FxPro-Demo")
        await executor.connect()
        result = await executor.place_order("EURUSD", "buy", 0.01, sl=1.0800, tp=1.1000)
    """

    # MT5 order type constants (fallback if mt5 not installed)
    _ORDER_TYPE_BUY  = 0
    _ORDER_TYPE_SELL = 1
    _TRADE_ACTION_DEAL   = 1
    _TRADE_ACTION_SLTP   = 6
    _TRADE_ACTION_REMOVE = 8
    _ORDER_FILLING_IOC   = 1
    _ORDER_FILLING_FOK   = 0

    def __init__(
        self,
        login: Optional[int] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
        path: Optional[str] = None,
        magic: int = 20240101,
    ):
        import os
        self.login    = login    or int(os.getenv("MT5_LOGIN", "0"))
        self.password = password or os.getenv("MT5_PASSWORD", "")
        self.server   = server   or os.getenv("MT5_SERVER", "FxPro-Demo")
        self.path     = path     or os.getenv("MT5_PATH", "")
        self.magic    = magic
        self._connected = False

    #  Connection 

    def connect(self) -> bool:
        """
        Initialise and log in to MT5.
        Returns True on success, False on failure.
        """
        if not MT5_AVAILABLE:
            logger.error("MetaTrader5 package not installed — cannot connect")
            return False

        if self._connected:
            return True

        # Initialise MT5 terminal
        init_kwargs: Dict[str, Any] = {}
        if self.path:
            init_kwargs["path"] = self.path

        if not mt5.initialize(**init_kwargs):
            err = mt5.last_error()
            logger.error(f"MT5 initialize() failed: {err}")
            return False

        # Login
        if not mt5.login(self.login, password=self.password, server=self.server):
            err = mt5.last_error()
            logger.error(f"MT5 login failed for account {self.login} on {self.server}: {err}")
            mt5.shutdown()
            return False

        self._connected = True
        info = mt5.account_info()
        logger.info(
            f"MT5 connected: account={info.login} server={info.server} "
            f"balance={info.balance:.2f} {info.currency} leverage=1:{info.leverage}"
        )
        return True

    def disconnect(self) -> None:
        """Shutdown MT5 connection."""
        if MT5_AVAILABLE and self._connected:
            mt5.shutdown()
            self._connected = False
            logger.info("MT5 disconnected")

    def ensure_connected(self) -> bool:
        """Reconnect if connection was lost."""
        if not self._connected:
            return self.connect()
        # Ping by fetching account info
        if MT5_AVAILABLE:
            info = mt5.account_info()
            if info is None:
                logger.warning("MT5 connection lost — reconnecting")
                self._connected = False
                return self.connect()
        return True

    #  Account Info 

    def get_account_info(self) -> Optional[MT5AccountInfo]:
        """Return current account snapshot."""
        if not self.ensure_connected():
            return None
        if not MT5_AVAILABLE:
            return None

        info = mt5.account_info()
        if info is None:
            logger.error(f"get_account_info failed: {mt5.last_error()}")
            return None

        return MT5AccountInfo(
            login=info.login,
            server=info.server,
            balance=info.balance,
            equity=info.equity,
            margin=info.margin,
            free_margin=info.margin_free,
            margin_level=info.margin_level,
            profit=info.profit,
            currency=info.currency,
            leverage=info.leverage,
            trade_allowed=info.trade_allowed,
        )

    #  Positions 

    def get_positions(self, symbol: Optional[str] = None) -> List[MT5Position]:
        """Return list of open positions, optionally filtered by symbol."""
        if not self.ensure_connected():
            return []
        if not MT5_AVAILABLE:
            return []

        raw = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if raw is None:
            return []

        positions = []
        for p in raw:
            positions.append(MT5Position(
                ticket=p.ticket,
                symbol=p.symbol,
                direction="buy" if p.type == 0 else "sell",
                volume=p.volume,
                open_price=p.price_open,
                current_price=p.price_current,
                stop_loss=p.sl,
                take_profit=p.tp,
                profit=p.profit,
                swap=p.swap,
                comment=p.comment,
                open_time=p.time,
            ))
        return positions

    #  Place Order 

    def place_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        price: float = 0.0,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
        comment: str = "QuantAlpha",
        order_type: str = "market",
    ) -> MT5OrderResult:
        """
        Place a market or limit order.

        Args:
            symbol:      MT5 symbol (e.g. "EURUSD")
            side:        "buy" or "sell"
            volume:      Lot size (e.g. 0.01)
            price:       Limit price (0 = market)
            stop_loss:   SL price (0 = none)
            take_profit: TP price (0 = none)
            comment:     Order comment
            order_type:  "market" | "limit"

        Returns:
            MT5OrderResult
        """
        if not self.ensure_connected():
            return MT5OrderResult(success=False, error="Not connected to MT5")
        if not MT5_AVAILABLE:
            return MT5OrderResult(success=False, error="MetaTrader5 not installed")

        # Resolve order type
        if side.lower() == "buy":
            mt5_type = mt5.ORDER_TYPE_BUY if order_type == "market" else mt5.ORDER_TYPE_BUY_LIMIT
        else:
            mt5_type = mt5.ORDER_TYPE_SELL if order_type == "market" else mt5.ORDER_TYPE_SELL_LIMIT

        # Get current price for market orders
        if order_type == "market" or price == 0.0:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return MT5OrderResult(success=False, error=f"Cannot get tick for {symbol}")
            price = tick.ask if side.lower() == "buy" else tick.bid

        # Get symbol info for filling mode
        sym_info = mt5.symbol_info(symbol)
        if sym_info is None:
            return MT5OrderResult(success=False, error=f"Symbol {symbol} not found")

        filling_type = mt5.ORDER_FILLING_IOC
        if sym_info.filling_mode == 1:
            filling_type = mt5.ORDER_FILLING_FOK

        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       symbol,
            "volume":       float(volume),
            "type":         mt5_type,
            "price":        float(price),
            "sl":           float(stop_loss),
            "tp":           float(take_profit),
            "deviation":    20,
            "magic":        self.magic,
            "comment":      comment[:31],   # MT5 limit
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": filling_type,
        }

        result = mt5.order_send(request)

        if result is None:
            err = mt5.last_error()
            logger.error(f"MT5 order_send returned None: {err}")
            return MT5OrderResult(success=False, error=str(err))

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(
                f"MT5 order failed: retcode={result.retcode} comment={result.comment} "
                f"symbol={symbol} side={side} volume={volume}"
            )
            return MT5OrderResult(
                success=False,
                retcode=result.retcode,
                comment=result.comment,
                error=f"retcode={result.retcode}: {result.comment}",
            )

        logger.info(
            f"MT5 order placed: ticket={result.order} symbol={symbol} "
            f"side={side} volume={volume} price={result.price:.5f}"
        )
        return MT5OrderResult(
            success=True,
            ticket=result.order,
            order_id=str(result.order),
            retcode=result.retcode,
            comment=result.comment,
            price=result.price,
            volume=volume,
            symbol=symbol,
        )

    #  Close Order 

    def close_order(
        self,
        ticket: int,
        volume: Optional[float] = None,
        comment: str = "QuantAlpha close",
    ) -> MT5OrderResult:
        """
        Close an open position by ticket.

        Args:
            ticket:  Position ticket number
            volume:  Partial close volume (None = full close)
            comment: Order comment

        Returns:
            MT5OrderResult
        """
        if not self.ensure_connected():
            return MT5OrderResult(success=False, error="Not connected to MT5")
        if not MT5_AVAILABLE:
            return MT5OrderResult(success=False, error="MetaTrader5 not installed")

        # Get position details
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return MT5OrderResult(success=False, error=f"Position {ticket} not found")

        pos = positions[0]
        close_volume = volume if volume else pos.volume

        # Opposite side to close
        close_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None:
            return MT5OrderResult(success=False, error=f"Cannot get tick for {pos.symbol}")

        close_price = tick.bid if pos.type == 0 else tick.ask

        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       pos.symbol,
            "volume":       float(close_volume),
            "type":         close_type,
            "position":     ticket,
            "price":        float(close_price),
            "deviation":    20,
            "magic":        self.magic,
            "comment":      comment[:31],
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            err = mt5.last_error() if result is None else result.comment
            logger.error(f"MT5 close_order failed: ticket={ticket} error={err}")
            return MT5OrderResult(
                success=False,
                retcode=result.retcode if result else 0,
                error=str(err),
            )

        logger.info(f"MT5 position closed: ticket={ticket} price={result.price:.5f}")
        return MT5OrderResult(
            success=True,
            ticket=result.order,
            order_id=str(result.order),
            retcode=result.retcode,
            price=result.price,
            volume=close_volume,
            symbol=pos.symbol,
        )

    #  Modify Order 

    def modify_order(
        self,
        ticket: int,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
    ) -> MT5OrderResult:
        """
        Modify SL/TP of an open position.

        Args:
            ticket:      Position ticket
            stop_loss:   New SL price (0 = unchanged)
            take_profit: New TP price (0 = unchanged)

        Returns:
            MT5OrderResult
        """
        if not self.ensure_connected():
            return MT5OrderResult(success=False, error="Not connected to MT5")
        if not MT5_AVAILABLE:
            return MT5OrderResult(success=False, error="MetaTrader5 not installed")

        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return MT5OrderResult(success=False, error=f"Position {ticket} not found")

        pos = positions[0]
        new_sl = stop_loss if stop_loss != 0.0 else pos.sl
        new_tp = take_profit if take_profit != 0.0 else pos.tp

        request = {
            "action":   mt5.TRADE_ACTION_SLTP,
            "symbol":   pos.symbol,
            "position": ticket,
            "sl":       float(new_sl),
            "tp":       float(new_tp),
        }

        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            err = mt5.last_error() if result is None else result.comment
            logger.error(f"MT5 modify_order failed: ticket={ticket} error={err}")
            return MT5OrderResult(
                success=False,
                retcode=result.retcode if result else 0,
                error=str(err),
            )

        logger.info(f"MT5 position modified: ticket={ticket} sl={new_sl} tp={new_tp}")
        return MT5OrderResult(
            success=True,
            ticket=ticket,
            order_id=str(ticket),
            retcode=result.retcode,
            symbol=pos.symbol,
        )

    #  Symbol Info 

    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """Return symbol specification dict."""
        if not self.ensure_connected() or not MT5_AVAILABLE:
            return None
        info = mt5.symbol_info(symbol)
        if info is None:
            return None
        return {
            "symbol":       info.name,
            "digits":       info.digits,
            "point":        info.point,
            "trade_contract_size": info.trade_contract_size,
            "volume_min":   info.volume_min,
            "volume_max":   info.volume_max,
            "volume_step":  info.volume_step,
            "spread":       info.spread,
        }

    def __repr__(self) -> str:
        status = "connected" if self._connected else "disconnected"
        return f"<MT5Executor login={self.login} server={self.server} [{status}]>"
