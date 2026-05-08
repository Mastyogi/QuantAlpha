"""
Production Telegram Notifier — AI Trading Bot v5
=================================================
Real python-telegram-bot v20+ | Console fallback | Priority queue
Rate-limited | Dedup | Retry | ReAct signal format
"""
from __future__ import annotations
import asyncio, time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Load .env to ensure TELEGRAM_BOT_TOKEN is available
try:
    from dotenv import load_dotenv
    from pathlib import Path
    env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
except:
    pass

from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)
PRIORITY = {"CRITICAL": 0, "SIGNAL": 1, "TRADE": 2, "WARNING": 3, "INFO": 4}

try:
    from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.error import TelegramError, Forbidden
    TELEGRAM_OK = True
except ImportError:
    TELEGRAM_OK = False
    Bot = None


class _Msg:
    __slots__ = ("priority", "ts", "chat_id", "text", "markup", "dedup")
    def __init__(self, priority, chat_id, text, markup=None, dedup=None):
        self.priority = priority; self.ts = time.monotonic()
        self.chat_id = chat_id; self.text = text
        self.markup = markup; self.dedup = dedup
    def __lt__(self, other): return self.priority < other.priority


class TelegramNotifier:
    """
    Production notifier. Reads TELEGRAM_BOT_TOKEN from .env.
    Falls back to console when token not set.
    """
    SIGNAL_EMOJI = {"BUY": "📈", "SELL": "📉", "NEUTRAL": "⚪"}

    def __init__(self):
        self._bot: Optional[Any] = None
        self._is_real = False
        self.admin_chat_id = settings.telegram_admin_chat_id
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._running = False
        self._dedup: Dict[str, float] = {}
        self._stats: Dict[str, int] = defaultdict(int)
        self._last_per_chat: Dict[int, float] = defaultdict(float)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self):
        # Get token directly from environment
        import os
        token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        
        if TELEGRAM_OK and token and token not in ("placeholder_token", "", "your_bot_token"):
            try:
                self._bot = Bot(token=token)
                info = await self._bot.get_me()
                self._is_real = True
                logger.info(f"Telegram ACTIVE: @{info.username}")
                print(f"\033[92m[TELEGRAM] ✅ Bot @{info.username} connected!\033[0m")
            except Exception as e:
                logger.warning(f"Telegram init failed ({e}) — console fallback")
                self._bot = None
                self._is_real = False
        else:
            logger.info("Telegram token not set — console fallback active")
        self._running = True
        asyncio.create_task(self._sender_loop())

    async def stop(self):
        self._running = False
        for _ in range(50):
            if self._queue.empty():
                break
            await asyncio.sleep(0.1)
        if self._bot:
            try:
                await self._bot.close()
            except Exception:
                pass

    @property
    def is_real(self) -> bool:
        return self._is_real

    # ── Public API ────────────────────────────────────────────────────────────

    async def send_alert(self, level: str, message: str,
                         symbol: str = "SYS", dedup_key: Optional[str] = None):
        emoji = {"INFO": "ℹ️", "WARNING": "⚠️", "CRITICAL": "🚨",
                 "SUCCESS": "✅", "SIGNAL": "🎯"}.get(level.upper(), "•")
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        text = f"{emoji} *[{level}]* `{ts}`\n{message}"
        await self._enqueue(level, text, dedup_key=dedup_key)

    async def send_signal(self, symbol: str, direction: str, entry_price: float,
                          stop_loss: float, take_profit: float, confidence: float,
                          timeframe: str, strategy_name: str, signal_score: float,
                          additional_info: Optional[dict] = None):
        """Send trade signal — standard format."""
        ai = additional_info or {}
        emoji = self.SIGNAL_EMOJI.get(direction, "⚪")
        rr = abs(take_profit - entry_price) / max(abs(entry_price - stop_loss), 1e-10)
        tp1 = ai.get("take_profit_1", entry_price + (take_profit - entry_price) * 0.5)

        lines = [
            f"{emoji} *{direction} SIGNAL — {symbol}*",
            "━━━━━━━━━━━━━━━━━━━━",
            f"🎯 *Score:*    `{signal_score:.0f}/100`",
            f"🤖 *AI Conf:* `{confidence:.0%}`",
            "━━━━━━━━━━━━━━━━━━━━",
            f"💰 *Entry:*   `{entry_price:.6g}`",
            f"🛑 *SL:*      `{stop_loss:.6g}`",
            f"🎯 *TP1:*     `{tp1:.6g}`",
            f"🎯 *TP2:*     `{take_profit:.6g}`",
            f"📊 *R:R:*     `{rr:.2f}:1`",
            f"⏱ *TF:*      `{timeframe}` | `{strategy_name}`",
            "━━━━━━━━━━━━━━━━━━━━",
            f"🕐 `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}`",
        ]
        # Append ReAct reasoning if provided
        if ai.get("react_reasoning"):
            lines += ["", "📋 *Analysis:*", ai["react_reasoning"][:300]]
        if ai.get("regime"):
            lines.append(f"📈 *Regime:* `{ai['regime'].upper()}`")

        text = "\n".join(lines)
        kb = self._signal_keyboard(symbol, direction)
        await self._enqueue("SIGNAL", text, markup=kb,
                            dedup_key=f"sig:{symbol}:{direction}:{int(entry_price)}")

    async def send_quant_signal(self, signal_data: dict):
        """
        Send full Quant-Grade signal with ReAct framework format (from PDF spec).
        signal_data keys: symbol, market, direction, confidence_score,
        observation, fundamental, sentiment, technical, on_chain,
        research_validation, conclusion, entry, sl, tp, lot_size, validity,
        risk_considerations
        """
        sym   = signal_data.get("symbol", "UNKNOWN")
        mkt   = signal_data.get("market", "Cryptocurrency")
        direc = signal_data.get("direction", "BUY")
        conf  = signal_data.get("confidence_score", 75)
        entry = signal_data.get("entry", 0)
        sl    = signal_data.get("sl", 0)
        tp    = signal_data.get("tp", 0)
        emoji = self.SIGNAL_EMOJI.get(direc, "⚪")
        rr    = abs(tp - entry) / max(abs(entry - sl), 1e-10)

        lines = [
            f"{'🔥' if conf >= 85 else '⚡'} *QUANT SIGNAL — {sym}*",
            f"{'━' * 22}",
            f"📊 *Market:*   `{mkt}`",
            f"{emoji} *Direction:* `{direc}`",
            f"🧠 *Confidence:* `{conf}%`",
            "",
            f"*📋 ReAct Reasoning:*",
            f"• *Obs:* {signal_data.get('observation','N/A')[:120]}",
            f"• *Tech:* {signal_data.get('technical','N/A')[:120]}",
            f"• *Fund:* {signal_data.get('fundamental','N/A')[:100]}",
            f"• *Sent:* {signal_data.get('sentiment','N/A')[:100]}",
        ]
        if signal_data.get("on_chain"):
            lines.append(f"• *OnChain:* {signal_data['on_chain'][:100]}")
        lines += [
            "",
            f"*🎯 Signal Parameters:*",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"💰 *Entry:*  `{entry:.6g}`",
            f"🛑 *SL:*     `{sl:.6g}`",
            f"🎯 *TP:*     `{tp:.6g}`",
            f"📊 *R:R:*    `{rr:.2f}:1`",
            f"📦 *Size:*   `{signal_data.get('lot_size','auto')}`",
            f"⏰ *Valid:*  `{signal_data.get('validity','24h')}`",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"⚠️ *Risk:* {signal_data.get('risk_considerations','Manage position size')[:100]}",
            f"🕐 `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}`",
        ]
        text = "\n".join(lines)
        kb = self._signal_keyboard(sym, direc)
        await self._enqueue("SIGNAL", text, markup=kb,
                            dedup_key=f"qsig:{sym}:{direc}:{int(entry)}")

    async def send_trade_opened(self, symbol: str, side: str, entry_price: float,
                                 stop_loss: float, take_profit: float, size_usd: float,
                                 order_id: str, rr_ratio: float):
        arrow = "📈" if side == "BUY" else "📉"
        lines = [
            f"{arrow} *TRADE OPENED — {symbol}*",
            "━━━━━━━━━━━━━━━━━━━━",
            f"Direction: `{side}` | Size: `${size_usd:.2f}`",
            f"Entry:  `{entry_price:.6g}`",
            f"SL:     `{stop_loss:.6g}`",
            f"TP:     `{take_profit:.6g}`",
            f"R:R:    `{rr_ratio:.2f}:1`",
            f"Mode:   `PAPER`",
            f"🕐 `{datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}`",
        ]
        await self._enqueue("TRADE", "\n".join(lines))

    async def send_trade_closed(self, symbol: str, side: str, entry_price: float,
                                 exit_price: float, pnl_usd: float, pnl_pct: float,
                                 close_reason: str):
        won = pnl_usd > 0
        emoji = "✅" if won else "❌"
        sign = "+" if won else ""
        lines = [
            f"{emoji} *TRADE CLOSED — {symbol}*",
            "━━━━━━━━━━━━━━━━━━━━",
            f"Direction: `{side}`",
            f"Entry:  `{entry_price:.6g}`",
            f"Exit:   `{exit_price:.6g}`",
            f"P&L:    `{sign}{pnl_usd:.4f} USD ({pnl_pct:+.2f}%)`",
            f"Reason: `{close_reason}`",
            f"🕐 `{datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}`",
        ]
        await self._enqueue("TRADE", "\n".join(lines))

    async def send_pnl_report(self, equity: float, daily_pnl: float, win_rate: float,
                               profit_factor: float, max_dd: float,
                               total_trades: int, day_num: int):
        sign = "📈" if daily_pnl >= 0 else "📉"
        pnl_sign = "+" if daily_pnl >= 0 else ""
        lines = [
            f"📊 *Daily P&L Report — Day {day_num}*",
            "━━━━━━━━━━━━━━━━━━━━",
            f"{sign} Daily P&L:  `{pnl_sign}{daily_pnl:.4f} USD`",
            f"💰 Equity:    `${equity:.4f}`",
            "━━━━━━━━━━━━━━━━━━━━",
            f"🎯 Win Rate:  `{win_rate:.1%}`",
            f"📊 PF:        `{profit_factor:.2f}`",
            f"📉 Max DD:    `{max_dd:.2f}%`",
            f"🔢 Trades:    `{total_trades}`",
            f"Mode: `PAPER` | `{datetime.now(timezone.utc).strftime('%Y-%m-%d UTC')}`",
        ]
        await self._enqueue("INFO", "\n".join(lines),
                            dedup_key=f"daily_day{day_num}")

    async def send_circuit_breaker(self, reason: str, equity: float, dd_pct: float):
        lines = [
            "🚨 *CIRCUIT BREAKER TRIGGERED*",
            "━━━━━━━━━━━━━━━━━━━━",
            f"Reason:   `{reason}`",
            f"Equity:   `${equity:.4f}`",
            f"Drawdown: `{dd_pct:.2f}%`",
            "Status:   `TRADING HALTED`",
            "Command:  `/resume` to restart",
        ]
        await self._enqueue("CRITICAL", "\n".join(lines))

    async def send_retrain_notification(self, symbol: str, precision: float,
                                         mode: str, deployed: bool):
        lines = [
            f"🤖 *Model Retrain — {symbol}*",
            f"Mode: `{mode}` | Deployed: `{'YES' if deployed else 'NO'}`",
            f"Precision: `{precision:.1%}`",
        ]
        await self._enqueue("INFO", "\n".join(lines),
                            dedup_key=f"retrain:{symbol}:{mode}")

    def get_stats(self) -> dict:
        return {
            "mode":      "REAL_TELEGRAM" if self._is_real else "CONSOLE_FALLBACK",
            "sent":      self._stats["sent"],
            "failed":    self._stats["failed"],
            "throttled": self._stats["throttled"],
            "queue":     self._queue.qsize(),
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _enqueue(self, level: str, text: str,
                       markup=None, dedup_key: Optional[str] = None):
        priority = PRIORITY.get(level.upper(), 4)
        if dedup_key:
            last = self._dedup.get(dedup_key, 0.0)
            if time.monotonic() - last < 60.0:
                self._stats["deduped"] += 1
                return
            self._dedup[dedup_key] = time.monotonic()
        if not self._is_real:
            self._console_print(level, text)
        msg = _Msg(priority, self.admin_chat_id, text, markup, dedup_key)
        await self._queue.put(msg)

    async def _sender_loop(self):
        while self._running:
            try:
                msg = await asyncio.wait_for(self._queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            if self._is_real and self._bot:
                await self._send_real(msg)
            else:
                self._console_print("INFO", msg.text)
                self._stats["sent"] += 1
                self._queue.task_done()

    async def _send_real(self, msg: _Msg):
        now = time.monotonic()
        wait = 1.05 - (now - self._last_per_chat[msg.chat_id])
        if wait > 0:
            self._stats["throttled"] += 1
            await asyncio.sleep(wait)
        for attempt in range(3):
            try:
                await self._bot.send_message(
                    chat_id=msg.chat_id,
                    text=msg.text,
                    parse_mode="Markdown",
                    reply_markup=msg.markup,
                )
                self._last_per_chat[msg.chat_id] = time.monotonic()
                self._stats["sent"] += 1
                self._queue.task_done()
                return
            except Exception as e:
                err = str(e).lower()
                if "flood" in err or "429" in err:
                    await asyncio.sleep(5.0 * (2 ** attempt))
                elif "blocked" in err or "forbidden" in err:
                    logger.error(f"Bot blocked by {msg.chat_id}")
                    self._stats["failed"] += 1
                    self._queue.task_done()
                    return
                elif attempt == 2:
                    logger.error(f"Telegram failed: {e}")
                    self._console_print("WARNING", msg.text)
                    self._stats["failed"] += 1
                    self._queue.task_done()
                    return
                else:
                    await asyncio.sleep(attempt + 1)

    def _console_print(self, level: str, text: str):
        colors = {
            "CRITICAL": "\033[91m", "SIGNAL": "\033[92m",
            "TRADE": "\033[94m", "WARNING": "\033[93m", "INFO": "\033[96m",
        }
        reset = "\033[0m"
        color = colors.get(level.upper(), "")
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        clean = text.replace("*", "").replace("`", "").replace("━", "—")[:300]
        try:
            print(f"{color}[{ts}] [{level}] {clean}{reset}")
        except UnicodeEncodeError:
            # Fallback for Windows console with limited encoding
            safe_text = clean.encode("ascii", "ignore").decode("ascii")
            print(f"{color}[{ts}] [{level}] {safe_text}{reset}")

    def _signal_keyboard(self, symbol: str, direction: str):
        if not TELEGRAM_OK:
            return None
        try:
            arrow = "📈" if direction == "BUY" else "📉"
            return InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(f"{arrow} Execute Paper",
                                         callback_data=f"sig_accept:{symbol}"),
                    InlineKeyboardButton("❌ Skip",
                                         callback_data=f"sig_skip:{symbol}"),
                ],
                [
                    InlineKeyboardButton("📊 Details",
                                         callback_data=f"sig_details:{symbol}"),
                    InlineKeyboardButton("📋 Chart",
                                         callback_data=f"sig_chart:{symbol}"),
                ],
            ])
        except Exception:
            return None
