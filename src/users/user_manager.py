"""
User Manager
=============
Handles user registration, verification, broker linking, and per-user state.
Architecture:
  - Each Telegram user gets a User row in the DB.
  - Each user has their own MT5 credentials (stored AES-encrypted).
  - Verification is manual (/verify <broker_account>) or via FxPro API.
  - Only verified users can start demo/real trading.
"""
from __future__ import annotations

import os
import secrets
import string
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import get_session
from src.database.models import User, VerificationStatus, BrokerMode, Referral
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ── Referral fee constants ────────────────────────────────────────────────────
SERVICE_FEE_PCT   = 0.15   # 15% total service fee on profits
REF_L1_PCT        = 0.025  # 2.5% to level-1 referrer
REF_L2_PCT        = 0.015  # 1.5% to level-2 referrer
REF_L3_PCT        = 0.010  # 1.0% to level-3 referrer
OWNER_FEE_PCT     = 0.10   # 10% to bot owner

FXPRO_PARTNER_LINK = "https://direct-fxpro.com/en/partner/2FiFKGf7J"


def _generate_referral_code(telegram_id: int) -> str:
    """Generate a short unique referral code from telegram_id + random suffix."""
    suffix = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    return f"QA{telegram_id % 100000:05d}{suffix}"


class UserManager:
    """
    Central user lifecycle manager.
    All DB operations are async-safe and gracefully handle DB unavailability.
    """

    # ── Create / Get ──────────────────────────────────────────────────────────

    async def get_or_create(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        referral_code: Optional[str] = None,
    ) -> Tuple[User, bool]:
        """
        Get existing user or create new one.
        Returns (user, created_flag).
        If referral_code is provided, links the referral chain.
        """
        async with get_session() as session:
            if session is None:
                # DB offline — return ephemeral user object
                user = User(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    referral_code=_generate_referral_code(telegram_id),
                )
                return user, True

            # Try to find existing user
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()

            if user:
                # Update name fields if changed
                if username and user.username != username:
                    user.username = username
                if first_name and user.first_name != first_name:
                    user.first_name = first_name
                return user, False

            # Create new user
            ref_code = _generate_referral_code(telegram_id)
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                referral_code=ref_code,
                verification_status=VerificationStatus.PENDING,
                broker_mode=BrokerMode.DEMO,
            )
            session.add(user)
            await session.flush()
            await session.refresh(user)

            # Process referral chain if code provided
            if referral_code:
                await self._process_referral(session, user, referral_code)

            logger.info(f"New user created: tg={telegram_id} ref={ref_code}")
            return user, True

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Fetch user by Telegram ID."""
        async with get_session() as session:
            if session is None:
                return None
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            return result.scalar_one_or_none()

    async def get_by_referral_code(self, code: str) -> Optional[User]:
        """Fetch user by referral code."""
        async with get_session() as session:
            if session is None:
                return None
            result = await session.execute(
                select(User).where(User.referral_code == code)
            )
            return result.scalar_one_or_none()

    # ── Verification ──────────────────────────────────────────────────────────

    async def verify_user(
        self,
        telegram_id: int,
        broker_account: str,
        admin_confirmed: bool = False,
    ) -> Tuple[bool, str]:
        """
        Verify a user's broker account.
        Returns (success, message).
        """
        async with get_session() as session:
            if session is None:
                return False, "Database unavailable"

            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                return False, "User not found. Please /start first."

            if user.verification_status == VerificationStatus.VERIFIED:
                return True, f"Already verified. Broker: {user.broker_account}"

            # Attempt FxPro API verification (stub — real API requires FxPro partner access)
            verified = await self._check_fxpro_account(broker_account)

            if verified or admin_confirmed:
                user.broker_account = broker_account
                user.verification_status = VerificationStatus.VERIFIED
                user.verified_at = datetime.now(timezone.utc)
                user.trading_enabled = True
                logger.info(f"User {telegram_id} verified with broker {broker_account}")
                return True, f"✅ Verified! Broker account: {broker_account}"
            else:
                return (
                    False,
                    "Could not verify broker account automatically.\n"
                    "Please ensure you registered via the partner link and contact support.",
                )

    async def _check_fxpro_account(self, broker_account: str) -> bool:
        """
        Check FxPro account via API.
        Currently a stub — returns True if account looks valid (non-empty).
        Real implementation requires FxPro Partner API credentials.
        """
        # TODO: Integrate with FxPro Partner API when credentials are available
        # For now: accept any non-empty account number as valid
        return bool(broker_account and len(broker_account) >= 4)

    async def admin_verify(self, telegram_id: int, broker_account: str) -> Tuple[bool, str]:
        """Admin-forced verification via /admin_verify command."""
        return await self.verify_user(telegram_id, broker_account, admin_confirmed=True)

    # ── Mode switching ────────────────────────────────────────────────────────

    async def set_mode(
        self, telegram_id: int, mode: str
    ) -> Tuple[bool, str]:
        """
        Switch user between demo/real/paper modes.
        Only verified users can switch to demo/real.
        """
        if mode not in ("paper", "demo", "real"):
            return False, "Invalid mode. Use: paper, demo, real"

        async with get_session() as session:
            if session is None:
                return False, "Database unavailable"

            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                return False, "User not found"

            if mode in ("demo", "real") and user.verification_status != VerificationStatus.VERIFIED:
                return (
                    False,
                    "You must be verified to use demo/real mode.\n"
                    f"Register at: {FXPRO_PARTNER_LINK}\nThen use /verify <account_number>",
                )

            user.current_mode = mode
            if mode == "demo":
                user.broker_mode = BrokerMode.DEMO
            elif mode == "real":
                user.broker_mode = BrokerMode.REAL

            logger.info(f"User {telegram_id} switched to {mode} mode")
            return True, f"✅ Switched to {mode.upper()} mode"

    # ── MT5 credentials ───────────────────────────────────────────────────────

    async def set_mt5_credentials(
        self,
        telegram_id: int,
        mt5_login: str,
        mt5_password: str,
        mt5_server: str,
    ) -> Tuple[bool, str]:
        """Store per-user MT5 credentials (password AES-encrypted)."""
        encrypted_pw = _encrypt_password(mt5_password)

        async with get_session() as session:
            if session is None:
                return False, "Database unavailable"

            await session.execute(
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(
                    mt5_login=mt5_login,
                    mt5_password_enc=encrypted_pw,
                    mt5_server=mt5_server,
                )
            )
            return True, "MT5 credentials saved"

    async def get_mt5_credentials(
        self, telegram_id: int
    ) -> Optional[dict]:
        """Retrieve decrypted MT5 credentials for a user."""
        user = await self.get_by_telegram_id(telegram_id)
        if not user or not user.mt5_login:
            return None
        return {
            "login": int(user.mt5_login),
            "password": _decrypt_password(user.mt5_password_enc or ""),
            "server": user.mt5_server or os.getenv("MT5_SERVER", "FxPro-Demo"),
        }

    # ── Referral chain ────────────────────────────────────────────────────────

    async def _process_referral(
        self,
        session: AsyncSession,
        new_user: User,
        referral_code: str,
    ) -> None:
        """
        Build 3-level referral chain for new_user.
        Level 1: direct referrer
        Level 2: referrer's referrer
        Level 3: level-2's referrer
        """
        # Find level-1 referrer
        result = await session.execute(
            select(User).where(User.referral_code == referral_code)
        )
        l1_user = result.scalar_one_or_none()
        if not l1_user or l1_user.id == new_user.id:
            return

        new_user.referred_by_id = l1_user.id

        # Create L1 referral
        session.add(Referral(
            referrer_id=l1_user.id,
            referred_id=new_user.id,
            level=1,
        ))

        # Find level-2 referrer
        if l1_user.referred_by_id:
            result2 = await session.execute(
                select(User).where(User.id == l1_user.referred_by_id)
            )
            l2_user = result2.scalar_one_or_none()
            if l2_user:
                session.add(Referral(
                    referrer_id=l2_user.id,
                    referred_id=new_user.id,
                    level=2,
                ))

                # Find level-3 referrer
                if l2_user.referred_by_id:
                    result3 = await session.execute(
                        select(User).where(User.id == l2_user.referred_by_id)
                    )
                    l3_user = result3.scalar_one_or_none()
                    if l3_user:
                        session.add(Referral(
                            referrer_id=l3_user.id,
                            referred_id=new_user.id,
                            level=3,
                        ))

        logger.info(f"Referral chain built for user {new_user.telegram_id}")

    async def get_referral_stats(self, telegram_id: int) -> dict:
        """Get referral statistics for a user."""
        async with get_session() as session:
            if session is None:
                return {"total": 0, "l1": 0, "l2": 0, "l3": 0, "earnings": 0.0}

            user = await self.get_by_telegram_id(telegram_id)
            if not user:
                return {"total": 0, "l1": 0, "l2": 0, "l3": 0, "earnings": 0.0}

            from sqlalchemy import func as sqlfunc
            from src.database.models import ReferralEarning

            # Count referrals by level
            counts = {}
            for lvl in (1, 2, 3):
                r = await session.execute(
                    select(sqlfunc.count(Referral.id)).where(
                        Referral.referrer_id == user.id,
                        Referral.level == lvl,
                    )
                )
                counts[lvl] = r.scalar() or 0

            # Total earnings
            earn_r = await session.execute(
                select(sqlfunc.sum(ReferralEarning.amount_usdt)).where(
                    ReferralEarning.user_id == user.id,
                    ReferralEarning.status == "paid",
                )
            )
            total_earnings = float(earn_r.scalar() or 0)

            # Pending earnings
            pend_r = await session.execute(
                select(sqlfunc.sum(ReferralEarning.amount_usdt)).where(
                    ReferralEarning.user_id == user.id,
                    ReferralEarning.status == "pending",
                )
            )
            pending_earnings = float(pend_r.scalar() or 0)

            return {
                "referral_code": user.referral_code,
                "total": counts[1] + counts[2] + counts[3],
                "l1": counts[1],
                "l2": counts[2],
                "l3": counts[3],
                "earnings_paid": total_earnings,
                "earnings_pending": pending_earnings,
                "link": f"https://t.me/QuantAlphaBot?start=ref_{user.referral_code}",
            }

    async def is_verified(self, telegram_id: int) -> bool:
        """Quick check if user is verified."""
        user = await self.get_by_telegram_id(telegram_id)
        return user is not None and user.verification_status == VerificationStatus.VERIFIED

    async def is_trading_enabled(self, telegram_id: int) -> bool:
        """Check if user can trade."""
        user = await self.get_by_telegram_id(telegram_id)
        return user is not None and user.trading_enabled and user.is_active


# ── Crypto helpers ────────────────────────────────────────────────────────────

def _encrypt_password(plaintext: str) -> str:
    """AES-encrypt a password using the app secret key."""
    try:
        from cryptography.fernet import Fernet
        import base64, hashlib
        key_raw = os.getenv("SECRET_KEY", "quantalpha-default-secret-key-32b")
        key = base64.urlsafe_b64encode(hashlib.sha256(key_raw.encode()).digest())
        f = Fernet(key)
        return f.encrypt(plaintext.encode()).decode()
    except Exception:
        # Fallback: base64 encode (not secure — use only if cryptography not installed)
        import base64
        return base64.b64encode(plaintext.encode()).decode()


def _decrypt_password(ciphertext: str) -> str:
    """Decrypt an AES-encrypted password."""
    try:
        from cryptography.fernet import Fernet
        import base64, hashlib
        key_raw = os.getenv("SECRET_KEY", "quantalpha-default-secret-key-32b")
        key = base64.urlsafe_b64encode(hashlib.sha256(key_raw.encode()).digest())
        f = Fernet(key)
        return f.decrypt(ciphertext.encode()).decode()
    except Exception:
        try:
            import base64
            return base64.b64decode(ciphertext.encode()).decode()
        except Exception:
            return ""


# Module-level singleton
user_manager = UserManager()
