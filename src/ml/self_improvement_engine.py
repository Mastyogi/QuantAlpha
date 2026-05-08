"""
Self-Improvement Engine
Autonomous learning system that continuously improves model accuracy.
"""

import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from src.ml.performance_tracker import PerformanceTracker, PerformanceMetrics
from src.ml.stacking_ensemble import EnhancedStackingEnsemble
from src.backtesting.walk_forward import WalkForwardValidator, WalkForwardReport
from src.database.repositories import (
    TradeRepository, ModelVersionRepository, ParameterChangeRepository
)
from src.database.models import ModelVersion
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceReport:
    """Daily performance analysis report."""
    timestamp: datetime
    metrics: PerformanceMetrics
    winning_conditions: List[Dict]
    losing_conditions: List[Dict]


class DeploymentManager:
    """Manages model versioning and deployment."""
    
    def __init__(self, model_dir: str = "models"):
        self.model_dir = model_dir
        self.model_repo = ModelVersionRepository()
    
    async def save_version(
        self,
        symbol: str,
        model_path: str,
        metrics: Dict,
        validation_report: WalkForwardReport
    ) -> int:
        """Save new model version to database."""
        version = ModelVersion(
            symbol=symbol,
            version=f"v{int(time.time())}",
            model_path=model_path,
            precision=metrics.get("precision", 0.0),
            recall=metrics.get("recall", 0.0),
            accuracy=metrics.get("accuracy", 0.0),
            auc=metrics.get("auc", 0.0),
            f1_score=metrics.get("f1", 0.0),
            training_samples=metrics.get("n_samples", 0),
            training_date=datetime.now(timezone.utc),
            validation_report={
                "oos_precision": validation_report.oos_precision,
                "oos_auc": validation_report.oos_auc,
                "sharpe_ratio": validation_report.sharpe_ratio,
                "max_drawdown_pct": validation_report.max_drawdown_pct,
                "n_folds": validation_report.n_folds
            },
            status="pending"
        )
        
        version_id = await self.model_repo.insert_version(version)
        logger.info(f"Model version saved: {symbol} v{version.version} (ID: {version_id})")
        return version_id
    
    async def get_current_precision(self, symbol: str) -> float:
        """Get precision of currently active model."""
        active_version = await self.model_repo.get_active_version(symbol)
        if active_version:
            return active_version.precision
        return 0.0
    
    async def deploy_version(self, version_id: int):
        """Deploy model version to production."""
        await self.model_repo.update_version_status(version_id, "active")
        logger.info(f"Model version {version_id} deployed to production")
    
    async def rollback_to_previous(self, symbol: str) -> Optional[ModelVersion]:
        """Rollback to previous model version."""
        previous = await self.model_repo.get_previous_version(symbol)
        if previous:
            await self.model_repo.update_version_status(previous.id, "active")
            logger.info(f"Rolled back {symbol} to version {previous.version}")
        return previous


class SelfImprovementEngine:
    """
    Autonomous learning engine that:
    - Analyzes daily performance
    - Retrains models weekly
    - Adjusts confidence thresholds
    - Proposes improvements for approval
    """
    
    def __init__(
        self,
        model_dir: str = "models",
        data_fetcher = None,
        min_precision_improvement: float = 0.02,  # 2%
        retrain_schedule_hours: int = 168,  # Weekly
        approval_system = None,
    ):
        self.model_dir = model_dir
        self.data_fetcher = data_fetcher
        self.min_improvement = min_precision_improvement
        self.retrain_schedule = retrain_schedule_hours
        self.approval_system = approval_system
        
        self.performance_tracker = PerformanceTracker()
        self.deployment_manager = DeploymentManager(model_dir)
        self.trade_repo = TradeRepository()
        self.param_repo = ParameterChangeRepository()
        
        self._running = False
        self._last_retrain: Dict[str, float] = {}
        self.active_symbols = ["EURUSD", "GBPUSD", "USDJPY"]
    
    async def start(self):
        """Start continuous improvement loops."""
        self._running = True
        asyncio.create_task(self._daily_analysis_loop())
        asyncio.create_task(self._weekly_retrain_loop())
        logger.info("Self-Improvement Engine started")
    
    async def stop(self):
        """Stop improvement loops."""
        self._running = False
        logger.info("Self-Improvement Engine stopped")
    
    async def _daily_analysis_loop(self):
        """Analyze completed trades daily."""
        while self._running:
            await asyncio.sleep(86400)  # 24 hours
            try:
                await self.analyze_daily_performance()
            except Exception as e:
                logger.error(f"Daily analysis failed: {e}", exc_info=True)
    
    async def _weekly_retrain_loop(self):
        """Retrain models weekly."""
        while self._running:
            await asyncio.sleep(self.retrain_schedule * 3600)
            try:
                await self.retrain_all_models()
            except Exception as e:
                logger.error(f"Weekly retrain failed: {e}", exc_info=True)
    
    async def analyze_daily_performance(self) -> PerformanceReport:
        """Analyze last 24h of trading."""
        logger.info("Starting daily performance analysis")
        
        # Get recent trades
        trades = await self.trade_repo.get_recent_trades(limit=100)
        
        # Filter last 24h
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(hours=24)
        recent_trades = [
            t for t in trades 
            if t.closed_at and t.closed_at >= yesterday
        ]
        
        if not recent_trades:
            logger.info("No trades in last 24h")
            return PerformanceReport(
                timestamp=now,
                metrics=PerformanceMetrics(
                    win_rate=0.0, profit_factor=0.0, sharpe_ratio=0.0,
                    sortino_ratio=0.0, max_drawdown=0.0, total_trades=0,
                    winning_trades=0, losing_trades=0, avg_win_pct=0.0,
                    avg_loss_pct=0.0, total_pnl=0.0
                ),
                winning_conditions=[],
                losing_conditions=[]
            )
        
        # Calculate metrics
        metrics = self.performance_tracker.calculate_metrics(recent_trades)
        
        # Extract conditions
        winning_conditions = self.performance_tracker.extract_winning_conditions(recent_trades)
        losing_conditions = self.performance_tracker.extract_losing_conditions(recent_trades)
        
        # Store performance
        await self.performance_tracker.store_performance(
            period="daily",
            metrics=metrics,
            symbol=None,
            strategy_name=None,
            equity=None
        )
        
        # Adjust confidence threshold if needed
        if metrics.win_rate < 0.65 and metrics.total_trades >= 30:
            await self._adjust_confidence_threshold(increase=True)
        
        logger.info(
            f"Daily analysis complete: {metrics.total_trades} trades, "
            f"win rate {metrics.win_rate:.1%}, "
            f"profit factor {metrics.profit_factor:.2f}"
        )
        
        return PerformanceReport(
            timestamp=now,
            metrics=metrics,
            winning_conditions=winning_conditions,
            losing_conditions=losing_conditions
        )
    
    async def _adjust_confidence_threshold(self, increase: bool):
        """Adjust confidence threshold based on performance."""
        # This would integrate with signal engine configuration
        # For now, just log the change
        old_threshold = 0.70  # Default
        new_threshold = old_threshold + 0.02 if increase else old_threshold - 0.02
        new_threshold = max(0.60, min(0.85, new_threshold))
        
        await self.param_repo.log_change({
            "timestamp": datetime.now(timezone.utc),
            "parameter_name": "confidence_threshold",
            "old_value": str(old_threshold),
            "new_value": str(new_threshold),
            "change_reason": f"Win rate adjustment ({'increase' if increase else 'decrease'})",
            "triggered_by": "self_improvement"
        })
        
        logger.info(f"Confidence threshold adjusted: {old_threshold} → {new_threshold}")
    
    async def retrain_all_models(self) -> Dict[str, Dict]:
        """Retrain models for all active symbols."""
        logger.info("Starting weekly model retraining for all symbols")
        
        results = {}
        for symbol in self.active_symbols:
            try:
                result = await self.retrain_model(symbol)
                results[symbol] = result
            except Exception as e:
                logger.error(f"Retrain failed for {symbol}: {e}", exc_info=True)
                results[symbol] = {"success": False, "error": str(e)}
        
        logger.info(f"Weekly retraining complete: {len(results)} symbols processed")
        return results
    
    async def retrain_model(self, symbol: str) -> Dict:
        """Retrain model for specific symbol."""
        logger.info(f"Retraining model for {symbol}")
        
        if not self.data_fetcher:
            logger.warning("No data fetcher configured")
            return {"success": False, "reason": "no_data_fetcher"}
        
        # Fetch recent 2000 bars
        try:
            from src.ai_engine.advanced_features import AdvancedFeaturePipeline
            
            df = self.data_fetcher.get_history_df(symbol, bars=2000)
            if df is None or len(df) < 500:
                logger.warning(f"Insufficient data for {symbol}: {len(df) if df is not None else 0} bars")
                return {"success": False, "reason": "insufficient_data"}
            
            # Prepare features
            pipeline = AdvancedFeaturePipeline()
            X, y = pipeline.prepare_training_data(df)
            
            if len(X) < 200:
                logger.warning(f"Insufficient samples for {symbol}: {len(X)}")
                return {"success": False, "reason": "insufficient_samples"}
            
            # Train new model
            new_model = EnhancedStackingEnsemble(symbol=symbol)
            train_size = int(len(X) * 0.8)
            metrics = new_model.train(X[:train_size], y[:train_size], tune=False)
            
            # Validate with walk-forward
            validator = WalkForwardValidator(n_folds=5)
            validation_report = validator.validate(df, symbol=symbol)
            
            # Compare with current model
            current_precision = await self.deployment_manager.get_current_precision(symbol)
            new_precision = metrics.get("precision", 0.0)
            improvement = new_precision - current_precision
            
            logger.info(
                f"{symbol} retraining complete: "
                f"current={current_precision:.1%}, "
                f"new={new_precision:.1%}, "
                f"improvement={improvement:+.1%}"
            )
            
            # Check if improvement meets threshold
            if improvement >= self.min_improvement:
                # Save model
                model_path = new_model.save(self.model_dir)
                
                # Save version to database
                version_id = await self.deployment_manager.save_version(
                    symbol=symbol,
                    model_path=model_path,
                    metrics=metrics,
                    validation_report=validation_report
                )
                
                # Propose deployment (will be handled by approval system)
                await self._propose_model_deployment(
                    symbol=symbol,
                    version_id=version_id,
                    current_precision=current_precision,
                    new_precision=new_precision,
                    improvement=improvement,
                    validation_report=validation_report
                )
                
                return {
                    "success": True,
                    "symbol": symbol,
                    "current_precision": current_precision,
                    "new_precision": new_precision,
                    "improvement": improvement,
                    "version_id": version_id,
                    "proposed_for_approval": True
                }
            else:
                logger.info(
                    f"{symbol} improvement {improvement:+.1%} below threshold "
                    f"{self.min_improvement:.1%} - not proposing deployment"
                )
                return {
                    "success": True,
                    "symbol": symbol,
                    "current_precision": current_precision,
                    "new_precision": new_precision,
                    "improvement": improvement,
                    "proposed_for_approval": False,
                    "reason": "insufficient_improvement"
                }
        
        except Exception as e:
            logger.error(f"Retrain error for {symbol}: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def _propose_model_deployment(
        self,
        symbol: str,
        version_id: int,
        current_precision: float,
        new_precision: float,
        improvement: float,
        validation_report: WalkForwardReport
    ):
        """Propose model deployment to approval system."""
        logger.info(
            f"📊 Model deployment proposal for {symbol}:\n"
            f"  Current Precision: {current_precision:.1%}\n"
            f"  New Precision: {new_precision:.1%}\n"
            f"  Improvement: {improvement:+.1%}\n"
            f"  OOS Precision: {validation_report.oos_precision:.1%}\n"
            f"  Sharpe Ratio: {validation_report.sharpe_ratio:.2f}\n"
            f"  Max Drawdown: {validation_report.max_drawdown_pct:.1f}%\n"
            f"  Version ID: {version_id}"
        )
        
        # Send to ApprovalSystem if configured
        if self.approval_system:
            from src.telegram.approval_system import ModelDeploymentProposal
            
            proposal = ModelDeploymentProposal(
                timestamp=datetime.now(timezone.utc),
                symbol=symbol,
                version_id=version_id,
                current_precision=current_precision,
                new_precision=new_precision,
                improvement_pct=improvement * 100,
                validation_metrics={
                    "oos_precision": validation_report.oos_precision,
                    "sharpe_ratio": validation_report.sharpe_ratio,
                    "max_drawdown_pct": validation_report.max_drawdown_pct,
                    "n_folds": validation_report.n_folds
                }
            )
            
            await self.approval_system.submit_proposal(proposal)
            logger.info(f"Proposal submitted to approval system for {symbol}")
        else:
            logger.warning("No approval system configured - proposal not submitted")

