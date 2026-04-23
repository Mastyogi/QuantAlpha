"""BotEngine v2 — wired with FineTunedSignalEngine, EventBus, DrawdownMonitor, MarketScanner."""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional
from config.settings import settings
from src.core.event_bus import EventBus, EventType, Event, bus
from src.data.exchange_client import ExchangeClient
from src.data.data_fetcher import DataFetcher
from src.data.market_scanner import MarketScanner, ScannerConfig
from src.execution.order_manager import OrderManager
from src.risk.drawdown_monitor import DrawdownMonitor
from src.risk.adaptive_risk import AdaptiveRiskManager
from src.signals.signal_engine import FineTunedSignalEngine, FinalSignal
from src.telegram.notifier import TelegramNotifier
from src.telegram.formatters import (
    format_signal, format_trade_opened, format_trade_closed,
    format_circuit_breaker, format_daily_limit,
    format_error, format_bot_started, format_model_retrained,
)
from src.database.repositories import TradeRepository, SignalRepository
from src.utils.logger import get_logger
logger = get_logger(__name__)

class BotEngineV2:
    def __init__(self, validate_on_start: bool = False):
        self.event_bus = bus
        self.exchange = ExchangeClient()
        self.fetcher = DataFetcher(self.exchange)
        self.notifier = TelegramNotifier()
        self.trade_repo = TradeRepository()
        self.signal_repo = SignalRepository()
        self.signal_engine = FineTunedSignalEngine(
            model_dir="models",
            confluence_threshold=float(getattr(settings,"ai_confidence_threshold",0.70)*100),
            max_risk_pct=float(getattr(settings,"risk_per_trade_pct",2.0)),
            account_equity=10_000.0,
        )
        self.drawdown_monitor = DrawdownMonitor(initial_equity=10_000.0)
        self.adaptive_risk = AdaptiveRiskManager(
            max_risk_pct=float(getattr(settings,"risk_per_trade_pct",2.0)),
            account_equity=10_000.0,
        )
        self.order_manager = OrderManager(self.exchange)
        self.scanner = MarketScanner(
            config=ScannerConfig(
                symbols=getattr(settings,"all_instruments",settings.trading_pairs),
                concurrency=5, scan_interval_s=60, fast_interval_s=15,
            ),
            data_fetcher=self.fetcher,
            signal_engine=self.signal_engine,
            on_signal_cb=self._on_signal_approved,
        )
        
        # ── GAP 9: Initialize new components ──────────────────────────────────
        from src.ml.auto_tuning_system import AutoTuningSystem
        from src.telegram.approval_system import ApprovalSystem
        from src.core.health_check import HealthCheckSystem
        from src.execution.profit_booking_engine import ProfitBookingEngine
        from src.ml.self_improvement_engine import SelfImprovementEngine
        from src.ml.performance_tracker import PerformanceTracker
        from src.database.pattern_library import PatternLibrary
        from src.risk.portfolio_compounder import PortfolioCompounder
        
        # Approval system
        self.approval_system = ApprovalSystem()
        
        # Auto-tuning system
        self.auto_tuning_system = AutoTuningSystem(
            approval_system=self.approval_system,
            n_trials=getattr(settings, "optuna_trials", 50),
            lookback_days=90,
        )
        
        # Health check system
        self.health_check_system = HealthCheckSystem(
            exchange_client=self.exchange,
            database_connection=None,  # Will be set after DB init
            telegram_notifier=self.notifier,
            signal_engine=self.signal_engine,
            order_manager=self.order_manager,
        )
        
        # Profit booking engine
        self.profit_booking_engine = ProfitBookingEngine(
            order_manager=self.order_manager,
            telegram_notifier=self.notifier,
        )
        
        # Performance tracker
        self.performance_tracker = PerformanceTracker()
        
        # Pattern library
        self.pattern_library = PatternLibrary()
        
        # Portfolio compounder
        self.portfolio_compounder = PortfolioCompounder(
            initial_equity=10_000.0,
            kelly_fraction=0.25,
        )
        
        # Self-improvement engine
        self.self_improvement_engine = SelfImprovementEngine(
            model_dir="models",
            data_fetcher=self.fetcher,
            approval_system=self.approval_system,
        )
        
        self._state = "INITIALIZING"
        self._running = False
        self._paused = False
        self._start_time: Optional[datetime] = None
        self._scan_count = 0
        self._signals_today = 0
        self._trades_today = 0
        self._wins_today = 0
        self._validate_on_start = validate_on_start
        self._register_event_handlers()

    async def start(self) -> None:
        logger.info("Starting BotEngineV2...")
        await self.event_bus.start()
        await self.exchange.initialize()
        await self.notifier.start()
        balance = await self.exchange.fetch_balance()
        initial_equity = float(balance.get("USDT", {}).get("total", 10_000.0))
        self.drawdown_monitor = DrawdownMonitor(initial_equity=initial_equity)
        self.adaptive_risk.account_equity = initial_equity
        self.signal_engine.account_equity = initial_equity
        self.order_manager.paper_trader.equity = initial_equity
        self.portfolio_compounder.current_equity = initial_equity
        
        if self._validate_on_start:
            self._state = "VALIDATING"
            await self._run_preflight_validation()
        from src.database.connection import create_tables
        await create_tables()
        
        # ── GAP 9: Start all background systems ───────────────────────────────
        logger.info("Starting background systems...")
        
        # Start profit booking engine monitoring
        asyncio.create_task(self.profit_booking_engine.start_monitoring())
        logger.info("✅ Profit booking engine started")
        
        # Start self-improvement engine daily loop
        asyncio.create_task(self.self_improvement_engine.start_daily_loop())
        logger.info("✅ Self-improvement engine started")
        
        # Start auto-tuning weekly scheduler
        asyncio.create_task(self.auto_tuning_system.schedule_weekly())
        logger.info("✅ Auto-tuning scheduler started")
        
        # Start health check loop (every 60 seconds)
        from src.core.health_check import run_health_check_loop
        asyncio.create_task(run_health_check_loop(
            self.health_check_system,
            interval=60,
            telegram_notifier=self.notifier
        ))
        logger.info("✅ Health check system started")
        
        self._state = "READY"
        self._running = True
        self._start_time = datetime.now(timezone.utc)
        await self.notifier.send_alert("INFO", format_bot_started(
            mode=settings.trading_mode, equity=initial_equity,
            pairs=getattr(settings,"all_instruments",settings.trading_pairs)[:6],
        ))
        await self.event_bus.publish(Event(
            type=EventType.BOT_STARTED,
            data={"equity": initial_equity, "mode": settings.trading_mode},
            source="bot_engine",
        ))
        logger.info(f"BotEngineV2 ready. Equity=${initial_equity:,.2f}")
        await self.scanner.start()

    async def _on_signal_approved(self, signal: FinalSignal) -> None:
        self._signals_today += 1
        self._scan_count += 1
        if not self.drawdown_monitor.trading_allowed:
            await self.event_bus.publish(Event(
                type=EventType.SIGNAL_REJECTED,
                data={"symbol": signal.symbol, "reason": self.drawdown_monitor.state.status_line()},
                source="bot_engine",
            ))
            return
        setup = signal.trade_setup
        try:
            await self.signal_repo.create_signal({
                "symbol": signal.symbol, "direction": signal.direction,
                "strategy_name": "FineTunedEnsemble",
                "timeframe": settings.primary_timeframe,
                "entry_price": setup.entry_price, "stop_loss": setup.stop_loss,
                "take_profit": setup.take_profit_2,
                "signal_score": signal.confluence_score,
                "ai_confidence": signal.ai_confidence,
            })
        except Exception as e:
            logger.debug(f"Signal DB log: {e}")
        reasons = signal.confluence.reasons[:4] if signal.confluence else []
        msg = format_signal(
            symbol=signal.symbol, direction=signal.direction,
            entry=setup.entry_price, stop_loss=setup.stop_loss,
            take_profit_1=setup.take_profit_1, take_profit_2=setup.take_profit_2,
            take_profit_3=setup.take_profit_3,
            confluence_score=signal.confluence_score,
            ai_confidence=signal.ai_confidence, rr_ratio=setup.rr_ratio,
            timeframe=settings.primary_timeframe,
            win_rate_est=signal.win_rate_estimate,
            risk_usd=self.drawdown_monitor.get_adjusted_risk_pct()/100*self.drawdown_monitor.current_equity,
            reasons=reasons,
        )
        await self.notifier.send_alert("SIGNAL", msg)
        await self.event_bus.emit_signal(
            symbol=signal.symbol, direction=signal.direction,
            score=signal.confluence_score, confidence=signal.ai_confidence,
            entry=setup.entry_price, stop_loss=setup.stop_loss,
            take_profit=setup.take_profit_2, rr_ratio=setup.rr_ratio,
        )
        if settings.trading_mode == "paper":
            await self._execute_trade(signal)

    async def _execute_trade(self, signal: FinalSignal) -> None:
        self._state = "EXECUTING"
        try:
            setup = signal.trade_setup
            adj_risk = self.drawdown_monitor.get_adjusted_risk_pct(
                base_risk_pct=float(getattr(settings,"risk_per_trade_pct",2.0))
            )
            if adj_risk <= 0:
                return
            size_usd = self.drawdown_monitor.current_equity * adj_risk / 100
            result = await self.order_manager.place_trade(
                symbol=signal.symbol, side=signal.direction.lower(),
                size_usd=size_usd, entry_price=setup.entry_price,
                stop_loss=setup.stop_loss, take_profit=setup.take_profit_2,
                confidence=signal.ai_confidence, strategy_name="FineTunedEnsemble",
            )
            self._trades_today += 1
            await self.notifier.send_alert("TRADE", format_trade_opened(
                symbol=signal.symbol, side=signal.direction,
                entry_price=setup.entry_price, stop_loss=setup.stop_loss,
                take_profit=setup.take_profit_2, size_usd=size_usd,
                order_id=result.get("id","paper"), is_paper=True, rr_ratio=setup.rr_ratio,
            ))
            await self.event_bus.emit_trade_opened(
                symbol=signal.symbol, side=signal.direction,
                entry=setup.entry_price, sl=setup.stop_loss,
                tp=setup.take_profit_2, size_usd=size_usd,
            )
        except Exception as e:
            logger.error(f"Trade execution: {e}", exc_info=True)
            await self.notifier.send_alert("CRITICAL", format_error("execution", str(e), True))
        finally:
            self._state = "READY"

    async def _check_open_positions(self) -> None:
        if settings.trading_mode != "paper":
            return
        try:
            positions = self.order_manager.paper_trader.open_positions
            if not positions:
                return
            symbols = list({p["symbol"] for p in positions.values()})
            prices = {}
            for sym in symbols:
                ticker = await self.exchange.fetch_ticker(sym)
                prices[sym] = ticker.get("last", 0.0)
            closed = await self.order_manager.check_and_close_positions(prices)
            for trade in closed:
                pnl = trade.get("pnl", 0.0)
                if pnl > 0:
                    self._wins_today += 1
                risk_state = await self.drawdown_monitor.update_equity(
                    self.order_manager.paper_trader.equity, realized_pnl=pnl
                )
                self.adaptive_risk.account_equity = self.drawdown_monitor.current_equity
                self.signal_engine.account_equity = self.drawdown_monitor.current_equity
                await self.notifier.send_alert("TRADE", format_trade_closed(
                    symbol=trade.get("symbol","?"), side=trade.get("side","?"),
                    entry_price=trade.get("entry_price",0),
                    exit_price=trade.get("exit_price",0),
                    pnl_usd=pnl, pnl_pct=pnl/self.drawdown_monitor.current_equity*100,
                    close_reason=trade.get("close_reason","unknown"), is_paper=True,
                ))
                await self.event_bus.emit_trade_closed(
                    symbol=trade.get("symbol","?"), pnl=pnl,
                    reason=trade.get("close_reason","unknown"),
                )
                if risk_state.circuit_broken:
                    await self._handle_circuit_break(risk_state)
        except Exception as e:
            logger.warning(f"Position check: {e}")

    async def _handle_circuit_break(self, risk_state) -> None:
        logger.critical("Circuit breaker triggered")
        await self.notifier.send_alert("CRITICAL", format_circuit_breaker(
            drawdown_pct=risk_state.drawdown_pct,
            equity=self.drawdown_monitor.current_equity,
            peak_equity=self.drawdown_monitor.peak_equity,
            reason=f"Max drawdown {risk_state.drawdown_pct:.1f}%",
        ))

    def _register_event_handlers(self) -> None:
        bus.subscribe(EventType.CIRCUIT_BREAK,   self._on_circuit_break)
        bus.subscribe(EventType.DAILY_LIMIT_HIT, self._on_daily_limit)
        bus.subscribe(EventType.BOT_ERROR,       self._on_bot_error)
        bus.subscribe(EventType.MODEL_RETRAINED, self._on_model_retrained)
        
        # ── GAP 9: Register TRADE_CLOSED event handlers ───────────────────────
        bus.subscribe(EventType.TRADE_CLOSED, self._on_trade_closed_pattern_update)
        bus.subscribe(EventType.TRADE_CLOSED, self._on_trade_closed_performance_track)
        bus.subscribe(EventType.TRADE_CLOSED, self._on_trade_closed_equity_update)

    async def _on_circuit_break(self, event: Event) -> None:
        await self.scanner.stop()
        await self.notifier.send_alert("CRITICAL", format_circuit_breaker(
            drawdown_pct=event.data.get("drawdown_pct",0),
            equity=self.drawdown_monitor.current_equity,
            peak_equity=self.drawdown_monitor.peak_equity,
            reason=event.data.get("reason","Circuit breaker"),
        ))

    async def _on_daily_limit(self, event: Event) -> None:
        await self.notifier.send_alert("WARNING", format_daily_limit(
            daily_loss_pct=event.data.get("daily_loss_pct",0),
            equity=self.drawdown_monitor.current_equity,
        ))

    async def _on_bot_error(self, event: Event) -> None:
        await self.notifier.send_alert("ERROR", format_error(
            event.data.get("component","?"), event.data.get("error","?")
        ))

    async def _on_model_retrained(self, event: Event) -> None:
        await self.notifier.send_alert("INFO", format_model_retrained(
            symbol=event.data.get("symbol","?"),
            precision=event.data.get("precision",0),
            accuracy=event.data.get("accuracy",0),
            auc=event.data.get("auc",0),
            n_samples=event.data.get("n_samples",0),
            threshold=event.data.get("threshold",0.5),
        ))
    
    # ── GAP 9: TRADE_CLOSED event handlers ────────────────────────────────────
    
    async def _on_trade_closed_pattern_update(self, event: Event) -> None:
        """Update pattern library when trade closes."""
        try:
            symbol = event.data.get("symbol")
            pnl = event.data.get("pnl", 0.0)
            pattern_id = event.data.get("pattern_id")
            
            if pattern_id:
                is_win = pnl > 0
                await self.pattern_library.update_pattern_performance(
                    pattern_id=pattern_id,
                    is_win=is_win,
                    pnl=pnl
                )
                logger.debug(f"Pattern {pattern_id} updated: {'WIN' if is_win else 'LOSS'}")
        except Exception as e:
            logger.error(f"Pattern update failed: {e}", exc_info=True)
    
    async def _on_trade_closed_performance_track(self, event: Event) -> None:
        """Track trade performance for self-improvement."""
        try:
            trade_data = {
                "symbol": event.data.get("symbol"),
                "pnl": event.data.get("pnl", 0.0),
                "pnl_pct": event.data.get("pnl_pct", 0.0),
                "entry_price": event.data.get("entry_price", 0.0),
                "exit_price": event.data.get("exit_price", 0.0),
                "close_reason": event.data.get("reason", "unknown"),
                "timestamp": datetime.now(timezone.utc),
            }
            
            await self.performance_tracker.record_trade(trade_data)
            logger.debug(f"Trade performance recorded for {trade_data['symbol']}")
        except Exception as e:
            logger.error(f"Performance tracking failed: {e}", exc_info=True)
    
    async def _on_trade_closed_equity_update(self, event: Event) -> None:
        """Update portfolio compounder equity."""
        try:
            pnl = event.data.get("pnl", 0.0)
            current_equity = self.order_manager.paper_trader.equity
            
            # Check if equity changed by 10% (compounding trigger)
            equity_changed = await self.portfolio_compounder.update_equity(
                new_equity=current_equity,
                realized_pnl=pnl
            )
            
            if equity_changed:
                logger.info(
                    f"💰 Equity milestone reached: ${current_equity:,.2f} "
                    f"(+{pnl:+.2f})"
                )
                
                # Notify via Telegram
                await self.notifier.send_alert(
                    "INFO",
                    f"💰 *Compounding Milestone*\n\n"
                    f"New Equity: `${current_equity:,.2f}`\n"
                    f"Trade PnL: `${pnl:+.2f}`\n"
                    f"Position sizes will be adjusted."
                )
        except Exception as e:
            logger.error(f"Equity update failed: {e}", exc_info=True)

    async def _run_preflight_validation(self) -> None:
        from src.backtesting.walk_forward import WalkForwardValidator
        v = WalkForwardValidator(n_folds=3, min_train_bars=150)
        for symbol in settings.trading_pairs[:3]:
            try:
                df = await self.fetcher.get_dataframe(symbol,"1h",limit=500)
                if df is None or len(df) < 200:
                    continue
                report = v.validate(df, symbol=symbol)
                ready, reason = v.is_production_ready(report)
                await self.notifier.send_alert(
                    "INFO" if ready else "WARNING",
                    f'{"✅" if ready else "⚠️"} *Validation [{symbol}]*\nOOS Precision: `{report.oos_precision:.1%}`\n{"Ready" if ready else reason}'
                )
            except Exception as e:
                logger.warning(f"Validation {symbol}: {e}")

    async def pause(self) -> None:
        self._paused = True; self._state = "PAUSED"
        await self.scanner.stop()
        await self.event_bus.publish(Event(type=EventType.BOT_PAUSED, source="admin"))

    async def resume(self) -> None:
        self._paused = False; self._state = "READY"
        asyncio.create_task(self.scanner.start())
        await self.event_bus.publish(Event(type=EventType.BOT_RESUMED, source="admin"))

    async def reset_circuit_breaker(self) -> bool:
        ok = self.drawdown_monitor.reset_circuit_breaker(admin_confirmed=True)
        if ok:
            asyncio.create_task(self.scanner.start())
        return ok

    async def stop(self) -> None:
        self._running = False
        await self.scanner.stop()
        await self.event_bus.stop()
        await self.notifier.stop()
        await self.exchange.close()

    async def get_status(self) -> Dict:
        uptime = (
            str(datetime.now(timezone.utc)-self._start_time).split(".")[0]
            if self._start_time else "00:00:00"
        )
        dd = self.drawdown_monitor.get_summary()
        es = self.signal_engine.get_session_stats()
        return {
            "is_running": self._running and not self._paused,
            "state": self._state, "mode": settings.trading_mode,
            "active_pairs": getattr(settings,"all_instruments",settings.trading_pairs),
            "equity": dd["current_equity"],
            "daily_pnl": dd["current_equity"]-dd.get("initial_equity",dd["current_equity"]),
            "drawdown_pct": dd["current_dd_pct"],
            "circuit_broken": dd["circuit_broken"],
            "trading_allowed": dd["trading_allowed"],
            "open_positions": len(self.order_manager.paper_trader.open_positions),
            "scan_count": self._scan_count,
            "signals_today": self._signals_today,
            "trades_today": self._trades_today,
            "wins_today": self._wins_today,
            "win_rate_today": self._wins_today/max(1,self._trades_today),
            "avg_confluence": es.get("avg_confluence",0),
            "uptime": uptime,
            "event_stats": self.event_bus.get_stats(),
        }

BotEngine = BotEngineV2
