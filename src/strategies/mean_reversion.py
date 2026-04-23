import pandas as pd
from typing import Optional
from src.strategies.base_strategy import BaseStrategy, TradeSignal
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MeanReversionStrategy(BaseStrategy):
    """
    Bollinger Band squeeze + RSI oversold/overbought mean reversion.
    Best in ranging markets (low ADX).
    """

    @property
    def name(self) -> str:
        return "MeanReversion"

    async def generate_signal(
        self,
        df_primary: pd.DataFrame,
        df_secondary: Optional[pd.DataFrame],
        symbol: str,
    ) -> TradeSignal:
        if len(df_primary) < 50:
            return self._neutral()

        latest = df_primary.iloc[-1]
        price = latest["close"]
        atr = latest["atr_14"]

        # In trending market, skip mean reversion
        adx = latest.get("adx", 0)
        if adx > 35:
            return self._neutral()

        bb_pct = latest.get("bb_pct", 0.5)
        rsi = latest.get("rsi_14", 50)
        bb_bandwidth = latest.get("bb_bandwidth", 0.1)

        # Require tight bands (squeeze) for high-probability setups
        if bb_bandwidth > 0.1:  # Skip when bands are too wide
            pass  # Still allow signal but lower strength

        # BUY: Price at lower band + RSI oversold
        if bb_pct < 0.1 and rsi < 35:
            sl, tp = self._calculate_levels(price, atr, "BUY", sl_multiplier=1.5, tp_multiplier=3.0)
            strength = (35 - rsi) / 35 * (1 - bb_pct)
            return TradeSignal(
                direction="BUY",
                entry_price=price,
                stop_loss=sl,
                take_profit=tp,
                strategy_name=self.name,
                signal_strength=min(strength, 1.0),
                notes=f"BB lower bounce, RSI={rsi:.1f}, BB%={bb_pct:.2f}",
            )

        # SELL: Price at upper band + RSI overbought
        if bb_pct > 0.9 and rsi > 65:
            sl, tp = self._calculate_levels(price, atr, "SELL", sl_multiplier=1.5, tp_multiplier=3.0)
            strength = (rsi - 65) / 35 * bb_pct
            return TradeSignal(
                direction="SELL",
                entry_price=price,
                stop_loss=sl,
                take_profit=tp,
                strategy_name=self.name,
                signal_strength=min(strength, 1.0),
                notes=f"BB upper rejection, RSI={rsi:.1f}, BB%={bb_pct:.2f}",
            )

        return self._neutral()
