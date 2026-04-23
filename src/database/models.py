from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, JSON, Enum as SAEnum
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()


class TradeDirection(enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class TradeStatus(enum.Enum):
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    STOPPED = "stopped"


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    exchange = Column(String(30), nullable=False, default="paper")
    order_id = Column(String(100), unique=True)
    direction = Column(SAEnum(TradeDirection), nullable=False)
    status = Column(SAEnum(TradeStatus), default=TradeStatus.PENDING)

    entry_price = Column(Float)
    exit_price = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    quantity = Column(Float)
    size_usd = Column(Float)

    pnl = Column(Float, default=0.0)
    pnl_pct = Column(Float, default=0.0)
    fees = Column(Float, default=0.0)

    strategy_name = Column(String(50))
    pattern_id = Column(String(50), index=True)  # Link to TradingPattern
    ai_confidence = Column(Float)
    signal_score = Column(Float)
    timeframe = Column(String(10))
    is_paper_trade = Column(Boolean, default=True)

    metadata_json = Column(JSON)
    opened_at = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Trade {self.symbol} {self.direction} @ {self.entry_price} [{self.status}]>"


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), index=True)
    direction = Column(SAEnum(TradeDirection))
    strategy_name = Column(String(50))
    timeframe = Column(String(10))
    entry_price = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    signal_score = Column(Float)
    ai_confidence = Column(Float)
    acted_upon = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Signal {self.symbol} {self.direction} confidence={self.ai_confidence}>"


class BotMetrics(Base):
    __tablename__ = "bot_metrics"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    equity = Column(Float)
    daily_pnl = Column(Float)
    total_trades = Column(Integer, default=0)
    open_positions = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    state = Column(String(20))
    details_json = Column(JSON)


# ============================================================================
# Self-Improvement System Models
# ============================================================================

class TradingPattern(Base):
    """Trading pattern discovered and validated by strategy discovery module."""
    __tablename__ = "trading_patterns"
    
    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    symbol = Column(String(20), nullable=False, index=True)
    asset_class = Column(String(20))  # crypto, forex, commodity
    
    entry_conditions = Column(JSON, nullable=False)
    exit_conditions = Column(JSON, nullable=False)
    market_regime = Column(String(20), index=True)  # TRENDING, RANGING, VOLATILE, DEAD
    timeframe = Column(String(10))
    
    discovery_date = Column(DateTime(timezone=True), nullable=False)
    validation_metrics = Column(JSON, nullable=False)
    
    usage_count = Column(Integer, default=0)
    live_win_rate = Column(Float, default=0.0)
    live_profit_factor = Column(Float, default=0.0)
    
    status = Column(String(20), default="active", index=True)  # active, deprecated
    deprecation_reason = Column(String)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<TradingPattern {self.name} [{self.status}] win_rate={self.live_win_rate:.1%}>"


class ModelVersion(Base):
    """ML model version tracking for self-improvement engine."""
    __tablename__ = "model_versions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    version = Column(String(50), nullable=False)
    model_path = Column(String(200), nullable=False)
    
    precision = Column(Float)
    recall = Column(Float)
    accuracy = Column(Float)
    auc = Column(Float)
    f1_score = Column(Float)
    
    training_samples = Column(Integer)
    training_date = Column(DateTime(timezone=True), nullable=False)
    validation_report = Column(JSON)
    
    status = Column(String(20), default="pending", index=True)  # pending, active, deprecated
    deployed_at = Column(DateTime(timezone=True))
    deprecated_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<ModelVersion {self.symbol} v{self.version} [{self.status}] precision={self.precision:.1%}>"


class PerformanceHistory(Base):
    """Performance metrics history for tracking improvement over time."""
    __tablename__ = "performance_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    period = Column(String(20), nullable=False)  # daily, weekly, monthly
    
    symbol = Column(String(20), index=True)
    strategy_name = Column(String(50))
    
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    
    total_pnl = Column(Float, default=0.0)
    avg_win_pct = Column(Float, default=0.0)
    avg_loss_pct = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)
    
    sharpe_ratio = Column(Float, default=0.0)
    sortino_ratio = Column(Float, default=0.0)
    max_drawdown_pct = Column(Float, default=0.0)
    
    equity = Column(Float)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<PerformanceHistory {self.period} {self.timestamp} win_rate={self.win_rate:.1%}>"


class ApprovalHistory(Base):
    """Approval workflow history for model updates and parameter changes."""
    __tablename__ = "approval_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    proposal_id = Column(String(50), unique=True, nullable=False, index=True)
    proposal_type = Column(String(50), nullable=False)
    proposal_data = Column(JSON, nullable=False)
    
    decision = Column(String(20), index=True)  # approved, rejected, paper_test
    admin_id = Column(String(50))
    decision_timestamp = Column(DateTime(timezone=True))
    
    execution_status = Column(String(20))  # pending, executed, failed
    execution_timestamp = Column(DateTime(timezone=True))
    execution_result = Column(JSON)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<ApprovalHistory {self.proposal_type} [{self.decision}]>"


class EquityHistory(Base):
    """Equity tracking for portfolio compounding analysis."""
    __tablename__ = "equity_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    equity = Column(Float, nullable=False)
    realized_pnl = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    
    open_positions = Column(Integer, default=0)
    portfolio_heat_pct = Column(Float, default=0.0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<EquityHistory {self.timestamp} equity=${self.equity:.2f}>"


class ParameterChange(Base):
    """Parameter change audit trail for auto-tuning system."""
    __tablename__ = "parameter_changes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    parameter_name = Column(String(100), nullable=False, index=True)
    old_value = Column(String)
    new_value = Column(String)
    change_reason = Column(String)
    triggered_by = Column(String(50))  # auto_tuning, manual, self_improvement
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<ParameterChange {self.parameter_name}: {self.old_value} → {self.new_value}>"


class AuditLog(Base):
    """Comprehensive audit logging for all system events."""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    component = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False, index=True)  # INFO, WARNING, ERROR, CRITICAL
    
    message = Column(String, nullable=False)
    details = Column(JSON)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<AuditLog [{self.severity}] {self.event_type}: {self.message[:50]}>"
