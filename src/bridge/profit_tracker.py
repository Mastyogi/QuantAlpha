"""
Profit Tracker
===============
Tracks per-user PnL for fee calculation.
Integrates with the referral engine to distribute fees on profitable trades.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import select

from src.database.connection import get_session
from src.database.models import User, ProfitRecord
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ProfitTracker:
    """Tracks trade profits and triggers fee distribution."""

    def __init__(self, referral_engine=None):
        self.referral_engine = referral_engine

    async def record_trade_profit(
        self,
        telegram_id: int,
        trade_id: int,
        gross_profit_usdt: float,
    ) -> Optional[ProfitRecord]:
        """
        Record a profitable trade and distribute fees.
        Only called when gross_profit_usdt > 0.
        """
        if gross_profit_usdt <= 0:
            return None

        async with get_session() as session:
            if session is None:
                return None

            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                return None

        # Distribute fees via referral engine
        if self.referral_engine:
            try:
                record = await self.referral_engine.distribute_profit_fees(
                    user_id=user.id,
                    trade_id=trade_id,
                    gross_profit_usdt=gross_profit_usdt,
                )
                return record
            except Exception as e:
                logger.error(f"Fee distribution failed: {e}", exc_info=True)

        return None

    async def get_user_pnl_summary(self, telegram_id: int) -> dict:
        """Get total PnL summary for a user."""
        async with get_session() as session:
            if session is None:
                return {}

            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                return {}

            from sqlalchemy import func as sqlfunc
            pnl_result = await session.execute(
                select(
                    sqlfunc.sum(ProfitRecord.gross_profit_usdt).label("total_gross"),
                    sqlfunc.sum(ProfitRecord.service_fee_usdt).label("total_fees"),
                    sqlfunc.sum(ProfitRecord.net_profit_usdt).label("total_net"),
                    sqlfunc.count(ProfitRecord.id).label("profitable_trades"),
                ).where(ProfitRecord.user_id == user.id)
            )
            row = pnl_result.one()
            return {
                "total_gross_profit": float(row.total_gross or 0),
                "total_fees_paid": float(row.total_fees or 0),
                "total_net_profit": float(row.total_net or 0),
                "profitable_trades": row.profitable_trades or 0,
                "escrow_balance": float(user.escrow_balance_usdt or 0),
                "trading_balance": float(user.trading_balance_usdt or 0),
            }
