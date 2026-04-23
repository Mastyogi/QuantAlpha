"""
Telegram Formatters
====================
Rich Markdown-formatted messages for every bot event.
All formatters return strings ready to send via python-telegram-bot.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M UTC")


def _pct(v: float) -> str:
    return f"{'+' if v >= 0 else ''}{v:.2f}%"


def _usd(v: float) -> str:
    return f"{'+'if v >= 0 else ''}${abs(v):,.2f}" if v != 0 else "$0.00"


def _price(v: float, symbol: str = "") -> str:
    fx = symbol and "/" not in symbol
    return f"{v:.4f}" if fx else f"{v:,.2f}"


# ── Signal Messages ───────────────────────────────────────────────────────────

def format_signal(
    symbol: str,
    direction: str,
    entry: float,
    stop_loss: float,
    take_profit_1: float,
    take_profit_2: float,
    take_profit_3: float,
    confluence_score: float,
    ai_confidence: float,
    rr_ratio: float,
    timeframe: str = "1H",
    win_rate_est: float = 0.0,
    risk_usd: float = 0.0,
    reasons: Optional[List[str]] = None,
) -> str:
    """
    Full trade signal notification.
    Example output:
    ╔══════════════════════════════╗
    ║ 📈 BUY SIGNAL — BTC/USDT    ║
    ╚══════════════════════════════╝
    ...
    """
    is_buy  = direction.upper() == "BUY"
    emoji   = "📈" if is_buy else "📉"
    score_e = "🔥" if confluence_score >= 85 else "✅" if confluence_score >= 75 else "⚠️"
    conf_e  = "🤖" if ai_confidence >= 0.80 else "🔸"

    risk_pct = abs(entry - stop_loss) / entry * 100

    lines = [
        f"{emoji} *{direction} SIGNAL — {symbol}*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"{score_e} *Confluence Score:* `{confluence_score:.0f}/100`",
        f"{conf_e} *AI Confidence:* `{ai_confidence:.0%}`",
        f"⏰ *Timeframe:* `{timeframe}`",
        f"",
        f"💰 *Entry:*     `{_price(entry, symbol)}`",
        f"🛑 *Stop Loss:* `{_price(stop_loss, symbol)}` `(-{risk_pct:.2f}%)`",
        f"",
        f"🎯 *Target 1:*  `{_price(take_profit_1, symbol)}` *(1:1)*",
        f"🎯 *Target 2:*  `{_price(take_profit_2, symbol)}` *({rr_ratio:.1f}:1)*",
        f"🎯 *Target 3:*  `{_price(take_profit_3, symbol)}` *(extended)*",
        f"",
        f"📊 *R:R Ratio:* `{rr_ratio:.2f}:1`",
    ]

    if risk_usd > 0:
        lines.append(f"💸 *Risk Amount:* `${risk_usd:.2f}`")
    if win_rate_est > 0:
        lines.append(f"🏆 *Est. Win Rate:* `{win_rate_est:.0%}`")

    if reasons:
        lines += ["", "📋 *Confluence Factors:*"]
        for r in reasons[:4]:
            lines.append(f"   ✓ {r}")

    lines += ["", f"⏱ _{_now()}_"]
    return "\n".join(lines)


def format_signal_rejected(
    symbol: str,
    direction: str,
    score: float,
    threshold: float,
    reason: str,
) -> str:
    """Brief rejection notification (usually not sent to avoid spam)."""
    return (
        f"🚫 *Signal Filtered — {symbol}*\n"
        f"Direction: `{direction}` | Score: `{score:.0f}/{threshold:.0f}`\n"
        f"Reason: _{reason}_\n"
        f"⏱ _{_now()}_"
    )


# ── Trade Execution ───────────────────────────────────────────────────────────

def format_trade_opened(
    symbol: str,
    side: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    size_usd: float,
    order_id: str,
    is_paper: bool = True,
    rr_ratio: float = 0.0,
) -> str:
    mode   = "📋 PAPER" if is_paper else "🔴 LIVE"
    emoji  = "🟢" if side.upper() == "BUY" else "🔴"
    return (
        f"{emoji} *Trade Opened* `{mode}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 *Symbol:* `{symbol}`\n"
        f"↕️ *Side:* `{side.upper()}`\n"
        f"💰 *Entry:* `{_price(entry_price, symbol)}`\n"
        f"🛑 *SL:* `{_price(stop_loss, symbol)}`\n"
        f"🎯 *TP:* `{_price(take_profit, symbol)}`\n"
        f"💼 *Size:* `${size_usd:,.2f}`\n"
        + (f"📊 *R:R:* `{rr_ratio:.2f}:1`\n" if rr_ratio > 0 else "")
        + f"🆔 `{order_id[:12]}...`\n"
        f"⏱ _{_now()}_"
    )


def format_trade_closed(
    symbol: str,
    side: str,
    entry_price: float,
    exit_price: float,
    pnl_usd: float,
    pnl_pct: float,
    close_reason: str,    # "take_profit" / "stop_loss" / "manual"
    hold_time: str = "",
    is_paper: bool = True,
) -> str:
    won   = pnl_usd > 0
    emoji = "💚 WIN" if won else "❌ LOSS"
    icon  = "🏆" if won else "💔"
    mode  = "📋" if is_paper else "🔴"
    reasons = {"take_profit": "🎯 Take Profit Hit", "stop_loss": "🛑 Stop Loss Hit", "manual": "✋ Manual Close"}
    return (
        f"{icon} *Trade Closed* {mode}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 *{symbol}* — `{side.upper()}`\n"
        f"📊 *Result:* {emoji}\n"
        f"💰 *P&L:* `{_usd(pnl_usd)}` `({_pct(pnl_pct)})`\n"
        f"🔻 *Entry:* `{_price(entry_price, symbol)}`\n"
        f"🔺 *Exit:* `{_price(exit_price, symbol)}`\n"
        f"📋 *Reason:* {reasons.get(close_reason, close_reason)}\n"
        + (f"⏳ *Hold:* `{hold_time}`\n" if hold_time else "")
        + f"⏱ _{_now()}_"
    )


# ── Risk Alerts ───────────────────────────────────────────────────────────────

def format_circuit_breaker(
    drawdown_pct: float,
    equity: float,
    peak_equity: float,
    reason: str,
) -> str:
    return (
        f"🚨🚨 *CIRCUIT BREAKER TRIGGERED* 🚨🚨\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"❌ *ALL TRADING HALTED*\n"
        f"📉 *Drawdown:* `{drawdown_pct:.1f}%`\n"
        f"💵 *Current Equity:* `${equity:,.2f}`\n"
        f"📈 *Peak Equity:* `${peak_equity:,.2f}`\n"
        f"🔍 *Reason:* {reason}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ Manual restart required via /reset\\_circuit\n"
        f"⏱ _{_now()}_"
    )


def format_drawdown_warning(
    drawdown_pct: float,
    threshold_pct: float,
    size_multiplier: float,
) -> str:
    return (
        f"⚠️ *Drawdown Warning*\n"
        f"Current DD: `{drawdown_pct:.1f}%` / `{threshold_pct:.1f}%` limit\n"
        f"Position size reduced to `{size_multiplier*100:.0f}%`\n"
        f"⏱ _{_now()}_"
    )


def format_daily_limit(daily_loss_pct: float, equity: float) -> str:
    return (
        f"🟡 *Daily Loss Limit Hit*\n"
        f"Daily Loss: `{daily_loss_pct:.1f}%`\n"
        f"Equity: `${equity:,.2f}`\n"
        f"Trading paused until next session.\n"
        f"⏱ _{_now()}_"
    )


# ── Performance Reports ───────────────────────────────────────────────────────

def format_daily_report(
    date_str: str,
    equity: float,
    daily_pnl: float,
    daily_pnl_pct: float,
    trades_taken: int,
    wins: int,
    losses: int,
    best_trade_usd: float,
    worst_trade_usd: float,
    signals_analyzed: int,
    signals_approved: int,
    avg_confluence: float,
) -> str:
    win_rate = wins / max(1, trades_taken)
    emoji    = "📈" if daily_pnl >= 0 else "📉"
    return (
        f"{emoji} *Daily Report — {date_str}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 *P&L:* `{_usd(daily_pnl)}` `({_pct(daily_pnl_pct)})`\n"
        f"💵 *Equity:* `${equity:,.2f}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Trades:* `{trades_taken}` | W/L: `{wins}/{losses}`\n"
        f"🏆 *Win Rate:* `{win_rate:.0%}`\n"
        f"🔺 *Best Trade:* `{_usd(best_trade_usd)}`\n"
        f"🔻 *Worst Trade:* `{_usd(worst_trade_usd)}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔍 *Signals Analyzed:* `{signals_analyzed}`\n"
        f"✅ *Signals Approved:* `{signals_approved}`\n"
        f"📐 *Avg Confluence:* `{avg_confluence:.0f}/100`\n"
        f"⏱ _{_now()}_"
    )


def format_status(
    state: str,
    mode: str,
    equity: float,
    daily_pnl: float,
    open_positions: int,
    uptime: str,
    scan_count: int,
    signals_today: int,
    drawdown_pct: float,
    circuit_broken: bool,
) -> str:
    state_emoji = {
        "READY": "🟢", "SCANNING": "🔄", "EXECUTING": "⚡",
        "PAUSED": "⏸️", "ERROR": "🔴", "INITIALIZING": "🔧"
    }.get(state, "⚪")
    return (
        f"🤖 *Bot Status*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{state_emoji} *State:* `{state}`\n"
        f"📋 *Mode:* `{mode.upper()}`\n"
        f"💵 *Equity:* `${equity:,.2f}`\n"
        f"📊 *Daily P&L:* `{_usd(daily_pnl)}`\n"
        f"📉 *Drawdown:* `{drawdown_pct:.1f}%`\n"
        + (f"🚨 *CIRCUIT BROKEN* ⛔\n" if circuit_broken else "")
        + f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 *Open Positions:* `{open_positions}`\n"
        f"🔍 *Scans:* `{scan_count}`\n"
        f"🎯 *Signals Today:* `{signals_today}`\n"
        f"⏱ *Uptime:* `{uptime}`\n"
        f"🕐 _{_now()}_"
    )


def format_model_retrained(
    symbol: str,
    precision: float,
    accuracy: float,
    auc: float,
    n_samples: int,
    threshold: float,
) -> str:
    grade = "🔥" if precision >= 0.72 else "✅" if precision >= 0.62 else "⚠️"
    return (
        f"🧠 *Model Retrained — {symbol}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{grade} *Win Rate Est:* `{precision:.1%}`\n"
        f"📊 *Accuracy:* `{accuracy:.1%}`\n"
        f"📈 *AUC:* `{auc:.3f}`\n"
        f"📦 *Samples:* `{n_samples:,}`\n"
        f"🎚️ *Threshold:* `{threshold:.2f}`\n"
        f"⏱ _{_now()}_"
    )


def format_walk_forward_report(
    symbol: str,
    oos_precision: float,
    oos_auc: float,
    precision_std: float,
    win_rate: float,
    sharpe: float,
    max_dd: float,
    total_return: float,
    performance_trend: str,
    is_ready: bool,
    reason: str,
) -> str:
    status = "✅ *PRODUCTION READY*" if is_ready else "❌ *NOT READY FOR LIVE*"
    return (
        f"📋 *Walk-Forward Report — {symbol}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{status}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 *OOS Win Rate:* `{oos_precision:.1%}`\n"
        f"📈 *AUC:* `{oos_auc:.3f}`\n"
        f"📊 *Precision Stability:* `±{precision_std:.3f}`\n"
        f"📉 *Performance Trend:* `{performance_trend}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💹 *Sim Win Rate:* `{win_rate:.1%}`\n"
        f"⚡ *Sharpe:* `{sharpe:.2f}`\n"
        f"📉 *Max DD:* `{max_dd:.1f}%`\n"
        f"💰 *Total Return:* `{_pct(total_return)}`\n"
        + (f"ℹ️ _{reason}_\n" if not is_ready else "")
        + f"⏱ _{_now()}_"
    )


# ── Error / System ────────────────────────────────────────────────────────────

def format_error(component: str, error: str, critical: bool = False) -> str:
    emoji = "🚨" if critical else "⚠️"
    return (
        f"{emoji} *{'CRITICAL' if critical else 'Warning'} — {component}*\n"
        f"`{error[:300]}`\n"
        f"⏱ _{_now()}_"
    )


def format_bot_started(mode: str, equity: float, pairs: List[str]) -> str:
    return (
        f"🤖✅ *AlphaBot Started*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 *Mode:* `{mode.upper()}`\n"
        f"💵 *Equity:* `${equity:,.2f}`\n"
        f"📌 *Pairs:* `{', '.join(pairs[:6])}`\n"
        f"⏱ _{_now()}_"
    )
