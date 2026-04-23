"""
Performance Tracker
Tracks and analyzes trading performance metrics for self-improvement.
"""

import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
from src.database.models import Trade, TradeStatus
from src.database.repositories import PerformanceHistoryRepository
from src.database.models import PerformanceHistory
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics container."""
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win_pct: float
    avg_loss_pct: float
    total_pnl: float
    calmar_ratio: float = 0.0


class PerformanceTracker:
    """Tracks and calculates trading performance metrics."""
    
    def __init__(self):
        self.perf_repo = PerformanceHistoryRepository()
    
    def calculate_metrics(self, trades: List[Trade]) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics from trades."""
        if not trades:
            return PerformanceMetrics(
                win_rate=0.0,
                profit_factor=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                max_drawdown=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                avg_win_pct=0.0,
                avg_loss_pct=0.0,
                total_pnl=0.0
            )
        
        # Filter closed trades
        closed_trades = [t for t in trades if t.status == TradeStatus.CLOSED]
        
        if not closed_trades:
            return PerformanceMetrics(
                win_rate=0.0,
                profit_factor=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                max_drawdown=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                avg_win_pct=0.0,
                avg_loss_pct=0.0,
                total_pnl=0.0
            )
        
        # Basic counts
        total_trades = len(closed_trades)
        winning_trades = len([t for t in closed_trades if t.pnl > 0])
        losing_trades = len([t for t in closed_trades if t.pnl <= 0])
        
        # Win rate
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
        
        # PnL calculations
        total_pnl = sum(t.pnl for t in closed_trades)
        wins = [t.pnl_pct for t in closed_trades if t.pnl > 0]
        losses = [abs(t.pnl_pct) for t in closed_trades if t.pnl <= 0]
        
        avg_win_pct = np.mean(wins) if wins else 0.0
        avg_loss_pct = np.mean(losses) if losses else 0.0
        
        # Profit factor
        total_wins = sum(t.pnl for t in closed_trades if t.pnl > 0)
        total_losses = abs(sum(t.pnl for t in closed_trades if t.pnl <= 0))
        profit_factor = total_wins / total_losses if total_losses > 0 else 0.0
        
        # Sharpe ratio
        returns = [t.pnl_pct for t in closed_trades]
        sharpe_ratio = self._calculate_sharpe_ratio(returns)
        
        # Sortino ratio
        sortino_ratio = self._calculate_sortino_ratio(returns)
        
        # Maximum drawdown
        max_drawdown = self._calculate_max_drawdown(closed_trades)
        
        # Calmar ratio
        annual_return = (total_pnl / closed_trades[0].size_usd) * 100 if closed_trades else 0.0
        calmar_ratio = annual_return / max_drawdown if max_drawdown > 0 else 0.0
        
        return PerformanceMetrics(
            win_rate=win_rate,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            avg_win_pct=avg_win_pct,
            avg_loss_pct=avg_loss_pct,
            total_pnl=total_pnl,
            calmar_ratio=calmar_ratio
        )
    
    def _calculate_sharpe_ratio(self, returns: List[float]) -> float:
        """Calculate Sharpe ratio."""
        if not returns or len(returns) < 2:
            return 0.0
        
        returns_array = np.array(returns)
        mean_return = np.mean(returns_array)
        std_return = np.std(returns_array)
        
        if std_return == 0:
            return 0.0
        
        # Annualized Sharpe (assuming daily returns)
        sharpe = (mean_return / std_return) * np.sqrt(252)
        return sharpe
    
    def _calculate_sortino_ratio(self, returns: List[float]) -> float:
        """Calculate Sortino ratio (downside deviation)."""
        if not returns or len(returns) < 2:
            return 0.0
        
        returns_array = np.array(returns)
        mean_return = np.mean(returns_array)
        
        # Downside deviation (only negative returns)
        negative_returns = returns_array[returns_array < 0]
        if len(negative_returns) == 0:
            return 0.0
        
        downside_std = np.std(negative_returns)
        
        if downside_std == 0:
            return 0.0
        
        # Annualized Sortino
        sortino = (mean_return / downside_std) * np.sqrt(252)
        return sortino
    
    def _calculate_max_drawdown(self, trades: List[Trade]) -> float:
        """Calculate maximum drawdown percentage."""
        if not trades:
            return 0.0
        
        # Calculate cumulative PnL
        cumulative_pnl = []
        running_pnl = 0.0
        
        for trade in sorted(trades, key=lambda t: t.closed_at or datetime.now(timezone.utc)):
            running_pnl += trade.pnl
            cumulative_pnl.append(running_pnl)
        
        if not cumulative_pnl:
            return 0.0
        
        # Calculate drawdown
        peak = cumulative_pnl[0]
        max_dd = 0.0
        
        for pnl in cumulative_pnl:
            if pnl > peak:
                peak = pnl
            
            drawdown = ((peak - pnl) / abs(peak)) * 100 if peak != 0 else 0.0
            max_dd = max(max_dd, drawdown)
        
        return max_dd
    
    def extract_winning_conditions(self, trades: List[Trade]) -> List[Dict]:
        """Extract conditions from winning trades."""
        winning_trades = [t for t in trades if t.status == TradeStatus.CLOSED and t.pnl > 0]
        
        conditions = []
        for trade in winning_trades:
            condition = {
                "symbol": trade.symbol,
                "direction": trade.direction.value if trade.direction else None,
                "strategy": trade.strategy_name,
                "timeframe": trade.timeframe,
                "ai_confidence": trade.ai_confidence,
                "signal_score": trade.signal_score,
                "pnl_pct": trade.pnl_pct,
            }
            conditions.append(condition)
        
        return conditions
    
    def extract_losing_conditions(self, trades: List[Trade]) -> List[Dict]:
        """Extract conditions from losing trades."""
        losing_trades = [t for t in trades if t.status == TradeStatus.CLOSED and t.pnl <= 0]
        
        conditions = []
        for trade in losing_trades:
            condition = {
                "symbol": trade.symbol,
                "direction": trade.direction.value if trade.direction else None,
                "strategy": trade.strategy_name,
                "timeframe": trade.timeframe,
                "ai_confidence": trade.ai_confidence,
                "signal_score": trade.signal_score,
                "pnl_pct": trade.pnl_pct,
            }
            conditions.append(condition)
        
        return conditions
    
    async def store_performance(
        self,
        period: str,
        metrics: PerformanceMetrics,
        symbol: Optional[str] = None,
        strategy_name: Optional[str] = None,
        equity: Optional[float] = None
    ):
        """Store performance metrics to database."""
        performance = PerformanceHistory(
            timestamp=datetime.now(timezone.utc),
            period=period,
            symbol=symbol,
            strategy_name=strategy_name,
            total_trades=metrics.total_trades,
            winning_trades=metrics.winning_trades,
            losing_trades=metrics.losing_trades,
            win_rate=metrics.win_rate,
            total_pnl=metrics.total_pnl,
            avg_win_pct=metrics.avg_win_pct,
            avg_loss_pct=metrics.avg_loss_pct,
            profit_factor=metrics.profit_factor,
            sharpe_ratio=metrics.sharpe_ratio,
            sortino_ratio=metrics.sortino_ratio,
            max_drawdown_pct=metrics.max_drawdown,
            equity=equity
        )
        
        await self.perf_repo.insert_performance(performance)
        logger.info(
            f"Performance stored: {period} - "
            f"Win Rate: {metrics.win_rate:.1%}, "
            f"Profit Factor: {metrics.profit_factor:.2f}, "
            f"Sharpe: {metrics.sharpe_ratio:.2f}"
        )
