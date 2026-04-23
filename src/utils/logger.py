import logging
import sys
import csv
from typing import Optional, Dict, List
from datetime import datetime, timezone
from enum import Enum


class AuditEventType(Enum):
    """Audit event types for comprehensive logging."""
    SIGNAL_GENERATED = "signal_generated"
    TRADE_EXECUTED = "trade_executed"
    TRADE_EXITED = "trade_exited"
    MODEL_RETRAINED = "model_retrained"
    PARAMETER_CHANGED = "parameter_changed"
    CIRCUIT_BREAKER_ACTIVATED = "circuit_breaker_activated"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"
    PATTERN_DISCOVERED = "pattern_discovered"
    PATTERN_DEPRECATED = "pattern_deprecated"
    EQUITY_UPDATED = "equity_updated"
    TP_HIT = "tp_hit"
    BREAKEVEN_SET = "breakeven_set"
    TRAILING_STOP_UPDATED = "trailing_stop_updated"


class AuditLogger:
    """
    Comprehensive audit logging system.
    Logs all critical events to database for compliance and analysis.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("audit")
        self._audit_repo = None
    
    @property
    def audit_repo(self):
        """Lazy load audit repository to avoid circular imports."""
        if self._audit_repo is None:
            from src.database.repositories import AuditLogRepository
            self._audit_repo = AuditLogRepository()
        return self._audit_repo
    
    async def log_event(
        self,
        event_type: AuditEventType,
        symbol: Optional[str] = None,
        details: Optional[Dict] = None,
        user_id: Optional[str] = None,
    ):
        """
        Log an audit event to database.
        
        Args:
            event_type: Type of event
            symbol: Trading symbol (if applicable)
            details: Additional event details as JSON
            user_id: User/admin who triggered the event (if applicable)
        """
        try:
            await self.audit_repo.create_log({
                "timestamp": datetime.now(timezone.utc),
                "event_type": event_type.value,
                "symbol": symbol,
                "details": details or {},
                "user_id": user_id,
            })
            
            self.logger.info(
                f"Audit: {event_type.value} | "
                f"Symbol: {symbol or 'N/A'} | "
                f"Details: {details}"
            )
        except Exception as e:
            self.logger.error(f"Failed to log audit event: {e}", exc_info=True)
    
    async def log_signal_generated(
        self,
        symbol: str,
        direction: str,
        confidence: float,
        strategy_name: str,
        details: Optional[Dict] = None,
    ):
        """Log signal generation event."""
        await self.log_event(
            event_type=AuditEventType.SIGNAL_GENERATED,
            symbol=symbol,
            details={
                "direction": direction,
                "confidence": confidence,
                "strategy_name": strategy_name,
                **(details or {})
            }
        )
    
    async def log_trade_executed(
        self,
        symbol: str,
        direction: str,
        size_usd: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        order_id: str,
        details: Optional[Dict] = None,
    ):
        """Log trade execution event."""
        await self.log_event(
            event_type=AuditEventType.TRADE_EXECUTED,
            symbol=symbol,
            details={
                "direction": direction,
                "size_usd": size_usd,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "order_id": order_id,
                **(details or {})
            }
        )
    
    async def log_trade_exited(
        self,
        symbol: str,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        exit_reason: str,
        order_id: str,
        details: Optional[Dict] = None,
    ):
        """Log trade exit event."""
        await self.log_event(
            event_type=AuditEventType.TRADE_EXITED,
            symbol=symbol,
            details={
                "exit_price": exit_price,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "exit_reason": exit_reason,
                "order_id": order_id,
                **(details or {})
            }
        )
    
    async def log_model_retrained(
        self,
        symbol: str,
        model_version: str,
        metrics: Dict,
        details: Optional[Dict] = None,
    ):
        """Log model retraining event."""
        await self.log_event(
            event_type=AuditEventType.MODEL_RETRAINED,
            symbol=symbol,
            details={
                "model_version": model_version,
                "metrics": metrics,
                **(details or {})
            }
        )
    
    async def log_parameter_changed(
        self,
        parameter_name: str,
        old_value: any,
        new_value: any,
        reason: str,
        user_id: Optional[str] = None,
        details: Optional[Dict] = None,
    ):
        """Log parameter change event."""
        await self.log_event(
            event_type=AuditEventType.PARAMETER_CHANGED,
            details={
                "parameter_name": parameter_name,
                "old_value": str(old_value),
                "new_value": str(new_value),
                "reason": reason,
                **(details or {})
            },
            user_id=user_id,
        )
    
    async def log_circuit_breaker_activated(
        self,
        reason: str,
        trigger_value: float,
        threshold: float,
        details: Optional[Dict] = None,
    ):
        """Log circuit breaker activation event."""
        await self.log_event(
            event_type=AuditEventType.CIRCUIT_BREAKER_ACTIVATED,
            details={
                "reason": reason,
                "trigger_value": trigger_value,
                "threshold": threshold,
                **(details or {})
            }
        )
    
    async def query_logs(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        symbol: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """
        Query audit logs with filters.
        
        Args:
            start_date: Start date filter
            end_date: End date filter
            symbol: Symbol filter
            event_type: Event type filter
            limit: Maximum number of results
        
        Returns:
            List of audit log entries
        """
        try:
            filters = {}
            if start_date:
                filters["start_date"] = start_date
            if end_date:
                filters["end_date"] = end_date
            if symbol:
                filters["symbol"] = symbol
            if event_type:
                filters["event_type"] = event_type.value
            
            logs = await self.audit_repo.query_logs(filters, limit=limit)
            return logs
        except Exception as e:
            self.logger.error(f"Failed to query audit logs: {e}", exc_info=True)
            return []
    
    async def export_logs_to_csv(
        self,
        filepath: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        symbol: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
    ):
        """
        Export audit logs to CSV file.
        
        Args:
            filepath: Output CSV file path
            start_date: Start date filter
            end_date: End date filter
            symbol: Symbol filter
            event_type: Event type filter
        """
        try:
            logs = await self.query_logs(
                start_date=start_date,
                end_date=end_date,
                symbol=symbol,
                event_type=event_type,
                limit=10000,  # Large limit for export
            )
            
            if not logs:
                self.logger.warning("No logs to export")
                return
            
            # Write to CSV
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['timestamp', 'event_type', 'symbol', 'user_id', 'details']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for log in logs:
                    writer.writerow({
                        'timestamp': log.get('timestamp', ''),
                        'event_type': log.get('event_type', ''),
                        'symbol': log.get('symbol', ''),
                        'user_id': log.get('user_id', ''),
                        'details': str(log.get('details', {})),
                    })
            
            self.logger.info(f"Exported {len(logs)} audit logs to {filepath}")
        except Exception as e:
            self.logger.error(f"Failed to export audit logs: {e}", exc_info=True)


# Global audit logger instance
_audit_logger = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def setup_logging(level: str = "INFO", format: str = "text") -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s %(name)s: %(message)s'
    ))
    logging.basicConfig(level=log_level, handlers=[handler], force=True)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    return logging.getLogger(name or "trading_bot")

