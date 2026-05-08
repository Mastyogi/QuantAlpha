from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import Trade, Signal, BotMetrics, TradeStatus, TradeDirection
from src.database.connection import get_session, is_db_available
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TradeRepository:
    """Data access layer for Trade records. Gracefully handles DB unavailability."""

    async def create_trade(self, trade_data: dict) -> Optional[Trade]:
        if not is_db_available():
            logger.debug("DB unavailable - trade not persisted to DB")
            # Return a mock trade object with an ID
            trade = Trade(**trade_data)
            trade.id = id(trade)  # Use object id as fake DB id
            return trade
        async with get_session() as session:
            if session is None:
                trade = Trade(**trade_data)
                trade.id = id(trade)
                return trade
            trade = Trade(**trade_data)
            session.add(trade)
            await session.flush()
            await session.refresh(trade)
            logger.info(f"Trade created: {trade.symbol} {trade.direction} id={trade.id}")
            return trade

    async def get_trade_by_order_id(self, order_id: str) -> Optional[Trade]:
        if not is_db_available():
            return None
        async with get_session() as session:
            if session is None:
                return None
            result = await session.execute(
                select(Trade).where(Trade.order_id == order_id)
            )
            return result.scalar_one_or_none()

    async def get_open_trades(self) -> List[Trade]:
        if not is_db_available():
            return []
        async with get_session() as session:
            if session is None:
                return []
            result = await session.execute(
                select(Trade).where(Trade.status == TradeStatus.OPEN)
            )
            return list(result.scalars().all())

    async def close_trade(self, order_id: str, exit_price: float, pnl: float, pnl_pct: float) -> Optional[Trade]:
        if not is_db_available():
            return None
        async with get_session() as session:
            if session is None:
                return None
            result = await session.execute(
                select(Trade).where(Trade.order_id == order_id)
            )
            trade = result.scalar_one_or_none()
            if trade:
                trade.exit_price = exit_price
                trade.pnl = pnl
                trade.pnl_pct = pnl_pct
                trade.status = TradeStatus.CLOSED
                trade.closed_at = datetime.now(timezone.utc)
            return trade

    async def get_daily_stats(self) -> dict:
        if not is_db_available():
            return {"total_trades": 0, "total_pnl": 0.0, "message": "DB offline"}
        async with get_session() as session:
            if session is None:
                return {"total_trades": 0, "total_pnl": 0.0, "message": "DB offline"}
            today = datetime.now(timezone.utc).date()
            result = await session.execute(
                select(
                    func.count(Trade.id).label("total"),
                    func.sum(Trade.pnl).label("total_pnl"),
                ).where(
                    Trade.status == TradeStatus.CLOSED,
                    func.date(Trade.closed_at) == today,
                )
            )
            row = result.one()
            wins_result = await session.execute(
                select(func.count(Trade.id)).where(
                    Trade.status == TradeStatus.CLOSED,
                    Trade.pnl > 0,
                    func.date(Trade.closed_at) == today,
                )
            )
            winning = wins_result.scalar() or 0
            return {
                "total_trades": row.total or 0,
                "winning_trades": winning,
                "total_pnl": row.total_pnl or 0.0,
            }

    async def get_recent_trades(self, limit: int = 20) -> List[Trade]:
        async with get_session() as session:
            result = await session.execute(
                select(Trade).order_by(Trade.created_at.desc()).limit(limit)
            )
            return list(result.scalars().all())

    async def get_trades_in_range(self, start_date: datetime, end_date: datetime) -> List[Trade]:
        if not is_db_available():
            return []
        async with get_session() as session:
            if session is None:
                return []
            result = await session.execute(
                select(Trade).where(
                    Trade.status == TradeStatus.CLOSED,
                    Trade.closed_at >= start_date,
                    Trade.closed_at <= end_date
                ).order_by(Trade.closed_at.asc())
            )
            return list(result.scalars().all())


class SignalRepository:
    """Data access layer for Signal records. Gracefully handles DB unavailability."""

    async def create_signal(self, signal_data: dict) -> Optional[Signal]:
        if not is_db_available():
            return None
        async with get_session() as session:
            if session is None:
                return None
            try:
                signal = Signal(**signal_data)
                session.add(signal)
                await session.flush()
                await session.refresh(signal)
                return signal
            except Exception as e:
                logger.debug(f"Signal DB log failed: {e}")
                return None

    async def get_recent_signals(self, limit: int = 20) -> List[Signal]:
        if not is_db_available():
            return []
        async with get_session() as session:
            if session is None:
                return []
            result = await session.execute(
                select(Signal).order_by(Signal.created_at.desc()).limit(limit)
            )
            return list(result.scalars().all())

    async def mark_acted_upon(self, signal_id: int):
        if not is_db_available():
            return
        async with get_session() as session:
            if session is None:
                return
            await session.execute(
                update(Signal).where(Signal.id == signal_id).values(acted_upon=True)
            )


class MetricsRepository:
    """Data access layer for BotMetrics records."""

    async def record_metrics(self, metrics_data: dict) -> Optional[BotMetrics]:
        if not is_db_available():
            return None
        async with get_session() as session:
            if session is None:
                return None
            metric = BotMetrics(**metrics_data)
            session.add(metric)
            await session.flush()
            return metric


# ============================================================================
# Self-Improvement System Repositories
# ============================================================================

from src.database.models import (
    TradingPattern, ModelVersion, PerformanceHistory,
    ApprovalHistory, EquityHistory, ParameterChange, AuditLog
)


class PatternRepository:
    """Data access layer for TradingPattern records."""
    
    async def insert_pattern(self, pattern: TradingPattern) -> str:
        """Insert new trading pattern."""
        async with get_session() as session:
            session.add(pattern)
            await session.flush()
            await session.refresh(pattern)
            logger.info(f"Pattern inserted: {pattern.name} (ID: {pattern.id})")
            return pattern.id
    
    async def get_pattern_by_id(self, pattern_id: str) -> Optional[TradingPattern]:
        """Get pattern by ID."""
        async with get_session() as session:
            result = await session.execute(
                select(TradingPattern).where(TradingPattern.id == pattern_id)
            )
            return result.scalar_one_or_none()
    
    async def get_active_patterns(
        self,
        market_regime: Optional[str] = None,
        asset_class: Optional[str] = None,
        min_win_rate: float = 0.55
    ) -> List[TradingPattern]:
        """Get all active patterns matching criteria."""
        async with get_session() as session:
            query = select(TradingPattern).where(TradingPattern.status == "active")
            
            if market_regime:
                query = query.where(TradingPattern.market_regime == market_regime)
            if asset_class:
                query = query.where(TradingPattern.asset_class == asset_class)
            
            query = query.where(TradingPattern.live_win_rate >= min_win_rate)
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def update_pattern(self, pattern: TradingPattern):
        """Update existing pattern."""
        async with get_session() as session:
            await session.merge(pattern)
            logger.info(f"Pattern updated: {pattern.id}")
    
    async def update_pattern_status(self, pattern_id: str, status: str, reason: str = None):
        """Update pattern status."""
        async with get_session() as session:
            await session.execute(
                update(TradingPattern)
                .where(TradingPattern.id == pattern_id)
                .values(status=status, deprecation_reason=reason)
            )
            logger.info(f"Pattern {pattern_id} status updated to {status}")


class ModelVersionRepository:
    """Data access layer for ModelVersion records."""
    
    async def insert_version(self, version: ModelVersion) -> int:
        """Insert new model version."""
        async with get_session() as session:
            session.add(version)
            await session.flush()
            await session.refresh(version)
            logger.info(f"Model version inserted: {version.symbol} v{version.version}")
            return version.id
    
    async def get_active_version(self, symbol: str) -> Optional[ModelVersion]:
        """Get active model version for symbol."""
        async with get_session() as session:
            result = await session.execute(
                select(ModelVersion)
                .where(ModelVersion.symbol == symbol, ModelVersion.status == "active")
                .order_by(ModelVersion.deployed_at.desc())
            )
            return result.scalar_one_or_none()
    
    async def get_previous_version(self, symbol: str) -> Optional[ModelVersion]:
        """Get previous model version for rollback."""
        async with get_session() as session:
            result = await session.execute(
                select(ModelVersion)
                .where(ModelVersion.symbol == symbol, ModelVersion.status == "deprecated")
                .order_by(ModelVersion.deprecated_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
    
    async def update_version_status(self, version_id: int, status: str):
        """Update model version status."""
        async with get_session() as session:
            timestamp_field = "deployed_at" if status == "active" else "deprecated_at"
            await session.execute(
                update(ModelVersion)
                .where(ModelVersion.id == version_id)
                .values(status=status, **{timestamp_field: datetime.now(timezone.utc)})
            )


class PerformanceHistoryRepository:
    """Data access layer for PerformanceHistory records."""
    
    async def insert_performance(self, performance: PerformanceHistory) -> int:
        """Insert performance record."""
        async with get_session() as session:
            session.add(performance)
            await session.flush()
            await session.refresh(performance)
            return performance.id
    
    async def get_recent_performance(
        self,
        period: str,
        symbol: Optional[str] = None,
        limit: int = 30
    ) -> List[PerformanceHistory]:
        """Get recent performance records."""
        async with get_session() as session:
            query = select(PerformanceHistory).where(PerformanceHistory.period == period)
            
            if symbol:
                query = query.where(PerformanceHistory.symbol == symbol)
            
            query = query.order_by(PerformanceHistory.timestamp.desc()).limit(limit)
            
            result = await session.execute(query)
            return list(result.scalars().all())


class ApprovalHistoryRepository:
    """Data access layer for ApprovalHistory records."""
    
    async def save_proposal(self, proposal_id: str, proposal: dict) -> int:
        """Save approval proposal."""
        async with get_session() as session:
            approval = ApprovalHistory(
                proposal_id=proposal_id,
                proposal_type=proposal.get("proposal_type", "unknown"),
                proposal_data=proposal
            )
            session.add(approval)
            await session.flush()
            await session.refresh(approval)
            return approval.id
    
    async def log_decision(
        self,
        proposal_id: str,
        decision: str,
        admin_id: str,
        timestamp: datetime
    ):
        """Log approval decision."""
        async with get_session() as session:
            await session.execute(
                update(ApprovalHistory)
                .where(ApprovalHistory.proposal_id == proposal_id)
                .values(
                    decision=decision,
                    admin_id=admin_id,
                    decision_timestamp=timestamp
                )
            )
    
    async def get_proposal(self, proposal_id: str) -> Optional[ApprovalHistory]:
        """Get proposal by ID."""
        async with get_session() as session:
            result = await session.execute(
                select(ApprovalHistory).where(ApprovalHistory.proposal_id == proposal_id)
            )
            return result.scalar_one_or_none()


class EquityHistoryRepository:
    """Data access layer for EquityHistory records."""
    
    async def record_equity(self, equity_data: dict) -> int:
        """Record equity snapshot."""
        async with get_session() as session:
            equity = EquityHistory(**equity_data)
            session.add(equity)
            await session.flush()
            await session.refresh(equity)
            return equity.id
    
    async def get_equity_history(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[EquityHistory]:
        """Get equity history within date range."""
        async with get_session() as session:
            query = select(EquityHistory)
            
            if start_date:
                query = query.where(EquityHistory.timestamp >= start_date)
            if end_date:
                query = query.where(EquityHistory.timestamp <= end_date)
            
            query = query.order_by(EquityHistory.timestamp.desc()).limit(limit)
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def get_latest_equity(self) -> Optional[EquityHistory]:
        """Get most recent equity record."""
        async with get_session() as session:
            result = await session.execute(
                select(EquityHistory)
                .order_by(EquityHistory.timestamp.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()


class ParameterChangeRepository:
    """Data access layer for ParameterChange records."""
    
    async def log_change(self, change_data: dict) -> int:
        """Log parameter change."""
        async with get_session() as session:
            change = ParameterChange(**change_data)
            session.add(change)
            await session.flush()
            await session.refresh(change)
            logger.info(
                f"Parameter change logged: {change.parameter_name} "
                f"{change.old_value} → {change.new_value}"
            )
            return change.id
    
    async def get_last_change(self, parameter_name: Optional[str] = None) -> Optional[ParameterChange]:
        """Get last parameter change."""
        async with get_session() as session:
            query = select(ParameterChange)
            
            if parameter_name:
                query = query.where(ParameterChange.parameter_name == parameter_name)
            
            query = query.order_by(ParameterChange.timestamp.desc()).limit(1)
            
            result = await session.execute(query)
            return result.scalar_one_or_none()
    
    async def get_change_history(
        self,
        parameter_name: Optional[str] = None,
        limit: int = 50
    ) -> List[ParameterChange]:
        """Get parameter change history."""
        async with get_session() as session:
            query = select(ParameterChange)
            
            if parameter_name:
                query = query.where(ParameterChange.parameter_name == parameter_name)
            
            query = query.order_by(ParameterChange.timestamp.desc()).limit(limit)
            
            result = await session.execute(query)
            return list(result.scalars().all())


class AuditLogRepository:
    """Data access layer for AuditLog records."""
    
    async def log_event(
        self,
        event_type: str,
        component: str,
        severity: str,
        message: str,
        details: Optional[dict] = None
    ) -> int:
        """Log audit event."""
        async with get_session() as session:
            log = AuditLog(
                timestamp=datetime.now(timezone.utc),
                event_type=event_type,
                component=component,
                severity=severity,
                message=message,
                details=details
            )
            session.add(log)
            await session.flush()
            await session.refresh(log)
            return log.id
    
    async def query_logs(
        self,
        event_type: Optional[str] = None,
        component: Optional[str] = None,
        severity: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditLog]:
        """Query audit logs with filters."""
        async with get_session() as session:
            query = select(AuditLog)
            
            if event_type:
                query = query.where(AuditLog.event_type == event_type)
            if component:
                query = query.where(AuditLog.component == component)
            if severity:
                query = query.where(AuditLog.severity == severity)
            if start_date:
                query = query.where(AuditLog.timestamp >= start_date)
            if end_date:
                query = query.where(AuditLog.timestamp <= end_date)
            
            query = query.order_by(AuditLog.timestamp.desc()).limit(limit)
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def export_logs_to_csv(
        self,
        output_path: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ):
        """Export logs to CSV file."""
        import csv
        
        logs = await self.query_logs(
            start_date=start_date,
            end_date=end_date,
            limit=10000
        )
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'event_type', 'component', 'severity', 'message', 'details'
            ])
            
            for log in logs:
                writer.writerow([
                    log.timestamp,
                    log.event_type,
                    log.component,
                    log.severity,
                    log.message,
                    str(log.details) if log.details else ''
                ])
        
        logger.info(f"Exported {len(logs)} logs to {output_path}")
