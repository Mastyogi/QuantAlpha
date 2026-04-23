"""
Telegram Inline Keyboard Menus
================================
All interactive button menus for the trading bot Telegram UI.

Menus:
  - Main control panel (status, pause, resume, PnL)
  - Signal action buttons (accept, skip, details)
  - Risk panel (set risk %, view exposure)
  - Trade management (close position, update SL/TP)
  - Admin panel (reset CB, retrain models)
"""
from __future__ import annotations

from typing import List, Optional

try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    InlineKeyboardButton = None
    InlineKeyboardMarkup = None


# ── Callback data constants ────────────────────────────────────────────────────
class CB:
    # Main panel
    STATUS         = "btn_status"
    PNL            = "btn_pnl"
    PAUSE          = "btn_pause"
    RESUME         = "btn_resume"
    SIGNALS        = "btn_signals"
    OPEN_TRADES    = "btn_open_trades"

    # Signal actions
    SIGNAL_ACCEPT  = "sig_accept"
    SIGNAL_SKIP    = "sig_skip"
    SIGNAL_CHART   = "sig_chart"
    SIGNAL_DETAILS = "sig_details"

    # Risk panel
    RISK_PANEL     = "btn_risk"
    RISK_1PCT      = "risk_1"
    RISK_2PCT      = "risk_2"
    RISK_3PCT      = "risk_3"

    # Trade management
    CLOSE_ALL      = "trade_close_all"
    CLOSE_TRADE    = "trade_close"  # + ":trade_id"

    # Admin
    ADMIN_PANEL    = "btn_admin"
    RESET_CB       = "admin_reset_cb"
    RETRAIN        = "admin_retrain"
    REFRESH        = "btn_refresh"

    @staticmethod
    def close_trade(trade_id: str) -> str:
        return f"{CB.CLOSE_TRADE}:{trade_id}"


def _build_markup(buttons: List[List]) -> Optional[object]:
    """Build InlineKeyboardMarkup from a list of button rows."""
    if not TELEGRAM_AVAILABLE:
        return None
    keyboard = [
        [InlineKeyboardButton(text=btn[0], callback_data=btn[1]) for btn in row]
        for row in buttons
    ]
    return InlineKeyboardMarkup(keyboard)


# ── Main Control Panel ────────────────────────────────────────────────────────

def main_panel_keyboard() -> Optional[object]:
    """Main bot control panel keyboard."""
    return _build_markup([
        [("📊 Status", CB.STATUS),    ("💰 P&L", CB.PNL)],
        [("📈 Signals", CB.SIGNALS),  ("📋 Trades", CB.OPEN_TRADES)],
        [("⏸ Pause",   CB.PAUSE),     ("▶️ Resume", CB.RESUME)],
        [("⚡ Risk",   CB.RISK_PANEL), ("🔧 Admin",  CB.ADMIN_PANEL)],
        [("🔄 Refresh", CB.REFRESH)],
    ])


# ── Signal Action Keyboard ────────────────────────────────────────────────────

def signal_action_keyboard(symbol: str, direction: str) -> Optional[object]:
    """Buttons shown with a new trade signal."""
    dir_emoji = "📈" if direction == "BUY" else "📉"
    return _build_markup([
        [
            (f"{dir_emoji} Execute Paper Trade", CB.SIGNAL_ACCEPT),
            ("❌ Skip", CB.SIGNAL_SKIP),
        ],
        [
            ("📊 Details", CB.SIGNAL_DETAILS),
            ("📋 Chart Levels", CB.SIGNAL_CHART),
        ],
    ])


# ── Risk Level Panel ──────────────────────────────────────────────────────────

def risk_panel_keyboard() -> Optional[object]:
    """Risk per trade adjustment panel."""
    return _build_markup([
        [
            ("🟢 1% Risk", CB.RISK_1PCT),
            ("🟡 2% Risk", CB.RISK_2PCT),
            ("🔴 3% Risk", CB.RISK_3PCT),
        ],
        [("⬅️ Back", CB.STATUS)],
    ])


# ── Open Trades Panel ─────────────────────────────────────────────────────────

def open_trades_keyboard(trade_ids: List[str]) -> Optional[object]:
    """Keyboard showing close buttons for each open trade."""
    if not trade_ids:
        return _build_markup([[("⬅️ Back", CB.STATUS)]])

    buttons = []
    for tid in trade_ids[:5]:   # max 5 to avoid huge keyboard
        short_id = tid[-8:]
        buttons.append([(f"❌ Close {short_id}", CB.close_trade(tid))])

    buttons.append([("❌ Close ALL", CB.CLOSE_ALL), ("⬅️ Back", CB.STATUS)])
    return _build_markup(buttons)


# ── Admin Panel ───────────────────────────────────────────────────────────────

def admin_panel_keyboard() -> Optional[object]:
    """Admin control panel — dangerous actions."""
    return _build_markup([
        [("🔓 Reset Circuit Breaker", CB.RESET_CB)],
        [("🤖 Retrain Models Now",    CB.RETRAIN)],
        [("⬅️ Back to Main",          CB.STATUS)],
    ])


# ── Confirmation Dialog ───────────────────────────────────────────────────────

def confirm_keyboard(action: str, yes_callback: str, no_callback: str) -> Optional[object]:
    """Generic confirmation dialog."""
    return _build_markup([
        [
            (f"✅ Yes, {action}", yes_callback),
            ("❌ Cancel",         no_callback),
        ]
    ])


# ── Status Refresh ────────────────────────────────────────────────────────────

def status_keyboard() -> Optional[object]:
    """Minimal keyboard under status messages."""
    return _build_markup([
        [("🔄 Refresh", CB.REFRESH), ("💰 P&L", CB.PNL)],
        [("📈 Signals",  CB.SIGNALS), ("📋 Trades", CB.OPEN_TRADES)],
    ])
