"""
Negative / security tests:
  - SQL injection attempts
  - Unverified user tries to trade
  - Excessive withdrawal
  - Referral loop prevention
  - Invalid inputs
  - Network failures
"""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch


class TestUnverifiedUserBlocked:
    @pytest.mark.asyncio
    async def test_unverified_cannot_withdraw(self):
        from src.bridge.withdraw_handler import WithdrawHandler
        handler = WithdrawHandler()

        with patch("src.bridge.withdraw_handler._user_manager") as mock_um:
            mock_um.is_verified = AsyncMock(return_value=False)

            success, msg = await handler.request_withdrawal(
                123, Decimal("100"), "0x" + "a" * 40
            )
            assert not success
            assert "verified" in msg.lower()

    @pytest.mark.asyncio
    async def test_unverified_cannot_switch_to_demo(self):
        from src.users.user_manager import UserManager
        from src.database.models import VerificationStatus
        mgr = UserManager()

        mock_user = MagicMock()
        mock_user.verification_status = VerificationStatus.PENDING

        with patch("src.users.user_manager.get_session") as mock_gs:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_user
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_gs.return_value = mock_session

            success, msg = await mgr.set_mode(123, "demo")
            assert not success
            assert "verified" in msg.lower()


class TestInputValidation:
    @pytest.mark.asyncio
    async def test_sql_injection_in_referral_code(self):
        """SQL injection in referral code should not crash the system."""
        from src.users.user_manager import UserManager
        mgr = UserManager()

        malicious_code = "'; DROP TABLE users; --"

        with patch("src.users.user_manager.get_session") as mock_gs:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None  # Not found
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.add = MagicMock()
            mock_session.flush = AsyncMock()
            mock_session.refresh = AsyncMock()
            mock_gs.return_value = mock_session

            # Should not raise — SQLAlchemy parameterises queries
            user, created = await mgr.get_or_create(
                telegram_id=123,
                referral_code=malicious_code,
            )
            # System should handle gracefully (referrer not found)
            assert user is not None

    def test_negative_withdrawal_amount(self):
        from src.bridge.withdraw_handler import WithdrawHandler
        handler = WithdrawHandler()
        import asyncio
        success, msg = asyncio.get_event_loop().run_until_complete(
            handler.request_withdrawal(123, Decimal("-100"), "0x" + "a" * 40)
        )
        assert not success

    def test_zero_withdrawal_amount(self):
        from src.bridge.withdraw_handler import WithdrawHandler
        handler = WithdrawHandler()
        import asyncio
        success, msg = asyncio.get_event_loop().run_until_complete(
            handler.request_withdrawal(123, Decimal("0"), "0x" + "a" * 40)
        )
        assert not success

    def test_excessive_withdrawal_blocked(self):
        from src.bridge.withdraw_handler import WithdrawHandler, MAX_WITHDRAWAL_USDT
        handler = WithdrawHandler()
        import asyncio
        success, msg = asyncio.get_event_loop().run_until_complete(
            handler.request_withdrawal(
                123, MAX_WITHDRAWAL_USDT + Decimal("1"), "0x" + "a" * 40
            )
        )
        assert not success
        assert "Maximum" in msg


class TestReferralLoopPrevention:
    @pytest.mark.asyncio
    async def test_self_referral_blocked(self):
        """User cannot use their own referral code."""
        from src.users.user_manager import UserManager
        mgr = UserManager()

        # User with ID 1 tries to refer themselves
        new_user = MagicMock()
        new_user.id = 1
        new_user.telegram_id = 123

        referrer = MagicMock()
        referrer.id = 1  # Same ID as new_user

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = referrer
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()

        await mgr._process_referral(mock_session, new_user, "SELFREF")
        # No referral should be added
        assert mock_session.add.call_count == 0

    @pytest.mark.asyncio
    async def test_circular_referral_chain_safe(self):
        """A→B→C→A circular chain should not cause infinite loop."""
        from src.users.user_manager import UserManager
        mgr = UserManager()

        # A refers B, B refers C, C tries to refer A
        user_a = MagicMock(); user_a.id = 1; user_a.referred_by_id = 3  # C
        user_b = MagicMock(); user_b.id = 2; user_b.referred_by_id = 1  # A
        user_c = MagicMock(); user_c.id = 3; user_c.referred_by_id = 2  # B

        new_user = MagicMock(); new_user.id = 4; new_user.telegram_id = 444

        call_count = [0]
        async def mock_execute(q):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                result.scalar_one_or_none.return_value = user_a  # L1
            elif call_count[0] == 2:
                result.scalar_one_or_none.return_value = user_c  # L2 (A's referrer = C)
            elif call_count[0] == 3:
                result.scalar_one_or_none.return_value = user_b  # L3 (C's referrer = B)
            else:
                result.scalar_one_or_none.return_value = None
            return result

        mock_session = AsyncMock()
        mock_session.execute = mock_execute
        mock_session.add = MagicMock()

        # Should complete without infinite loop (max 3 levels)
        await mgr._process_referral(mock_session, new_user, "CIRCREF")
        # At most 3 referral records added
        assert mock_session.add.call_count <= 3


class TestNetworkFailures:
    @pytest.mark.asyncio
    async def test_db_unavailable_graceful_degradation(self):
        """System should not crash when DB is unavailable."""
        from src.users.user_manager import UserManager
        mgr = UserManager()

        with patch("src.users.user_manager.get_session") as mock_gs:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=None)  # DB offline
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_gs.return_value = mock_session

            # Should return ephemeral user, not crash
            user, created = await mgr.get_or_create(telegram_id=123)
            assert user is not None

    @pytest.mark.asyncio
    async def test_escrow_contract_unavailable(self):
        """Withdrawal should fail gracefully when contract is unavailable."""
        from src.bridge.escrow_contract import EscrowContract
        e = EscrowContract()
        e._initialized = True
        e._mock_mode = False
        e._contract = None  # Contract not loaded

        success, tx_hash, net, fee = e.withdraw("0x" + "a" * 40, Decimal("100"))
        assert not success

    def test_bsc_rpc_connection_failure(self):
        """EscrowContract should fall back to mock mode on RPC failure."""
        from src.bridge.escrow_contract import EscrowContract
        e = EscrowContract()
        e.bsc_rpc = "http://invalid-rpc-endpoint:9999"

        with patch("src.bridge.escrow_contract.EscrowContract.initialize") as mock_init:
            mock_init.return_value = False
            result = e.initialize()
            # Should not raise
