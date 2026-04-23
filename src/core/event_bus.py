"""
Event Bus
==========
Lightweight async pub/sub system.
All bot components communicate through events — no direct coupling.

Events emitted:
  signal.generated   → New trade signal approved
  signal.rejected    → Signal failed confluence/AI check
  trade.opened       → Position opened (paper or live)
  trade.closed       → Position closed (hit SL/TP)
  risk.circuit_break → Max drawdown hit — all trading halted
  risk.daily_limit   → Daily loss limit hit — paused for day
  model.retrained    → AI model retrained with new data
  bot.error          → Unexpected error in any component
  market.regime      → Market regime changed (trending/ranging/volatile)
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


class EventType(str, Enum):
    # Signal lifecycle
    SIGNAL_GENERATED   = "signal.generated"
    SIGNAL_REJECTED    = "signal.rejected"
    # Trade lifecycle
    TRADE_OPENED       = "trade.opened"
    TRADE_CLOSED       = "trade.closed"
    TRADE_UPDATED      = "trade.updated"    # SL moved, partial close
    # Risk events
    CIRCUIT_BREAK      = "risk.circuit_break"
    DAILY_LIMIT_HIT    = "risk.daily_limit"
    DRAWDOWN_WARNING   = "risk.drawdown_warning"  # 50% of max drawdown
    EQUITY_UPDATE      = "risk.equity_update"
    # AI / Model
    MODEL_RETRAINED    = "model.retrained"
    MODEL_DEGRADED     = "model.degraded"   # accuracy dropped
    # Market
    MARKET_REGIME      = "market.regime"
    PRICE_ALERT        = "market.price_alert"
    # System
    BOT_STARTED        = "bot.started"
    BOT_STOPPED        = "bot.stopped"
    BOT_PAUSED         = "bot.paused"
    BOT_RESUMED        = "bot.resumed"
    BOT_ERROR          = "bot.error"
    SCAN_COMPLETED     = "bot.scan_completed"


@dataclass
class Event:
    """Base event payload."""
    type:      EventType
    data:      Dict[str, Any] = field(default_factory=dict)
    source:    str = "unknown"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    priority:  int = 0     # Higher = more important (processed first)

    def __lt__(self, other: "Event") -> bool:
        return self.priority > other.priority  # Higher priority = smaller in heap


# ── Handler types ─────────────────────────────────────────────────────────────
AsyncHandler = Callable[["Event"], Coroutine]
SyncHandler  = Callable[["Event"], None]


class EventBus:
    """
    Central async event bus.
    Singleton — use EventBus.get_instance() everywhere.
    """
    _instance: Optional["EventBus"] = None

    def __init__(self):
        self._handlers: Dict[EventType, List[AsyncHandler]] = defaultdict(list)
        self._global_handlers: List[AsyncHandler] = []       # Fired on ALL events
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._history: List[Event] = []
        self._max_history = 200
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._stats: Dict[str, int] = defaultdict(int)

    @classmethod
    def get_instance(cls) -> "EventBus":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Subscribe ──────────────────────────────────────────────────────────────

    def subscribe(self, event_type: EventType, handler: AsyncHandler) -> None:
        """Register an async handler for a specific event type."""
        self._handlers[event_type].append(handler)
        logger.debug(f"EventBus: subscribed to {event_type.value}")

    def subscribe_all(self, handler: AsyncHandler) -> None:
        """Handler fires on ALL events (for logging, monitoring)."""
        self._global_handlers.append(handler)

    def unsubscribe(self, event_type: EventType, handler: AsyncHandler) -> None:
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    # ── Publish ───────────────────────────────────────────────────────────────

    async def publish(self, event: Event) -> None:
        """Publish event to the bus. Non-blocking."""
        try:
            await self._queue.put(event)
            self._stats[event.type.value] += 1
        except asyncio.QueueFull:
            logger.warning(f"EventBus queue full — dropping {event.type.value}")

    def publish_sync(self, event: Event) -> None:
        """Fire-and-forget from sync context."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.publish(event))
            else:
                loop.run_until_complete(self.publish(event))
        except Exception as e:
            logger.error(f"EventBus publish_sync error: {e}")

    # ── Convenience factories ─────────────────────────────────────────────────

    async def emit_signal(self, symbol: str, direction: str, score: float,
                          confidence: float, **kwargs) -> None:
        await self.publish(Event(
            type=EventType.SIGNAL_GENERATED,
            data={"symbol": symbol, "direction": direction,
                  "confluence_score": score, "ai_confidence": confidence, **kwargs},
            source="signal_engine", priority=8,
        ))

    async def emit_trade_opened(self, symbol: str, side: str, entry: float,
                                sl: float, tp: float, size_usd: float, **kwargs) -> None:
        await self.publish(Event(
            type=EventType.TRADE_OPENED,
            data={"symbol": symbol, "side": side, "entry": entry,
                  "stop_loss": sl, "take_profit": tp, "size_usd": size_usd, **kwargs},
            source="order_manager", priority=9,
        ))

    async def emit_trade_closed(self, symbol: str, pnl: float, reason: str, **kwargs) -> None:
        await self.publish(Event(
            type=EventType.TRADE_CLOSED,
            data={"symbol": symbol, "pnl": pnl, "reason": reason, **kwargs},
            source="order_manager", priority=9,
        ))

    async def emit_circuit_break(self, reason: str, drawdown_pct: float) -> None:
        await self.publish(Event(
            type=EventType.CIRCUIT_BREAK,
            data={"reason": reason, "drawdown_pct": drawdown_pct},
            source="drawdown_monitor", priority=10,  # Highest
        ))

    async def emit_error(self, component: str, error: str) -> None:
        await self.publish(Event(
            type=EventType.BOT_ERROR,
            data={"component": component, "error": error},
            source=component, priority=7,
        ))

    # ── Dispatcher loop ───────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start async event dispatcher. Call once at bot startup."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._dispatch_loop())
        logger.info("EventBus started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"EventBus stopped. Events processed: {sum(self._stats.values())}")

    async def _dispatch_loop(self) -> None:
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._dispatch(event)
                self._history.append(event)
                if len(self._history) > self._max_history:
                    self._history.pop(0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"EventBus dispatch error: {e}", exc_info=True)

    async def _dispatch(self, event: Event) -> None:
        """Dispatch event to all registered handlers concurrently."""
        handlers = list(self._handlers.get(event.type, []))
        handlers += self._global_handlers

        if not handlers:
            logger.debug(f"EventBus: no handlers for {event.type.value}")
            return

        results = await asyncio.gather(
            *[self._safe_call(h, event) for h in handlers],
            return_exceptions=True,
        )
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"EventBus handler error for {event.type.value}: {r}")

    @staticmethod
    async def _safe_call(handler: AsyncHandler, event: Event) -> None:
        try:
            await handler(event)
        except Exception as e:
            logger.error(f"Handler {handler.__name__} failed: {e}", exc_info=True)
            raise

    # ── Inspection ────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, int]:
        return dict(self._stats)

    def get_recent_events(self, n: int = 20, event_type: Optional[EventType] = None) -> List[Event]:
        events = self._history[-n:]
        if event_type:
            events = [e for e in events if e.type == event_type]
        return events

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()


# ── Module-level convenience ──────────────────────────────────────────────────
bus = EventBus.get_instance()
