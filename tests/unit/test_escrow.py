"""
Unit tests for EscrowContract and WithdrawHandler.
Tests fee deduction, address validation, mock mode behaviour.
"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch, AsyncMock


class TestEscrowContractMockMode:
    """Tests that run without Web3 (mock mode)."""

    def setup_method(self):
        from src.bridge.escrow_contract import EscrowContract
        self.escrow = EscrowContract()
        self.escrow._initialized = True
        self.escrow._mock_mode = True

    def test_mock_mode_withdraw_returns_correct_split(self):
        amount = Decimal("100")
        success, tx_hash, net, fee = self.escrow.withdraw("0x1234", amount)
        assert success
        assert fee == Decimal("15")   # 15%
        assert net == Decimal("85")   # 85%
        assert net + fee == amount

    def test_mock_mode_balance_returns_zero(self):
        bal = self.escrow.get_usdt_balance("0x1234")
        assert bal == Decimal("0")

    def test_mock_mode_not_paused(self):
        assert not self.escrow.is_paused()

    def test_fee_calculation_various_amounts(self):
        test_cases = [
            (Decimal("10"),    Decimal("1.5"),   Decimal("8.5")),
            (Decimal("1000"),  Decimal("150"),   Decimal("850")),
            (Decimal("0.01"),  Decimal("0.0015"),Decimal("0.0085")),
        ]
        for amount, expected_fee, expected_net in test_cases:
            _, _, net, fee = self.escrow.withdraw("0x1234", amount)
            assert abs(fee - expected_fee) < Decimal("0.0001"), f"Fee mismatch for {amount}"
            assert abs(net - expected_net) < Decimal("0.0001"), f"Net mismatch for {amount}"


class TestWithdrawHandlerValidation:
    """Tests for withdrawal validation logic."""

    @pytest.mark.asyncio
    async def test_minimum_withdrawal_enforced(self):
        from src.bridge.withdraw_handler import WithdrawHandler
        handler = WithdrawHandler()
        success, msg = await handler.request_withdrawal(
            123, Decimal("5"), "0x" + "a" * 40
        )
        assert not success
        assert "Minimum" in msg

    @pytest.mark.asyncio
    async def test_invalid_address_rejected(self):
        from src.bridge.withdraw_handler import WithdrawHandler
        handler = WithdrawHandler()
        success, msg = await handler.request_withdrawal(
            123, Decimal("100"), "not_an_address"
        )
        assert not success
        assert "Invalid" in msg

    @pytest.mark.asyncio
    async def test_address_without_0x_rejected(self):
        from src.bridge.withdraw_handler import WithdrawHandler, _is_valid_bsc_address
        assert not _is_valid_bsc_address("abcdef1234567890abcdef1234567890abcdef12")

    def test_valid_bsc_address(self):
        from src.bridge.withdraw_handler import _is_valid_bsc_address
        valid = "0x" + "a" * 40
        assert _is_valid_bsc_address(valid)

    def test_short_address_rejected(self):
        from src.bridge.withdraw_handler import _is_valid_bsc_address
        assert not _is_valid_bsc_address("0x1234")

    @pytest.mark.asyncio
    async def test_insufficient_balance_rejected(self):
        from src.bridge.withdraw_handler import WithdrawHandler
        from src.database.models import User, VerificationStatus
        handler = WithdrawHandler()

        mock_user = MagicMock()
        mock_user.escrow_balance_usdt = Decimal("50")
        mock_user.verification_status = VerificationStatus.VERIFIED

        with patch("src.bridge.withdraw_handler.get_session") as mock_gs:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_user
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_gs.return_value = mock_session

            with patch("src.bridge.withdraw_handler._user_manager") as mock_um:
                mock_um.is_verified = AsyncMock(return_value=True)

                success, msg = await handler.request_withdrawal(
                    123, Decimal("100"), "0x" + "a" * 40
                )
                assert not success
                assert "Insufficient" in msg


class TestFeeIntegrity:
    """Verify 15% fee is always exactly deducted — no rounding exploits."""

    def test_fee_is_exactly_15_pct(self):
        from src.bridge.escrow_contract import EscrowContract
        e = EscrowContract()
        e._initialized = True
        e._mock_mode = True

        for amount_int in [10, 100, 1000, 9999, 12345]:
            amount = Decimal(str(amount_int))
            _, _, net, fee = e.withdraw("0x" + "a" * 40, amount)
            expected_fee = amount * Decimal("0.15")
            expected_net = amount - expected_fee
            assert fee == expected_fee, f"Fee wrong for {amount}"
            assert net == expected_net, f"Net wrong for {amount}"
            assert net + fee == amount, f"Split doesn't sum to {amount}"
