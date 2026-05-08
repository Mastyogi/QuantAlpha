from src.utils.logger import get_logger
import os

# Load .env to ensure TELEGRAM_BOT_TOKEN is available
try:
    from dotenv import load_dotenv
    from pathlib import Path
    env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
except:
    pass

# Import settings safely
try:
    from config.settings import settings
except Exception:
    settings = None

# Import new user handlers
from src.telegram.user_handlers import (
    handle_start as handle_start_new,
    handle_register,
    handle_verify,
    handle_deposit,
    handle_withdraw,
    handle_balance,
    handle_referral,
    handle_referrals,
    handle_withdraw_ref,
    handle_leaderboard,
    handle_mode,
    handle_settings,
    handle_history,
    handle_chart,
    handle_alert,
    handle_export,
    handle_support,
    handle_feedback,
    handle_user_callback,
)

logger = get_logger(__name__)


def build_telegram_app(engine):
    """
    Build the Telegram Application with all command handlers.
    Returns None if Telegram not configured.
    """
    try:
        from telegram.ext import Application, CommandHandler, CallbackQueryHandler
        from telegram import Update
        from telegram.ext import ContextTypes
        import os
        
        # Get token directly from environment (already loaded in main.py)
        telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN', 'placeholder_token')
        telegram_admin_chat_id = int(os.getenv('TELEGRAM_ADMIN_CHAT_ID', '0'))
        
        logger.info(f"Telegram token: {telegram_bot_token[:20]}...")
        
        if not telegram_bot_token or telegram_bot_token == "placeholder_token":
            logger.warning("Telegram bot token not configured — bot commands disabled")
            return _MockTelegramApp()

        app = Application.builder().token(telegram_bot_token).build()

        # ── Helper: bind engine to handler ───────────────────────────────────
        def _bind(fn):
            async def _handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
                await fn(update, ctx, engine)
            _handler.__name__ = fn.__name__
            return _handler

        # ── Core / original commands ──────────────────────────────────────────
        app.add_handler(CommandHandler("start",   _bind(handle_start_new)))
        app.add_handler(CommandHandler("status",  _bind(handle_status)))
        app.add_handler(CommandHandler("pause",   _bind(handle_pause)))
        app.add_handler(CommandHandler("resume",  _bind(handle_resume)))
        app.add_handler(CommandHandler("pnl",     _bind(handle_pnl)))
        app.add_handler(CommandHandler("signals", _bind(handle_signals)))
        app.add_handler(CommandHandler("help",    _bind(handle_help)))
        app.add_handler(CommandHandler("audit",   _bind(handle_audit)))
        app.add_handler(CommandHandler("rollback",    _bind(handle_rollback)))
        app.add_handler(CommandHandler("performance", _bind(handle_performance)))
        app.add_handler(CommandHandler("patterns",    _bind(handle_patterns)))
        app.add_handler(CommandHandler("retrain",     _bind(handle_retrain)))
        app.add_handler(CommandHandler("optimize",    _bind(handle_optimize)))
        app.add_handler(CommandHandler("health",      _bind(handle_health)))
        app.add_handler(CommandHandler("tune",         _bind(handle_tune)))
        app.add_handler(CommandHandler("tuning_status",_bind(handle_tuning_status)))
        app.add_handler(CommandHandler("pattern_off",  _bind(handle_pattern_off)))
        app.add_handler(CommandHandler("pattern_on",   _bind(handle_pattern_on)))
        app.add_handler(CommandHandler("regime",       _bind(handle_regime)))

        # ── NEW: User management & escrow commands ────────────────────────────
        app.add_handler(CommandHandler("register",     _bind(handle_register)))
        app.add_handler(CommandHandler("verify",       _bind(handle_verify)))
        app.add_handler(CommandHandler("deposit",      _bind(handle_deposit)))
        app.add_handler(CommandHandler("withdraw",     _bind(handle_withdraw)))
        app.add_handler(CommandHandler("balance",      _bind(handle_balance)))
        app.add_handler(CommandHandler("referral",     _bind(handle_referral)))
        app.add_handler(CommandHandler("referrals",    _bind(handle_referrals)))
        app.add_handler(CommandHandler("withdraw_ref", _bind(handle_withdraw_ref)))
        app.add_handler(CommandHandler("leaderboard",  _bind(handle_leaderboard)))
        app.add_handler(CommandHandler("mode",         _bind(handle_mode)))
        app.add_handler(CommandHandler("settings",     _bind(handle_settings)))
        app.add_handler(CommandHandler("history",      _bind(handle_history)))
        app.add_handler(CommandHandler("chart",        _bind(handle_chart)))
        app.add_handler(CommandHandler("alert",        _bind(handle_alert)))
        app.add_handler(CommandHandler("export",       _bind(handle_export)))
        app.add_handler(CommandHandler("support",      _bind(handle_support)))
        app.add_handler(CommandHandler("feedback",     _bind(handle_feedback)))

        # ── Callback query handler (inline buttons) ───────────────────────────
        app.add_handler(CallbackQueryHandler(_bind(handle_all_callbacks)))

        return app

    except ImportError:
        logger.warning("python-telegram-bot not installed — Telegram disabled")
        return _MockTelegramApp()
    except Exception as e:
        logger.error(f"Telegram app creation failed: {e}", exc_info=True)
        return _MockTelegramApp()


async def handle_all_callbacks(update, context, engine=None):
    """Route all callback queries to the right handler."""
    query = update.callback_query
    data = query.data or ""

    # User-facing callbacks (mode_demo, deposit, balance, referral, etc.)
    user_prefixes = ("mode_", "deposit", "balance", "referral")
    if any(data.startswith(p) for p in user_prefixes):
        await handle_user_callback(update, context, engine)
        return

    # Approval system callbacks
    if data.startswith(("approve_", "reject_", "paper_")):
        await handle_callback(update, context)
        return

    # Legacy signal callbacks
    await handle_callback(update, context)


async def handle_start(update, context, engine):
    """Legacy start handler — now delegates to new user_handlers.handle_start."""
    await handle_start_new(update, context, engine)


async def handle_status(update, context, engine):
    status = await engine.get_status()
    running_icon = "🟢" if status["is_running"] else "🔴"
    text = (
        f"{running_icon} *BOT STATUS*\n\n"
        f"State: `{status['state']}`\n"
        f"Mode: `{status['mode'].upper()}`\n"
        f"Uptime: `{status['uptime']}`\n"
        f"Equity: `${status['equity']:,.2f}`\n"
        f"Daily PnL: `${status['daily_pnl']:+.2f}`\n"
        f"Open Positions: `{status['open_positions']}`\n"
        f"Pairs: `{', '.join(status['active_pairs'])}`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def handle_pause(update, context, engine):
    await engine.pause()
    await update.message.reply_text("⏸ Bot paused. Use /resume to restart.")


async def handle_resume(update, context, engine):
    await engine.resume()
    await update.message.reply_text("▶️ Bot resumed.")


async def handle_pnl(update, context, engine):
    status = await engine.get_status()
    stats = engine.order_manager.get_paper_stats()
    text = (
        "📊 *P&L REPORT*\n\n"
        f"Equity: `${stats['equity']:,.2f}`\n"
        f"Total PnL: `${stats['total_pnl']:+.2f}`\n"
        f"Win Rate: `{stats['win_rate']:.1f}%`\n"
        f"Total Trades: `{stats['total_trades']}`\n"
        f"Open Positions: `{stats['open_positions']}`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def handle_signals(update, context, engine):
    await update.message.reply_text(
        "📡 Signal log coming soon. Check logs for recent signals.", parse_mode="Markdown"
    )


async def handle_help(update, context):
    text = (
        "🤖 *BOT COMMANDS*\n\n"
        "**Basic Commands**\n"
        "/start — Main menu\n"
        "/status — Bot & system status\n"
        "/health — System health check\n"
        "/signals — Recent trade signals\n"
        "/pnl — P&L summary\n"
        "/pause — Pause trading\n"
        "/resume — Resume trading\n\n"
        "**Performance & Analytics**\n"
        "/performance — Compounding stats\n"
        "/patterns — Active trading patterns\n"
        "/audit — Generate audit report\n\n"
        "**Advanced Commands**\n"
        "/retrain <symbol> — Trigger model retraining\n"
        "/optimize — Trigger parameter optimization\n"
        "/rollback <symbol> — Emergency model rollback\n\n"
        "/help — This message"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def handle_audit(update, context, engine):
    """Generate and send codebase audit report."""
    await update.message.reply_text("🔍 Generating codebase audit report... This may take a minute.")
    
    try:
        from src.audit.audit_engine import CodebaseAuditor
        
        # Run audit
        auditor = CodebaseAuditor(root_dir="src")
        report = await auditor.run_full_audit()
        
        # Generate summary for Telegram
        summary = (
            "📋 *CODEBASE AUDIT REPORT*\n\n"
            f"**Structure**\n"
            f"• Python Files: `{report.structure_summary.get('python_files', 0)}`\n"
            f"• Total Lines: `{report.structure_summary.get('total_lines', 0):,}`\n"
            f"• Components: `{len(report.structure_summary.get('components', {}))}`\n\n"
            f"**Quality**\n"
            f"• Functions: `{report.quality_metrics.get('total_functions', 0)}`\n"
            f"• Classes: `{report.quality_metrics.get('total_classes', 0)}`\n"
            f"• Docstring Coverage: `{report.quality_metrics.get('docstring_coverage', 0):.1f}%`\n\n"
            f"**Gaps Identified**\n"
            f"• Critical: `{len([g for g in report.identified_gaps if g.severity == 'CRITICAL'])}`\n"
            f"• High: `{len([g for g in report.identified_gaps if g.severity == 'HIGH'])}`\n"
            f"• Medium: `{len([g for g in report.identified_gaps if g.severity == 'MEDIUM'])}`\n"
            f"• Low: `{len([g for g in report.identified_gaps if g.severity == 'LOW'])}`\n\n"
            f"**Top Recommendations**\n"
        )
        
        # Add top 3 recommendations
        for rec in report.recommendations[:3]:
            summary += f"• {rec.title} (Priority {rec.priority})\n"
        
        summary += "\n📄 Full report saved to `audit_report.md`"
        
        # Save full report
        report.save("audit_report.md")
        
        # Send summary
        await update.message.reply_text(summary, parse_mode="Markdown")
        
        # Send full report as file
        try:
            with open("audit_report.md", "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename="audit_report.md",
                    caption="📋 Complete Audit Report"
                )
        except Exception as e:
            logger.error(f"Could not send audit report file: {e}")
    
    except Exception as e:
        logger.error(f"Audit failed: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Audit failed: {str(e)}\nCheck logs for details.",
            parse_mode="Markdown"
        )


async def handle_callback(update, context):
    """Handle callback queries from inline buttons."""
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    # Approval system callbacks
    if data.startswith("approve_") or data.startswith("reject_") or data.startswith("paper_"):
        await handle_approval_callback(query, data)
        return

    # Legacy signal callbacks
    if data.startswith("accept_"):
        symbol = data.replace("accept_", "")
        await query.edit_message_text(f"✅ Signal accepted for {symbol}")
    elif data.startswith("skip_"):
        symbol = data.replace("skip_", "")
        await query.edit_message_text(f"⏭ Signal skipped for {symbol}")
    elif data.startswith("chart_"):
        symbol = data.replace("chart_", "")
        await query.edit_message_text(f"📊 Chart for {symbol} — check TradingView")


async def handle_approval_callback(query, data: str):
    """Handle approval system callbacks."""
    try:
        from src.telegram.approval_system import ApprovalSystem
        
        # Parse callback data
        parts = data.split("_", 1)
        if len(parts) != 2:
            await query.edit_message_text("❌ Invalid callback data")
            return
        
        decision, proposal_id = parts
        admin_id = str(query.from_user.id)
        
        # Get approval system instance (would be passed from engine)
        # For now, create a new instance
        approval_system = ApprovalSystem()
        
        # Handle decision
        await approval_system.handle_approval(proposal_id, decision, admin_id)
        
        # Update message
        decision_text = {
            "approve": "✅ Approved",
            "reject": "❌ Rejected",
            "paper": "📝 Sent to Paper Trading"
        }.get(decision, "Processed")
        
        await query.edit_message_text(
            f"{query.message.text}\n\n{decision_text} by admin {admin_id}"
        )
    
    except Exception as e:
        logger.error(f"Approval callback error: {e}", exc_info=True)
        await query.edit_message_text(f"❌ Error processing approval: {str(e)}")


async def handle_rollback(update, context, engine):
    """Handle emergency model rollback."""
    try:
        # Parse command arguments
        args = context.args
        if not args:
            await update.message.reply_text(
                "⚠️ Usage: `/rollback <symbol>`\n"
                "Example: `/rollback EURUSD`",
                parse_mode="Markdown"
            )
            return
        
        symbol = args[0]
        
        await update.message.reply_text(f"🔄 Rolling back model for {symbol}...")
        
        from src.ml.self_improvement_engine import DeploymentManager
        
        deployment_manager = DeploymentManager()
        previous_version = await deployment_manager.rollback_to_previous(symbol)
        
        if previous_version:
            await update.message.reply_text(
                f"✅ *Rollback Successful*\n\n"
                f"Symbol: `{symbol}`\n"
                f"Reverted to: `{previous_version.version}`\n"
                f"Precision: `{previous_version.precision:.1%}`\n"
                f"Deployed: `{previous_version.deployed_at}`",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"❌ No previous version found for {symbol}",
                parse_mode="Markdown"
            )
    
    except Exception as e:
        logger.error(f"Rollback failed: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Rollback failed: {str(e)}",
            parse_mode="Markdown"
        )


class _MockTelegramApp:
    """No-op Telegram app when bot token not configured."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def start(self):
        pass

    async def stop(self):
        pass
    
    async def shutdown(self):
        pass

    class updater:
        @staticmethod
        async def start_polling(*args, **kwargs):
            pass

        @staticmethod
        async def stop():
            pass


async def handle_performance(update, context, engine):
    """Show compounding performance statistics."""
    try:
        await update.message.reply_text("📊 Fetching performance stats...")
        
        if hasattr(engine, 'order_manager'):
            try:
                stats = await engine.order_manager.get_compounding_stats()
                if stats.get('enabled'):
                    text = (
                        "💰 *COMPOUNDING PERFORMANCE*\n\n"
                        f"Initial Equity: `${stats['initial_equity']:,.2f}`\n"
                        f"Current Equity: `${stats['current_equity']:,.2f}`\n"
                        f"Total Return: `{stats['total_return_pct']:+.2f}%`\n"
                        f"Open Positions: `{stats['open_positions']}`\n"
                        f"Portfolio Heat: `{stats['portfolio_heat_pct']:.2f}%`"
                    )
                else:
                    text = "⚠️ Compounding is disabled"
            except Exception:
                # Fallback to paper stats if DB unavailable
                paper_stats = engine.order_manager.get_paper_stats()
                text = (
                    "💰 *PERFORMANCE (Paper Mode)*\n\n"
                    f"Equity: `${paper_stats.get('equity', 10000):,.2f}`\n"
                    f"Total PnL: `${paper_stats.get('total_pnl', 0):+.2f}`\n"
                    f"Win Rate: `{paper_stats.get('win_rate', 0):.1f}%`\n"
                    f"Total Trades: `{paper_stats.get('total_trades', 0)}`\n"
                    f"Open Positions: `{paper_stats.get('open_positions', 0)}`\n\n"
                    f"_Note: Database offline, showing local stats_"
                )
        else:
            text = "❌ Order manager not available"
        
        await update.message.reply_text(text, parse_mode="Markdown")
    
    except Exception as e:
        logger.error(f"Performance command error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode="Markdown")


async def handle_patterns(update, context, engine):
    """List active trading patterns."""
    try:
        await update.message.reply_text("🔍 Fetching active patterns...")
        
        from src.database.pattern_library import PatternLibrary
        
        pattern_lib = PatternLibrary()
        
        # Get top patterns
        top_patterns = await pattern_lib.get_top_patterns(limit=10)
        
        if not top_patterns:
            await update.message.reply_text("📋 No patterns discovered yet")
            return
        
        text = "🎯 *ACTIVE TRADING PATTERNS*\n\n"
        
        for i, pattern in enumerate(top_patterns, 1):
            text += (
                f"{i}. *{pattern.name}*\n"
                f"   Win Rate: `{pattern.win_rate:.1%}`\n"
                f"   Profit Factor: `{pattern.profit_factor:.2f}`\n"
                f"   Sharpe: `{pattern.sharpe_ratio:.2f}`\n"
                f"   Trades: `{pattern.trade_count}`\n"
                f"   Regime: `{pattern.regime}`\n\n"
            )
        
        # Get stats
        stats = await pattern_lib.get_statistics()
        text += (
            f"📊 *STATISTICS*\n"
            f"Total Patterns: `{stats['total_patterns']}`\n"
            f"Active Patterns: `{stats['active_patterns']}`\n"
            f"Avg Win Rate: `{stats['avg_win_rate']:.1%}`"
        )
        
        await update.message.reply_text(text, parse_mode="Markdown")
    
    except Exception as e:
        logger.error(f"Patterns command error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode="Markdown")


async def handle_retrain(update, context, engine):
    """Trigger manual model retraining."""
    try:
        # Parse command arguments
        args = context.args
        if not args:
            await update.message.reply_text(
                "⚠️ Usage: `/retrain <symbol>`\n"
                "Example: `/retrain EURUSD`",
                parse_mode="Markdown"
            )
            return
        
        symbol = args[0]
        
        await update.message.reply_text(f"🔄 Starting retraining for {symbol}...")
        
        from src.ml.self_improvement_engine import SelfImprovementEngine
        
        # Get self-improvement engine from bot engine
        if hasattr(engine, 'self_improvement_engine'):
            si_engine = engine.self_improvement_engine
        else:
            # Create new instance
            si_engine = SelfImprovementEngine(
                model_trainer=None,  # Would need proper initialization
                performance_tracker=None,
                approval_system=None,
            )
        
        # Trigger retraining
        await si_engine.retrain_model(symbol)
        
        await update.message.reply_text(
            f"✅ Retraining completed for {symbol}\n"
            f"Check approval system for deployment proposal.",
            parse_mode="Markdown"
        )
    
    except Exception as e:
        logger.error(f"Retrain command error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode="Markdown")


async def handle_optimize(update, context, engine):
    """Trigger manual parameter optimization."""
    try:
        await update.message.reply_text("🔧 Starting parameter optimization...")
        
        # This would integrate with the auto-tuning system (Task 15)
        # For now, show placeholder
        await update.message.reply_text(
            "⚠️ Auto-tuning system not yet implemented\n"
            "This will be available after Task 15 completion.",
            parse_mode="Markdown"
        )
    
    except Exception as e:
        logger.error(f"Optimize command error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode="Markdown")


# Mock Telegram app for when Telegram is not configured
class _MockTelegramApp:
    """Mock Telegram app that does nothing."""
    
    async def initialize(self):
        pass
    
    async def start(self):
        pass
    
    async def stop(self):
        pass
    
    async def shutdown(self):
        pass
    
    def run_polling(self, *args, **kwargs):
        pass


async def handle_health(update, context, engine):
    """Show system health status."""
    try:
        await update.message.reply_text("🏥 Checking system health...")
        
        # Get health check system from engine
        if hasattr(engine, 'health_check_system'):
            health_system = engine.health_check_system
            await health_system.check_all_components()
            
            report = health_system.get_health_report()
            overall_status = report['overall_status']
            
            # Status emoji
            status_emoji = {
                'healthy': '✅',
                'degraded': '⚠️',
                'unhealthy': '🔴',
                'unknown': '❓'
            }
            
            text = f"{status_emoji.get(overall_status, '❓')} *SYSTEM HEALTH*\n\n"
            text += f"Overall: `{overall_status.upper()}`\n\n"
            text += "*Components:*\n"
            
            for name, component in report['components'].items():
                comp_emoji = status_emoji.get(component['status'], '❓')
                text += f"{comp_emoji} {name}: `{component['status']}`\n"
                
                if component.get('response_time_ms'):
                    text += f"   Response: {component['response_time_ms']:.0f}ms\n"
                
                if component['status'] != 'healthy':
                    text += f"   {component['message']}\n"
            
            await update.message.reply_text(text, parse_mode="Markdown")
        else:
            await update.message.reply_text(
                "⚠️ Health check system not configured",
                parse_mode="Markdown"
            )
    
    except Exception as e:
        logger.error(f"Health command error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode="Markdown")



# ── GAP 8: New Command Handlers ───────────────────────────────────────────────

async def handle_tune(update, context, engine):
    """Manually trigger parameter optimization."""
    try:
        # Check if user is admin
        user_id = str(update.effective_user.id)
        admin_chat_id = os.getenv('TELEGRAM_ADMIN_CHAT_ID', '0')
        admin_ids = [str(admin_chat_id)]
        
        if user_id not in admin_ids:
            await update.message.reply_text(
                "❌ Unauthorized. Only admins can trigger optimization.",
                parse_mode="Markdown"
            )
            return
        
        await update.message.reply_text("🔧 Starting parameter optimization... This may take a few minutes.")
        
        if hasattr(engine, 'auto_tuning_system'):
            result = await engine.auto_tuning_system.optimize()
            
            if result:
                text = (
                    f"✅ *Optimization Complete*\n\n"
                    f"Best Sharpe: `{result.best_sharpe:.3f}`\n"
                    f"OOS Sharpe: `{result.out_of_sample_sharpe:.3f}`\n"
                    f"Trials: `{result.trials_completed}`\n"
                    f"Time: `{result.optimization_time:.1f}s`\n\n"
                    f"Proposal created for approval."
                )
            else:
                text = "⚠️ Optimization failed - insufficient data"
        else:
            text = "❌ Auto-tuning system not available"
        
        await update.message.reply_text(text, parse_mode="Markdown")
    
    except Exception as e:
        logger.error(f"Tune command error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode="Markdown")


async def handle_tuning_status(update, context, engine):
    """Show auto-tuning system status."""
    try:
        if hasattr(engine, 'auto_tuning_system'):
            status = engine.auto_tuning_system.get_status()
            
            if status.get('last_run'):
                text = (
                    f"🔧 *Auto-Tuning Status*\n\n"
                    f"Last Run: `{status['last_run']}`\n"
                    f"Best Sharpe: `{status.get('best_sharpe', 0):.3f}`\n"
                    f"OOS Sharpe: `{status.get('oos_sharpe', 0):.3f}`\n"
                    f"Trials: `{status.get('trials', 0)}`\n"
                )
                
                if status.get('next_scheduled'):
                    text += f"\nNext Run: `{status['next_scheduled']}`"
                
                if status.get('best_params'):
                    text += "\n\n*Best Parameters:*\n"
                    for param, value in status['best_params'].items():
                        text += f"• {param}: `{value:.3f}`\n"
            else:
                text = "⚠️ No optimization runs yet"
        else:
            text = "❌ Auto-tuning system not available"
        
        await update.message.reply_text(text, parse_mode="Markdown")
    
    except Exception as e:
        logger.error(f"Tuning status command error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode="Markdown")


async def handle_pattern_off(update, context, engine):
    """Disable a trading pattern."""
    try:
        # Check if user is admin
        user_id = str(update.effective_user.id)
        admin_chat_id = os.getenv('TELEGRAM_ADMIN_CHAT_ID', '0')
        admin_ids = [str(admin_chat_id)]
        
        if user_id not in admin_ids:
            await update.message.reply_text(
                "❌ Unauthorized. Only admins can modify patterns.",
                parse_mode="Markdown"
            )
            return
        
        # Parse command arguments
        args = context.args
        if not args:
            await update.message.reply_text(
                "⚠️ Usage: `/pattern_off <pattern_id>`\n"
                "Example: `/pattern_off pattern_123`",
                parse_mode="Markdown"
            )
            return
        
        pattern_id = args[0]
        
        from src.database.pattern_library import PatternLibrary
        pattern_lib = PatternLibrary()
        
        success = await pattern_lib.deactivate_pattern(pattern_id)
        
        if success:
            await update.message.reply_text(
                f"✅ Pattern `{pattern_id}` disabled",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"❌ Pattern `{pattern_id}` not found",
                parse_mode="Markdown"
            )
    
    except Exception as e:
        logger.error(f"Pattern off command error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode="Markdown")


async def handle_pattern_on(update, context, engine):
    """Enable a trading pattern."""
    try:
        # Check if user is admin
        user_id = str(update.effective_user.id)
        admin_chat_id = os.getenv('TELEGRAM_ADMIN_CHAT_ID', '0')
        admin_ids = [str(admin_chat_id)]
        
        if user_id not in admin_ids:
            await update.message.reply_text(
                "❌ Unauthorized. Only admins can modify patterns.",
                parse_mode="Markdown"
            )
            return
        
        # Parse command arguments
        args = context.args
        if not args:
            await update.message.reply_text(
                "⚠️ Usage: `/pattern_on <pattern_id>`\n"
                "Example: `/pattern_on pattern_123`",
                parse_mode="Markdown"
            )
            return
        
        pattern_id = args[0]
        
        from src.database.pattern_library import PatternLibrary
        pattern_lib = PatternLibrary()
        
        success = await pattern_lib.activate_pattern(pattern_id)
        
        if success:
            await update.message.reply_text(
                f"✅ Pattern `{pattern_id}` enabled",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"❌ Pattern `{pattern_id}` not found",
                parse_mode="Markdown"
            )
    
    except Exception as e:
        logger.error(f"Pattern on command error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode="Markdown")


async def handle_regime(update, context, engine):
    """Show current market regime for all trading pairs."""
    try:
        await update.message.reply_text("🔍 Detecting market regimes...")
        
        from src.signals.regime_detector import MarketRegimeDetector
        
        regime_detector = MarketRegimeDetector()
        
        text = "📊 *MARKET REGIMES*\n\n"
        
        trading_pairs = os.getenv('PAIRS', 'EURUSD,GBPUSD').split(',')
        
        # Check regime for each trading pair
        for symbol in trading_pairs[:6]:
            try:
                symbol = symbol.strip()
                # Get data from exchange client
                if hasattr(engine, 'exchange_client'):
                    df = await engine.exchange_client.fetch_ohlcv(symbol, "1h", limit=100)
                else:
                    df = None
                
                if df is not None and len(df) >= 30:
                    result = regime_detector.detect(df)
                    regime_emoji = {
                        "TRENDING": "📈", "RANGING": "↔️",
                        "BREAKOUT": "🚀", "VOLATILE": "⚡", "DEAD": "💤"
                    }
                    emoji = regime_emoji.get(result.regime, "❓")
                    text += f"{emoji} `{symbol}`: *{result.regime}* ({result.confidence:.0%})\n"
                else:
                    text += f"❓ `{symbol}`: `INSUFFICIENT DATA`\n"
            
            except Exception as e:
                logger.warning(f"Regime detection failed for {symbol}: {e}")
                text += f"❌ `{symbol}`: `ERROR`\n"
        
        await update.message.reply_text(text, parse_mode="Markdown")
    
    except Exception as e:
        logger.error(f"Regime command error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode="Markdown")
