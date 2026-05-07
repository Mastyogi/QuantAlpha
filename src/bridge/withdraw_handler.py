"""
Withdraw Handler
=================
Processes withdrawal requests.
Deducts 15% service fee via escrow contract.
85% goes to user wallet, 15% to service wallet.
"""
from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timezone
from typing import Tuple

from sqlalchemy import select, update

from src.bridge.escrow_contract import escrow
from src.database.connection import get_session
from src.database.models import User, EscrowTransaction
from src.utils.logger import get_logger
from src.users.user_manager import user_manager as _user_manager

logger = get_logger(__name__)

FXPRO_PARTNER_LINK = "https://direct-fxpro.com/en/partner/2FiFKGf7J"

MIN_WITHDRAWAL_USDT = Decimal("10")   # Minimum withdrawal amount
MAX_WITHDRAWAL_USDT = Decimal("50000")


class WithdrawHandler:
    """Handles user withdrawal requests with 15% fee deduction."""

    def __init__(self, telegram_notifier=None):
        self.notifier = telegram_notifier

    async def request_withdrawal(
        self,
        telegram_id: int,
        amount_usdt: Decimal,
        to_address: str,
    ) -> Tuple[bool, str]:
        """
        Process a withdrawal request.

        Args:
            telegram_id:  User's Telegram ID
            amount_usdt:  Amount to withdraw (before fee)
            to_address:   Destination BSC wallet address

        Returns:
            (success, message)
        """
        # Validate amount
        if amount_usdt < MIN_WITHDRAWAL_USDT:
            return False, f"Minimum withdrawal is {MIN_WITHDRAWAL_USDT} USDT"
        if amount_usdt > MAX_WITHDRAWAL_USDT:
            return False, f"Maximum withdrawal is {MAX_WITHDRAWAL_USDT} USDT"

        # Validate address
        if not _is_valid_bsc_address(to_address):
            return False, "Invalid BSC wallet address"

        # Check user is verified before DB session
        if not await _user_manager.is_verified(telegram_id):
            return (
                False,
                "You must be verified to withdraw.\n"
                f"Register at: {FXPRO_PARTNER_LINK}\nThen use /verify",
            )

        async with get_session() as session:
            if session is None:
                return False, "Database unavailable"

            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                return False, "User not found"

            # Check balance
            available = Decimal(str(user.escrow_balance_usdt or 0))
            if available < amount_usdt:
                return (
                    False,
                    f"Insufficient balance. Available: {available:.4f} USDT, "
                    f"Requested: {amount_usdt:.4f} USDT",
                )

            # Check contract not paused
            escrow.initialize()
            if escrow.is_paused():
                return False, "Withdrawals are temporarily paused. Please try again later."

            # Deduct from user balance first (prevent double-spend)
            await session.execute(
                update(User)
                .where(User.id == user.id)
                .values(escrow_balance_usdt=User.escrow_balance_usdt - amount_usdt)
            )

            # Execute withdrawal via contract
            success, tx_hash, net_amount, fee_amount = escrow.withdraw(
                to_address=to_address,
                amount_usdt=amount_usdt,
            )

            if not success:
                # Refund on failure
                await session.execute(
                    update(User)
                    .where(User.id == user.id)
                    .values(escrow_balance_usdt=User.escrow_balance_usdt + amount_usdt)
                )
                return False, "Withdrawal failed. Your balance has been restored."

            # Record transaction
            tx_record = EscrowTransaction(
                user_id=user.id,
                tx_type="withdrawal",
                amount_usdt=amount_usdt,
                fee_usdt=fee_amount,
                net_usdt=net_amount,
                tx_hash=tx_hash,
                from_address=escrow.generate_deposit_address(telegram_id),
                to_address=to_address,
                block_number=0,
                confirmations=0,
                status="confirmed" if success else "failed",
                confirmed_at=datetime.now(timezone.utc),
            )
            session.add(tx_record)

            logger.info(
                f"Withdrawal: user={telegram_id} amount={amount_usdt} "
                f"net={net_amount} fee={fee_amount} tx={tx_hash}"
            )

            msg = (
                f"✅ Withdrawal processed!\n\n"
                f"Amount: `{amount_usdt:.4f} USDT`\n"
                f"Service fee (15%): `{fee_amount:.4f} USDT`\n"
                f"You receive: `{net_amount:.4f} USDT`\n"
                f"To: `{to_address[:10]}...{to_address[-6:]}`\n"
                f"TX: `{tx_hash[:20]}...`"
            )

            if self.notifier:
                try:
                    await self.notifier.send_alert("INFO", msg)
                except Exception:
                    pass

            return True, msg

    async def get_withdrawal_history(self, telegram_id: int, limit: int = 10) -> list:
        """Get withdrawal history for a user."""
        async with get_session() as session:
            if session is None:
                return []

            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                return []

            txs = await session.execute(
                select(EscrowTransaction)
                .where(
                    EscrowTransaction.user_id == user.id,
                    EscrowTransaction.tx_type == "withdrawal",
                )
                .order_by(EscrowTransaction.created_at.desc())
                .limit(limit)
            )
            return [
                {
                    "amount": float(tx.amount_usdt),
                    "fee": float(tx.fee_usdt),
                    "net": float(tx.net_usdt),
                    "status": tx.status,
                    "tx_hash": tx.tx_hash,
                    "date": tx.created_at.isoformat() if tx.created_at else "",
                }
                for tx in txs.scalars().all()
            ]


def _is_valid_bsc_address(address: str) -> bool:
    """Basic BSC address validation."""
    if not address:
        return False
    if not address.startswith("0x"):
        return False
    if len(address) != 42:
        return False
    try:
        int(address, 16)
        return True
    except ValueError:
        return False
