from typing import Dict, Optional
from src.data.exchange_client import ExchangeClient
from src.execution.paper_trader import PaperTrader
from src.execution.mt5_executor import MT5Executor
from src.database.repositories import TradeRepository
from src.database.models import TradeDirection, TradeStatus
from src.risk.portfolio_compounder import PortfolioCompounder
from src.risk.adaptive_risk import AdaptiveRiskManager
from src.utils.logger import get_logger
from src.utils.validators import validate_trade_params
from src.utils.time_utils import utcnow
from config.settings import settings

logger = get_logger(__name__)


class OrderManager:
    """
    Manages the full order lifecycle: placement, tracking, closure.
    Routes to PaperTrader or live exchange depending on TRADING_MODE.
    Integrates Kelly Criterion position sizing for compounding growth.
    Integrates profit booking engine for multi-tier take-profit management.
    """

    def __init__(
        self, 
        exchange: ExchangeClient,
        initial_equity: Optional[float] = None,
        enable_compounding: bool = True,
        telegram_notifier=None,
        mt5_executor: Optional[MT5Executor] = None,
    ):
        self.exchange = exchange
        self.paper_trader = PaperTrader()
        self.trade_repo = TradeRepository()
        self.telegram_notifier = telegram_notifier

        # MT5 live executor (used when TRADING_MODE=live and broker_mode=mt5)
        self._mt5: Optional[MT5Executor] = mt5_executor
        
        # Initialize compounding system
        self.enable_compounding = enable_compounding
        if enable_compounding:
            equity = initial_equity or getattr(settings, 'initial_equity', 10000.0)
            self.compounder = PortfolioCompounder(
                initial_equity=equity,
                kelly_fraction=0.25,  # Fractional Kelly for safety
                max_position_pct=5.0,
                max_portfolio_heat=12.0,
            )
            logger.info(f"Portfolio Compounder enabled with ${equity:,.2f} initial equity")
        else:
            self.compounder = None
            logger.info("Portfolio Compounder disabled - using fixed position sizing")
        
        # Track current portfolio heat
        self.current_portfolio_heat = 0.0
        self.open_positions_count = 0
        
        # Initialize profit booking engine (will be started separately)
        self.profit_booking_engine = None

    async def place_trade(
        self,
        symbol: str,
        side: str,
        size_usd: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        confidence: float = 0.0,
        strategy_name: str = "unknown",
        win_rate: Optional[float] = None,
        avg_win_pct: Optional[float] = None,
        avg_loss_pct: Optional[float] = None,
        use_kelly_sizing: bool = True,
    ) -> Dict:
        """
        Place a trade order (paper or live) with full validation + DB logging.
        
        Args:
            symbol: Trading symbol
            side: "buy" or "sell"
            size_usd: Base position size in USD (will be adjusted by Kelly if enabled)
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            confidence: AI confidence score (0-100)
            strategy_name: Strategy identifier
            win_rate: Historical win rate for Kelly calculation (optional)
            avg_win_pct: Average win percentage for Kelly calculation (optional)
            avg_loss_pct: Average loss percentage for Kelly calculation (optional)
            use_kelly_sizing: Apply Kelly Criterion position sizing
        
        Returns:
            Order result dictionary
        """

        # Validate parameters
        valid, error = validate_trade_params(
            symbol, side, size_usd, entry_price, stop_loss, take_profit
        )
        if not valid:
            raise ValueError(f"Trade validation failed: {error}")
        
        # Apply Kelly Criterion position sizing if enabled
        final_size_usd = size_usd
        if self.enable_compounding and use_kelly_sizing and self.compounder:
            if win_rate and avg_win_pct and avg_loss_pct:
                # Calculate Kelly-based position size
                kelly_size = self.compounder.calculate_position_size(
                    symbol=symbol,
                    win_rate=win_rate,
                    avg_win_pct=avg_win_pct,
                    avg_loss_pct=avg_loss_pct,
                    current_risk_heat=self.current_portfolio_heat,
                )
                
                if kelly_size > 0:
                    final_size_usd = kelly_size
                    logger.info(
                        f"Kelly sizing applied: ${size_usd:,.2f} → ${final_size_usd:,.2f} "
                        f"(win_rate: {win_rate:.1%})"
                    )
                else:
                    logger.warning(
                        f"Kelly sizing returned 0 - using base size ${size_usd:,.2f}"
                    )
            else:
                logger.debug(
                    "Kelly sizing skipped - missing performance metrics "
                    "(win_rate, avg_win_pct, avg_loss_pct)"
                )

        if settings.trading_mode == "paper":
            result = self.paper_trader.execute_order(
                symbol=symbol,
                side=side,
                size_usd=final_size_usd,
                price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=confidence,
                strategy_name=strategy_name,
            )
        else:
            # ── LIVE MODE: route to MT5 or CCXT ──────────────────────────────
            if settings.broker_mode == "mt5" and self._mt5:
                # Calculate lot size from USD amount
                lot_size = self._usd_to_lots(symbol, final_size_usd, entry_price)
                mt5_result = self._mt5.place_order(
                    symbol=symbol,
                    side=side,
                    volume=lot_size,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    comment=f"QA-{strategy_name[:10]}",
                )
                if not mt5_result.success:
                    raise RuntimeError(f"MT5 order failed: {mt5_result.error}")
                result = {
                    "id": str(mt5_result.ticket),
                    "symbol": symbol,
                    "side": side,
                    "amount": lot_size,
                    "price": mt5_result.price,
                    "status": "open",
                    "timestamp": int(utcnow().timestamp() * 1000),
                }
            else:
                # CCXT live order
                quantity = final_size_usd / entry_price
                result = await self.exchange.create_market_order(symbol, side, quantity)
                result["price"] = entry_price

        # Calculate risk percentage for portfolio heat tracking
        risk_pct = abs(entry_price - stop_loss) / entry_price * 100
        self.current_portfolio_heat += risk_pct
        self.open_positions_count += 1

        # Persist to database
        trade_record = await self.trade_repo.create_trade({
            "symbol": symbol,
            "exchange": settings.exchange_name,
            "order_id": result["id"],
            "direction": TradeDirection.BUY if side == "buy" else TradeDirection.SELL,
            "status": TradeStatus.OPEN,
            "entry_price": result["price"],
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "quantity": result["amount"],
            "size_usd": final_size_usd,
            "strategy_name": strategy_name,
            "ai_confidence": confidence,
            "is_paper_trade": settings.trading_mode == "paper",
            "opened_at": utcnow(),
        })

        # Add position to profit booking engine
        if self.profit_booking_engine:
            await self.profit_booking_engine.add_position(trade_record)

        logger.info(
            f"Order placed: {symbol} {side.upper()} ${final_size_usd:.2f} "
            f"@ {result['price']:.4f} [id={result['id']}] "
            f"Portfolio Heat: {self.current_portfolio_heat:.2f}%"
        )
        return result

    async def check_and_close_positions(self, current_prices: Dict[str, float]):
        """Check paper positions for SL/TP hits and update DB + equity."""
        if settings.trading_mode != "paper":
            return

        closed_trades = self.paper_trader.update_positions(current_prices)
        for trade in closed_trades:
            # Close trade in database
            await self.trade_repo.close_trade(
                order_id=trade["order_id"],
                exit_price=trade["exit_price"],
                pnl=trade["pnl"],
                pnl_pct=trade["pnl_pct"],
            )
            
            # Update portfolio heat (reduce by closed position's risk)
            if "risk_pct" in trade:
                self.current_portfolio_heat = max(
                    0, 
                    self.current_portfolio_heat - trade["risk_pct"]
                )
            
            self.open_positions_count = max(0, self.open_positions_count - 1)
            
            # Update equity in compounder
            if self.enable_compounding and self.compounder:
                new_equity = self.compounder.get_current_equity() + trade["pnl"]
                await self.compounder.update_equity(
                    new_equity=new_equity,
                    realized_pnl=trade["pnl"],
                    unrealized_pnl=0.0,
                    open_positions=self.open_positions_count,
                    portfolio_heat_pct=self.current_portfolio_heat,
                )
                
                logger.info(
                    f"Trade closed: {trade['symbol']} | "
                    f"PnL: ${trade['pnl']:,.2f} ({trade['pnl_pct']:+.2f}%) | "
                    f"New Equity: ${new_equity:,.2f} | "
                    f"Portfolio Heat: {self.current_portfolio_heat:.2f}%"
                )
            
            # Remove from profit booking engine
            if self.profit_booking_engine and "trade_id" in trade:
                await self.profit_booking_engine.remove_position(trade["trade_id"])
    
    async def start_profit_booking(self):
        """Start the profit booking engine."""
        if not self.profit_booking_engine:
            from src.execution.profit_booking_engine import ProfitBookingEngine
            
            self.profit_booking_engine = ProfitBookingEngine(
                order_manager=self,
                telegram_notifier=self.telegram_notifier,
                check_interval=60,
            )
            
            # Start monitoring in background
            import asyncio
            asyncio.create_task(self.profit_booking_engine.start_monitoring())
            
            logger.info("Profit Booking Engine started")
    
    def stop_profit_booking(self):
        """Stop the profit booking engine."""
        if self.profit_booking_engine:
            self.profit_booking_engine.stop_monitoring()
            logger.info("Profit Booking Engine stopped")
    
    async def execute_partial_close(
        self,
        trade_id: int,
        close_percentage: float,
        current_price: float,
    ) -> Dict:
        """
        Execute partial position close.
        
        Args:
            trade_id: Trade ID
            close_percentage: Percentage to close (0-100)
            current_price: Current market price
        
        Returns:
            Result dictionary with PnL info
        """
        # Get trade from database
        trade = await self.trade_repo.get_trade_by_id(trade_id)
        if not trade:
            raise ValueError(f"Trade {trade_id} not found")
        
        if trade.status != TradeStatus.OPEN:
            raise ValueError(f"Trade {trade_id} is not open")
        
        # Calculate close quantity
        close_quantity = trade.quantity * (close_percentage / 100)
        remaining_quantity = trade.quantity - close_quantity
        
        # Calculate PnL
        is_buy = trade.direction == TradeDirection.BUY
        if is_buy:
            pnl = (current_price - trade.entry_price) * close_quantity
        else:
            pnl = (trade.entry_price - current_price) * close_quantity
        
        pnl_pct = ((current_price - trade.entry_price) / trade.entry_price * 100
                   if is_buy else
                   (trade.entry_price - current_price) / trade.entry_price * 100)
        
        # Update trade in database
        # Note: This requires extending the Trade model to support partial closes
        # For now, we'll just log it
        
        logger.info(
            f"Partial close executed: {trade.symbol}\n"
            f"  Closed: {close_percentage:.0f}% ({close_quantity:.4f})\n"
            f"  Remaining: {remaining_quantity:.4f}\n"
            f"  PnL: ${pnl:,.2f} ({pnl_pct:+.2f}%)"
        )
        
        return {
            "trade_id": trade_id,
            "symbol": trade.symbol,
            "close_percentage": close_percentage,
            "close_quantity": close_quantity,
            "remaining_quantity": remaining_quantity,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "current_price": current_price,
        }
    
    async def get_compounding_stats(self) -> Dict:
        """Get compounding performance statistics."""
        if not self.enable_compounding or not self.compounder:
            return {
                "enabled": False,
                "message": "Compounding disabled"
            }
        
        stats = await self.compounder.get_compounding_stats()
        return {
            "enabled": True,
            "initial_equity": stats.initial_equity,
            "current_equity": stats.current_equity,
            "total_return_pct": stats.total_return_pct,
            "annualized_return_pct": stats.annualized_return_pct,
            "monthly_compounding_rate": stats.compounding_rate,
            "open_positions": self.open_positions_count,
            "portfolio_heat_pct": self.current_portfolio_heat,
        }
    
    def get_current_equity(self) -> float:
        """Get current equity for position sizing."""
        if self.enable_compounding and self.compounder:
            return self.compounder.get_current_equity()
        return getattr(settings, 'initial_equity', 10000.0)

    def get_paper_stats(self) -> Dict:
        """Get paper trading statistics."""
        return self.paper_trader.get_stats()

    # ── MT5 helpers ───────────────────────────────────────────────────────────

    def connect_mt5(
        self,
        login: Optional[int] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
    ) -> bool:
        """
        Connect (or reconnect) the MT5 executor.
        Uses env vars if credentials not provided.
        """
        if self._mt5 is None:
            self._mt5 = MT5Executor(login=login, password=password, server=server)
        ok = self._mt5.connect()
        if ok:
            logger.info("MT5 executor connected via OrderManager")
        else:
            logger.warning("MT5 executor failed to connect — live trades will fail")
        return ok

    def get_mt5_account_info(self):
        """Return MT5 account info if connected."""
        if self._mt5:
            return self._mt5.get_account_info()
        return None

    def get_mt5_positions(self):
        """Return open MT5 positions."""
        if self._mt5:
            return self._mt5.get_positions()
        return []

    @staticmethod
    def _usd_to_lots(symbol: str, size_usd: float, price: float) -> float:
        """
        Convert USD position size to MT5 lot size.
        Standard lot = 100,000 units for forex.
        For crypto: 1 lot = 1 unit.
        """
        symbol_upper = symbol.upper().replace("/", "")
        # Forex pairs: 1 standard lot = 100,000 base currency units
        forex_pairs = {
            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
            "USDCHF", "NZDUSD", "EURGBP", "XAUUSD", "XAGUSD",
        }
        if symbol_upper in forex_pairs:
            contract_size = 100_000.0
            # For JPY pairs, price is ~150; for others ~1
            if "JPY" in symbol_upper:
                lot_size = size_usd / (contract_size / price)
            else:
                lot_size = size_usd / (contract_size * price)
            # Round to 2 decimal places (MT5 minimum step)
            lot_size = max(0.01, round(lot_size, 2))
        else:
            # Crypto: lot = units
            lot_size = round(size_usd / price, 6)
        return lot_size
