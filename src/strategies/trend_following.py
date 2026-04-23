import pandas as pd
from typing import Optional
from src.strategies.base_strategy import BaseStrategy, TradeSignal
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TrendFollowingStrategy(BaseStrategy):
    """
    EMA crossover with ADX trend-strength filter.
    Entry: EMA 9/21 cross + ADX > 25 + Volume spike
    """

    @property
    def name(self) -> str:
        return "TrendFollowing"

    async def generate_signal(
        self,
        df_primary: pd.DataFrame,
        df_secondary: Optional[pd.DataFrame],
        symbol: str,
    ) -> TradeSignal:
        if len(df_primary) < 50:
            return self._neutral()

        latest = df_primary.iloc[-1]
        prev = df_primary.iloc[-2]

        price = latest["close"]
        atr = latest["atr_14"]
        adx = latest.get("adx", 0)
        volume_ratio = latest.get("volume_ratio", 1)

        # Filter: trend must be established (ADX > 25)
        if adx < 25:
            return self._neutral()

        # Filter: require volume confirmation
        if volume_ratio < 1.2:
            return self._neutral()

        # BUY signal: EMA 9 crosses above EMA 21
        ema_cross_up = (
            latest["ema_9"] > latest["ema_21"] and
            prev["ema_9"] <= prev["ema_21"]
        )

        # SELL signal: EMA 9 crosses below EMA 21
        ema_cross_down = (
            latest["ema_9"] < latest["ema_21"] and
            prev["ema_9"] >= prev["ema_21"]
        )

        # Also signal on strong sustained trend
        strong_uptrend = latest.get("trend_up", False) and latest["signal_score"] > 60
        strong_downtrend = latest.get("trend_down", False) and latest["signal_score"] < -60

        if ema_cross_up or strong_uptrend:
            sl, tp = self._calculate_levels(price, atr, "BUY")
            strength = min(adx / 100 * volume_ratio, 1.0)
            return TradeSignal(
                direction="BUY",
                entry_price=price,
                stop_loss=sl,
                take_profit=tp,
                strategy_name=self.name,
                signal_strength=strength,
                notes=f"EMA cross up, ADX={adx:.1f}, Vol={volume_ratio:.2f}x",
            )

        if ema_cross_down or strong_downtrend:
            sl, tp = self._calculate_levels(price, atr, "SELL")
            strength = min(adx / 100 * volume_ratio, 1.0)
            return TradeSignal(
                direction="SELL",
                entry_price=price,
                stop_loss=sl,
                take_profit=tp,
                strategy_name=self.name,
                signal_strength=strength,
                notes=f"EMA cross down, ADX={adx:.1f}, Vol={volume_ratio:.2f}x",
            )

        return self._neutral()
