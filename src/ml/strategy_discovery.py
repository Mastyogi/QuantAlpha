"""
Strategy Discovery Module
Automatically discovers and validates profitable trading patterns.
"""

import uuid
from typing import List, Dict, Optional
from datetime import datetime, timezone
from collections import Counter
from src.database.models import Trade, TradingPattern, TradeStatus
from src.database.repositories import TradeRepository
from src.database.pattern_library import PatternLibrary
from src.backtesting.walk_forward import WalkForwardValidator
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PatternExtractor:
    """Extracts patterns from trade history."""
    
    def extract_patterns(self, trades: List[Trade]) -> List[Dict]:
        """Extract potential patterns from winning trades."""
        # Filter winning trades
        winning_trades = [
            t for t in trades 
            if t.status == TradeStatus.CLOSED and t.pnl > 0
        ]
        
        if len(winning_trades) < 10:
            logger.info(f"Insufficient winning trades for pattern extraction: {len(winning_trades)}")
            return []
        
        patterns = []
        
        # Group by common characteristics
        # 1. By symbol + direction
        symbol_direction_groups = {}
        for trade in winning_trades:
            key = f"{trade.symbol}_{trade.direction.value if trade.direction else 'UNKNOWN'}"
            if key not in symbol_direction_groups:
                symbol_direction_groups[key] = []
            symbol_direction_groups[key].append(trade)
        
        # Extract patterns from groups with sufficient trades
        for key, group_trades in symbol_direction_groups.items():
            if len(group_trades) < 5:
                continue
            
            # Calculate average characteristics
            avg_confidence = sum(t.ai_confidence or 0 for t in group_trades) / len(group_trades)
            avg_signal_score = sum(t.signal_score or 0 for t in group_trades) / len(group_trades)
            avg_pnl_pct = sum(t.pnl_pct or 0 for t in group_trades) / len(group_trades)
            
            # Extract common timeframes
            timeframes = [t.timeframe for t in group_trades if t.timeframe]
            most_common_timeframe = Counter(timeframes).most_common(1)[0][0] if timeframes else "1h"
            
            # Extract common strategies
            strategies = [t.strategy_name for t in group_trades if t.strategy_name]
            most_common_strategy = Counter(strategies).most_common(1)[0][0] if strategies else "unknown"
            
            # Create pattern candidate
            symbol, direction = key.split("_")
            pattern = {
                "symbol": symbol,
                "direction": direction,
                "timeframe": most_common_timeframe,
                "strategy": most_common_strategy,
                "avg_confidence": avg_confidence,
                "avg_signal_score": avg_signal_score,
                "avg_pnl_pct": avg_pnl_pct,
                "sample_size": len(group_trades),
                "entry_conditions": {
                    "min_confidence": avg_confidence * 0.9,  # 90% of average
                    "min_signal_score": avg_signal_score * 0.9,
                    "direction": direction,
                    "timeframe": most_common_timeframe,
                },
                "exit_conditions": {
                    "take_profit_pct": avg_pnl_pct * 1.5,  # Target 1.5x average
                    "stop_loss_pct": avg_pnl_pct * 0.5,  # Risk 0.5x average
                },
            }
            
            patterns.append(pattern)
        
        logger.info(f"Extracted {len(patterns)} pattern candidates from {len(winning_trades)} winning trades")
        return patterns


class PatternValidator:
    """Validates patterns using walk-forward testing."""
    
    def __init__(self, data_fetcher=None):
        self.data_fetcher = data_fetcher
        self.validator = WalkForwardValidator(n_folds=5, min_train_bars=200)
    
    async def validate(
        self,
        pattern: Dict,
        min_bars: int = 500
    ) -> Optional[Dict]:
        """Validate pattern using walk-forward testing."""
        if not self.data_fetcher:
            logger.warning("No data fetcher configured for pattern validation")
            return None
        
        symbol = pattern["symbol"]
        
        # Fetch historical data
        df = self.data_fetcher.get_history_df(symbol, bars=min_bars)
        if df is None or len(df) < min_bars:
            logger.warning(f"Insufficient data for {symbol}: {len(df) if df is not None else 0} bars")
            return None
        
        # Run walk-forward validation
        try:
            report = self.validator.validate(df, symbol=symbol)
            
            # Extract validation metrics
            validation_metrics = {
                "win_rate": report.oos_precision,
                "profit_factor": report.win_rate / (1 - report.win_rate) if report.win_rate < 1 else 999,
                "sharpe_ratio": report.sharpe_ratio,
                "max_drawdown_pct": report.max_drawdown_pct,
                "total_trades": report.simulated_trades,
                "n_folds": report.n_folds,
            }
            
            logger.info(
                f"Pattern validation for {symbol}: "
                f"win_rate={validation_metrics['win_rate']:.1%}, "
                f"sharpe={validation_metrics['sharpe_ratio']:.2f}"
            )
            
            return validation_metrics
        
        except Exception as e:
            logger.error(f"Pattern validation failed for {symbol}: {e}", exc_info=True)
            return None


class StrategyDiscoveryModule:
    """
    Main strategy discovery orchestrator.
    Discovers, validates, and stores profitable trading patterns.
    """
    
    def __init__(
        self,
        pattern_library: PatternLibrary,
        data_fetcher=None,
        min_win_rate: float = 0.60,
        min_profit_factor: float = 1.8,
        min_sharpe: float = 2.0,
        min_trades: int = 50,
    ):
        self.pattern_library = pattern_library
        self.data_fetcher = data_fetcher
        self.min_win_rate = min_win_rate
        self.min_profit_factor = min_profit_factor
        self.min_sharpe = min_sharpe
        self.min_trades = min_trades
        
        self.pattern_extractor = PatternExtractor()
        self.pattern_validator = PatternValidator(data_fetcher)
        self.trade_repo = TradeRepository()
    
    async def discover_patterns_monthly(self) -> List[TradingPattern]:
        """Run pattern discovery monthly."""
        logger.info("Starting monthly pattern discovery")
        
        # Get last 90 days of trades
        trades = await self.trade_repo.get_recent_trades(limit=1000)
        
        if len(trades) < 50:
            logger.info(f"Insufficient trades for pattern discovery: {len(trades)}")
            return []
        
        # Extract pattern candidates
        candidates = self.pattern_extractor.extract_patterns(trades)
        
        if not candidates:
            logger.info("No pattern candidates extracted")
            return []
        
        logger.info(f"Extracted {len(candidates)} pattern candidates")
        
        # Validate each pattern
        validated_patterns = []
        for candidate in candidates:
            try:
                validation_result = await self._validate_pattern(candidate)
                if validation_result:
                    validated_patterns.append(validation_result)
            except Exception as e:
                logger.error(f"Pattern validation error: {e}", exc_info=True)
        
        logger.info(f"Validated {len(validated_patterns)}/{len(candidates)} patterns")
        
        # Add validated patterns to library
        added_count = 0
        for pattern in validated_patterns:
            try:
                await self.pattern_library.add_pattern(pattern)
                added_count += 1
            except Exception as e:
                logger.error(f"Failed to add pattern to library: {e}")
        
        logger.info(f"Added {added_count} new patterns to library")
        return validated_patterns
    
    async def _validate_pattern(self, candidate: Dict) -> Optional[TradingPattern]:
        """Validate pattern candidate."""
        # Run walk-forward validation
        validation_metrics = await self.pattern_validator.validate(candidate)
        
        if not validation_metrics:
            return None
        
        # Check if meets minimum thresholds
        if validation_metrics["win_rate"] < self.min_win_rate:
            logger.debug(
                f"Pattern rejected: win_rate {validation_metrics['win_rate']:.1%} "
                f"< {self.min_win_rate:.1%}"
            )
            return None
        
        if validation_metrics["profit_factor"] < self.min_profit_factor:
            logger.debug(
                f"Pattern rejected: profit_factor {validation_metrics['profit_factor']:.2f} "
                f"< {self.min_profit_factor:.2f}"
            )
            return None
        
        if validation_metrics["sharpe_ratio"] < self.min_sharpe:
            logger.debug(
                f"Pattern rejected: sharpe {validation_metrics['sharpe_ratio']:.2f} "
                f"< {self.min_sharpe:.2f}"
            )
            return None
        
        # Create TradingPattern object
        pattern_id = str(uuid.uuid4())
        pattern_name = f"{candidate['symbol']}_{candidate['direction']}_{candidate['timeframe']}"
        
        pattern = TradingPattern(
            id=pattern_id,
            name=pattern_name,
            symbol=candidate["symbol"],
            asset_class="crypto" if "/" in candidate["symbol"] else "forex",
            entry_conditions=candidate["entry_conditions"],
            exit_conditions=candidate["exit_conditions"],
            market_regime="TRENDING",  # Default, can be refined
            timeframe=candidate["timeframe"],
            discovery_date=datetime.now(timezone.utc),
            validation_metrics=validation_metrics,
            usage_count=0,
            live_win_rate=0.0,
            live_profit_factor=0.0,
            status="active",
        )
        
        logger.info(
            f"Pattern validated: {pattern_name}\n"
            f"  Win Rate: {validation_metrics['win_rate']:.1%}\n"
            f"  Profit Factor: {validation_metrics['profit_factor']:.2f}\n"
            f"  Sharpe Ratio: {validation_metrics['sharpe_ratio']:.2f}"
        )
        
        return pattern
    
    async def test_patterns_quarterly(self):
        """Test all patterns quarterly for degradation."""
        logger.info("Starting quarterly pattern degradation test")
        
        active_patterns = await self.pattern_library.get_active_patterns(min_win_rate=0.0)
        
        if not active_patterns:
            logger.info("No active patterns to test")
            return
        
        deprecated_count = 0
        for pattern in active_patterns:
            # Get recent trades for this pattern
            all_trades = await self.trade_repo.get_recent_trades(limit=500)
            pattern_trades = [
                t for t in all_trades 
                if t.pattern_id == pattern.id and t.status == TradeStatus.CLOSED
            ]
            
            if len(pattern_trades) < 30:
                logger.debug(f"Pattern {pattern.name} has insufficient trades: {len(pattern_trades)}")
                continue
            
            # Calculate recent win rate
            wins = sum(1 for t in pattern_trades if t.pnl > 0)
            win_rate = wins / len(pattern_trades)
            
            # Check if degraded
            if win_rate < 0.55:
                await self.pattern_library.deprecate_pattern(
                    pattern.id,
                    reason=f"Win rate dropped to {win_rate:.1%} over {len(pattern_trades)} trades"
                )
                deprecated_count += 1
                logger.warning(
                    f"Pattern {pattern.name} deprecated: "
                    f"win_rate={win_rate:.1%} over {len(pattern_trades)} trades"
                )
        
        logger.info(
            f"Quarterly pattern test complete: "
            f"{deprecated_count} patterns deprecated out of {len(active_patterns)}"
        )
