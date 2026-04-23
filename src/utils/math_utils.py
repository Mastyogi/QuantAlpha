import numpy as np
from typing import List, Optional


def calculate_kelly_fraction(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """
    Kelly Criterion for position sizing.
    Returns fraction of capital to risk (capped at 25%).
    """
    if avg_loss == 0:
        return 0.0
    b = avg_win / abs(avg_loss)
    p = win_rate
    q = 1 - p
    kelly = (b * p - q) / b
    return max(0.0, min(kelly * 0.25, 0.25))  # Quarter-Kelly, max 25%


def calculate_sharpe_ratio(returns: List[float], periods_per_year: int = 252) -> float:
    """Annualized Sharpe Ratio."""
    if not returns or len(returns) < 2:
        return 0.0
    arr = np.array(returns)
    mean = np.mean(arr)
    std = np.std(arr)
    if std == 0:
        return 0.0
    return (mean / std) * np.sqrt(periods_per_year)


def calculate_sortino_ratio(returns: List[float], periods_per_year: int = 252) -> float:
    """Sortino Ratio (penalizes only downside volatility)."""
    if not returns:
        return 0.0
    arr = np.array(returns)
    mean = np.mean(arr)
    downside = arr[arr < 0]
    if len(downside) == 0:
        return float("inf")
    downside_std = np.std(downside)
    if downside_std == 0:
        return 0.0
    return (mean / downside_std) * np.sqrt(periods_per_year)


def calculate_max_drawdown(equity_curve: List[float]) -> float:
    """Maximum drawdown percentage from equity curve."""
    if not equity_curve:
        return 0.0
    arr = np.array(equity_curve)
    peak = np.maximum.accumulate(arr)
    drawdown = (peak - arr) / np.where(peak > 0, peak, 1) * 100
    return float(np.max(drawdown))


def round_to_tick(price: float, tick_size: float) -> float:
    """Round price to nearest tick size."""
    if tick_size <= 0:
        return price
    return round(round(price / tick_size) * tick_size, 8)


def pct_change(old: float, new: float) -> float:
    """Percentage change from old to new."""
    if old == 0:
        return 0.0
    return (new - old) / old * 100
