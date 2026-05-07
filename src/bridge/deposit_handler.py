"""
Deposit Handler
================
Listens for BSC blockchain deposits and credits user balances.
Polls BSC node every 30 seconds for new USDT transfers to the bot wallet.
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update

from src.bridge.escrow_contract import escrow
from src.database.connection import get_session
from src.database.models import User, EscrowTransaction
from src.utils.logger import get_logger

logger = get_logger(__name__)

REQUIRED_CONFIRMATIONS = 3
POLL_INTERVAL_SECONDS = 30


class DepositHandler:
    """
    Monitors BSC for incoming USDT deposits and credits user escrow balances.
    """

    def __init__(self, telegram_notifier=None):
        self.notifier = telegram_notifier
        self._running = False
        self._last_block: int = 0
        self._processed_hashes: set = set()

    async def start(self) -> None:
        """Start the deposit monitoring loop."""
        escrow.initialize()
        self._running = True
        logger.info("DepositHandler started")
        asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        self._running = False

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._check_new_deposits()
            except Exception as e:
                logger.error(f"DepositHandler poll error: {e}", exc_info=True)
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def _check_new_deposits(self) -> None:
        """Check for new USDT transfers to the bot wallet."""
        if escrow.mock_mode or not escrow._w3:
            return

        try:
            current_block = escrow._w3.eth.block_number
            from_block = max(self._last_block, current_block - 100)

            # Get Transfer events to our deposit address
            deposit_address = escrow.generate_deposit_address(0)
            if not deposit_address or deposit_address.startswith("0x000"):
                return

            from web3 import Web3
            transfer_filter = escrow._usdt.events.Transfer.create_filter(
                fromBlock=from_block,
                toBlock="latest",
                argument_filters={"to": Web3.to_checksum_address(deposit_address)},
            )
            events = transfer_filter.get_all_entries()

            for event in events:
                tx_hash = event["transactionHash"].hex()
                if tx_hash in self._processed_hashes:
                    continue

                amount_raw = event["args"]["value"]
                amount_usdt = Decimal(str(amount_raw)) / Decimal("1e18")
                from_address = event["args"]["from"]

                # Check confirmations
                receipt = escrow._w3.eth.get_transaction_receipt(tx_hash)
                confirmations = current_block - receipt["blockNumber"]
                if confirmations < REQUIRED_CONFIRMATIONS:
                    continue

                # Credit user balance
                await self._credit_deposit(
                    tx_hash=tx_hash,
                    from_address=from_address,
                    amount_usdt=amount_usdt,
                    block_number=receipt["blockNumber"],
                    confirmations=confirmations,
                )
                self._processed_hashes.add(tx_hash)

            self._last_block = current_block

        except Exception as e:
            logger.error(f"_check_new_deposits error: {e}")

    async def _credit_deposit(
        self,
        tx_hash: str,
        from_address: str,
        amount_usdt: Decimal,
        block_number: int,
        confirmations: int,
    ) -> None:
        """Credit a confirmed deposit to the user's escrow balance."""
        async with get_session() as session:
            if session is None:
                return

            # Find user by escrow address
            result = await session.execute(
                select(User).where(User.escrow_address == from_address.lower())
            )
            user = result.scalar_one_or_none()

            if not user:
                logger.warning(f"Deposit from unknown address {from_address}: {amount_usdt} USDT")
                return

            # Check for duplicate
            dup = await session.execute(
                select(EscrowTransaction).where(EscrowTransaction.tx_hash == tx_hash)
            )
            if dup.scalar_one_or_none():
                return

            # Record transaction
            tx_record = EscrowTransaction(
                user_id=user.id,
                tx_type="deposit",
                amount_usdt=amount_usdt,
                fee_usdt=Decimal("0"),
                net_usdt=amount_usdt,
                tx_hash=tx_hash,
                from_address=from_address,
                to_address=escrow.generate_deposit_address(user.telegram_id),
                block_number=block_number,
                confirmations=confirmations,
                status="confirmed",
                confirmed_at=datetime.now(timezone.utc),
            )
            session.add(tx_record)

            # Update user balance
            await session.execute(
                update(User)
                .where(User.id == user.id)
                .values(escrow_balance_usdt=User.escrow_balance_usdt + amount_usdt)
            )

            logger.info(f"Deposit credited: user={user.telegram_id} amount={amount_usdt} USDT tx={tx_hash}")

            # Notify user
            if self.notifier:
                try:
                    await self.notifier.send_alert(
                        "INFO",
                        f"💰 *Deposit Confirmed*\n\n"
                        f"Amount: `{amount_usdt:.4f} USDT`\n"
                        f"TX: `{tx_hash[:20]}...`\n"
                        f"Confirmations: `{confirmations}`\n\n"
                        f"Your balance has been credited.",
                        symbol="DEPOSIT",
                    )
                except Exception:
                    pass

    async def manual_credit(
        self,
        telegram_id: int,
        amount_usdt: Decimal,
        tx_hash: str = "manual",
    ) -> bool:
        """Manually credit a deposit (for testing or admin use)."""
        async with get_session() as session:
            if session is None:
                return False

            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                return False

            tx_record = EscrowTransaction(
                user_id=user.id,
                tx_type="deposit",
                amount_usdt=amount_usdt,
                fee_usdt=Decimal("0"),
                net_usdt=amount_usdt,
                tx_hash=f"{tx_hash}_{telegram_id}_{int(datetime.now().timestamp())}",
                from_address="manual",
                to_address="manual",
                block_number=0,
                confirmations=99,
                status="confirmed",
                confirmed_at=datetime.now(timezone.utc),
            )
            session.add(tx_record)

            await session.execute(
                update(User)
                .where(User.id == user.id)
                .values(escrow_balance_usdt=User.escrow_balance_usdt + amount_usdt)
            )
            logger.info(f"Manual deposit: user={telegram_id} amount={amount_usdt}")
            return True
