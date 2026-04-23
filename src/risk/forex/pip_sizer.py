"""
Forex / Commodity pip-based position sizer.

For forex the risk is:
    lots = (account_risk_usd) / (stop_pips * pip_value_per_lot_usd)

where:
    account_risk_usd = equity * risk_pct / 100
    stop_pips        = |entry - stop_loss| / pip_size
    pip_value_per_lot_usd  = standard pip value for 1 lot in USD
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.utils.logger import get_logger
from src.data.forex.broker_client import (
    get_pip_size, get_pip_value_usd,
    MIN_LOT, MAX_LOT, is_forex_or_commodity
)

logger = get_logger(__name__)


@dataclass
class ForexSizeResult:
    symbol:         str
    lots:           float     # MT5 lot size
    notional_usd:   float     # approximate USD value
    stop_pips:      float     # distance to SL in pips
    risk_usd:       float     # exact USD at risk
    risk_pct:       float     # % of equity at risk
    pip_size:       float
    pip_value_usd:  float     # per lot


class ForexPositionSizer:
    """
    Calculates lot size for forex and commodity instruments
    using the classic pip-risk formula.
    """

    def __init__(self, max_risk_pct: float = 1.0, max_lot: float = 0.5):
        self.max_risk_pct = max_risk_pct  # max % of equity to risk per trade
        self.max_lot = max_lot            # hard lot cap

    def calculate_lot_size(
        self,
        symbol: str,
        equity: float,
        entry_price: float,
        stop_loss_price: float,
        risk_pct: Optional[float] = None,
    ) -> ForexSizeResult:
        """
        Calculate optimal lot size for a forex/commodity trade.

        Args:
            symbol:           e.g. "EURUSD", "XAUUSD"
            equity:           account equity in USD
            entry_price:      trade entry price
            stop_loss_price:  stop-loss price
            risk_pct:         % of equity to risk (default: self.max_risk_pct)
        """
        risk_pct = risk_pct or self.max_risk_pct

        pip_size = get_pip_size(symbol)
        pip_val  = get_pip_value_usd(symbol)
        clean    = symbol.upper().replace("/", "")

        # Distance to stop in pips
        stop_distance = abs(entry_price - stop_loss_price)
        stop_pips     = stop_distance / pip_size if pip_size > 0 else 1.0
        if stop_pips < 0.1:
            stop_pips = 0.1  # avoid div-by-zero / absurd sizes

        # Account risk in USD
        account_risk_usd = equity * (risk_pct / 100.0)

        # Lot size formula
        # 1 lot → stop_pips × pip_val_usd = total risk per lot
        risk_per_lot = stop_pips * pip_val
        if risk_per_lot <= 0:
            lots = MIN_LOT.get(clean, 0.01)
        else:
            lots = account_risk_usd / risk_per_lot

        # Apply limits
        min_l = MIN_LOT.get(clean, 0.01)
        max_l = min(MAX_LOT.get(clean, 100.0), self.max_lot)
        lots = max(min_l, min(round(lots, 2), max_l))

        # Approximate notional USD
        if clean.startswith("USD"):
            notional_usd = lots * 100_000
        else:
            notional_usd = lots * 100_000 * entry_price

        actual_risk_usd = stop_pips * pip_val * lots
        actual_risk_pct = (actual_risk_usd / equity * 100) if equity > 0 else 0

        result = ForexSizeResult(
            symbol=symbol,
            lots=lots,
            notional_usd=round(notional_usd, 2),
            stop_pips=round(stop_pips, 1),
            risk_usd=round(actual_risk_usd, 2),
            risk_pct=round(actual_risk_pct, 3),
            pip_size=pip_size,
            pip_value_usd=pip_val,
        )
        logger.debug(
            f"ForexSizer {symbol}: {lots} lots | "
            f"SL={stop_pips:.1f} pips | risk=${actual_risk_usd:.2f} ({actual_risk_pct:.2f}%)"
        )
        return result

    def pips_to_price(self, symbol: str, price: float, pips: float, direction: str) -> float:
        """Convert a pip distance to a price level."""
        pip_size = get_pip_size(symbol)
        delta = pips * pip_size
        if direction in ("buy", "long"):
            return price + delta
        return price - delta

    def price_to_pips(self, symbol: str, price1: float, price2: float) -> float:
        """Convert a price difference to pips."""
        pip_size = get_pip_size(symbol)
        return abs(price1 - price2) / pip_size if pip_size > 0 else 0.0
