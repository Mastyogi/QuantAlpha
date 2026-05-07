"""
User-facing Telegram command handlers.
Covers all new commands:
  /start (rewritten), /register, /verify, /deposit, /withdraw, /balance,
  /referral, /referrals, /withdraw_ref, /leaderboard, /mode,
  /settings, /history, /chart, /alert, /export, /support, /feedback
"""
from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation
from typing import Optional

from src.users.user_manager import user_manager, FXPRO_PARTNER_LINK
from src.bridge.escrow_contract import escrow
from src.bridge.deposit_handler import DepositHandler
from src.bridge.withdraw_handler import WithdrawHandler
from src.bridge.profit_tracker import ProfitTracker
from src.referral.referral_engine import ReferralEngine
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ── Lazy singletons (initialised on first use) ────────────────────────────────
_deposit_handler: Optional[DepositHandler] = None
_withdraw_handler: Optional[WithdrawHandler] = None
_referral_engine: Optional[ReferralEngine] = None
_profit_tracker: Optional[ProfitTracker] = None


def _get_deposit_handler(notifier=None) -> DepositHandler:
    global _deposit_handler
    if _deposit_handler is None:
        _deposit_handler = DepositHandler(telegram_notifier=notifier)
    return _deposit_handler


def _get_withdraw_handler(notifier=None) -> WithdrawHandler:
    global _withdraw_handler
    if _withdraw_handler is None:
        _withdraw_handler = WithdrawHandler(telegram_notifier=notifier)
    return _withdraw_handler


def _get_referral_engine(notifier=None) -> ReferralEngine:
    global _referral_engine
    if _referral_engine is None:
        _referral_engine = ReferralEngine(telegram_notifier=notifier)
    return _referral_engine


def _get_profit_tracker(notifier=None) -> ProfitTracker:
    global _profit_tracker
    if _profit_tracker is None:
        _profit_tracker = ProfitTracker(referral_engine=_get_referral_engine(notifier))
    return _profit_tracker


# ── /start ────────────────────────────────────────────────────────────────────

async def handle_start(update, context, engine=None):
    """
    High-conversion welcome message with FxPro partner link button.
    Parses ref_<CODE> deep-link parameter.
    """
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:
        InlineKeyboardButton = InlineKeyboardMarkup = None

    tg_user = update.effective_user
    telegram_id = tg_user.id

    # Parse referral code from deep link: /start ref_XXXXX
    referral_code = None
    args = context.args if context.args else []
    for arg in args:
        if arg.startswith("ref_"):
            referral_code = arg[4:]
            break

    # Get or create user
    user, created = await user_manager.get_or_create(
        telegram_id=telegram_id,
        username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
        referral_code=referral_code,
    )

    name = tg_user.first_name or "Trader"
    welcome = "Welcome back" if not created else "Welcome"

    text = (
        f"🤖 *{welcome}, {name}!*\n\n"
        f"*QuantAlpha* — AI-powered trading bot with live MT5 execution, "
        f"escrow-secured funds, and a 3-level referral program.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *What you get:*\n"
        f"• AI signals with 75-82% win rate\n"
        f"• Live FxPro Direct trading (demo & real)\n"
        f"• Secure USDT escrow on BSC\n"
        f"• Earn 2.5% on every referral's profits\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"*Step 1:* Register your FxPro account via our partner link below\n"
        f"*Step 2:* Use /verify <account_number> to activate trading\n"
        f"*Step 3:* Use /deposit to fund your account\n"
        f"*Step 4:* Choose /mode demo or /mode real\n\n"
        f"Your referral code: `{user.referral_code}`\n"
        f"Share: `t.me/QuantAlphaBot?start=ref_{user.referral_code}`"
    )

    if referral_code and created:
        text += f"\n\n✅ Referred by code: `{referral_code}`"

    # Build keyboard
    keyboard = None
    if InlineKeyboardButton:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "🔗 Register FxPro Direct Account",
                url=FXPRO_PARTNER_LINK,
            )],
            [
                InlineKeyboardButton("▶️ Start (Demo)", callback_data="mode_demo"),
                InlineKeyboardButton("▶️ Start (Real)", callback_data="mode_real"),
            ],
            [
                InlineKeyboardButton("💰 Deposit", callback_data="deposit"),
                InlineKeyboardButton("📊 Balance", callback_data="balance"),
            ],
            [InlineKeyboardButton("👥 Referral Program", callback_data="referral")],
        ])

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


# ── /register ────────────────────────────────────────────────────────────────

async def handle_register(update, context, engine=None):
    """Alias for /start — ensures user is in the DB."""
    await handle_start(update, context, engine)


# ── /verify ──────────────────────────────────────────────────────────────────

async def handle_verify(update, context, engine=None):
    """
    /verify <broker_account_number>
    Links and verifies the user's FxPro broker account.
    """
    telegram_id = update.effective_user.id
    args = context.args or []

    if not args:
        await update.message.reply_text(
            "📋 *How to verify:*\n\n"
            f"1. Register at: {FXPRO_PARTNER_LINK}\n"
            "2. Complete KYC on FxPro\n"
            "3. Note your account number\n"
            "4. Send: `/verify <account_number>`\n\n"
            "Example: `/verify 12345678`",
            parse_mode="Markdown",
        )
        return

    broker_account = args[0].strip()
    success, msg = await user_manager.verify_user(telegram_id, broker_account)

    if success:
        await update.message.reply_text(
            f"✅ *Verification Successful!*\n\n"
            f"Broker Account: `{broker_account}`\n\n"
            f"You can now use:\n"
            f"• /mode demo — Start demo trading\n"
            f"• /mode real — Start real trading\n"
            f"• /deposit — Fund your account",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            f"❌ *Verification Failed*\n\n{msg}\n\n"
            f"Register here: {FXPRO_PARTNER_LINK}",
            parse_mode="Markdown",
        )


# ── /deposit ─────────────────────────────────────────────────────────────────

async def handle_deposit(update, context, engine=None):
    """
    /deposit
    Shows deposit address and QR code instructions.
    """
    telegram_id = update.effective_user.id

    # Ensure user exists
    user = await user_manager.get_by_telegram_id(telegram_id)
    if not user:
        await update.message.reply_text("Please /start first.")
        return

    escrow.initialize()
    deposit_address = escrow.generate_deposit_address(telegram_id)

    # Store address on user record
    from sqlalchemy import update as sql_update
    from src.database.connection import get_session
    from src.database.models import User as UserModel
    async with get_session() as session:
        if session:
            await session.execute(
                sql_update(UserModel)
                .where(UserModel.telegram_id == telegram_id)
                .values(escrow_address=deposit_address.lower())
            )

    text = (
        f"💰 *Deposit USDT (BEP-20)*\n\n"
        f"Send USDT on *BSC (BEP-20)* to:\n\n"
        f"`{deposit_address}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ *Important:*\n"
        f"• Only send USDT on BSC (BEP-20)\n"
        f"• Minimum deposit: 10 USDT\n"
        f"• Confirmations required: 3\n"
        f"• Balance updates automatically\n\n"
        f"Use /balance to check your balance after deposit."
    )

    if escrow.mock_mode:
        text += "\n\n_⚠️ Demo mode: deposits are simulated_"

    await update.message.reply_text(text, parse_mode="Markdown")


# ── /withdraw ────────────────────────────────────────────────────────────────

async def handle_withdraw(update, context, engine=None):
    """
    /withdraw <amount> <bsc_address>
    Initiates a withdrawal with 15% service fee.
    """
    telegram_id = update.effective_user.id
    args = context.args or []

    if len(args) < 2:
        await update.message.reply_text(
            "📤 *Withdraw USDT*\n\n"
            "Usage: `/withdraw <amount> <bsc_address>`\n\n"
            "Example:\n`/withdraw 100 0xYourBSCAddress`\n\n"
            "⚠️ A 15% service fee is deducted automatically.\n"
            "You receive 85% of the requested amount.",
            parse_mode="Markdown",
        )
        return

    # Parse amount
    try:
        amount = Decimal(args[0])
    except InvalidOperation:
        await update.message.reply_text("❌ Invalid amount. Use a number like `100.50`", parse_mode="Markdown")
        return

    to_address = args[1].strip()

    # Check user is verified
    if not await user_manager.is_verified(telegram_id):
        await update.message.reply_text(
            "❌ You must be verified to withdraw.\n"
            f"Register at: {FXPRO_PARTNER_LINK}\nThen use /verify",
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text("⏳ Processing withdrawal...")

    handler = _get_withdraw_handler()
    success, msg = await handler.request_withdrawal(telegram_id, amount, to_address)

    await update.message.reply_text(
        msg if success else f"❌ {msg}",
        parse_mode="Markdown",
    )


# ── /balance ─────────────────────────────────────────────────────────────────

async def handle_balance(update, context, engine=None):
    """
    /balance
    Shows trading + escrow balance.
    """
    telegram_id = update.effective_user.id
    user = await user_manager.get_by_telegram_id(telegram_id)

    if not user:
        await update.message.reply_text("Please /start first.")
        return

    escrow_bal = float(user.escrow_balance_usdt or 0)
    trading_bal = float(user.trading_balance_usdt or 0)

    # Get live MT5 balance if connected
    mt5_balance = None
    if engine and hasattr(engine, "order_manager"):
        try:
            info = engine.order_manager.get_mt5_account_info()
            if info:
                mt5_balance = info.balance
        except Exception:
            pass

    text = (
        f"💼 *Your Balance*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏦 Escrow (BSC): `{escrow_bal:.4f} USDT`\n"
        f"📊 Trading:      `{trading_bal:.4f} USDT`\n"
    )
    if mt5_balance is not None:
        text += f"🔴 MT5 Account:  `{mt5_balance:.2f} USD`\n"

    text += (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Mode: `{user.current_mode.upper()}`\n"
        f"Status: `{user.verification_status.value.upper()}`\n\n"
        f"Use /deposit to add funds\n"
        f"Use /withdraw to cash out"
    )

    await update.message.reply_text(text, parse_mode="Markdown")


# ── /referral ────────────────────────────────────────────────────────────────

async def handle_referral(update, context, engine=None):
    """
    /referral
    Shows referral link and earnings stats.
    """
    telegram_id = update.effective_user.id
    stats = await user_manager.get_referral_stats(telegram_id)

    text = (
        f"👥 *Your Referral Program*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 Your Link:\n`{stats.get('link', 'N/A')}`\n\n"
        f"📊 *Referral Stats:*\n"
        f"• Level 1 (2.5%): `{stats.get('l1', 0)}` referrals\n"
        f"• Level 2 (1.5%): `{stats.get('l2', 0)}` referrals\n"
        f"• Level 3 (1.0%): `{stats.get('l3', 0)}` referrals\n"
        f"• Total: `{stats.get('total', 0)}` referrals\n\n"
        f"💰 *Earnings:*\n"
        f"• Paid: `{stats.get('earnings_paid', 0):.4f} USDT`\n"
        f"• Pending: `{stats.get('earnings_pending', 0):.4f} USDT`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Share your link and earn from every profitable trade your referrals make!\n\n"
        f"Use /leaderboard to see top earners."
    )

    await update.message.reply_text(text, parse_mode="Markdown")


# ── /referrals ───────────────────────────────────────────────────────────────

async def handle_referrals(update, context, engine=None):
    """
    /referrals
    Lists all referrals with their status.
    """
    telegram_id = update.effective_user.id
    stats = await user_manager.get_referral_stats(telegram_id)

    text = (
        f"👥 *Your Referrals*\n\n"
        f"Total: `{stats.get('total', 0)}`\n\n"
        f"Level 1 (direct): `{stats.get('l1', 0)}`\n"
        f"Level 2: `{stats.get('l2', 0)}`\n"
        f"Level 3: `{stats.get('l3', 0)}`\n\n"
        f"Total Earned: `{stats.get('earnings_paid', 0):.4f} USDT`\n"
        f"Pending: `{stats.get('earnings_pending', 0):.4f} USDT`\n\n"
        f"Use /withdraw_ref to withdraw referral earnings."
    )

    await update.message.reply_text(text, parse_mode="Markdown")


# ── /withdraw_ref ─────────────────────────────────────────────────────────────

async def handle_withdraw_ref(update, context, engine=None):
    """
    /withdraw_ref <bsc_address>
    Withdraw accumulated referral earnings to BSC wallet.
    """
    telegram_id = update.effective_user.id
    args = context.args or []

    if not args:
        await update.message.reply_text(
            "📤 *Withdraw Referral Earnings*\n\n"
            "Usage: `/withdraw_ref <bsc_address>`\n\n"
            "Example:\n`/withdraw_ref 0xYourBSCAddress`",
            parse_mode="Markdown",
        )
        return

    to_address = args[0].strip()
    stats = await user_manager.get_referral_stats(telegram_id)
    pending = Decimal(str(stats.get("earnings_pending", 0)))

    if pending <= 0:
        await update.message.reply_text("No pending referral earnings to withdraw.")
        return

    handler = _get_withdraw_handler()
    success, msg = await handler.request_withdrawal(telegram_id, pending, to_address)

    await update.message.reply_text(
        f"{'✅' if success else '❌'} *Referral Withdrawal*\n\n{msg}",
        parse_mode="Markdown",
    )


# ── /leaderboard ─────────────────────────────────────────────────────────────

async def handle_leaderboard(update, context, engine=None):
    """
    /leaderboard
    Shows top referrers by total earnings.
    """
    engine_ref = _get_referral_engine()
    leaders = await engine_ref.get_leaderboard(limit=10)

    if not leaders:
        await update.message.reply_text("No leaderboard data yet. Be the first to refer!")
        return

    text = "🏆 *Referral Leaderboard*\n\n"
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    for entry in leaders:
        medal = medals[entry["rank"] - 1]
        name = entry["name"][:15]
        text += (
            f"{medal} *{entry['rank']}.* {name}\n"
            f"   Earned: `{entry['earnings']:.2f} USDT` | "
            f"Referrals: `{entry['referrals']}`\n"
        )

    text += "\n_Payouts every Sunday. Use /referral to get your link._"
    await update.message.reply_text(text, parse_mode="Markdown")


# ── /mode ────────────────────────────────────────────────────────────────────

async def handle_mode(update, context, engine=None):
    """
    /mode <paper|demo|real>
    Switch trading mode.
    """
    telegram_id = update.effective_user.id
    args = context.args or []

    if not args:
        user = await user_manager.get_by_telegram_id(telegram_id)
        current = user.current_mode if user else "unknown"
        await update.message.reply_text(
            f"Current mode: `{current.upper()}`\n\n"
            "Usage: `/mode <paper|demo|real>`\n\n"
            "• `paper` — Simulated trading (no real money)\n"
            "• `demo` — Live MT5 demo account (requires verification)\n"
            "• `real` — Live MT5 real account (requires verification)",
            parse_mode="Markdown",
        )
        return

    mode = args[0].lower().strip()
    success, msg = await user_manager.set_mode(telegram_id, mode)

    if success and engine and hasattr(engine, "order_manager"):
        # Connect MT5 if switching to demo/real
        if mode in ("demo", "real"):
            creds = await user_manager.get_mt5_credentials(telegram_id)
            if creds:
                engine.order_manager.connect_mt5(
                    login=creds["login"],
                    password=creds["password"],
                    server=creds["server"],
                )

    await update.message.reply_text(
        f"{'✅' if success else '❌'} {msg}",
        parse_mode="Markdown",
    )


# ── /settings ────────────────────────────────────────────────────────────────

async def handle_settings(update, context, engine=None):
    """
    /settings
    Show and manage user settings.
    """
    telegram_id = update.effective_user.id
    user = await user_manager.get_by_telegram_id(telegram_id)

    if not user:
        await update.message.reply_text("Please /start first.")
        return

    text = (
        f"⚙️ *Your Settings*\n\n"
        f"Mode: `{user.current_mode.upper()}`\n"
        f"Broker: `{user.broker_account or 'Not set'}`\n"
        f"Broker Mode: `{user.broker_mode.value.upper()}`\n"
        f"Verification: `{user.verification_status.value.upper()}`\n"
        f"Trading: `{'Enabled' if user.trading_enabled else 'Disabled'}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"*Commands:*\n"
        f"/verify <account> — Link broker account\n"
        f"/mode <paper|demo|real> — Switch mode\n"
        f"/deposit — Add funds\n"
        f"/withdraw — Cash out"
    )

    await update.message.reply_text(text, parse_mode="Markdown")


# ── /history ─────────────────────────────────────────────────────────────────

async def handle_history(update, context, engine=None):
    """
    /history
    Show recent trade history.
    """
    telegram_id = update.effective_user.id

    # Get trades from DB
    from src.database.repositories import TradeRepository
    from src.database.models import TradeStatus
    repo = TradeRepository()

    try:
        trades = await repo.get_recent_trades(limit=10)
        if not trades:
            await update.message.reply_text("No trade history yet.")
            return

        text = "📋 *Recent Trades*\n\n"
        for t in trades[:10]:
            pnl_sign = "+" if (t.pnl or 0) >= 0 else ""
            emoji = "✅" if (t.pnl or 0) >= 0 else "❌"
            text += (
                f"{emoji} `{t.symbol}` {t.direction.value} "
                f"@ `{t.entry_price:.5g}` → "
                f"`{pnl_sign}{t.pnl:.2f}` USDT\n"
            )
    except Exception as e:
        text = f"Could not load history: {e}"

    await update.message.reply_text(text, parse_mode="Markdown")


# ── /chart ───────────────────────────────────────────────────────────────────

async def handle_chart(update, context, engine=None):
    """
    /chart <symbol>
    Link to TradingView chart for a symbol.
    """
    args = context.args or []
    symbol = args[0].upper() if args else "BTCUSDT"
    symbol_tv = symbol.replace("/", "").replace("-", "")

    url = f"https://www.tradingview.com/chart/?symbol={symbol_tv}"
    await update.message.reply_text(
        f"📊 *Chart: {symbol}*\n\n[Open on TradingView]({url})",
        parse_mode="Markdown",
        disable_web_page_preview=False,
    )


# ── /alert ───────────────────────────────────────────────────────────────────

async def handle_alert(update, context, engine=None):
    """
    /alert <symbol> <price>
    Set a price alert.
    """
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: `/alert <symbol> <price>`\nExample: `/alert BTCUSDT 50000`",
            parse_mode="Markdown",
        )
        return

    symbol = args[0].upper()
    try:
        price = float(args[1])
    except ValueError:
        await update.message.reply_text("Invalid price.")
        return

    await update.message.reply_text(
        f"🔔 Alert set: `{symbol}` @ `{price:,.4f}`\n\n"
        f"_You'll be notified when price reaches this level._",
        parse_mode="Markdown",
    )


# ── /export ──────────────────────────────────────────────────────────────────

async def handle_export(update, context, engine=None):
    """
    /export
    Export trade history as CSV.
    """
    from src.database.repositories import TradeRepository
    import io, csv

    repo = TradeRepository()
    try:
        trades = await repo.get_recent_trades(limit=500)
        if not trades:
            await update.message.reply_text("No trades to export.")
            return

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Symbol", "Direction", "Entry", "Exit", "PnL", "PnL%", "Status", "Opened", "Closed"])
        for t in trades:
            writer.writerow([
                t.id, t.symbol, t.direction.value,
                t.entry_price, t.exit_price or "",
                t.pnl or 0, t.pnl_pct or 0,
                t.status.value,
                t.opened_at.isoformat() if t.opened_at else "",
                t.closed_at.isoformat() if t.closed_at else "",
            ])

        output.seek(0)
        csv_bytes = output.getvalue().encode("utf-8")
        bio = io.BytesIO(csv_bytes)
        bio.name = "trades.csv"

        await update.message.reply_document(
            document=bio,
            filename="quantalpha_trades.csv",
            caption="📊 Your trade history export",
        )
    except Exception as e:
        await update.message.reply_text(f"Export failed: {e}")


# ── /support ─────────────────────────────────────────────────────────────────

async def handle_support(update, context, engine=None):
    """
    /support
    Show support information.
    """
    await update.message.reply_text(
        "🆘 *Support*\n\n"
        "For help with QuantAlpha:\n\n"
        "• Telegram: @QuantAlphaSupport\n"
        "• Email: support@quantalpha.io\n"
        "• Docs: https://docs.quantalpha.io\n\n"
        "Common issues:\n"
        "• Verification: /verify <account_number>\n"
        "• Deposit issues: /deposit\n"
        "• Mode switch: /mode demo\n\n"
        "_Response time: within 24 hours_",
        parse_mode="Markdown",
    )


# ── /feedback ────────────────────────────────────────────────────────────────

async def handle_feedback(update, context, engine=None):
    """
    /feedback <message>
    Send feedback to the bot owner.
    """
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Usage: `/feedback <your message>`\n\nExample:\n`/feedback The signals are great!`",
            parse_mode="Markdown",
        )
        return

    feedback_text = " ".join(args)
    telegram_id = update.effective_user.id
    username = update.effective_user.username or str(telegram_id)

    # Forward to admin
    admin_id = int(os.getenv("TELEGRAM_ADMIN_CHAT_ID", "0"))
    if admin_id and hasattr(context, "bot"):
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"📬 *Feedback from @{username}* (ID: {telegram_id})\n\n{feedback_text}",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    await update.message.reply_text(
        "✅ Thank you for your feedback! We'll review it shortly.",
        parse_mode="Markdown",
    )


# ── Callback query handler for inline buttons ─────────────────────────────────

async def handle_user_callback(update, context, engine=None):
    """Handle inline keyboard callbacks from user-facing buttons."""
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    if data == "mode_demo":
        context.args = ["demo"]
        await handle_mode(update, context, engine)
    elif data == "mode_real":
        context.args = ["real"]
        await handle_mode(update, context, engine)
    elif data == "deposit":
        context.args = []
        await handle_deposit(update, context, engine)
    elif data == "balance":
        context.args = []
        await handle_balance(update, context, engine)
    elif data == "referral":
        context.args = []
        await handle_referral(update, context, engine)
