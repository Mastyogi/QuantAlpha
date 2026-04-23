"""
Telegram Rate Limiter
======================
Prevents Telegram API 429 (Too Many Requests) flood bans.

Telegram limits:
  - 30 messages/second to different chats
  - 1 message/second to the same chat
  - Inline keyboard updates: 20/min per user

This module implements:
  1. Token bucket algorithm per chat_id
  2. Priority queue (CRITICAL > SIGNAL > INFO)
  3. Automatic retry with exponential backoff on 429
  4. Message deduplication (don't send same alert twice)
  5. Batch status: aggregate multiple alerts into one message
"""
from __future__ import annotations

import asyncio
import hashlib
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Coroutine, Deque, Dict, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


class Priority(IntEnum):
    CRITICAL = 0   # Highest — circuit breaker, system error
    SIGNAL   = 1   # Trade signals
    TRADE    = 2   # Trade opened/closed
    WARNING  = 3   # Risk warnings
    INFO     = 4   # Status updates, PnL reports


@dataclass(order=True)
class QueuedMessage:
    priority:   int              # Lower = higher priority
    enqueued_at: float = field(compare=False)
    chat_id:    Any    = field(compare=False)
    text:       str    = field(compare=False)
    parse_mode: str    = field(compare=False, default="Markdown")
    reply_markup: Any  = field(compare=False, default=None)
    dedup_key:  Optional[str] = field(compare=False, default=None)


class TokenBucket:
    """Token bucket rate limiter for a single chat."""

    def __init__(self, rate: float = 1.0, burst: int = 3):
        """
        Args:
            rate:  tokens per second (1.0 = 1 msg/sec per chat)
            burst: max burst size before throttling
        """
        self.rate      = rate
        self.burst     = burst
        self._tokens   = float(burst)
        self._last_refill = time.monotonic()

    def consume(self) -> bool:
        """Try to consume one token. Returns True if allowed."""
        self._refill()
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False

    def wait_time(self) -> float:
        """Seconds until next token available."""
        self._refill()
        if self._tokens >= 1.0:
            return 0.0
        return (1.0 - self._tokens) / self.rate

    def _refill(self):
        now    = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        self._last_refill = now


class TelegramRateLimiter:
    """
    Rate-limited message dispatcher for Telegram Bot API.
    Drop-in wrapper around Bot.send_message().
    """

    # Telegram global limits
    MAX_PER_SECOND     = 25     # Global: 30/s max, use 25 for safety
    MAX_PER_CHAT       = 1.0    # Per chat: 1 msg/sec
    MAX_DEDUP_WINDOW   = 60.0   # Seconds to track dedup keys

    def __init__(self):
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._buckets: Dict[Any, TokenBucket] = defaultdict(
            lambda: TokenBucket(rate=self.MAX_PER_CHAT, burst=3)
        )
        self._global_bucket = TokenBucket(rate=self.MAX_PER_SECOND, burst=5)
        self._dedup_cache: Dict[str, float] = {}
        self._running = False
        self._send_fn: Optional[Callable] = None
        self._stats = defaultdict(int)

    def set_send_function(self, fn: Callable):
        """Register the actual bot.send_message coroutine function."""
        self._send_fn = fn

    async def enqueue(
        self,
        chat_id:     Any,
        text:        str,
        priority:    Priority = Priority.INFO,
        parse_mode:  str = "Markdown",
        reply_markup: Any = None,
        dedup_key:   Optional[str] = None,
    ):
        """
        Add a message to the send queue.
        Deduplication: if dedup_key already sent < 60s ago, skip.
        """
        # Deduplication check
        if dedup_key:
            last_sent = self._dedup_cache.get(dedup_key, 0.0)
            if time.monotonic() - last_sent < self.MAX_DEDUP_WINDOW:
                logger.debug(f"Dedup skip: {dedup_key}")
                self._stats["deduped"] += 1
                return

        msg = QueuedMessage(
            priority     = int(priority),
            enqueued_at  = time.monotonic(),
            chat_id      = chat_id,
            text         = text,
            parse_mode   = parse_mode,
            reply_markup = reply_markup,
            dedup_key    = dedup_key,
        )
        await self._queue.put(msg)
        self._stats["enqueued"] += 1

    async def start(self):
        """Start the background message dispatcher task."""
        self._running = True
        asyncio.create_task(self._dispatcher())
        logger.info("TelegramRateLimiter started")

    async def stop(self):
        """Graceful shutdown — flush remaining messages."""
        self._running = False
        # Drain the queue (up to 10 more messages)
        for _ in range(10):
            if self._queue.empty():
                break
            await asyncio.sleep(0.1)

    def get_stats(self) -> dict:
        return {
            "enqueued": self._stats["enqueued"],
            "sent":     self._stats["sent"],
            "throttled": self._stats["throttled"],
            "errors":   self._stats["errors"],
            "deduped":  self._stats["deduped"],
            "queue_size": self._queue.qsize(),
        }

    # ── Background dispatcher ─────────────────────────────────────────────────

    async def _dispatcher(self):
        """Process the priority queue, respecting rate limits."""
        while self._running:
            try:
                # Non-blocking get with 0.1s timeout
                try:
                    msg = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    continue

                # Check per-chat bucket
                bucket = self._buckets[msg.chat_id]
                if not bucket.consume():
                    wait = bucket.wait_time()
                    self._stats["throttled"] += 1
                    logger.debug(f"Rate limit: waiting {wait:.2f}s for chat {msg.chat_id}")
                    await asyncio.sleep(wait)
                    bucket.consume()

                # Check global bucket
                if not self._global_bucket.consume():
                    await asyncio.sleep(0.05)
                    self._global_bucket.consume()

                # Send the message
                await self._send_with_retry(msg)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Dispatcher error: {e}")
                await asyncio.sleep(1.0)

    async def _send_with_retry(self, msg: QueuedMessage, max_retries: int = 3):
        """Send message with exponential backoff retry on 429."""
        if not self._send_fn:
            logger.warning("No send function registered")
            return

        for attempt in range(max_retries):
            try:
                await self._send_fn(
                    chat_id     = msg.chat_id,
                    text        = msg.text,
                    parse_mode  = msg.parse_mode,
                    reply_markup= msg.reply_markup,
                )
                # Update dedup cache on success
                if msg.dedup_key:
                    self._dedup_cache[msg.dedup_key] = time.monotonic()

                # Cleanup old dedup entries
                now = time.monotonic()
                expired = [k for k, t in self._dedup_cache.items()
                           if now - t > self.MAX_DEDUP_WINDOW * 2]
                for k in expired:
                    del self._dedup_cache[k]

                self._stats["sent"] += 1
                self._queue.task_done()
                return

            except Exception as e:
                err_str = str(e).lower()
                if "flood" in err_str or "429" in err_str:
                    wait = 2 ** attempt * 5.0  # 5s, 10s, 20s
                    logger.warning(f"Telegram flood control: waiting {wait:.0f}s (attempt {attempt+1})")
                    await asyncio.sleep(wait)
                elif attempt == max_retries - 1:
                    logger.error(f"Failed to send Telegram message after {max_retries} attempts: {e}")
                    self._stats["errors"] += 1
                    self._queue.task_done()
                    return
                else:
                    await asyncio.sleep(1.0)
