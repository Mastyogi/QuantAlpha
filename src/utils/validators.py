from typing import Any, Optional
import pandas as pd


def validate_ohlcv(df: pd.DataFrame) -> bool:
    """Validate OHLCV DataFrame has required columns and no critical NaNs."""
    required = ["open", "high", "low", "close", "volume"]
    if not all(col in df.columns for col in required):
        return False
    if df.empty:
        return False
    # Check high >= low
    if not (df["high"] >= df["low"]).all():
        return False
    # No NaN in core price columns
    if df[required].isnull().any().any():
        return False
    return True


def validate_symbol(symbol: str) -> bool:
    """Validate trading pair format (e.g., BTC/USDT)."""
    if not symbol or "/" not in symbol:
        return False
    parts = symbol.split("/")
    return len(parts) == 2 and all(len(p) >= 2 for p in parts)


def validate_price(price: float) -> bool:
    """Validate price is positive finite number."""
    return isinstance(price, (int, float)) and price > 0 and price == price  # NaN check


def validate_trade_params(
    symbol: str,
    side: str,
    size_usd: float,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
) -> tuple[bool, str]:
    """Full trade parameter validation. Returns (valid, error_message)."""
    if not validate_symbol(symbol):
        return False, f"Invalid symbol: {symbol}"
    if side not in ("buy", "sell"):
        return False, f"Invalid side: {side}. Must be 'buy' or 'sell'"
    if size_usd <= 0:
        return False, f"size_usd must be positive, got {size_usd}"
    if not all(validate_price(p) for p in [entry_price, stop_loss, take_profit]):
        return False, "entry_price, stop_loss, take_profit must all be positive"

    if side == "buy":
        if stop_loss >= entry_price:
            return False, f"BUY stop_loss ({stop_loss}) must be < entry ({entry_price})"
        if take_profit <= entry_price:
            return False, f"BUY take_profit ({take_profit}) must be > entry ({entry_price})"
    else:
        if stop_loss <= entry_price:
            return False, f"SELL stop_loss ({stop_loss}) must be > entry ({entry_price})"
        if take_profit >= entry_price:
            return False, f"SELL take_profit ({take_profit}) must be < entry ({entry_price})"

    return True, "OK"
