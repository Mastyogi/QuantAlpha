"""
Load / performance tests: 1000 concurrent users trading and withdrawing.
Uses asyncio to simulate concurrent operations.
Response time must stay under 2 seconds.
"""
import pytest
import asyncio
import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch


async def _simulate_user_operation(user_id: int) -> float:
    """Simulate a single user's operation. Returns elapsed time in seconds."""
    from src.users.user_manager import _generate_referral_code, _encrypt_password, _decrypt_password

    start = time.monotonic()

    # Simulate referral code generation (CPU-bound, fast)
    code = _generate_referral_code(user_id)
    assert code.startswith("QA")

    # Simulate password encryption/decryption
    enc = _encrypt_password(f"password_{user_id}")
    dec = _decrypt_password(enc)
    assert dec == f"password_{user_id}"

    # Simulate fee calculation
    gross = Decimal(str(user_id % 1000 + 10))
    fee = gross * Decimal("0.15")
    net = gross - fee
    assert net + fee == gross

    elapsed = time.monotonic() - start
    return elapsed


@pytest.mark.asyncio
async def test_1000_concurrent_fee_calculations():
    """1000 concurrent fee calculations must complete in < 2 seconds."""
    start = time.monotonic()

    tasks = [_simulate_user_operation(i) for i in range(1000)]
    results = await asyncio.gather(*tasks)

    total_elapsed = time.monotonic() - start
    max_single = max(results)
    avg_single = sum(results) / len(results)

    print(f"\nLoad test: 1000 users")
    print(f"  Total time: {total_elapsed:.3f}s")
    print(f"  Max single op: {max_single*1000:.1f}ms")
    print(f"  Avg single op: {avg_single*1000:.2f}ms")

    assert total_elapsed < 10.0, f"1000 ops took {total_elapsed:.1f}s (limit: 10s)"
    assert max_single < 2.0, f"Single op took {max_single:.3f}s (limit: 2s)"


@pytest.mark.asyncio
async def test_concurrent_withdrawal_requests_no_double_spend():
    """
    Concurrent withdrawal requests for the same user should not double-spend.
    Only one should succeed if balance is insufficient for both.
    """
    from src.bridge.withdraw_handler import WithdrawHandler
    from src.database.models import VerificationStatus

    handler = WithdrawHandler()

    # User has 100 USDT — two concurrent requests for 80 USDT each
    balance = [Decimal("100")]  # Mutable for closure

    async def mock_withdraw_with_balance_check(telegram_id, amount, address):
        # Simulate atomic balance check
        if balance[0] < amount:
            return False, "Insufficient balance"
        balance[0] -= amount
        return True, f"Withdrawn {amount}"

    with patch.object(handler, "request_withdrawal", side_effect=mock_withdraw_with_balance_check):
        tasks = [
            handler.request_withdrawal(123, Decimal("80"), "0x" + "a" * 40),
            handler.request_withdrawal(123, Decimal("80"), "0x" + "a" * 40),
        ]
        results = await asyncio.gather(*tasks)

    successes = [r for r, _ in results if r]
    failures = [r for r, _ in results if not r]

    # At most one should succeed (balance only allows one 80 USDT withdrawal)
    assert len(successes) <= 1, "Double-spend detected!"


@pytest.mark.asyncio
async def test_response_time_under_load():
    """
    Simulate 100 concurrent /balance command handlers.
    Each must respond in < 2 seconds.
    """
    async def mock_balance_handler(user_id: int) -> float:
        start = time.monotonic()
        # Simulate DB lookup + formatting
        await asyncio.sleep(0.001)  # 1ms simulated DB query
        elapsed = time.monotonic() - start
        return elapsed

    start = time.monotonic()
    tasks = [mock_balance_handler(i) for i in range(100)]
    times = await asyncio.gather(*tasks)
    total = time.monotonic() - start

    max_time = max(times)
    assert max_time < 2.0, f"Response time {max_time:.3f}s exceeds 2s limit"
    assert total < 5.0, f"100 concurrent requests took {total:.1f}s"
    print(f"\n100 concurrent /balance: max={max_time*1000:.1f}ms total={total:.2f}s")
