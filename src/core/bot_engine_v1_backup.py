import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional
from src.data.exchange_client import ExchangeClient
from src.data.data_fetcher import DataFetcher
from src.indicators.technical import TechnicalIndicators
from src.strategies.ensemble_strategy import EnsembleStrategy
from src.ai_engine.model_predictor import ModelPredictor
from src.risk.risk_manager import RiskManager
from src.execution.order_manager import OrderManager
from src.telegram.notifier import TelegramNotifier
from src.database.repositories import TradeRepository, SignalRepository
from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


class BotEngine:
    """
    Central orchestrator — state machine controlling all bot components.
    States: INITIALIZING → READY → SCANNING → EXECUTING → PAUSED → ERROR
    """

    def __init__(self):
        self.exchange = ExchangeClient()
        self.data_fetcher = DataFetcher(self.exchange)
        self.strategy = EnsembleStrategy()
        self.ai_predictor = ModelPredictor()
        self.risk_manager = RiskManager()
        self.order_manager = OrderManager(self.exchange)
        self.notifier = TelegramNotifier()
        self.trade_repo = TradeRepository()
        self.signal_repo = SignalRepository()

        self._state = "INITIALIZING"
        self._running = False
        self._paused = False
        self._start_time: Optional[datetime] = None
        self._scan_interval = 60  # seconds between full scans
        self._scan_count = 0

    async def start(self):
        """Full bot startup sequence."""
        logger.info("Starting AI Trading Bot...")

        await self.exchange.initialize()
        await self.notifier.start()
        await self.ai_predictor.load_models()

        # Initialize database tables
        from src.database.connection import create_tables
        await create_tables()

        # Get initial balance
        balance = await self.exchange.fetch_balance()
        initial_equity = balance.get("USDT", {}).get("total", 10000.0)
        await self.risk_manager.update_equity(initial_equity)
        self.order_manager.paper_trader.equity = initial_equity

        self._state = "READY"
        self._running = True
        self._start_time = datetime.now(timezone.utc)

        await self.notifier.send_alert(
            "SUCCESS",
            f"🤖 Trading Bot Started!\n"
            f"Mode: {settings.trading_mode.upper()}\n"
            f"Pairs: {', '.join(settings.trading_pairs)}\n"
            f"Equity: ${initial_equity:,.2f}",
        )

        logger.info(f"Bot started in {settings.trading_mode.upper()} mode")
        await self._main_loop()

    async def _main_loop(self):
        """Main scanning and signal generation loop."""
        logger.info("Main loop started")
        while self._running:
            try:
                if not self._paused:
                    self._state = "SCANNING"
                    await self._scan_all_pairs()
                    await self._check_open_positions()
                    self._state = "READY"
                    self._scan_count += 1

                await asyncio.sleep(self._scan_interval)

            except asyncio.CancelledError:
                logger.info("Main loop cancelled — shutting down")
                break
            except Exception as e:
                logger.error(f"Main loop error: {e}", exc_info=True)
                self._state = "ERROR"
                await self.notifier.send_alert(
                    "CRITICAL",
                    f"Main loop error: {str(e)[:300]}",
                    critical_ping=True,
                )
                await asyncio.sleep(30)
                self._state = "READY"

    async def _scan_all_pairs(self):
        """Scan all trading pairs concurrently for signals."""
        tasks = [self._scan_pair(pair) for pair in settings.trading_pairs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for pair, result in zip(settings.trading_pairs, results):
            if isinstance(result, Exception):
                logger.error(f"Error scanning {pair}: {result}")

    async def _scan_pair(self, symbol: str):
        """Full signal pipeline for one trading pair."""
        try:
            # 1. Fetch multi-timeframe data
            df_primary = await self.data_fetcher.get_dataframe(
                symbol, settings.primary_timeframe, limit=200
            )
            df_secondary = await self.data_fetcher.get_dataframe(
                symbol, settings.secondary_timeframe, limit=100
            )

            # 2. Add indicators
            df_primary = TechnicalIndicators.add_all_indicators(df_primary)
            df_secondary = TechnicalIndicators.add_all_indicators(df_secondary)

            # 3. Get strategy signal
            signal = await self.strategy.generate_signal(df_primary, df_secondary, symbol)

            if signal.direction == "NEUTRAL":
                return

            # 4. AI confidence check
            ai_result = await self.ai_predictor.predict(df_primary, symbol)

            if ai_result.direction == "NEUTRAL":
                logger.debug(f"{symbol}: AI confidence too low — skipping")
                return

            if ai_result.direction != signal.direction:
                logger.info(f"{symbol}: Strategy ({signal.direction}) vs AI ({ai_result.direction}) mismatch — skipping")
                return

            # 5. Risk management check
            risk_result = await self.risk_manager.check_trade(
                symbol=symbol,
                side=signal.direction.lower(),
                proposed_size_usd=self.risk_manager.current_equity * 0.02,
                entry_price=signal.entry_price,
                stop_loss_price=signal.stop_loss,
                take_profit_price=signal.take_profit,
                ai_confidence=ai_result.confidence,
            )

            if not risk_result.approved:
                logger.info(f"{symbol}: Trade rejected by risk: {risk_result.reason}")
                return

            # 6. Log signal to DB
            await self.signal_repo.create_signal({
                "symbol": symbol,
                "direction": signal.direction,
                "strategy_name": signal.strategy_name,
                "timeframe": settings.primary_timeframe,
                "entry_price": signal.entry_price,
                "stop_loss": signal.stop_loss,
                "take_profit": signal.take_profit,
                "signal_score": float(df_primary["signal_score"].iloc[-1]),
                "ai_confidence": ai_result.confidence,
            })

            # 7. Send signal to Telegram
            await self.notifier.send_signal(
                symbol=symbol,
                direction=signal.direction,
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                confidence=ai_result.confidence,
                timeframe=settings.primary_timeframe,
                strategy_name=signal.strategy_name,
                signal_score=float(df_primary["signal_score"].iloc[-1]),
            )

            # 8. Auto-execute in paper mode
            if settings.trading_mode == "paper":
                await self._execute_trade(symbol, signal, risk_result.adjusted_size, ai_result.confidence)

        except Exception as e:
            logger.error(f"_scan_pair({symbol}) failed: {e}", exc_info=True)

    async def _execute_trade(self, symbol, signal, size_usd, confidence):
        """Execute trade with full logging."""
        self._state = "EXECUTING"
        try:
            result = await self.order_manager.place_trade(
                symbol=symbol,
                side=signal.direction.lower(),
                size_usd=size_usd or (self.risk_manager.current_equity * 0.02),
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                confidence=confidence,
                strategy_name=signal.strategy_name,
            )

            self.risk_manager.register_open_position(
                result["id"], symbol, size_usd or (self.risk_manager.current_equity * 0.02)
            )

            await self.notifier.send_trade_executed(
                symbol=symbol,
                side=signal.direction.lower(),
                amount=result["amount"],
                price=result["price"],
                order_id=result["id"],
                is_paper=(settings.trading_mode == "paper"),
            )

            logger.info(f"Trade executed: {symbol} {signal.direction} @ {result['price']:.4f}")

        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            await self.notifier.send_alert("CRITICAL", f"Trade execution failed for {symbol}: {e}")
        finally:
            self._state = "READY"

    async def _check_open_positions(self):
        """Check if any paper positions hit SL/TP."""
        if settings.trading_mode != "paper":
            return
        # Fetch current prices for all pairs with open positions
        try:
            positions = self.order_manager.paper_trader.open_positions
            if not positions:
                return
            symbols = list({p["symbol"] for p in positions.values()})
            current_prices = {}
            for symbol in symbols:
                ticker = await self.exchange.fetch_ticker(symbol)
                current_prices[symbol] = ticker.get("last", 0)

            closed = await self.order_manager.check_and_close_positions(current_prices)
            for trade in closed:
                await self.risk_manager.update_equity(
                    self.order_manager.paper_trader.equity,
                    realized_pnl=trade["pnl"],
                )
                self.risk_manager.remove_position(trade["order_id"])
        except Exception as e:
            logger.warning(f"Position check error: {e}")

    async def get_status(self) -> Dict:
        uptime = (
            str(datetime.now(timezone.utc) - self._start_time).split(".")[0]
            if self._start_time
            else "00:00:00"
        )
        return {
            "is_running": self._running and not self._paused,
            "state": self._state,
            "mode": settings.trading_mode,
            "active_pairs": settings.trading_pairs,
            "equity": self.risk_manager.current_equity,
            "open_positions": len(self.risk_manager.open_positions),
            "daily_pnl": self.risk_manager.daily_pnl,
            "uptime": uptime,
            "scan_count": self._scan_count,
        }

    async def pause(self):
        self._paused = True
        self._state = "PAUSED"
        logger.info("Bot paused by admin")

    async def resume(self):
        self._paused = False
        self._state = "READY"
        logger.info("Bot resumed by admin")

    async def stop(self):
        self._running = False
        await self.notifier.stop()
        await self.exchange.close()
        logger.info("Bot stopped gracefully")
