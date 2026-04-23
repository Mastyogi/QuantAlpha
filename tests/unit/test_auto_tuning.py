"""
Unit tests for AutoTuningSystem
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch
from src.ml.auto_tuning_system import AutoTuningSystem, OptimizationResult
from src.telegram.approval_system import ApprovalSystem


@pytest.fixture
def mock_approval_system():
    """Mock approval system."""
    approval_system = Mock(spec=ApprovalSystem)
    approval_system.create_proposal = AsyncMock(return_value="proposal_123")
    return approval_system


@pytest.fixture
def auto_tuning_system(mock_approval_system):
    """Create AutoTuningSystem instance."""
    return AutoTuningSystem(
        approval_system=mock_approval_system,
        n_trials=10,  # Reduced for testing
        lookback_days=30,
    )


@pytest.mark.asyncio
async def test_optimization_with_sufficient_data(auto_tuning_system):
    """Test optimization runs successfully with sufficient trade data."""
    # Mock trade data
    mock_trades = []
    for i in range(50):
        trade = Mock()
        trade.ai_confidence = 0.75
        trade.pnl_pct = 2.0 if i % 2 == 0 else -1.0  # 50% win rate
        mock_trades.append(trade)
    
    with patch.object(auto_tuning_system.trade_repo, 'get_trades_in_range', 
                     return_value=mock_trades):
        result = await auto_tuning_system.optimize()
        
        assert result is not None
        assert isinstance(result, OptimizationResult)
        assert result.trials_completed == 10
        assert result.best_sharpe != 0
        assert 'min_confluence_score' in result.best_params
        assert 'kelly_fraction' in result.best_params


@pytest.mark.asyncio
async def test_optimization_insufficient_data(auto_tuning_system):
    """Test optimization fails gracefully with insufficient data."""
    # Mock insufficient trade data
    mock_trades = [Mock() for _ in range(10)]  # Less than 30
    
    with patch.object(auto_tuning_system.trade_repo, 'get_trades_in_range',
                     return_value=mock_trades):
        result = await auto_tuning_system.optimize()
        
        assert result is None


@pytest.mark.asyncio
async def test_parameter_bounds(auto_tuning_system):
    """Test that optimized parameters are within bounds."""
    mock_trades = []
    for i in range(50):
        trade = Mock()
        trade.ai_confidence = 0.75
        trade.pnl_pct = 2.0 if i % 2 == 0 else -1.0
        mock_trades.append(trade)
    
    with patch.object(auto_tuning_system.trade_repo, 'get_trades_in_range',
                     return_value=mock_trades):
        result = await auto_tuning_system.optimize()
        
        if result:
            params = result.best_params
            
            # Check bounds
            assert 60.0 <= params['min_confluence_score'] <= 90.0
            assert 0.20 <= params['kelly_fraction'] <= 0.45
            assert 0.55 <= params['min_ai_confidence'] <= 0.85
            assert 1.2 <= params['tp1_multiplier'] <= 2.0
            assert 2.0 <= params['tp2_multiplier'] <= 4.0
            assert 3.5 <= params['tp3_multiplier'] <= 6.0


@pytest.mark.asyncio
async def test_get_status(auto_tuning_system):
    """Test get_status returns correct format."""
    status = auto_tuning_system.get_status()
    
    assert 'last_run' in status
    assert 'next_scheduled' in status
    assert status['last_run'] is None  # No optimization run yet
    
    # After setting last_optimization
    auto_tuning_system.last_optimization = OptimizationResult(
        best_params={'test': 1.0},
        best_sharpe=1.5,
        trials_completed=10,
        optimization_time=30.0,
        out_of_sample_sharpe=1.3,
        timestamp=datetime.now(timezone.utc)
    )
    
    status = auto_tuning_system.get_status()
    assert status['last_run'] is not None
    assert status['best_sharpe'] == 1.5
    assert status['oos_sharpe'] == 1.3
