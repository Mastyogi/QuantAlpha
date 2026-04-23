"""
Portfolio Compounder
Kelly Criterion position sizing for exponential fund growth.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
from src.database.repositories import EquityHistoryRepository
from src.database.models import EquityHistory
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CompoundingStats:
    """Compounding performance statistics."""
    initial_equity: float
    current_equity: float
    total_return_pct: float
    annualized_return_pct: float
    compounding_rate: float  # Monthly compounding rate


class KellyCriterionCalculator:
    """
    Kelly Criterion position sizing calculator.
    Formula: Kelly% = W - [(1-W) / R]
    where W = win rate, R = avg_win / avg_loss
    """
    
    def calculate(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
    ) -> float:
        """
        Calculate Kelly percentage.
        
        Args:
            win_rate: Win rate (0.0 to 1.0)
            avg_win: Average win percentage
            avg_loss: Average loss percentage
        
        Returns:
            Kelly percentage (0-100)
        """
        if avg_loss == 0:
            logger.warning("Average loss is zero - cannot calculate Kelly")
            return 0.0
        
        # Win/Loss ratio
        win_loss_ratio = avg_win / avg_loss
        
        # Kelly formula: W - [(1-W) / R]
        kelly_pct = win_rate - ((1 - win_rate) / win_loss_ratio)
        
        # Kelly can be negative (don't trade) or > 100% (cap it)
        kelly_pct = max(0, min(kelly_pct * 100, 100))
        
        return kelly_pct


class EquityTracker:
    """Tracks equity history for compounding analysis."""
    
    def __init__(self, initial_equity: float):
        self.initial_equity = initial_equity
        self.equity_repo = EquityHistoryRepository()
        self._history: List[EquityHistory] = []
    
    async def record_update(
        self,
        timestamp: datetime,
        equity: float,
        pnl: float,
        unrealized_pnl: float = 0.0,
        open_positions: int = 0,
        portfolio_heat_pct: float = 0.0
    ):
        """Record equity update."""
        equity_record = EquityHistory(
            timestamp=timestamp,
            equity=equity,
            realized_pnl=pnl,
            unrealized_pnl=unrealized_pnl,
            open_positions=open_positions,
            portfolio_heat_pct=portfolio_heat_pct
        )
        
        await self.equity_repo.record_equity({
            "timestamp": timestamp,
            "equity": equity,
            "realized_pnl": pnl,
            "unrealized_pnl": unrealized_pnl,
            "open_positions": open_positions,
            "portfolio_heat_pct": portfolio_heat_pct
        })
        
        self._history.append(equity_record)
    
    async def get_history(self, days: int = 30) -> List[EquityHistory]:
        """Get equity history."""
        if not self._history:
            # Load from database
            self._history = await self.equity_repo.get_equity_history(limit=days * 24)
        return self._history


class CompoundingAnalyzer:
    """Analyzes compounding performance."""
    
    def calculate_monthly_rate(self, history: List[EquityHistory]) -> float:
        """Calculate monthly compounding rate."""
        if len(history) < 2:
            return 0.0
        
        # Get first and last equity
        first_equity = history[0].equity
        last_equity = history[-1].equity
        
        # Calculate days elapsed
        days_elapsed = (history[-1].timestamp - history[0].timestamp).days
        
        if days_elapsed == 0 or first_equity == 0:
            return 0.0
        
        # Calculate monthly rate
        months_elapsed = days_elapsed / 30.0
        if months_elapsed == 0:
            return 0.0
        
        # Compound growth rate: (final/initial)^(1/periods) - 1
        monthly_rate = (last_equity / first_equity) ** (1 / months_elapsed) - 1
        
        return monthly_rate * 100  # Return as percentage


class PortfolioCompounder:
    """
    Main portfolio compounding engine.
    Implements Kelly Criterion position sizing for exponential growth.
    """
    
    def __init__(
        self,
        initial_equity: float,
        kelly_fraction: float = 0.25,  # Fractional Kelly for safety
        max_position_pct: float = 5.0,
        max_portfolio_heat: float = 12.0,
    ):
        self.initial_equity = initial_equity
        self.current_equity = initial_equity
        self.kelly_fraction = kelly_fraction
        self.max_position_pct = max_position_pct
        self.max_portfolio_heat = max_portfolio_heat
        
        self.kelly_calculator = KellyCriterionCalculator()
        self.equity_tracker = EquityTracker(initial_equity)
        self.compounding_analyzer = CompoundingAnalyzer()
        
        logger.info(
            f"Portfolio Compounder initialized:\n"
            f"  Initial Equity: ${initial_equity:,.2f}\n"
            f"  Kelly Fraction: {kelly_fraction}\n"
            f"  Max Position: {max_position_pct}%\n"
            f"  Max Portfolio Heat: {max_portfolio_heat}%"
        )
    
    def calculate_position_size(
        self,
        symbol: str,
        win_rate: float,
        avg_win_pct: float,
        avg_loss_pct: float,
        current_risk_heat: float,
    ) -> float:
        """
        Calculate position size using Kelly Criterion.
        
        Args:
            symbol: Trading symbol
            win_rate: Historical win rate (0.0 to 1.0)
            avg_win_pct: Average win percentage
            avg_loss_pct: Average loss percentage
            current_risk_heat: Current portfolio risk heat percentage
        
        Returns:
            Position size in USD
        """
        # Calculate Kelly percentage
        kelly_pct = self.kelly_calculator.calculate(
            win_rate=win_rate,
            avg_win=avg_win_pct,
            avg_loss=avg_loss_pct,
        )
        
        # Apply fractional Kelly for safety
        kelly_pct = kelly_pct * self.kelly_fraction
        
        # Calculate position size based on current equity
        position_size_usd = self.current_equity * (kelly_pct / 100)
        
        # Apply maximum position size limit
        max_size = self.current_equity * (self.max_position_pct / 100)
        position_size_usd = min(position_size_usd, max_size)
        
        # Check portfolio heat limit
        if current_risk_heat + kelly_pct > self.max_portfolio_heat:
            # Reduce size to stay within heat limit
            available_heat = self.max_portfolio_heat - current_risk_heat
            position_size_usd = self.current_equity * (available_heat / 100)
        
        # Ensure non-negative
        position_size_usd = max(0, position_size_usd)
        
        logger.debug(
            f"Position size calculated for {symbol}:\n"
            f"  Kelly%: {kelly_pct:.2f}%\n"
            f"  Fractional Kelly: {kelly_pct * self.kelly_fraction:.2f}%\n"
            f"  Position Size: ${position_size_usd:,.2f}\n"
            f"  Current Equity: ${self.current_equity:,.2f}\n"
            f"  Risk Heat: {current_risk_heat:.2f}%"
        )
        
        return position_size_usd
    
    async def update_equity(
        self,
        new_equity: float,
        realized_pnl: float,
        unrealized_pnl: float = 0.0,
        open_positions: int = 0,
        portfolio_heat_pct: float = 0.0
    ):
        """Update equity after trade closes."""
        old_equity = self.current_equity
        self.current_equity = new_equity
        
        # Track equity change
        await self.equity_tracker.record_update(
            timestamp=datetime.now(timezone.utc),
            equity=new_equity,
            pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            open_positions=open_positions,
            portfolio_heat_pct=portfolio_heat_pct
        )
        
        # Check for 10% equity change (trigger position size adjustment)
        pct_change = abs(new_equity - old_equity) / old_equity if old_equity > 0 else 0
        if pct_change >= 0.10:
            logger.info(
                f"📊 Equity changed by {pct_change:.1%}: "
                f"${old_equity:,.2f} → ${new_equity:,.2f}\n"
                f"Position sizes will adjust automatically on next trade."
            )
    
    async def get_compounding_stats(self) -> CompoundingStats:
        """Get compounding performance statistics."""
        history = await self.equity_tracker.get_history(days=90)
        
        if len(history) < 2:
            return CompoundingStats(
                initial_equity=self.initial_equity,
                current_equity=self.current_equity,
                total_return_pct=0.0,
                annualized_return_pct=0.0,
                compounding_rate=0.0,
            )
        
        # Total return
        total_return_pct = (
            (self.current_equity - self.initial_equity) / self.initial_equity * 100
        )
        
        # Annualized return
        days_elapsed = (history[-1].timestamp - history[0].timestamp).days
        if days_elapsed > 0:
            annualized_return_pct = (
                (self.current_equity / self.initial_equity) ** (365 / days_elapsed) - 1
            ) * 100
        else:
            annualized_return_pct = 0.0
        
        # Monthly compounding rate
        compounding_rate = self.compounding_analyzer.calculate_monthly_rate(history)
        
        return CompoundingStats(
            initial_equity=self.initial_equity,
            current_equity=self.current_equity,
            total_return_pct=total_return_pct,
            annualized_return_pct=annualized_return_pct,
            compounding_rate=compounding_rate,
        )
    
    def get_current_equity(self) -> float:
        """Get current equity."""
        return self.current_equity
    
    def get_position_size_multiplier(self, win_rate: float) -> float:
        """
        Calculate position size multiplier based on win rate.
        Formula: base_size × (1 + (win_rate - 0.60) × 2)
        """
        multiplier = 1 + (win_rate - 0.60) * 2
        
        # Clamp between 0.5 and 1.5
        multiplier = max(0.5, min(1.5, multiplier))
        
        return multiplier
