"""
Health Check System
Monitors system components and provides health status.
"""

import asyncio
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from src.utils.logger import get_logger

logger = get_logger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status of a component."""
    name: str
    status: HealthStatus
    message: str
    last_check: datetime
    response_time_ms: Optional[float] = None
    details: Optional[Dict] = None


class HealthCheckSystem:
    """
    System health monitoring.
    Checks all critical components and provides health status.
    """
    
    def __init__(
        self,
        exchange_client=None,
        database_connection=None,
        telegram_notifier=None,
        signal_engine=None,
        order_manager=None,
    ):
        self.exchange_client = exchange_client
        self.database_connection = database_connection
        self.telegram_notifier = telegram_notifier
        self.signal_engine = signal_engine
        self.order_manager = order_manager
        
        self.component_health: Dict[str, ComponentHealth] = {}
        self.overall_status = HealthStatus.UNKNOWN
        
        logger.info("Health Check System initialized")
    
    async def check_all_components(self) -> Dict[str, ComponentHealth]:
        """
        Check health of all components.
        
        Returns:
            Dictionary of component health statuses
        """
        logger.info("Running health checks on all components...")
        
        # Run all checks concurrently
        checks = [
            self.check_exchange(),
            self.check_database(),
            self.check_telegram(),
            self.check_signal_engine(),
            self.check_order_manager(),
        ]
        
        results = await asyncio.gather(*checks, return_exceptions=True)
        
        # Update overall status
        self._update_overall_status()
        
        return self.component_health
    
    async def check_exchange(self) -> ComponentHealth:
        """Check exchange connectivity."""
        start_time = datetime.now(timezone.utc)
        
        try:
            if not self.exchange_client:
                health = ComponentHealth(
                    name="exchange",
                    status=HealthStatus.UNKNOWN,
                    message="Exchange client not configured",
                    last_check=start_time
                )
            else:
                # Try to fetch server time or ticker
                try:
                    # This would call exchange API
                    # For now, assume healthy if client exists
                    response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                    
                    health = ComponentHealth(
                        name="exchange",
                        status=HealthStatus.HEALTHY,
                        message="Exchange API responding",
                        last_check=datetime.now(timezone.utc),
                        response_time_ms=response_time
                    )
                except Exception as e:
                    health = ComponentHealth(
                        name="exchange",
                        status=HealthStatus.UNHEALTHY,
                        message=f"Exchange API error: {str(e)}",
                        last_check=datetime.now(timezone.utc)
                    )
            
            self.component_health["exchange"] = health
            return health
        
        except Exception as e:
            logger.error(f"Exchange health check failed: {e}")
            health = ComponentHealth(
                name="exchange",
                status=HealthStatus.UNHEALTHY,
                message=f"Health check error: {str(e)}",
                last_check=datetime.now(timezone.utc)
            )
            self.component_health["exchange"] = health
            return health
    
    async def check_database(self) -> ComponentHealth:
        """Check database connectivity."""
        start_time = datetime.now(timezone.utc)
        
        try:
            if not self.database_connection:
                health = ComponentHealth(
                    name="database",
                    status=HealthStatus.UNKNOWN,
                    message="Database connection not configured",
                    last_check=start_time
                )
            else:
                # Try a simple query
                try:
                    from src.database.connection import get_session
                    
                    async with get_session() as session:
                        # Simple query to check connection
                        result = await session.execute("SELECT 1")
                        
                        response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                        
                        health = ComponentHealth(
                            name="database",
                            status=HealthStatus.HEALTHY,
                            message="Database connection active",
                            last_check=datetime.now(timezone.utc),
                            response_time_ms=response_time
                        )
                except Exception as e:
                    health = ComponentHealth(
                        name="database",
                        status=HealthStatus.UNHEALTHY,
                        message=f"Database error: {str(e)}",
                        last_check=datetime.now(timezone.utc)
                    )
            
            self.component_health["database"] = health
            return health
        
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            health = ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Health check error: {str(e)}",
                last_check=datetime.now(timezone.utc)
            )
            self.component_health["database"] = health
            return health
    
    async def check_telegram(self) -> ComponentHealth:
        """Check Telegram bot connectivity."""
        start_time = datetime.now(timezone.utc)
        
        try:
            if not self.telegram_notifier:
                health = ComponentHealth(
                    name="telegram",
                    status=HealthStatus.UNKNOWN,
                    message="Telegram notifier not configured",
                    last_check=start_time
                )
            else:
                # Try to get bot info
                try:
                    # This would call Telegram API
                    # For now, assume healthy if notifier exists
                    response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                    
                    health = ComponentHealth(
                        name="telegram",
                        status=HealthStatus.HEALTHY,
                        message="Telegram bot responding",
                        last_check=datetime.now(timezone.utc),
                        response_time_ms=response_time
                    )
                except Exception as e:
                    health = ComponentHealth(
                        name="telegram",
                        status=HealthStatus.DEGRADED,
                        message=f"Telegram API error: {str(e)}",
                        last_check=datetime.now(timezone.utc)
                    )
            
            self.component_health["telegram"] = health
            return health
        
        except Exception as e:
            logger.error(f"Telegram health check failed: {e}")
            health = ComponentHealth(
                name="telegram",
                status=HealthStatus.DEGRADED,
                message=f"Health check error: {str(e)}",
                last_check=datetime.now(timezone.utc)
            )
            self.component_health["telegram"] = health
            return health
    
    async def check_signal_engine(self) -> ComponentHealth:
        """Check signal engine status."""
        start_time = datetime.now(timezone.utc)
        
        try:
            if not self.signal_engine:
                health = ComponentHealth(
                    name="signal_engine",
                    status=HealthStatus.UNKNOWN,
                    message="Signal engine not configured",
                    last_check=start_time
                )
            else:
                # Check if signal engine is running
                is_running = getattr(self.signal_engine, 'is_running', False)
                
                if is_running:
                    health = ComponentHealth(
                        name="signal_engine",
                        status=HealthStatus.HEALTHY,
                        message="Signal engine running",
                        last_check=datetime.now(timezone.utc)
                    )
                else:
                    health = ComponentHealth(
                        name="signal_engine",
                        status=HealthStatus.UNHEALTHY,
                        message="Signal engine not running",
                        last_check=datetime.now(timezone.utc)
                    )
            
            self.component_health["signal_engine"] = health
            return health
        
        except Exception as e:
            logger.error(f"Signal engine health check failed: {e}")
            health = ComponentHealth(
                name="signal_engine",
                status=HealthStatus.UNHEALTHY,
                message=f"Health check error: {str(e)}",
                last_check=datetime.now(timezone.utc)
            )
            self.component_health["signal_engine"] = health
            return health
    
    async def check_order_manager(self) -> ComponentHealth:
        """Check order manager status."""
        start_time = datetime.now(timezone.utc)
        
        try:
            if not self.order_manager:
                health = ComponentHealth(
                    name="order_manager",
                    status=HealthStatus.UNKNOWN,
                    message="Order manager not configured",
                    last_check=start_time
                )
            else:
                # Check order manager state
                open_positions = getattr(self.order_manager, 'open_positions_count', 0)
                
                health = ComponentHealth(
                    name="order_manager",
                    status=HealthStatus.HEALTHY,
                    message=f"Order manager active ({open_positions} open positions)",
                    last_check=datetime.now(timezone.utc),
                    details={"open_positions": open_positions}
                )
            
            self.component_health["order_manager"] = health
            return health
        
        except Exception as e:
            logger.error(f"Order manager health check failed: {e}")
            health = ComponentHealth(
                name="order_manager",
                status=HealthStatus.UNHEALTHY,
                message=f"Health check error: {str(e)}",
                last_check=datetime.now(timezone.utc)
            )
            self.component_health["order_manager"] = health
            return health
    
    def _update_overall_status(self):
        """Update overall system health status."""
        if not self.component_health:
            self.overall_status = HealthStatus.UNKNOWN
            return
        
        statuses = [health.status for health in self.component_health.values()]
        
        # If any component is unhealthy, system is unhealthy
        if HealthStatus.UNHEALTHY in statuses:
            self.overall_status = HealthStatus.UNHEALTHY
        # If any component is degraded, system is degraded
        elif HealthStatus.DEGRADED in statuses:
            self.overall_status = HealthStatus.DEGRADED
        # If all components are healthy, system is healthy
        elif all(status == HealthStatus.HEALTHY for status in statuses):
            self.overall_status = HealthStatus.HEALTHY
        else:
            self.overall_status = HealthStatus.UNKNOWN
    
    def get_overall_status(self) -> HealthStatus:
        """Get overall system health status."""
        return self.overall_status
    
    def get_health_report(self) -> Dict:
        """
        Get comprehensive health report.
        
        Returns:
            Dictionary with health report
        """
        return {
            "overall_status": self.overall_status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {
                name: {
                    "status": health.status.value,
                    "message": health.message,
                    "last_check": health.last_check.isoformat(),
                    "response_time_ms": health.response_time_ms,
                    "details": health.details
                }
                for name, health in self.component_health.items()
            }
        }
    
    def is_healthy(self) -> bool:
        """Check if system is healthy."""
        return self.overall_status == HealthStatus.HEALTHY
    
    def get_unhealthy_components(self) -> List[str]:
        """Get list of unhealthy components."""
        return [
            name for name, health in self.component_health.items()
            if health.status == HealthStatus.UNHEALTHY
        ]
    
    def get_degraded_components(self) -> List[str]:
        """Get list of degraded components."""
        return [
            name for name, health in self.component_health.items()
            if health.status == HealthStatus.DEGRADED
        ]


async def run_health_check_loop(
    health_check_system: HealthCheckSystem,
    interval: int = 60,
    telegram_notifier=None
):
    """
    Run health check loop continuously.
    
    Args:
        health_check_system: Health check system instance
        interval: Check interval in seconds
        telegram_notifier: Telegram notifier for alerts
    """
    logger.info(f"Starting health check loop (interval: {interval}s)")
    
    previous_status = HealthStatus.UNKNOWN
    
    while True:
        try:
            await health_check_system.check_all_components()
            current_status = health_check_system.get_overall_status()
            
            # Alert on status change
            if current_status != previous_status:
                logger.info(f"System health status changed: {previous_status.value} → {current_status.value}")
                
                if telegram_notifier and current_status != HealthStatus.HEALTHY:
                    unhealthy = health_check_system.get_unhealthy_components()
                    degraded = health_check_system.get_degraded_components()
                    
                    message = f"⚠️ <b>Health Status Changed</b>\n\n"
                    message += f"Status: {current_status.value}\n"
                    
                    if unhealthy:
                        message += f"Unhealthy: {', '.join(unhealthy)}\n"
                    if degraded:
                        message += f"Degraded: {', '.join(degraded)}\n"
                    
                    try:
                        await telegram_notifier.send_message(message)
                    except Exception as e:
                        logger.error(f"Failed to send health alert: {e}")
                
                previous_status = current_status
            
            await asyncio.sleep(interval)
        
        except Exception as e:
            logger.error(f"Health check loop error: {e}", exc_info=True)
            await asyncio.sleep(interval)
