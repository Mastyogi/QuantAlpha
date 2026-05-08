"""
Integration tests for full trading pipeline
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch


@pytest.mark.integration
@pytest.mark.asyncio
async def test_signal_to_trade_pipeline():
    """Test complete pipeline from signal generation to trade execution."""
    from src.core.bot_engine import BotEngineV2
    from src.signals.signal_engine import FinalSignal
    from src.risk.adaptive_risk import TradeSetup
    
    # Create bot engine instance
    engine = BotEngineV2(validate_on_start=False)
    
    # Mock broker to avoid real API calls
    engine.broker.get_account_info = AsyncMock(return_value={"equity": 10000.0, "balance": 10000.0})
    engine.broker.initialize = AsyncMock()
    
    # Mock notifier to avoid console print/queue issues
    engine.notifier = AsyncMock()
    engine.notifier.send_alert = AsyncMock()
    engine.notifier.send_trade_opened = AsyncMock()
    
    # Mock event bus to avoid background dispatching
    engine.event_bus = Mock()
    engine.event_bus.emit_signal = AsyncMock()
    engine.event_bus.emit_trade_opened = AsyncMock()
    
    # Mock trade repository to avoid DB hangs
    engine.order_manager.trade_repo = AsyncMock()
    engine.order_manager.trade_repo.create_trade = AsyncMock(return_value=Mock(id="test_id"))
    
    # Create sample dataframe
    dates = pd.date_range(start='2024-01-01', periods=100, freq='1H')
    df = pd.DataFrame({
        'timestamp': dates,
        'open': np.linspace(40000, 42000, 100),
        'high': np.linspace(41000, 43000, 100),
        'low': np.linspace(39000, 41000, 100),
        'close': np.linspace(40000, 42000, 100),
        'volume': np.random.uniform(100, 1000, 100),
    })
    
    # Mock signal generation
    mock_signal = FinalSignal(
        symbol="EURUSD",
        direction="BUY",
        approved=True,
        confluence_score=85.0,
        ai_confidence=0.80,
        win_rate_estimate=0.65,
        trade_setup=TradeSetup(
            symbol="EURUSD",
            direction="BUY",
            entry_price=41000.0,
            stop_loss=40500.0,
            take_profit_1=41500.0,
            take_profit_2=42000.0,
            take_profit_3=42500.0,
            risk_pct=1.22,
            reward_pct=2.44,
            rr_ratio=2.0,
            atr_value=500.0,
            position_size_usd=200.0,
            trailing_activation=41250.0,
            invalidation=40000.0,
        ),
        confluence=None,
    )
    
    # Test signal approval callback
    await engine._on_signal_approved(mock_signal)
    
    # Verify trade was executed
    assert engine._trades_today == 1
    assert len(engine.order_manager.paper_trader.open_positions) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_regime_detection_integration():
    """Test regime detection integration with signal engine."""
    from src.signals.regime_detector import MarketRegimeDetector
    from src.signals.signal_engine import FineTunedSignalEngine
    
    regime_detector = MarketRegimeDetector()
    signal_engine = FineTunedSignalEngine(
        model_dir="models",
        confluence_threshold=75.0,
        max_risk_pct=2.0,
        account_equity=10000.0,
    )
    
    # Create trending dataframe
    dates = pd.date_range(start='2024-01-01', periods=100, freq='1H')
    df = pd.DataFrame({
        'timestamp': dates,
        'open': np.linspace(40000, 45000, 100),
        'high': np.linspace(41000, 46000, 100),
        'low': np.linspace(39000, 44000, 100),
        'close': np.linspace(40000, 45000, 100),
        'volume': np.random.uniform(100, 1000, 100),
    })
    
    # Detect regime
    regime = await regime_detector.detect_regime(df, "EURUSD")
    
    # Should detect TRENDING or BREAKOUT
    assert regime in ["TRENDING", "BREAKOUT", "VOLATILE"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_event_bus_integration():
    """Test event bus integration with multiple components."""
    from src.core.event_bus import EventBus, EventType, Event
    
    bus = EventBus.get_instance()
    await bus.start()
    
    # Track events
    received_events = []
    
    async def event_handler(event: Event):
        received_events.append(event)
    
    # Subscribe to events
    bus.subscribe(EventType.TRADE_CLOSED, event_handler)
    
    # Publish event
    await bus.publish(Event(
        type=EventType.TRADE_CLOSED,
        data={"symbol": "EURUSD", "pnl": 100.0},
        source="test",
    ))
    
    # Wait for event processing
    await asyncio.sleep(0.5)
    
    # Verify event was received
    assert len(received_events) > 0
    assert received_events[0].type == EventType.TRADE_CLOSED
    
    await bus.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_correlation_guard_integration():
    """Test correlation guard integration with adaptive risk manager."""
    from src.risk.adaptive_risk import AdaptiveRiskManager
    
    adaptive_risk = AdaptiveRiskManager(
        max_risk_pct=2.0,
        account_equity=10000.0,
    )
    
    # Mock open positions
    open_positions = [
        {"symbol": "EURUSD"},
        {"symbol": "GBPUSD"},
    ]
    
    # Test correlation check
    result = await adaptive_risk.check_correlation_guard(
        symbol="BNB/USDT",
        open_positions=open_positions,
    )
    
    # Should return a result (even if Redis unavailable)
    assert result is not None
    assert hasattr(result, 'approved')
    assert hasattr(result, 'position_size_adjustment')


import asyncio
