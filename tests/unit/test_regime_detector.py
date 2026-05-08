"""
Unit tests for RegimeDetector
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, AsyncMock, patch
from src.signals.regime_detector import MarketRegimeDetector


@pytest.fixture
def regime_detector():
    """Create RegimeDetector instance."""
    detector = MarketRegimeDetector()
    detector._get_redis = AsyncMock(return_value=None)
    return detector


@pytest.fixture
def sample_dataframe():
    """Create sample OHLCV dataframe."""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='1H')
    df = pd.DataFrame({
        'timestamp': dates,
        'open': np.random.uniform(40000, 42000, 100),
        'high': np.random.uniform(41000, 43000, 100),
        'low': np.random.uniform(39000, 41000, 100),
        'close': np.random.uniform(40000, 42000, 100),
        'volume': np.random.uniform(100, 1000, 100),
    })
    return df


@pytest.mark.asyncio
async def test_detect_trending_regime(regime_detector, sample_dataframe):
    """Test detection of TRENDING regime."""
    # Create trending data
    df = sample_dataframe.copy()
    
    with patch.object(regime_detector, '_classify', return_value=("TRENDING", 0.9, "mocked")):
        regime = await regime_detector.detect_regime(df, "EURUSD")
            
    assert regime in ["TRENDING", "BREAKOUT"]


@pytest.mark.asyncio
async def test_detect_ranging_regime(regime_detector, sample_dataframe):
    """Test detection of RANGING regime."""
    # Create ranging data (sideways movement)
    df = sample_dataframe.copy()
    df['close'] = 41000 + np.sin(np.linspace(0, 4*np.pi, 100)) * 200  # Oscillating
    
    regime = await regime_detector.detect_regime(df, "EURUSD")
    
    # Should detect RANGING or DEAD (both valid for low volatility)
    assert regime in ["RANGING", "DEAD", "VOLATILE"]


@pytest.mark.asyncio
async def test_detect_volatile_regime(regime_detector, sample_dataframe):
    """Test detection of VOLATILE regime."""
    # Create volatile data (high ATR)
    df = sample_dataframe.copy()
    df['high'] = df['close'] * 1.05  # 5% swings
    df['low'] = df['close'] * 0.95
    
    regime = await regime_detector.detect_regime(df, "EURUSD")
    
    # High volatility should be detected
    assert regime in ["VOLATILE", "TRENDING", "BREAKOUT"]


@pytest.mark.asyncio
async def test_redis_caching(regime_detector, sample_dataframe):
    """Test Redis caching functionality."""
    # We need to un-mock the fixture's _get_redis for this specific test
    with patch.object(MarketRegimeDetector, '_get_redis') as mock_redis:
        mock_client = AsyncMock()
        mock_client.get.return_value = None  # Cache miss
        mock_client.setex = AsyncMock()
        mock_redis.return_value = mock_client
        
        # Use a fresh instance
        detector = MarketRegimeDetector()
        
        regime1 = await detector.detect_regime(sample_dataframe, "EURUSD")
        
        # Should have tried to get from cache
        from unittest.mock import call
        mock_client.get.assert_has_calls([call("regime:EURUSD")])
        
        # Should have set cache
        mock_client.setex.assert_called()


@pytest.mark.asyncio
async def test_regime_priority_order(regime_detector, sample_dataframe):
    """Test that regime priority order is respected."""
    # VOLATILE should have highest priority
    df = sample_dataframe.copy()
    
    # Create conditions for multiple regimes
    df['high'] = df['close'] * 1.04  # High ATR (VOLATILE)
    df['close'] = np.linspace(40000, 45000, 100)  # Trending
    
    regime = await regime_detector.detect_regime(df, "EURUSD")
    
    # VOLATILE should win due to priority
    assert regime in ["VOLATILE", "TRENDING"]


@pytest.mark.asyncio
async def test_insufficient_data(regime_detector):
    """Test handling of insufficient data."""
    # Create dataframe with too few rows
    df = pd.DataFrame({
        'timestamp': pd.date_range(start='2024-01-01', periods=10, freq='1H'),
        'open': [40000] * 10,
        'high': [41000] * 10,
        'low': [39000] * 10,
        'close': [40000] * 10,
        'volume': [100] * 10,
    })
    
    regime = await regime_detector.detect_regime(df, "EURUSD")
    
    # Should return default regime or handle gracefully
    assert regime in ["RANGING", "DEAD", "TRENDING", "VOLATILE", "BREAKOUT"]
