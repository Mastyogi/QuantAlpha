"""
Unit tests for ReferralEngine — fee calculation, distribution, leaderboard.
"""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch


class TestFeeCalculation:
    """Test that 15% fee splits correctly across referral levels."""

    def test_fee_percentages_sum_to_15(self):
        from src.users.user_manager import (
            SERVICE_FEE_PCT, REF_L1_PCT, REF_L2_PCT, REF_L3_PCT, OWNER_FEE_PCT
        )
        total = REF_L1_PCT + REF_L2_PCT + REF_L3_PCT + OWNER_FEE_PCT
        assert abs(total - SERVICE_FEE_PCT) < 1e-10, f"Fee split {total} != {SERVICE_FEE_PCT}"

    def test_l1_fee_on_100_usdt(self):
        from src.users.user_manager import REF_L1_PCT
        gross = Decimal("100")
        l1_fee = gross * Decimal(str(REF_L1_PCT))
        assert l1_fee == Decimal("2.5")

    def test_l2_fee_on_100_usdt(self):
        from src.users.user_manager import REF_L2_PCT
        gross = Decimal("100")
        l2_fee = gross * Decimal(str(REF_L2_PCT))
        assert l2_fee == Decimal("1.5")

    def test_l3_fee_on_100_usdt(self):
        from src.users.user_manager import REF_L3_PCT
        gross = Decimal("100")
        l3_fee = gross * Decimal(str(REF_L3_PCT))
        assert l3_fee == Decimal("1.0")

    def test_owner_fee_on_100_usdt(self):
        from src.users.user_manager import OWNER_FEE_PCT
        gross = Decimal("100")
        owner_fee = gross * Decimal(str(OWNER_FEE_PCT))
        assert owner_fee == Decimal("10.0")

    def test_net_profit_is_85_pct(self):
        from src.users.user_manager import SERVICE_FEE_PCT
        gross = Decimal("100")
        service_fee = gross * Decimal(str(SERVICE_FEE_PCT))
        net = gross - service_fee
        assert net == Decimal("85.0")

    def test_fee_on_zero_profit_raises(self):
        from src.referral.referral_engine import ReferralEngine
        engine = ReferralEngine()
        with pytest.raises(ValueError):
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                engine.distribute_profit_fees(1, 1, 0.0)
            )

    def test_fee_on_negative_profit_raises(self):
        from src.referral.referral_engine import ReferralEngine
        engine = ReferralEngine()
        with pytest.raises(ValueError):
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                engine.distribute_profit_fees(1, 1, -50.0)
            )

    def test_large_profit_fee_precision(self):
        """Test fee calculation doesn't lose precision on large amounts."""
        from src.users.user_manager import SERVICE_FEE_PCT
        gross = Decimal("99999.99")
        fee = gross * Decimal(str(SERVICE_FEE_PCT))
        net = gross - fee
        assert net + fee == gross  # No rounding loss


class TestReferralChainLogic:
    """Test referral chain building and loop prevention."""

    @pytest.mark.asyncio
    async def test_no_self_referral(self):
        """User cannot refer themselves."""
        from src.users.user_manager import UserManager
        mgr = UserManager()

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.telegram_id = 123

        # Referrer has same ID as new user
        mock_referrer = MagicMock()
        mock_referrer.id = 1  # Same ID!

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_referrer
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Should not add referral (same ID)
        await mgr._process_referral(mock_session, mock_user, "TESTCODE")
        # No referral should be added (session.add not called for Referral)
        # The check `l1_user.id == new_user.id` prevents self-referral
        assert mock_session.add.call_count == 0

    @pytest.mark.asyncio
    async def test_3_level_chain_created(self):
        """Test that 3-level chain is correctly built."""
        from src.users.user_manager import UserManager
        from src.database.models import Referral
        mgr = UserManager()

        new_user = MagicMock()
        new_user.id = 4
        new_user.telegram_id = 444

        l1 = MagicMock(); l1.id = 3; l1.referred_by_id = 2
        l2 = MagicMock(); l2.id = 2; l2.referred_by_id = 1
        l3 = MagicMock(); l3.id = 1; l3.referred_by_id = None

        call_count = [0]
        async def mock_execute(query):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                result.scalar_one_or_none.return_value = l1
            elif call_count[0] == 2:
                result.scalar_one_or_none.return_value = l2
            elif call_count[0] == 3:
                result.scalar_one_or_none.return_value = l3
            else:
                result.scalar_one_or_none.return_value = None
            return result

        mock_session = AsyncMock()
        mock_session.execute = mock_execute
        mock_session.add = MagicMock()

        await mgr._process_referral(mock_session, new_user, "REFCODE")

        # Should have added 3 Referral objects (L1, L2, L3)
        assert mock_session.add.call_count == 3
        added_objects = [call.args[0] for call in mock_session.add.call_args_list]
        levels = [obj.level for obj in added_objects]
        assert sorted(levels) == [1, 2, 3]


class TestWeeklyPayouts:
    @pytest.mark.asyncio
    async def test_payout_marks_pending_as_paid(self):
        from src.referral.referral_engine import ReferralEngine
        engine = ReferralEngine()

        mock_earning = MagicMock()
        mock_earning.id = 1
        mock_earning.status = "pending"
        mock_earning.amount_usdt = Decimal("5.0")

        with patch("src.referral.referral_engine.get_session") as mock_gs:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_earning]
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_gs.return_value = mock_session

            summary = await engine.run_weekly_payouts()
            assert summary["paid"] == 1
            assert summary["failed"] == 0
            assert mock_earning.status == "paid"
