from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import pandas as pd


@dataclass
class TradeSignal:
    direction: str          # "BUY" | "SELL" | "NEUTRAL"
    entry_price: float
    stop_loss: float
    take_profit: float
    strategy_name: str
    signal_strength: float  # 0.0 - 1.0
    notes: str = ""

    @property
    def risk_reward(self) -> float:
        """Calculate risk:reward ratio."""
        if self.direction == "BUY":
            risk = abs(self.entry_price - self.stop_loss)
            reward = abs(self.take_profit - self.entry_price)
        elif self.direction == "SELL":
            risk = abs(self.stop_loss - self.entry_price)
            reward = abs(self.entry_price - self.take_profit)
        else:
            return 0.0
        return reward / max(risk, 1e-10)

    @property
    def is_valid(self) -> bool:
        """Check signal has valid prices."""
        return (
            self.direction != "NEUTRAL"
            and self.entry_price > 0
            and self.stop_loss > 0
            and self.take_profit > 0
            and self.risk_reward >= 1.0
        )


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy identifier."""
        ...

    @abstractmethod
    async def generate_signal(
        self,
        df_primary: pd.DataFrame,
        df_secondary: Optional[pd.DataFrame],
        symbol: str,
    ) -> TradeSignal:
        """Generate a trade signal from market data."""
        ...

    def _neutral(self) -> TradeSignal:
        """Return a neutral (no-trade) signal."""
        return TradeSignal(
            direction="NEUTRAL",
            entry_price=0.0,
            stop_loss=0.0,
            take_profit=0.0,
            strategy_name=self.name,
            signal_strength=0.0,
        )

    def _calculate_levels(
        self,
        price: float,
        atr: float,
        direction: str,
        sl_multiplier: float = 2.0,
        tp_multiplier: float = 4.0,
    ) -> tuple:
        """Calculate stop loss and take profit based on ATR."""
        if direction == "BUY":
            stop_loss = price - (atr * sl_multiplier)
            take_profit = price + (atr * tp_multiplier)
        else:
            stop_loss = price + (atr * sl_multiplier)
            take_profit = price - (atr * tp_multiplier)
        return stop_loss, take_profit
