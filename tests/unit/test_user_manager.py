"""
Unit tests for UserManager — registration, verification, referral chain.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_session():
    """Mock async DB session."""
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


@pytest.fixture
def sample_user():
    from src.database.models import User, VerificationStatus, BrokerMode
    u = User(
        id=1,
        telegram_id=123456789,
        username="testuser",
        first_name="Test",
        referral_code="QA12345ABCD",
        verification_status=VerificationStatus.PENDING,
        broker_mode=BrokerMode.DEMO,
        is_active=True,
        trading_enabled=False,
    )
    return u


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestReferralCodeGeneration:
    def test_code_format(self):
        from src.users.user_manager import _generate_referral_code
        code = _generate_referral_code(123456789)
        assert code.startswith("QA")
        assert len(code) == 11  # QA + 5 digits + 4 chars

    def test_code_uniqueness(self):
        from src.users.user_manager import _generate_referral_code
        codes = {_generate_referral_code(i) for i in range(100)}
        # Should have high uniqueness (random suffix)
        assert len(codes) > 50


class TestPasswordEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        from src.users.user_manager import _encrypt_password, _decrypt_password
        plaintext = "MySecretPassword123!"
        encrypted = _encrypt_password(plaintext)
        assert encrypted != plaintext
        decrypted = _decrypt_password(encrypted)
        assert decrypted == plaintext

    def test_empty_password(self):
        from src.users.user_manager import _encrypt_password, _decrypt_password
        enc = _encrypt_password("")
        dec = _decrypt_password(enc)
        assert dec == ""


class TestUserManagerVerification:
    @pytest.mark.asyncio
    async def test_verify_empty_account_fails(self):
        from src.users.user_manager import UserManager
        mgr = UserManager()
        with patch("src.users.user_manager.get_session") as mock_gs:
            mock_gs.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_gs.return_value.__aexit__ = AsyncMock(return_value=False)
            success, msg = await mgr.verify_user(123, "")
            assert not success

    @pytest.mark.asyncio
    async def test_verify_valid_account(self):
        from src.users.user_manager import UserManager
        from src.database.models import User, VerificationStatus
        mgr = UserManager()

        mock_user = MagicMock()
        mock_user.verification_status = VerificationStatus.PENDING
        mock_user.broker_account = None

        with patch("src.users.user_manager.get_session") as mock_gs:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_user
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_gs.return_value = mock_session

            success, msg = await mgr.verify_user(123, "12345678")
            assert success
            assert "Verified" in msg

    @pytest.mark.asyncio
    async def test_already_verified_returns_true(self):
        from src.users.user_manager import UserManager
        from src.database.models import User, VerificationStatus
        mgr = UserManager()

        mock_user = MagicMock()
        mock_user.verification_status = VerificationStatus.VERIFIED
        mock_user.broker_account = "12345678"

        with patch("src.users.user_manager.get_session") as mock_gs:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_user
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_gs.return_value = mock_session

            success, msg = await mgr.verify_user(123, "12345678")
            assert success
            assert "Already verified" in msg


class TestModeSwitch:
    @pytest.mark.asyncio
    async def test_invalid_mode_rejected(self):
        from src.users.user_manager import UserManager
        mgr = UserManager()
        success, msg = await mgr.set_mode(123, "invalid_mode")
        assert not success
        assert "Invalid mode" in msg

    @pytest.mark.asyncio
    async def test_unverified_cannot_use_demo(self):
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
