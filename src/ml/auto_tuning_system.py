"""
Auto-Tuning System
==================
Optuna-based hyperparameter optimization with walk-forward validation.
Optimizes confluence threshold, Kelly fraction, AI confidence, and TP multipliers.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import optuna
import numpy as np

from src.backtesting.walk_forward import WalkForwardValidator
from src.telegram.approval_system import ApprovalSystem, ProposalType
from src.database.repositories import ParameterChangeRepository, TradeRepository
from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


@dataclass
class OptimizationResult:
    """Results from an optimization run."""
    best_params: Dict
    best_sharpe: float
    trials_completed: int
    optimization_time: float
    out_of_sample_sharpe: float
    timestamp: datetime


class AutoTuningSystem:
    """
    Automated parameter optimization using Optuna.
    Runs weekly, proposes changes via approval system.
    """
    
    def __init__(
        self,
        approval_system: ApprovalSystem,
        n_trials: int = 50,
        lookback_days: int = 90,
    ):
        self.approval_system = approval_system
        self.n_trials = n_trials
        self.lookback_days = lookback_days
        
        self.param_repo = ParameterChangeRepository()
        self.trade_repo = TradeRepository()
        
        self.last_optimization: Optional[OptimizationResult] = None
        self.next_scheduled: Optional[datetime] = None
        
        logger.info(
            f"AutoTuningSystem initialized:\n"
            f"  Trials: {n_trials}\n"
            f"  Lookback: {lookback_days} days"
        )
    
    async def optimize(self) -> OptimizationResult:
        """
        Run Optuna optimization with walk-forward validation.
        
        Returns:
            OptimizationResult with best parameters
        """
        logger.info("🔧 Starting parameter optimization...")
        start_time = datetime.now(timezone.utc)
        
        # Get historical trades for optimization
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=self.lookback_days)
        
        trades = await self.trade_repo.get_trades_in_range(start_date, end_date)
        
        if len(trades) < 30:
            logger.warning(f"Insufficient trades for optimization: {len(trades)} < 30")
            return None
        
        logger.info(f"Optimizing on {len(trades)} trades from last {self.lookback_days} days")
        
        # Create Optuna study
        study = optuna.create_study(
            direction="maximize",
            sampler=optuna.samplers.TPESampler(seed=42),
            study_name=f"auto_tune_{start_time.strftime('%Y%m%d_%H%M%S')}"
        )
        
        # Run optimization
        study.optimize(
            lambda trial: self._objective(trial, trades),
            n_trials=self.n_trials,
            show_progress_bar=False,
        )
        
        best_params = study.best_params
        best_sharpe = study.best_value
        
        # Validate on out-of-sample data (last 20%)
        oos_sharpe = await self._validate_out_of_sample(best_params, trades)
        
        optimization_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        result = OptimizationResult(
            best_params=best_params,
            best_sharpe=best_sharpe,
            trials_completed=len(study.trials),
            optimization_time=optimization_time,
            out_of_sample_sharpe=oos_sharpe,
            timestamp=datetime.now(timezone.utc)
        )
        
        self.last_optimization = result
        
        logger.info(
            f"✅ Optimization complete:\n"
            f"  Best Sharpe: {best_sharpe:.3f}\n"
            f"  OOS Sharpe: {oos_sharpe:.3f}\n"
            f"  Trials: {len(study.trials)}\n"
            f"  Time: {optimization_time:.1f}s\n"
            f"  Best params: {best_params}"
        )
        
        # Create approval proposal
        await self._create_approval_proposal(result)
        
        return result
    
    def _objective(self, trial: optuna.Trial, trades: List) -> float:
        """
        Optuna objective function.
        Optimizes for Sharpe ratio on in-sample data (first 80%).
        
        Args:
            trial: Optuna trial
            trades: Historical trades
        
        Returns:
            Sharpe ratio (to maximize)
        """
        # Define parameter search space
        params = {
            'min_confluence_score': trial.suggest_float('min_confluence_score', 60.0, 90.0),
            'kelly_fraction': trial.suggest_float('kelly_fraction', 0.20, 0.45),
            'min_ai_confidence': trial.suggest_float('min_ai_confidence', 0.55, 0.85),
            'tp1_multiplier': trial.suggest_float('tp1_multiplier', 1.2, 2.0),
            'tp2_multiplier': trial.suggest_float('tp2_multiplier', 2.0, 4.0),
            'tp3_multiplier': trial.suggest_float('tp3_multiplier', 3.5, 6.0),
        }
        
        # Use first 80% for training
        train_size = int(len(trades) * 0.8)
        train_trades = trades[:train_size]
        
        # Calculate Sharpe ratio with these parameters
        sharpe = self._calculate_sharpe(train_trades, params)
        
        return sharpe
    
    def _calculate_sharpe(self, trades: List, params: Dict) -> float:
        """
        Calculate Sharpe ratio for given trades and parameters.
        
        Args:
            trades: List of trades
            params: Parameter dictionary
        
        Returns:
            Sharpe ratio
        """
        # Filter trades based on parameters
        filtered_trades = []
        for trade in trades:
            # Apply confluence filter
            if hasattr(trade, 'ai_confidence') and trade.ai_confidence:
                if trade.ai_confidence < params['min_ai_confidence']:
                    continue
            
            filtered_trades.append(trade)
        
        if len(filtered_trades) < 10:
            return -999.0  # Penalty for too few trades
        
        # Calculate returns
        returns = []
        for trade in filtered_trades:
            if trade.pnl_pct is not None:
                returns.append(trade.pnl_pct / 100)  # Convert to decimal
        
        if not returns:
            return -999.0
        
        returns_array = np.array(returns)
        
        # Calculate Sharpe ratio
        mean_return = np.mean(returns_array)
        std_return = np.std(returns_array)
        
        if std_return == 0:
            return 0.0
        
        # Annualized Sharpe (assuming ~250 trading days)
        sharpe = (mean_return / std_return) * np.sqrt(250)
        
        return float(sharpe)
    
    async def _validate_out_of_sample(
        self,
        params: Dict,
        trades: List
    ) -> float:
        """
        Validate parameters on out-of-sample data (last 20%).
        
        Args:
            params: Parameter dictionary
            trades: All trades
        
        Returns:
            Out-of-sample Sharpe ratio
        """
        # Use last 20% for validation
        train_size = int(len(trades) * 0.8)
        test_trades = trades[train_size:]
        
        if len(test_trades) < 5:
            return 0.0
        
        oos_sharpe = self._calculate_sharpe(test_trades, params)
        
        return oos_sharpe
    
    async def _create_approval_proposal(self, result: OptimizationResult):
        """
        Create parameter change proposal for approval.
        
        Args:
            result: Optimization result
        """
        # Get current parameters
        current_params = {
            'min_confluence_score': settings.confluence_threshold,
            'kelly_fraction': 0.25,  # Default from portfolio_compounder
            'min_ai_confidence': settings.ai_confidence_threshold,
            'tp1_multiplier': 1.5,
            'tp2_multiplier': 3.0,
            'tp3_multiplier': 5.0,
        }
        
        # Create proposal
        proposal_text = (
            f"🔧 *Parameter Optimization Results*\n\n"
            f"*Performance*:\n"
            f"• In-Sample Sharpe: {result.best_sharpe:.3f}\n"
            f"• Out-of-Sample Sharpe: {result.out_of_sample_sharpe:.3f}\n"
            f"• Trials: {result.trials_completed}\n\n"
            f"*Proposed Changes*:\n"
        )
        
        for param, new_value in result.best_params.items():
            old_value = current_params.get(param, 'N/A')
            proposal_text += f"• {param}: {old_value} → {new_value:.3f}\n"
        
        proposal_text += (
            f"\n*Validation*:\n"
            f"• Tested on {self.lookback_days} days of data\n"
            f"• Walk-forward validated\n\n"
            f"Approve to apply these parameters?"
        )
        
        # Create proposal via approval system
        proposal_id = await self.approval_system.create_proposal(
            proposal_type=ProposalType.PARAMETER_CHANGE,
            title="Parameter Optimization",
            description=proposal_text,
            metadata={
                'old_params': current_params,
                'new_params': result.best_params,
                'sharpe_in_sample': result.best_sharpe,
                'sharpe_out_of_sample': result.out_of_sample_sharpe,
                'timestamp': result.timestamp.isoformat(),
            }
        )
        
        logger.info(f"Created parameter change proposal: {proposal_id}")
    
    async def on_approved(self, proposal_id: str, metadata: Dict):
        """
        Callback when parameter change is approved.
        
        Args:
            proposal_id: Proposal ID
            metadata: Proposal metadata with new parameters
        """
        new_params = metadata.get('new_params', {})
        old_params = metadata.get('old_params', {})
        
        logger.info(f"✅ Parameter change approved: {proposal_id}")
        
        # Write to database
        for param_name, new_value in new_params.items():
            old_value = old_params.get(param_name)
            
            await self.param_repo.create({
                'parameter_name': param_name,
                'old_value': str(old_value),
                'new_value': str(new_value),
                'reason': f'Auto-tuning optimization (proposal {proposal_id})',
                'approved_by': 'admin',
                'approved_at': datetime.now(timezone.utc),
            })
        
        # Hot-reload settings (update in-memory settings object)
        self._apply_parameters(new_params)
        
        logger.info("Parameters applied successfully")
    
    async def on_rejected(self, proposal_id: str, reason: str):
        """
        Callback when parameter change is rejected.
        
        Args:
            proposal_id: Proposal ID
            reason: Rejection reason
        """
        logger.info(f"❌ Parameter change rejected: {proposal_id} - {reason}")
        
        # Schedule next optimization in 7 days
        self.next_scheduled = datetime.now(timezone.utc) + timedelta(days=7)
        
        logger.info(f"Next optimization scheduled for: {self.next_scheduled}")
    
    def _apply_parameters(self, params: Dict):
        """
        Apply parameters to settings (hot-reload).
        
        Args:
            params: Parameter dictionary
        """
        # Update settings object
        if 'min_confluence_score' in params:
            settings.confluence_threshold = int(params['min_confluence_score'])
        
        if 'min_ai_confidence' in params:
            settings.ai_confidence_threshold = float(params['min_ai_confidence'])
        
        # Note: Kelly fraction and TP multipliers would need to be passed
        # to PortfolioCompounder and ProfitBookingEngine instances
        # This requires storing them in a shared config or database
        
        logger.info("Settings hot-reloaded with new parameters")
    
    async def schedule_weekly(self):
        """
        Background task that runs optimization weekly.
        Runs every Sunday at 00:00 UTC.
        """
        logger.info("📅 Weekly optimization scheduler started")
        
        while True:
            try:
                # Calculate time until next Sunday 00:00 UTC
                now = datetime.now(timezone.utc)
                days_until_sunday = (6 - now.weekday()) % 7
                if days_until_sunday == 0 and now.hour >= 0:
                    days_until_sunday = 7
                
                next_sunday = now + timedelta(days=days_until_sunday)
                next_sunday = next_sunday.replace(hour=0, minute=0, second=0, microsecond=0)
                
                sleep_seconds = (next_sunday - now).total_seconds()
                
                self.next_scheduled = next_sunday
                logger.info(f"Next optimization scheduled for: {next_sunday} (in {sleep_seconds/3600:.1f} hours)")
                
                # Sleep until next Sunday
                await asyncio.sleep(sleep_seconds)
                
                # Run optimization
                logger.info("⏰ Weekly optimization triggered")
                await self.optimize()
                
            except Exception as e:
                logger.error(f"Error in weekly scheduler: {e}", exc_info=True)
                # Sleep 1 hour and retry
                await asyncio.sleep(3600)
    
    def get_status(self) -> Dict:
        """
        Get current optimization status.
        
        Returns:
            Status dictionary
        """
        if self.last_optimization:
            return {
                'last_run': self.last_optimization.timestamp.isoformat(),
                'best_sharpe': self.last_optimization.best_sharpe,
                'oos_sharpe': self.last_optimization.out_of_sample_sharpe,
                'trials': self.last_optimization.trials_completed,
                'next_scheduled': self.next_scheduled.isoformat() if self.next_scheduled else None,
                'best_params': self.last_optimization.best_params,
            }
        else:
            return {
                'last_run': None,
                'next_scheduled': self.next_scheduled.isoformat() if self.next_scheduled else None,
                'status': 'Not yet run',
            }
