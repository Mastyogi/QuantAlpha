"""add_self_improvement_tables

Revision ID: ad2b6e5caad9
Revises: 
Create Date: 2026-04-22 20:20:06.205730

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ad2b6e5caad9'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add self-improvement tables."""
    
    # 1. Trading Patterns Table
    op.create_table(
        'trading_patterns',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False, index=True),
        sa.Column('asset_class', sa.String(20)),
        sa.Column('entry_conditions', sa.JSON, nullable=False),
        sa.Column('exit_conditions', sa.JSON, nullable=False),
        sa.Column('market_regime', sa.String(20), index=True),
        sa.Column('timeframe', sa.String(10)),
        sa.Column('discovery_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('validation_metrics', sa.JSON, nullable=False),
        sa.Column('usage_count', sa.Integer, default=0),
        sa.Column('live_win_rate', sa.Float, default=0.0),
        sa.Column('live_profit_factor', sa.Float, default=0.0),
        sa.Column('status', sa.String(20), default='active', index=True),
        sa.Column('deprecation_reason', sa.String),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    
    # 2. Model Versions Table
    op.create_table(
        'model_versions',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('symbol', sa.String(20), nullable=False, index=True),
        sa.Column('version', sa.String(50), nullable=False),
        sa.Column('model_path', sa.String(200), nullable=False),
        sa.Column('precision', sa.Float),
        sa.Column('recall', sa.Float),
        sa.Column('accuracy', sa.Float),
        sa.Column('auc', sa.Float),
        sa.Column('f1_score', sa.Float),
        sa.Column('training_samples', sa.Integer),
        sa.Column('training_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('validation_report', sa.JSON),
        sa.Column('status', sa.String(20), default='pending', index=True),
        sa.Column('deployed_at', sa.DateTime(timezone=True)),
        sa.Column('deprecated_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # 3. Performance History Table
    op.create_table(
        'performance_history',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('period', sa.String(20), nullable=False),
        sa.Column('symbol', sa.String(20), index=True),
        sa.Column('strategy_name', sa.String(50)),
        sa.Column('total_trades', sa.Integer, default=0),
        sa.Column('winning_trades', sa.Integer, default=0),
        sa.Column('losing_trades', sa.Integer, default=0),
        sa.Column('win_rate', sa.Float, default=0.0),
        sa.Column('total_pnl', sa.Float, default=0.0),
        sa.Column('avg_win_pct', sa.Float, default=0.0),
        sa.Column('avg_loss_pct', sa.Float, default=0.0),
        sa.Column('profit_factor', sa.Float, default=0.0),
        sa.Column('sharpe_ratio', sa.Float, default=0.0),
        sa.Column('sortino_ratio', sa.Float, default=0.0),
        sa.Column('max_drawdown_pct', sa.Float, default=0.0),
        sa.Column('equity', sa.Float),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # 4. Approval History Table
    op.create_table(
        'approval_history',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('proposal_id', sa.String(50), unique=True, nullable=False, index=True),
        sa.Column('proposal_type', sa.String(50), nullable=False),
        sa.Column('proposal_data', sa.JSON, nullable=False),
        sa.Column('decision', sa.String(20), index=True),
        sa.Column('admin_id', sa.String(50)),
        sa.Column('decision_timestamp', sa.DateTime(timezone=True)),
        sa.Column('execution_status', sa.String(20)),
        sa.Column('execution_timestamp', sa.DateTime(timezone=True)),
        sa.Column('execution_result', sa.JSON),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # 5. Equity History Table
    op.create_table(
        'equity_history',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('equity', sa.Float, nullable=False),
        sa.Column('realized_pnl', sa.Float, default=0.0),
        sa.Column('unrealized_pnl', sa.Float, default=0.0),
        sa.Column('open_positions', sa.Integer, default=0),
        sa.Column('portfolio_heat_pct', sa.Float, default=0.0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # 6. Parameter Changes Table
    op.create_table(
        'parameter_changes',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('parameter_name', sa.String(100), nullable=False, index=True),
        sa.Column('old_value', sa.String),
        sa.Column('new_value', sa.String),
        sa.Column('change_reason', sa.String),
        sa.Column('triggered_by', sa.String(50)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # 7. Audit Logs Table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('event_type', sa.String(50), nullable=False, index=True),
        sa.Column('component', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False, index=True),
        sa.Column('message', sa.String, nullable=False),
        sa.Column('details', sa.JSON),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # 8. Add pattern_id field to existing trades table
    op.add_column('trades', sa.Column('pattern_id', sa.String(50), index=True))


def downgrade() -> None:
    """Downgrade schema - Remove self-improvement tables."""
    
    # Remove pattern_id from trades table
    op.drop_column('trades', 'pattern_id')
    
    # Drop all new tables in reverse order
    op.drop_table('audit_logs')
    op.drop_table('parameter_changes')
    op.drop_table('equity_history')
    op.drop_table('approval_history')
    op.drop_table('performance_history')
    op.drop_table('model_versions')
    op.drop_table('trading_patterns')
