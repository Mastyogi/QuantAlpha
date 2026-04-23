import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional
from src.indicators.technical import TechnicalIndicators
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BacktestTrade:
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    entry_time: object
    exit_price: float = 0.0
    exit_time: object = None
    exit_reason: str = ""
    pnl_pct: float = 0.0


@dataclass
class BacktestResult:
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    profit_factor: float
    avg_win_pct: float
    avg_loss_pct: float
    best_trade_pct: float
    worst_trade_pct: float
    trades: List[BacktestTrade] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Backtest Results: {self.symbol} {self.timeframe}\n"
            f"Period: {self.start_date} → {self.end_date}\n"
            f"Trades: {self.total_trades} ({self.winning_trades}W/{self.losing_trades}L)\n"
            f"Win Rate: {self.win_rate:.1f}%\n"
            f"Total Return: {self.total_return_pct:+.2f}%\n"
            f"Max Drawdown: {self.max_drawdown_pct:.2f}%\n"
            f"Sharpe Ratio: {self.sharpe_ratio:.2f}\n"
            f"Profit Factor: {self.profit_factor:.2f}"
        )


class VectorizedBacktester:
    """
    High-speed vectorized backtesting engine.
    Simulates trades with realistic slippage, fees, and partial fills.
    """

    MAKER_FEE = 0.001
    TAKER_FEE = 0.001
    SLIPPAGE = 0.0005

    def run(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        initial_capital: float = 10000.0,
        risk_per_trade_pct: float = 1.0,
    ) -> BacktestResult:
        """Run full backtest with indicator-based signals."""
        df = TechnicalIndicators.add_all_indicators(df.copy())
        trades: List[BacktestTrade] = []
        equity = initial_capital
        peak_equity = equity
        max_drawdown = 0.0
        in_trade = False
        current_trade: Optional[BacktestTrade] = None

        for i in range(50, len(df)):
            row = df.iloc[i]
            price = row["close"]

            # Manage open trade
            if in_trade and current_trade:
                if current_trade.direction == "BUY":
                    if price <= current_trade.stop_loss:
                        pnl_pct = (
                            (current_trade.stop_loss - current_trade.entry_price)
                            / current_trade.entry_price
                        ) - self.TAKER_FEE * 2
                        current_trade.exit_price = current_trade.stop_loss
                        current_trade.exit_time = row.name
                        current_trade.exit_reason = "STOP_LOSS"
                        current_trade.pnl_pct = pnl_pct * 100
                        equity *= 1 + pnl_pct * risk_per_trade_pct / 100
                        trades.append(current_trade)
                        in_trade = False

                    elif price >= current_trade.take_profit:
                        pnl_pct = (
                            (current_trade.take_profit - current_trade.entry_price)
                            / current_trade.entry_price
                        ) - self.TAKER_FEE * 2
                        current_trade.exit_price = current_trade.take_profit
                        current_trade.exit_time = row.name
                        current_trade.exit_reason = "TAKE_PROFIT"
                        current_trade.pnl_pct = pnl_pct * 100
                        equity *= 1 + pnl_pct * risk_per_trade_pct / 100
                        trades.append(current_trade)
                        in_trade = False

                elif current_trade.direction == "SELL":
                    if price >= current_trade.stop_loss:
                        pnl_pct = (
                            (current_trade.entry_price - current_trade.stop_loss)
                            / current_trade.entry_price
                            * -1
                        ) - self.TAKER_FEE * 2
                        current_trade.exit_price = current_trade.stop_loss
                        current_trade.exit_time = row.name
                        current_trade.exit_reason = "STOP_LOSS"
                        current_trade.pnl_pct = pnl_pct * 100
                        equity *= 1 + pnl_pct * risk_per_trade_pct / 100
                        trades.append(current_trade)
                        in_trade = False

                    elif price <= current_trade.take_profit:
                        pnl_pct = (
                            (current_trade.entry_price - current_trade.take_profit)
                            / current_trade.entry_price
                        ) - self.TAKER_FEE * 2
                        current_trade.exit_price = current_trade.take_profit
                        current_trade.exit_time = row.name
                        current_trade.exit_reason = "TAKE_PROFIT"
                        current_trade.pnl_pct = pnl_pct * 100
                        equity *= 1 + pnl_pct * risk_per_trade_pct / 100
                        trades.append(current_trade)
                        in_trade = False

            # Find new signal
            if not in_trade:
                signal_score = row.get("signal_score", 0)
                atr = row.get("atr_14", price * 0.01)
                volume_ratio = row.get("volume_ratio", 1)
                adx = row.get("adx", 0)

                if signal_score > 50 and volume_ratio > 1.2 and adx > 25:
                    entry = price * (1 + self.SLIPPAGE)
                    sl = entry - (atr * 2)
                    tp = entry + (atr * 4)
                    current_trade = BacktestTrade(
                        symbol=symbol,
                        direction="BUY",
                        entry_price=entry,
                        stop_loss=sl,
                        take_profit=tp,
                        entry_time=row.name,
                    )
                    in_trade = True

                elif signal_score < -50 and volume_ratio > 1.2 and adx > 25:
                    entry = price * (1 - self.SLIPPAGE)
                    sl = entry + (atr * 2)
                    tp = entry - (atr * 4)
                    current_trade = BacktestTrade(
                        symbol=symbol,
                        direction="SELL",
                        entry_price=entry,
                        stop_loss=sl,
                        take_profit=tp,
                        entry_time=row.name,
                    )
                    in_trade = True

            # Track drawdown
            if equity > peak_equity:
                peak_equity = equity
            dd = (peak_equity - equity) / max(peak_equity, 1) * 100
            if dd > max_drawdown:
                max_drawdown = dd

        if not trades:
            logger.warning(f"No trades generated for {symbol}")

        wins = [t for t in trades if t.pnl_pct > 0]
        losses = [t for t in trades if t.pnl_pct <= 0]
        total_return = (equity - initial_capital) / initial_capital * 100

        if trades:
            returns = [t.pnl_pct for t in trades]
            sharpe = (np.mean(returns) / max(np.std(returns), 0.001)) * np.sqrt(252)
        else:
            sharpe = 0.0

        gross_profit = sum(t.pnl_pct for t in wins) if wins else 0
        gross_loss = abs(sum(t.pnl_pct for t in losses)) if losses else 1
        profit_factor = gross_profit / max(gross_loss, 0.001)

        return BacktestResult(
            symbol=symbol,
            timeframe=timeframe,
            start_date=str(df.index[0]),
            end_date=str(df.index[-1]),
            total_trades=len(trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate=len(wins) / max(len(trades), 1) * 100,
            total_return_pct=total_return,
            max_drawdown_pct=max_drawdown,
            sharpe_ratio=sharpe,
            profit_factor=profit_factor,
            avg_win_pct=np.mean([t.pnl_pct for t in wins]) if wins else 0,
            avg_loss_pct=np.mean([t.pnl_pct for t in losses]) if losses else 0,
            best_trade_pct=max((t.pnl_pct for t in trades), default=0),
            worst_trade_pct=min((t.pnl_pct for t in trades), default=0),
            trades=trades,
        )
