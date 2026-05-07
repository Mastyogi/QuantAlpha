"""
Integration tests: full user flow
  register → deposit → trade → profit → withdraw → referral earnings
"""
import pytest
import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.integration
class TestFullUserFlow:
    """End-to-end user journey test."""

    @pytest.mark.asyncio
    async def test_register_and_verify_flow(self):
        """User registers, gets referral code, verifies broker account."""
        from src.users.user_manager import UserManager
        from src.database.models import VerificationStatus

        mgr = UserManager()

        # Mock DB session
        created_user = MagicMock()
        created_user.id = 1
        created_user.telegram_id = 999888777
        created_user.referral_code = "QA99888ABCD"
        created_user.verification_status = VerificationStatus.PENDING
        created_user.broker_account = None

        with patch("src.users.user_manager.get_session") as mock_gs:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            # First call: get_or_create (user not found → create)
            not_found = MagicMock()
            not_found.scalar_one_or_none.return_value = None
            found = MagicMock()
            found.scalar_one_or_none.return_value = created_user

            call_count = [0]
            async def mock_execute(q):
                call_count[0] += 1
                if call_count[0] <= 1:
                    return not_found
                return found

            mock_session.execute = mock_execute
            mock_session.add = MagicMock()
            mock_session.flush = AsyncMock()
            mock_session.refresh = AsyncMock()
            mock_gs.return_value = mock_session

            user, created = await mgr.get_or_create(
                telegram_id=999888777,
                username="integrationtest",
                first_name="Integration",
            )
            assert created is True

        # Now verify
        with patch("src.users.user_manager.get_session") as mock_gs2:
            mock_session2 = AsyncMock()
            mock_session2.__aenter__ = AsyncMock(return_value=mock_session2)
            mock_session2.__aexit__ = AsyncMock(return_value=False)
            mock_result2 = MagicMock()
            mock_result2.scalar_one_or_none.return_value = created_user
            mock_session2.execute = AsyncMock(return_value=mock_result2)
            mock_gs2.return_value = mock_session2

            success, msg = await mgr.verify_user(999888777, "87654321")
            assert success
            assert created_user.verification_status == VerificationStatus.VERIFIED

    @pytest.mark.asyncio
    async def test_deposit_and_balance_flow(self):
        """User deposits USDT and balance is credited."""
        from src.bridge.deposit_handler import DepositHandler
        from src.database.models import User

        handler = DepositHandler()

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.telegram_id = 999888777
        mock_user.escrow_address = "0xabc123"

        with patch("src.bridge.deposit_handler.get_session") as mock_gs:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            call_count = [0]
            async def mock_execute(q):
                call_count[0] += 1
                result = MagicMock()
                if call_count[0] == 1:
                    result.scalar_one_or_none.return_value = mock_user
                else:
                    result.scalar_one_or_none.return_value = None  # No duplicate
                return result

            mock_session.execute = mock_execute
            mock_session.add = MagicMock()
            mock_gs.return_value = mock_session

            success = await handler.manual_credit(999888777, Decimal("100"))
            assert success

    @pytest.mark.asyncio
    async def test_profit_fee_distribution(self):
        """Trade profit triggers correct fee distribution."""
        from src.referral.referral_engine import ReferralEngine
        from src.database.models import User

        engine = ReferralEngine()

        mock_user = MagicMock()
        mock_user.id = 1

        l1_user = MagicMock(); l1_user.id = 2
        l2_user = MagicMock(); l2_user.id = 3
        l3_user = MagicMock(); l3_user.id = 4

        with patch("src.referral.referral_engine.get_session") as mock_gs:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            # Mock referral chain query
            from src.database.models import Referral
            mock_rows = [
                MagicMock(Referral=MagicMock(level=1, referred_id=1), User=l1_user),
                MagicMock(Referral=MagicMock(level=2, referred_id=1), User=l2_user),
                MagicMock(Referral=MagicMock(level=3, referred_id=1), User=l3_user),
            ]
            mock_result = MagicMock()
            mock_result.all.return_value = mock_rows
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.add = MagicMock()
            mock_session.flush = AsyncMock()
            mock_session.refresh = AsyncMock()
            mock_gs.return_value = mock_session

            record = await engine.distribute_profit_fees(
                user_id=1,
                trade_id=100,
                gross_profit_usdt=100.0,
            )

            assert record is not None
            assert float(record.service_fee_usdt) == pytest.approx(15.0, abs=0.01)
            assert float(record.net_profit_usdt) == pytest.approx(85.0, abs=0.01)
            assert float(record.ref_l1_fee_usdt) == pytest.approx(2.5, abs=0.01)
            assert float(record.ref_l2_fee_usdt) == pytest.approx(1.5, abs=0.01)
            assert float(record.ref_l3_fee_usdt) == pytest.approx(1.0, abs=0.01)
            assert float(record.owner_fee_usdt) == pytest.approx(10.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_withdrawal_deducts_15_pct(self):
        """Withdrawal correctly deducts 15% and sends 85% to user."""
        from src.bridge.withdraw_handler import WithdrawHandler
        from src.database.models import User, VerificationStatus

        handler = WithdrawHandler()

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.escrow_balance_usdt = Decimal("200")
        mock_user.verification_status = VerificationStatus.VERIFIED

        with patch("src.bridge.withdraw_handler.get_session") as mock_gs, \
             patch("src.bridge.withdraw_handler._user_manager") as mock_um, \
             patch("src.bridge.withdraw_handler.escrow") as mock_escrow:

            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_user
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.add = MagicMock()
            mock_gs.return_value = mock_session

            mock_um.is_verified = AsyncMock(return_value=True)
            mock_escrow.initialize = MagicMock()
            mock_escrow.is_paused.return_value = False
            mock_escrow.generate_deposit_address.return_value = "0x" + "a" * 40
            # Simulate 15% fee deduction
            mock_escrow.withdraw.return_value = (
                True,
                "0x" + "b" * 64,
                Decimal("85"),   # net
                Decimal("15"),   # fee
            )

            success, msg = await handler.request_withdrawal(
                123, Decimal("100"), "0x" + "a" * 40
            )
            assert success
            assert "85" in msg
            assert "15" in msg
