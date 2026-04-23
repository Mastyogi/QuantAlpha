"""
Unit tests for Error Handler
"""
import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch
from src.core.error_handler import (
    ErrorHandler,
    ErrorSeverity,
    ComponentType,
    ErrorContext,
    ExponentialBackoff,
)


@pytest.fixture
def error_handler():
    """Create ErrorHandler instance."""
    return ErrorHandler()


@pytest.fixture
def mock_telegram():
    """Mock Telegram notifier."""
    notifier = Mock()
    notifier.send_message = AsyncMock()
    return notifier


@pytest.mark.asyncio
async def test_handle_error_basic(error_handler):
    """Test basic error handling."""
    error = Exception("Test error")
    
    context = await error_handler.handle_error(
        component=ComponentType.EXCHANGE,
        error=error,
        severity=ErrorSeverity.MEDIUM,
    )
    
    assert isinstance(context, ErrorContext)
    assert context.component == ComponentType.EXCHANGE
    assert context.error_type == "Exception"
    assert context.error_message == "Test error"
    assert context.severity == ErrorSeverity.MEDIUM


@pytest.mark.asyncio
async def test_circuit_breaker_activation(error_handler):
    """Test circuit breaker activates after threshold errors."""
    error = Exception("Repeated error")
    
    # Generate errors to trigger circuit breaker
    for i in range(15):
        await error_handler.handle_error(
            component=ComponentType.EXCHANGE,
            error=error,
            severity=ErrorSeverity.HIGH,
        )
    
    # Circuit breaker should be activated
    assert ComponentType.EXCHANGE in error_handler.circuit_breaker_state
    assert not error_handler.is_component_healthy(ComponentType.EXCHANGE)


@pytest.mark.asyncio
async def test_exponential_backoff():
    """Test exponential backoff calculation."""
    backoff = ExponentialBackoff(base_delay=1.0, max_delay=60.0)
    
    delay0 = backoff.get_delay(0)
    delay1 = backoff.get_delay(1)
    delay2 = backoff.get_delay(2)
    delay3 = backoff.get_delay(3)
    
    # Delays should increase exponentially
    assert delay0 < delay1 < delay2 < delay3
    
    # Should not exceed max_delay
    delay_large = backoff.get_delay(100)
    assert delay_large <= 60.0


@pytest.mark.asyncio
async def test_critical_error_notification(error_handler, mock_telegram):
    """Test that critical errors trigger Telegram notification."""
    error_handler.telegram_notifier = mock_telegram
    
    error = Exception("Critical error")
    
    await error_handler.handle_error(
        component=ComponentType.DATABASE,
        error=error,
        severity=ErrorSeverity.CRITICAL,
    )
    
    # Should have sent Telegram notification
    mock_telegram.send_message.assert_called_once()
    call_args = mock_telegram.send_message.call_args[0][0]
    assert "CRITICAL" in call_args or "🚨" in call_args


@pytest.mark.asyncio
async def test_component_health_tracking(error_handler):
    """Test component health tracking."""
    # Initially all components should be healthy
    assert error_handler.is_component_healthy(ComponentType.EXCHANGE)
    
    # After database error, database should be unhealthy
    await error_handler.handle_database_error(
        error=Exception("DB error"),
        operation="insert",
    )
    
    assert not error_handler.is_component_healthy(ComponentType.DATABASE)


@pytest.mark.asyncio
async def test_error_count_tracking(error_handler):
    """Test error count tracking per component."""
    error = Exception("Test error")
    
    initial_count = error_handler.get_error_count(ComponentType.EXCHANGE)
    
    await error_handler.handle_error(
        component=ComponentType.EXCHANGE,
        error=error,
        severity=ErrorSeverity.MEDIUM,
    )
    
    new_count = error_handler.get_error_count(ComponentType.EXCHANGE)
    assert new_count == initial_count + 1


@pytest.mark.asyncio
async def test_error_count_reset(error_handler):
    """Test error count reset."""
    error = Exception("Test error")
    
    # Generate some errors
    for _ in range(5):
        await error_handler.handle_error(
            component=ComponentType.EXCHANGE,
            error=error,
            severity=ErrorSeverity.MEDIUM,
        )
    
    assert error_handler.get_error_count(ComponentType.EXCHANGE) == 5
    
    # Reset count
    error_handler.reset_error_count(ComponentType.EXCHANGE)
    
    assert error_handler.get_error_count(ComponentType.EXCHANGE) == 0
