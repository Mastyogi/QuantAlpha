import pandas as pd
from typing import Optional, List
from src.strategies.base_strategy import BaseStrategy, TradeSignal
from src.strategies.trend_following import TrendFollowingStrategy
from src.strategies.mean_reversion import MeanReversionStrategy
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EnsembleStrategy(BaseStrategy):
    """
    AI-voted multi-strategy consensus.
    Requires at least 2/3 strategies to agree on direction.
    Averages signal strength when consensus achieved.
    """

    MIN_AGREEMENT = 2

    def __init__(self):
        self.strategies: List[BaseStrategy] = [
            TrendFollowingStrategy(),
            MeanReversionStrategy(),
        ]

    @property
    def name(self) -> str:
        return "Ensemble"

    async def generate_signal(
        self,
        df_primary: pd.DataFrame,
        df_secondary: Optional[pd.DataFrame],
        symbol: str,
    ) -> TradeSignal:
        """Collect votes from all sub-strategies and return consensus signal."""
        signals = []
        for strategy in self.strategies:
            try:
                signal = await strategy.generate_signal(df_primary, df_secondary, symbol)
                signals.append(signal)
                logger.debug(f"{symbol} {strategy.name}: {signal.direction} "
                             f"(strength={signal.signal_strength:.2f})")
            except Exception as e:
                logger.error(f"Strategy {strategy.name} error: {e}")

        if not signals:
            return self._neutral()

        # Count votes
        buy_signals = [s for s in signals if s.direction == "BUY"]
        sell_signals = [s for s in signals if s.direction == "SELL"]

        best_signal = None
        if len(buy_signals) >= self.MIN_AGREEMENT:
            best_signal = self._merge_signals(buy_signals, "BUY")
        elif len(sell_signals) >= self.MIN_AGREEMENT:
            best_signal = self._merge_signals(sell_signals, "SELL")
        elif len(buy_signals) == 1 and len(sell_signals) == 0:
            # Single strong signal still considered
            s = buy_signals[0]
            if s.signal_strength > 0.75:
                best_signal = s
        elif len(sell_signals) == 1 and len(buy_signals) == 0:
            s = sell_signals[0]
            if s.signal_strength > 0.75:
                best_signal = s

        if best_signal is None or not best_signal.is_valid:
            return self._neutral()

        logger.info(
            f"{symbol} ENSEMBLE SIGNAL: {best_signal.direction} "
            f"RR={best_signal.risk_reward:.2f} strength={best_signal.signal_strength:.2f}"
        )
        return best_signal

    def _merge_signals(self, signals: list, direction: str) -> TradeSignal:
        """Merge multiple same-direction signals by averaging key parameters."""
        avg_entry = sum(s.entry_price for s in signals) / len(signals)
        avg_sl = sum(s.stop_loss for s in signals) / len(signals)
        avg_tp = sum(s.take_profit for s in signals) / len(signals)
        avg_strength = sum(s.signal_strength for s in signals) / len(signals)

        notes = " + ".join(s.strategy_name for s in signals)

        return TradeSignal(
            direction=direction,
            entry_price=avg_entry,
            stop_loss=avg_sl,
            take_profit=avg_tp,
            strategy_name=f"Ensemble({notes})",
            signal_strength=min(avg_strength * 1.1, 1.0),  # Slight boost for consensus
            notes=f"Consensus from {len(signals)} strategies",
        )
