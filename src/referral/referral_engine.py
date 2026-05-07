"""
Referral Engine
================
Handles 3-level referral fee distribution on trade profits.

Fee structure (applied to 15% service fee):
  Level 1 referrer: 2.5% of gross profit
  Level 2 referrer: 1.5% of gross profit
  Level 3 referrer: 1.0% of gross profit
  Bot owner:       10.0% of gross profit
  Total:           15.0% service fee

Weekly automated payouts with failure handling.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import get_session
from src.database.models import (
    User, Referral, ReferralEarning, ProfitRecord, EscrowTransaction
)
from src.users.user_manager import (
    SERVICE_FEE_PCT, REF_L1_PCT, REF_L2_PCT, REF_L3_PCT, OWNER_FEE_PCT
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ReferralEngine:
    """
    Distributes referral earnings when a trade closes with profit.
    Runs weekly automated payouts.
    """

    def __init__(self, telegram_notifier=None):
        self.notifier = telegram_notifier
        self._running = False

    # ── Core fee distribution ─────────────────────────────────────────────────

    async def distribute_profit_fees(
        self,
        user_id: int,
        trade_id: int,
        gross_profit_usdt: float,
    ) -> ProfitRecord:
        """
        Calculate and record fee distribution for a profitable trade.

        Args:
            user_id:           DB user ID of the trader
            trade_id:          DB trade ID
            gross_profit_usdt: Gross profit in USDT

        Returns:
            ProfitRecord with all fee breakdowns
        """
        if gross_profit_usdt <= 0:
            raise ValueError("distribute_profit_fees called with non-positive profit")

        gross = Decimal(str(gross_profit_usdt))
        service_fee = gross * Decimal(str(SERVICE_FEE_PCT))
        net_profit   = gross - service_fee

        # Referral fee breakdown
        l1_fee = gross * Decimal(str(REF_L1_PCT))
        l2_fee = gross * Decimal(str(REF_L2_PCT))
        l3_fee = gross * Decimal(str(REF_L3_PCT))
        owner_fee = gross * Decimal(str(OWNER_FEE_PCT))

        async with get_session() as session:
            if session is None:
                logger.warning("DB unavailable — fee distribution skipped")
                return ProfitRecord(
                    user_id=user_id,
                    trade_id=trade_id,
                    gross_profit_usdt=gross,
                    service_fee_usdt=service_fee,
                    net_profit_usdt=net_profit,
                )

            # Get referral chain for this user
            referrers = await self._get_referral_chain(session, user_id)

            # Create profit record
            record = ProfitRecord(
                user_id=user_id,
                trade_id=trade_id,
                gross_profit_usdt=gross,
                service_fee_usdt=service_fee,
                net_profit_usdt=net_profit,
                ref_l1_fee_usdt=l1_fee if len(referrers) >= 1 else Decimal("0"),
                ref_l2_fee_usdt=l2_fee if len(referrers) >= 2 else Decimal("0"),
                ref_l3_fee_usdt=l3_fee if len(referrers) >= 3 else Decimal("0"),
                owner_fee_usdt=owner_fee,
                processed=False,
            )
            session.add(record)
            await session.flush()
            await session.refresh(record)

            # Create ReferralEarning rows for each referrer
            fee_map = {1: (l1_fee, REF_L1_PCT), 2: (l2_fee, REF_L2_PCT), 3: (l3_fee, REF_L3_PCT)}
            for level, referrer_user in referrers.items():
                fee_amount, fee_pct = fee_map[level]
                earning = ReferralEarning(
                    user_id=referrer_user.id,
                    source_trade_id=trade_id,
                    level=level,
                    amount_usdt=fee_amount,
                    fee_pct=fee_pct * 100,
                    status="pending",
                )
                session.add(earning)

                # Update referrer's escrow balance
                await session.execute(
                    update(User)
                    .where(User.id == referrer_user.id)
                    .values(
                        escrow_balance_usdt=User.escrow_balance_usdt + fee_amount
                    )
                )

            record.processed = True
            logger.info(
                f"Fee distribution: trade={trade_id} gross=${gross:.4f} "
                f"service=${service_fee:.4f} net=${net_profit:.4f} "
                f"referrers={len(referrers)}"
            )
            return record

    async def _get_referral_chain(
        self, session: AsyncSession, user_id: int
    ) -> dict:
        """
        Get up to 3 levels of referrers for a user.
        Returns {1: User, 2: User, 3: User} (only levels that exist).
        """
        result = await session.execute(
            select(Referral, User)
            .join(User, User.id == Referral.referrer_id)
            .where(Referral.referred_id == user_id)
            .order_by(Referral.level)
        )
        rows = result.all()
        return {row.Referral.level: row.User for row in rows if row.Referral.level <= 3}

    # ── Leaderboard ───────────────────────────────────────────────────────────

    async def get_leaderboard(self, limit: int = 10) -> List[dict]:
        """Get top referrers by total earnings."""
        async with get_session() as session:
            if session is None:
                return []

            from sqlalchemy import func as sqlfunc
            result = await session.execute(
                select(
                    User.telegram_id,
                    User.username,
                    User.first_name,
                    sqlfunc.sum(ReferralEarning.amount_usdt).label("total_earnings"),
                    sqlfunc.count(ReferralEarning.id).label("total_referrals"),
                )
                .join(ReferralEarning, ReferralEarning.user_id == User.id)
                .where(ReferralEarning.status == "paid")
                .group_by(User.id)
                .order_by(sqlfunc.sum(ReferralEarning.amount_usdt).desc())
                .limit(limit)
            )
            rows = result.all()
            return [
                {
                    "rank": i + 1,
                    "name": row.username or row.first_name or f"User{row.telegram_id}",
                    "earnings": float(row.total_earnings or 0),
                    "referrals": row.total_referrals,
                }
                for i, row in enumerate(rows)
            ]

    # ── Weekly payout ─────────────────────────────────────────────────────────

    async def run_weekly_payouts(self) -> dict:
        """
        Process all pending referral earnings.
        Called weekly by the scheduler.
        Returns summary dict.
        """
        logger.info("Starting weekly referral payouts...")
        paid = 0
        failed = 0
        total_amount = Decimal("0")

        async with get_session() as session:
            if session is None:
                return {"paid": 0, "failed": 0, "total": 0.0, "error": "DB unavailable"}

            # Get all pending earnings
            result = await session.execute(
                select(ReferralEarning).where(ReferralEarning.status == "pending")
            )
            pending = result.scalars().all()

            for earning in pending:
                try:
                    # In production: trigger BSC transfer here
                    # For now: mark as paid (real transfer in withdraw_handler)
                    earning.status = "paid"
                    earning.paid_at = datetime.now(timezone.utc)
                    paid += 1
                    total_amount += earning.amount_usdt
                except Exception as e:
                    logger.error(f"Payout failed for earning {earning.id}: {e}")
                    earning.status = "failed"
                    failed += 1

        summary = {
            "paid": paid,
            "failed": failed,
            "total_usdt": float(total_amount),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"Weekly payouts complete: {summary}")

        if self.notifier:
            try:
                await self.notifier.send_alert(
                    "INFO",
                    f"💰 *Weekly Referral Payouts*\n\n"
                    f"Paid: `{paid}` earnings\n"
                    f"Total: `${float(total_amount):.4f} USDT`\n"
                    f"Failed: `{failed}`",
                )
            except Exception:
                pass

        return summary

    async def start_weekly_scheduler(self) -> None:
        """Background task: run payouts every Sunday 00:00 UTC."""
        self._running = True
        logger.info("Referral payout scheduler started")
        while self._running:
            try:
                now = datetime.now(timezone.utc)
                # Next Sunday 00:00
                days_until_sunday = (6 - now.weekday()) % 7 or 7
                next_run = (now + timedelta(days=days_until_sunday)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                sleep_secs = (next_run - now).total_seconds()
                logger.info(f"Next referral payout: {next_run} (in {sleep_secs/3600:.1f}h)")
                await asyncio.sleep(sleep_secs)
                await self.run_weekly_payouts()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Referral scheduler error: {e}", exc_info=True)
                await asyncio.sleep(3600)

    def stop(self) -> None:
        self._running = False
