"""
Pattern Library
Persistent storage and management of validated trading patterns.
"""

import json
from typing import List, Optional, Dict
from datetime import datetime, timezone
from src.database.models import TradingPattern
from src.database.repositories import PatternRepository
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PatternQueryEngine:
    """Advanced pattern search and filtering."""
    
    def __init__(self, repository: PatternRepository):
        self.repository = repository
    
    async def query_patterns(
        self,
        status: str = "active",
        market_regime: Optional[str] = None,
        asset_class: Optional[str] = None,
        min_win_rate: float = 0.55,
    ) -> List[TradingPattern]:
        """Query patterns with advanced filtering."""
        patterns = await self.repository.get_active_patterns(
            market_regime=market_regime,
            asset_class=asset_class,
            min_win_rate=min_win_rate
        )
        
        # Additional filtering by status
        if status:
            patterns = [p for p in patterns if p.status == status]
        
        # Sort by live win rate (best first)
        patterns.sort(key=lambda p: p.live_win_rate, reverse=True)
        
        return patterns
    
    async def get_top_patterns(
        self,
        limit: int = 10,
        market_regime: Optional[str] = None
    ) -> List[TradingPattern]:
        """Get top performing patterns."""
        patterns = await self.query_patterns(
            status="active",
            market_regime=market_regime,
            min_win_rate=0.55
        )
        
        return patterns[:limit]
    
    async def get_patterns_by_symbol(
        self,
        symbol: str,
        min_win_rate: float = 0.55
    ) -> List[TradingPattern]:
        """Get patterns for specific symbol."""
        all_patterns = await self.repository.get_active_patterns(
            min_win_rate=min_win_rate
        )
        
        return [p for p in all_patterns if p.symbol == symbol]


class PatternLibrary:
    """
    Main pattern storage interface.
    Manages validated trading patterns with performance tracking.
    """
    
    def __init__(self, db_connection=None):
        self.db = db_connection
        self.repository = PatternRepository()
        self.query_engine = PatternQueryEngine(self.repository)
    
    async def add_pattern(self, pattern: TradingPattern) -> str:
        """Add validated pattern to library."""
        # Validate pattern has required fields
        if not pattern.id:
            raise ValueError("Pattern must have an ID")
        if not pattern.name:
            raise ValueError("Pattern must have a name")
        if not pattern.entry_conditions:
            raise ValueError("Pattern must have entry conditions")
        if not pattern.exit_conditions:
            raise ValueError("Pattern must have exit conditions")
        if not pattern.validation_metrics:
            raise ValueError("Pattern must have validation metrics")
        
        # Check validation metrics meet minimum thresholds
        metrics = pattern.validation_metrics
        if metrics.get("win_rate", 0) < 0.60:
            raise ValueError(f"Pattern win rate {metrics.get('win_rate', 0):.1%} below 60% threshold")
        if metrics.get("profit_factor", 0) < 1.8:
            raise ValueError(f"Pattern profit factor {metrics.get('profit_factor', 0):.2f} below 1.8 threshold")
        if metrics.get("sharpe_ratio", 0) < 2.0:
            raise ValueError(f"Pattern Sharpe ratio {metrics.get('sharpe_ratio', 0):.2f} below 2.0 threshold")
        
        # Insert pattern
        pattern_id = await self.repository.insert_pattern(pattern)
        
        logger.info(
            f"Pattern added to library: {pattern.name} (ID: {pattern_id})\n"
            f"  Win Rate: {metrics.get('win_rate', 0):.1%}\n"
            f"  Profit Factor: {metrics.get('profit_factor', 0):.2f}\n"
            f"  Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}"
        )
        
        return pattern_id
    
    async def get_pattern(self, pattern_id: str) -> Optional[TradingPattern]:
        """Retrieve pattern by ID."""
        return await self.repository.get_pattern_by_id(pattern_id)
    
    async def get_active_patterns(
        self,
        market_regime: Optional[str] = None,
        asset_class: Optional[str] = None,
        min_win_rate: float = 0.55,
    ) -> List[TradingPattern]:
        """Get all active patterns matching criteria."""
        return await self.query_engine.query_patterns(
            status="active",
            market_regime=market_regime,
            asset_class=asset_class,
            min_win_rate=min_win_rate
        )
    
    async def update_pattern_performance(
        self,
        pattern_id: str,
        trade_result: bool,  # True = win, False = loss
    ):
        """Update pattern performance after trade."""
        pattern = await self.get_pattern(pattern_id)
        if not pattern:
            logger.warning(f"Pattern {pattern_id} not found for performance update")
            return
        
        # Update usage count
        pattern.usage_count += 1
        
        # Update live win rate
        wins = int(pattern.live_win_rate * (pattern.usage_count - 1))
        if trade_result:
            wins += 1
        pattern.live_win_rate = wins / pattern.usage_count
        
        # Update pattern in database
        await self.repository.update_pattern(pattern)
        
        logger.info(
            f"Pattern {pattern.name} performance updated: "
            f"usage={pattern.usage_count}, win_rate={pattern.live_win_rate:.1%}"
        )
        
        # Check if pattern should be deprecated
        if pattern.usage_count >= 30 and pattern.live_win_rate < 0.58:
            await self.deprecate_pattern(
                pattern_id,
                reason=f"Win rate dropped to {pattern.live_win_rate:.1%} over {pattern.usage_count} trades"
            )
    
    async def deprecate_pattern(self, pattern_id: str, reason: str):
        """Mark pattern as deprecated."""
        await self.repository.update_pattern_status(
            pattern_id=pattern_id,
            status="deprecated",
            reason=reason
        )
        
        logger.warning(f"Pattern {pattern_id} deprecated: {reason}")
    
    async def export_patterns(self, output_path: str):
        """Export patterns to JSON for backup."""
        patterns = await self.get_active_patterns()
        
        data = []
        for pattern in patterns:
            pattern_dict = {
                "id": pattern.id,
                "name": pattern.name,
                "symbol": pattern.symbol,
                "asset_class": pattern.asset_class,
                "entry_conditions": pattern.entry_conditions,
                "exit_conditions": pattern.exit_conditions,
                "market_regime": pattern.market_regime,
                "timeframe": pattern.timeframe,
                "discovery_date": pattern.discovery_date.isoformat() if pattern.discovery_date else None,
                "validation_metrics": pattern.validation_metrics,
                "usage_count": pattern.usage_count,
                "live_win_rate": pattern.live_win_rate,
                "live_profit_factor": pattern.live_profit_factor,
                "status": pattern.status,
            }
            data.append(pattern_dict)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Exported {len(patterns)} patterns to {output_path}")
    
    async def import_patterns(self, input_path: str) -> int:
        """Import patterns from JSON file."""
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        imported_count = 0
        for pattern_dict in data:
            try:
                pattern = TradingPattern(
                    id=pattern_dict["id"],
                    name=pattern_dict["name"],
                    symbol=pattern_dict["symbol"],
                    asset_class=pattern_dict.get("asset_class"),
                    entry_conditions=pattern_dict["entry_conditions"],
                    exit_conditions=pattern_dict["exit_conditions"],
                    market_regime=pattern_dict.get("market_regime"),
                    timeframe=pattern_dict.get("timeframe"),
                    discovery_date=datetime.fromisoformat(pattern_dict["discovery_date"]) if pattern_dict.get("discovery_date") else datetime.now(timezone.utc),
                    validation_metrics=pattern_dict["validation_metrics"],
                    usage_count=pattern_dict.get("usage_count", 0),
                    live_win_rate=pattern_dict.get("live_win_rate", 0.0),
                    live_profit_factor=pattern_dict.get("live_profit_factor", 0.0),
                    status=pattern_dict.get("status", "active"),
                )
                
                await self.add_pattern(pattern)
                imported_count += 1
            
            except Exception as e:
                logger.error(f"Failed to import pattern {pattern_dict.get('id')}: {e}")
        
        logger.info(f"Imported {imported_count}/{len(data)} patterns from {input_path}")
        return imported_count
    
    async def get_statistics(self) -> Dict:
        """Get overall pattern library statistics (alias for get_pattern_statistics)."""
        return await self.get_pattern_statistics()

    async def get_top_patterns(self, limit: int = 10, market_regime: Optional[str] = None) -> List[TradingPattern]:
        """Get top performing patterns (delegates to query engine)."""
        return await self.query_engine.get_top_patterns(limit=limit, market_regime=market_regime)

    async def activate_pattern(self, pattern_id: str) -> bool:
        """Activate a pattern."""
        try:
            await self.repository.update_pattern_status(pattern_id=pattern_id, status="active", reason="Manual activation")
            return True
        except Exception:
            return False

    async def deactivate_pattern(self, pattern_id: str) -> bool:
        """Deactivate a pattern."""
        try:
            await self.repository.update_pattern_status(pattern_id=pattern_id, status="inactive", reason="Manual deactivation")
            return True
        except Exception:
            return False
        """Get overall pattern library statistics."""
        all_patterns = await self.repository.get_active_patterns(min_win_rate=0.0)
        active_patterns = [p for p in all_patterns if p.status == "active"]
        deprecated_patterns = [p for p in all_patterns if p.status == "deprecated"]
        
        if not all_patterns:
            return {
                "total_patterns": 0,
                "active_patterns": 0,
                "deprecated_patterns": 0,
                "avg_win_rate": 0.0,
                "avg_usage_count": 0.0,
                "top_pattern": None,
            }
        
        # Calculate statistics
        avg_win_rate = sum(p.live_win_rate for p in active_patterns) / len(active_patterns) if active_patterns else 0.0
        avg_usage = sum(p.usage_count for p in active_patterns) / len(active_patterns) if active_patterns else 0.0
        
        # Find top pattern
        top_pattern = max(active_patterns, key=lambda p: p.live_win_rate) if active_patterns else None
        
        # Group by market regime
        regime_counts = {}
        for pattern in active_patterns:
            regime = pattern.market_regime or "unknown"
            regime_counts[regime] = regime_counts.get(regime, 0) + 1
        
        return {
            "total_patterns": len(all_patterns),
            "active_patterns": len(active_patterns),
            "deprecated_patterns": len(deprecated_patterns),
            "avg_win_rate": avg_win_rate,
            "avg_usage_count": avg_usage,
            "top_pattern": {
                "name": top_pattern.name,
                "win_rate": top_pattern.live_win_rate,
                "usage_count": top_pattern.usage_count,
            } if top_pattern else None,
            "patterns_by_regime": regime_counts,
        }
