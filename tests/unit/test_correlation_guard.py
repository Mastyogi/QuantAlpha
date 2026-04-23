"""
Unit tests for Correlation Guard
"""
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from src.risk.adaptive_risk import AdaptiveRiskManager, RiskCheckResult


@pytest.fixture
def adaptive_risk():
    """Create AdaptiveRiskManager instance."""
    return AdaptiveRiskManager(
        max_risk_pct=2.0,
        account_equity=10000.0,
    )


@pytest.fixture
def mock_correlation_matrix():
    """Mock correlation matrix."""
    return {
        "BTCUSDT": {
            "ETHUSDT": 0.85,
            "BNBUSDT": 0.75,
            "ADAUSDT": 0.60,
        },
        "ETHUSDT": {
            "BTCUSDT": 0.85,
            "BNBUSDT": 0.80,
        },
        "BNBUSDT": {
            "BTCUSDT": 0.75,
            "ETHUSDT": 0.80,
        }
    }


@pytest.mark.asyncio
async def test_no_open_positions(adaptive_risk):
    """Test correlation guard with no open positions."""
    result = await adaptive_risk.check_correlation_guard(
        symbol="BTC/USDT",
        open_positions=[],
    )
    
    assert result.approved is True
    assert result.position_size_adjustment == 1.0
    assert "No open positions" in result.reason


@pytest.mark.asyncio
async def test_high_correlation_blocks_trade(adaptive_risk, mock_correlation_matrix):
    """Test that high correlation (>90%) blocks trade."""
    open_positions = [{"symbol": "ETH/USDT"}]
    
    # Mock correlation matrix with very high correlation
    high_corr_matrix = {
        "BTCUSDT": {"ETHUSDT": 0.95},
        "ETHUSDT": {"BTCUSDT": 0.95}
    }
    
    with patch.object(adaptive_risk, '_get_redis') as mock_redis:
        mock_client = AsyncMock()
        mock_client.get.return_value = json.dumps(high_corr_matrix)
        mock_redis.return_value = mock_client
        
        result = await adaptive_risk.check_correlation_guard(
            symbol="BTC/USDT",
            open_positions=open_positions,
        )
        
        assert result.approved is False
        assert result.position_size_adjustment == 0.0
        assert "High correlation" in result.reason


@pytest.mark.asyncio
async def test_moderate_correlation_reduces_size(adaptive_risk, mock_correlation_matrix):
    """Test that moderate correlation (70-90%) reduces position size."""
    open_positions = [{"symbol": "ETH/USDT"}]
    
    with patch.object(adaptive_risk, '_get_redis') as mock_redis:
        mock_client = AsyncMock()
        mock_client.get.return_value = json.dumps(mock_correlation_matrix)
        mock_redis.return_value = mock_client
        
        result = await adaptive_risk.check_correlation_guard(
            symbol="BTC/USDT",
            open_positions=open_positions,
        )
        
        assert result.approved is True
        assert result.position_size_adjustment == 0.5  # 50% reduction
        assert "Moderate correlation" in result.reason


@pytest.mark.asyncio
async def test_low_correlation_allows_full_size(adaptive_risk, mock_correlation_matrix):
    """Test that low correlation (<70%) allows full position size."""
    open_positions = [{"symbol": "ADA/USDT"}]
    
    with patch.object(adaptive_risk, '_get_redis') as mock_redis:
        mock_client = AsyncMock()
        mock_client.get.return_value = json.dumps(mock_correlation_matrix)
        mock_redis.return_value = mock_client
        
        result = await adaptive_risk.check_correlation_guard(
            symbol="BTC/USDT",
            open_positions=open_positions,
        )
        
        assert result.approved is True
        assert result.position_size_adjustment == 1.0
        assert "Low correlation" in result.reason


@pytest.mark.asyncio
async def test_redis_unavailable_failsafe(adaptive_risk):
    """Test fail-safe behavior when Redis is unavailable."""
    open_positions = [{"symbol": "ETH/USDT"}]
    
    with patch.object(adaptive_risk, '_get_redis', return_value=None):
        result = await adaptive_risk.check_correlation_guard(
            symbol="BTC/USDT",
            open_positions=open_positions,
        )
        
        # Should allow trade (fail-safe)
        assert result.approved is True
        assert result.position_size_adjustment == 1.0
        assert "unavailable" in result.reason.lower()


@pytest.mark.asyncio
async def test_correlation_matrix_not_found(adaptive_risk):
    """Test behavior when correlation matrix is not in Redis."""
    open_positions = [{"symbol": "ETH/USDT"}]
    
    with patch.object(adaptive_risk, '_get_redis') as mock_redis:
        mock_client = AsyncMock()
        mock_client.get.return_value = None  # Matrix not found
        mock_redis.return_value = mock_client
        
        result = await adaptive_risk.check_correlation_guard(
            symbol="BTC/USDT",
            open_positions=open_positions,
        )
        
        # Should allow trade (fail-safe)
        assert result.approved is True
        assert result.position_size_adjustment == 1.0
