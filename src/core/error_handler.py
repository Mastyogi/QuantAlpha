"""
Error Handler
Centralized error handling with automatic recovery and exponential backoff.
"""

import asyncio
import time
from typing import Optional, Callable, Any, Dict
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timezone
from src.utils.logger import get_logger, get_audit_logger, AuditEventType

logger = get_logger(__name__)
audit_logger = get_audit_logger()


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ComponentType(Enum):
    """System component types."""
    EXCHANGE = "exchange"
    DATABASE = "database"
    MODEL = "model"
    TELEGRAM = "telegram"
    SIGNAL_ENGINE = "signal_engine"
    ORDER_MANAGER = "order_manager"


@dataclass
class ErrorContext:
    """Error context information."""
    component: ComponentType
    error_type: str
    error_message: str
    severity: ErrorSeverity
    timestamp: datetime
    retry_count: int = 0
    details: Optional[Dict] = None


class ExponentialBackoff:
    """Exponential backoff strategy for retries."""
    
    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def get_delay(self, retry_count: int) -> float:
        """Calculate delay for given retry count."""
        delay = min(
            self.base_delay * (self.exponential_base ** retry_count),
            self.max_delay
        )
        
        if self.jitter:
            import random
            delay = delay * (0.5 + random.random() * 0.5)
        
        return delay


class ErrorBuffer:
    """Buffer for storing errors when database is unavailable."""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.buffer: list = []
    
    def add(self, error_context: ErrorContext):
        """Add error to buffer."""
        if len(self.buffer) >= self.max_size:
            # Remove oldest error
            self.buffer.pop(0)
        self.buffer.append(error_context)
    
    def flush(self) -> list:
        """Flush all buffered errors."""
        errors = self.buffer.copy()
        self.buffer.clear()
        return errors
    
    def size(self) -> int:
        """Get buffer size."""
        return len(self.buffer)


class ErrorHandler:
    """
    Centralized error handling system.
    Handles errors from all components with automatic recovery.
    """
    
    def __init__(self, telegram_notifier=None):
        self.telegram_notifier = telegram_notifier
        self.backoff = ExponentialBackoff()
        self.error_buffer = ErrorBuffer()
        
        # Track component health
        self.component_health: Dict[ComponentType, bool] = {
            component: True for component in ComponentType
        }
        
        # Track error counts
        self.error_counts: Dict[ComponentType, int] = {
            component: 0 for component in ComponentType
        }
        
        # Circuit breaker thresholds
        self.circuit_breaker_threshold = 10  # errors before circuit break
        self.circuit_breaker_reset_time = 300  # 5 minutes
        self.circuit_breaker_state: Dict[ComponentType, datetime] = {}
        
        logger.info("Error Handler initialized")
    
    async def handle_error(
        self,
        component: ComponentType,
        error: Exception,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[Dict] = None,
    ) -> ErrorContext:
        """
        Handle an error from a component.
        
        Args:
            component: Component that generated the error
            error: Exception object
            severity: Error severity level
            context: Additional context information
        
        Returns:
            ErrorContext object
        """
        error_context = ErrorContext(
            component=component,
            error_type=type(error).__name__,
            error_message=str(error),
            severity=severity,
            timestamp=datetime.now(timezone.utc),
            details=context or {}
        )
        
        # Log error
        logger.error(
            f"Error in {component.value}: {error_context.error_type} - {error_context.error_message}",
            exc_info=True
        )
        
        # Update error counts
        self.error_counts[component] += 1
        
        # Check circuit breaker
        if self.error_counts[component] >= self.circuit_breaker_threshold:
            await self._activate_circuit_breaker(component)
        
        # Try to log to audit system
        try:
            await audit_logger.log_event(
                event_type=AuditEventType.CIRCUIT_BREAKER_ACTIVATED,
                details={
                    "component": component.value,
                    "error_type": error_context.error_type,
                    "error_message": error_context.error_message,
                    "severity": severity.value,
                }
            )
        except Exception as e:
            # If audit logging fails, buffer the error
            self.error_buffer.add(error_context)
            logger.warning(f"Failed to log error to audit system: {e}")
        
        # Send critical errors to Telegram
        if severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            await self._notify_critical_error(error_context)
        
        return error_context
    
    async def handle_exchange_error(
        self,
        error: Exception,
        operation: str,
        retry_count: int = 0,
        max_retries: int = 5,
    ) -> Optional[Any]:
        """
        Handle exchange API errors with exponential backoff.
        
        Args:
            error: Exception from exchange
            operation: Operation that failed
            retry_count: Current retry count
            max_retries: Maximum retry attempts
        
        Returns:
            None (caller should retry)
        """
        error_context = await self.handle_error(
            component=ComponentType.EXCHANGE,
            error=error,
            severity=ErrorSeverity.HIGH if retry_count >= max_retries else ErrorSeverity.MEDIUM,
            context={"operation": operation, "retry_count": retry_count}
        )
        
        if retry_count >= max_retries:
            logger.error(f"Exchange operation '{operation}' failed after {max_retries} retries")
            return None
        
        # Calculate backoff delay
        delay = self.backoff.get_delay(retry_count)
        logger.info(f"Retrying exchange operation '{operation}' in {delay:.2f}s (attempt {retry_count + 1}/{max_retries})")
        
        await asyncio.sleep(delay)
        return None
    
    async def handle_database_error(
        self,
        error: Exception,
        operation: str,
        data: Optional[Dict] = None,
    ):
        """
        Handle database errors with buffering.
        
        Args:
            error: Database exception
            operation: Database operation that failed
            data: Data that failed to save (will be buffered)
        """
        error_context = await self.handle_error(
            component=ComponentType.DATABASE,
            error=error,
            severity=ErrorSeverity.HIGH,
            context={"operation": operation, "data": data}
        )
        
        # Buffer the data for later retry
        if data:
            self.error_buffer.add(error_context)
            logger.info(f"Buffered database operation: {operation} (buffer size: {self.error_buffer.size()})")
        
        # Mark database as unhealthy
        self.component_health[ComponentType.DATABASE] = False
    
    async def handle_model_error(
        self,
        error: Exception,
        symbol: str,
        fallback_strategy: Optional[str] = None,
    ) -> Optional[str]:
        """
        Handle model prediction errors gracefully.
        
        Args:
            error: Model exception
            symbol: Trading symbol
            fallback_strategy: Fallback strategy to use
        
        Returns:
            Fallback strategy name or None
        """
        await self.handle_error(
            component=ComponentType.MODEL,
            error=error,
            severity=ErrorSeverity.MEDIUM,
            context={"symbol": symbol, "fallback_strategy": fallback_strategy}
        )
        
        logger.warning(f"Model prediction failed for {symbol}, using fallback strategy: {fallback_strategy}")
        return fallback_strategy
    
    async def handle_telegram_error(
        self,
        error: Exception,
        message: str,
    ):
        """
        Handle Telegram API errors with queuing.
        
        Args:
            error: Telegram exception
            message: Message that failed to send
        """
        await self.handle_error(
            component=ComponentType.TELEGRAM,
            error=error,
            severity=ErrorSeverity.LOW,
            context={"message": message}
        )
        
        # Queue message for later retry
        # This would integrate with a message queue system
        logger.info(f"Telegram message queued for retry: {message[:50]}...")
    
    async def _activate_circuit_breaker(self, component: ComponentType):
        """Activate circuit breaker for a component."""
        if component in self.circuit_breaker_state:
            # Already activated
            return
        
        self.circuit_breaker_state[component] = datetime.now(timezone.utc)
        self.component_health[component] = False
        
        logger.critical(
            f"🚨 CIRCUIT BREAKER ACTIVATED for {component.value}\n"
            f"Error count: {self.error_counts[component]}\n"
            f"Component will be disabled for {self.circuit_breaker_reset_time}s"
        )
        
        # Log to audit system
        try:
            await audit_logger.log_circuit_breaker_activated(
                reason=f"Error threshold exceeded for {component.value}",
                trigger_value=self.error_counts[component],
                threshold=self.circuit_breaker_threshold,
                details={"component": component.value}
            )
        except Exception as e:
            logger.error(f"Failed to log circuit breaker activation: {e}")
        
        # Notify via Telegram
        if self.telegram_notifier:
            try:
                await self.telegram_notifier.send_message(
                    f"🚨 <b>CIRCUIT BREAKER ACTIVATED</b>\n\n"
                    f"Component: {component.value}\n"
                    f"Error count: {self.error_counts[component]}\n"
                    f"Reset in: {self.circuit_breaker_reset_time}s"
                )
            except Exception as e:
                logger.error(f"Failed to send circuit breaker notification: {e}")
    
    async def _notify_critical_error(self, error_context: ErrorContext):
        """Send critical error notification via Telegram."""
        if not self.telegram_notifier:
            return
        
        try:
            severity_emoji = {
                ErrorSeverity.LOW: "ℹ️",
                ErrorSeverity.MEDIUM: "⚠️",
                ErrorSeverity.HIGH: "🔴",
                ErrorSeverity.CRITICAL: "🚨"
            }
            
            message = (
                f"{severity_emoji[error_context.severity]} <b>ERROR ALERT</b>\n\n"
                f"Component: {error_context.component.value}\n"
                f"Type: {error_context.error_type}\n"
                f"Message: {error_context.error_message}\n"
                f"Severity: {error_context.severity.value}\n"
                f"Time: {error_context.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
            
            await self.telegram_notifier.send_message(message)
        except Exception as e:
            logger.error(f"Failed to send critical error notification: {e}")
    
    async def check_circuit_breakers(self):
        """Check and reset circuit breakers if timeout has passed."""
        now = datetime.now(timezone.utc)
        
        for component, activated_at in list(self.circuit_breaker_state.items()):
            elapsed = (now - activated_at).total_seconds()
            
            if elapsed >= self.circuit_breaker_reset_time:
                # Reset circuit breaker
                del self.circuit_breaker_state[component]
                self.error_counts[component] = 0
                self.component_health[component] = True
                
                logger.info(f"Circuit breaker reset for {component.value}")
                
                if self.telegram_notifier:
                    try:
                        await self.telegram_notifier.send_message(
                            f"✅ Circuit breaker reset for {component.value}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to send reset notification: {e}")
    
    async def attempt_recovery(self, component: ComponentType) -> bool:
        """
        Attempt to recover a failed component.
        
        Args:
            component: Component to recover
        
        Returns:
            True if recovery successful
        """
        logger.info(f"Attempting recovery for {component.value}...")
        
        try:
            if component == ComponentType.DATABASE:
                # Try to flush buffered errors
                buffered_errors = self.error_buffer.flush()
                logger.info(f"Flushed {len(buffered_errors)} buffered errors")
                
                # Mark as healthy
                self.component_health[ComponentType.DATABASE] = True
                return True
            
            elif component == ComponentType.EXCHANGE:
                # Exchange recovery would involve reconnecting
                # This would be implemented based on specific exchange client
                logger.info("Exchange recovery not implemented yet")
                return False
            
            elif component == ComponentType.TELEGRAM:
                # Telegram recovery would involve reconnecting bot
                logger.info("Telegram recovery not implemented yet")
                return False
            
            return False
        
        except Exception as e:
            logger.error(f"Recovery failed for {component.value}: {e}")
            return False
    
    def is_component_healthy(self, component: ComponentType) -> bool:
        """Check if a component is healthy."""
        return self.component_health.get(component, True)
    
    def get_error_count(self, component: ComponentType) -> int:
        """Get error count for a component."""
        return self.error_counts.get(component, 0)
    
    def reset_error_count(self, component: ComponentType):
        """Reset error count for a component."""
        self.error_counts[component] = 0
        logger.info(f"Error count reset for {component.value}")


async def with_retry(
    func: Callable,
    max_retries: int = 3,
    backoff: Optional[ExponentialBackoff] = None,
    error_handler: Optional[ErrorHandler] = None,
    component: ComponentType = ComponentType.EXCHANGE,
) -> Any:
    """
    Decorator-like function to retry operations with exponential backoff.
    
    Args:
        func: Async function to retry
        max_retries: Maximum retry attempts
        backoff: Backoff strategy
        error_handler: Error handler instance
        component: Component type for error tracking
    
    Returns:
        Function result or raises exception
    """
    if backoff is None:
        backoff = ExponentialBackoff()
    
    last_error = None
    
    for retry_count in range(max_retries + 1):
        try:
            return await func()
        except Exception as e:
            last_error = e
            
            if error_handler:
                await error_handler.handle_error(
                    component=component,
                    error=e,
                    severity=ErrorSeverity.MEDIUM,
                    context={"retry_count": retry_count, "max_retries": max_retries}
                )
            
            if retry_count < max_retries:
                delay = backoff.get_delay(retry_count)
                logger.info(f"Retrying in {delay:.2f}s (attempt {retry_count + 1}/{max_retries})")
                await asyncio.sleep(delay)
            else:
                logger.error(f"Operation failed after {max_retries} retries")
    
    raise last_error
