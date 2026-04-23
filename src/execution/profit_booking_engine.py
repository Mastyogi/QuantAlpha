"""
Profit Booking Engine
Multi-tier take-profit system with trailing stops and breakeven management.
"""

import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone
from src.database.repositories import TradeRepository
from src.database.models import Trade, TradeStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TakeProfitLevel:
    """Take profit level configuration."""
    level: int  # 1, 2, or 3
    price: float
    percentage: float  # Percentage of position to close (33%, 33%, 34%)
    hit: bool = False


@dataclass
class PositionState:
    """Current state of a position for profit booking."""
    trade_id: int
    symbol: str
    direction: str  # BUY or SELL
    entry_price: float
    stop_loss: float
    current_sl: float  # Current stop loss (may be trailed)
    quantity: float
    remaining_quantity: float
    tp_levels: List[TakeProfitLevel]
    breakeven_set: bool = False
    trailing_active: bool = False
    last_update: datetime = None


class TakeProfitManager:
    """Manages multi-tier take-profit levels."""
    
    def calculate_tp_levels(
        self,
        entry_price: float,
        stop_loss: float,
        direction: str,
    ) -> List[TakeProfitLevel]:
        """
        Calculate three TP levels based on stop distance.
        
        TP1: 1.5x stop distance (33% close)
        TP2: 3.0x stop distance (33% close)
        TP3: 5.0x stop distance (34% close)
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            direction: "BUY" or "SELL"
        
        Returns:
            List of TakeProfitLevel objects
        """
        stop_distance = abs(entry_price - stop_loss)
        is_buy = direction.upper() == "BUY"
        
        if is_buy:
            tp1 = entry_price + (stop_distance * 1.5)
            tp2 = entry_price + (stop_distance * 3.0)
            tp3 = entry_price + (stop_distance * 5.0)
        else:
            tp1 = entry_price - (stop_distance * 1.5)
            tp2 = entry_price - (stop_distance * 3.0)
            tp3 = entry_price - (stop_distance * 5.0)
        
        return [
            TakeProfitLevel(level=1, price=tp1, percentage=33.0),
            TakeProfitLevel(level=2, price=tp2, percentage=33.0),
            TakeProfitLevel(level=3, price=tp3, percentage=34.0),
        ]
    
    def check_tp_hit(
        self,
        current_price: float,
        tp_level: TakeProfitLevel,
        direction: str,
    ) -> bool:
        """Check if TP level has been hit."""
        is_buy = direction.upper() == "BUY"
        
        if tp_level.hit:
            return False
        
        if is_buy:
            return current_price >= tp_level.price
        else:
            return current_price <= tp_level.price


class TrailingStopManager:
    """Manages trailing stop logic."""
    
    def calculate_trailing_stop(
        self,
        current_price: float,
        entry_price: float,
        current_sl: float,
        direction: str,
        lock_in_pct: float = 0.50,  # Lock in 50% of gains
    ) -> Tuple[float, bool]:
        """
        Calculate trailing stop to lock in profits.
        
        Args:
            current_price: Current market price
            entry_price: Entry price
            current_sl: Current stop loss
            direction: "BUY" or "SELL"
            lock_in_pct: Percentage of gains to lock in (0.5 = 50%)
        
        Returns:
            (new_sl, moved) - New stop loss and whether it moved
        """
        is_buy = direction.upper() == "BUY"
        
        if is_buy:
            # Calculate profit distance
            profit_distance = current_price - entry_price
            
            # New SL locks in lock_in_pct of profit
            new_sl = entry_price + (profit_distance * lock_in_pct)
            
            # Only trail up, never down
            if new_sl > current_sl:
                return new_sl, True
        else:
            # Calculate profit distance
            profit_distance = entry_price - current_price
            
            # New SL locks in lock_in_pct of profit
            new_sl = entry_price - (profit_distance * lock_in_pct)
            
            # Only trail down, never up
            if new_sl < current_sl:
                return new_sl, True
        
        return current_sl, False


class BreakevenManager:
    """Manages breakeven stop loss adjustment."""
    
    def should_move_to_breakeven(
        self,
        current_price: float,
        entry_price: float,
        tp1_price: float,
        direction: str,
    ) -> bool:
        """Check if price has reached TP1 to move SL to breakeven."""
        is_buy = direction.upper() == "BUY"
        
        if is_buy:
            return current_price >= tp1_price
        else:
            return current_price <= tp1_price
    
    def calculate_breakeven_sl(
        self,
        entry_price: float,
        direction: str,
        buffer_pct: float = 0.001,  # 0.1% buffer above/below entry
    ) -> float:
        """
        Calculate breakeven stop loss with small buffer.
        
        Args:
            entry_price: Entry price
            direction: "BUY" or "SELL"
            buffer_pct: Buffer percentage (0.001 = 0.1%)
        
        Returns:
            Breakeven stop loss price
        """
        is_buy = direction.upper() == "BUY"
        
        if is_buy:
            # Set SL slightly below entry
            return entry_price * (1 - buffer_pct)
        else:
            # Set SL slightly above entry
            return entry_price * (1 + buffer_pct)


class ProfitBookingEngine:
    """
    Main profit booking engine.
    Monitors positions and executes multi-tier profit taking.
    """
    
    def __init__(
        self,
        order_manager,
        telegram_notifier=None,
        check_interval: int = 60,  # Check every 60 seconds
    ):
        self.order_manager = order_manager
        self.telegram_notifier = telegram_notifier
        self.check_interval = check_interval
        
        self.tp_manager = TakeProfitManager()
        self.trailing_manager = TrailingStopManager()
        self.breakeven_manager = BreakevenManager()
        
        self.trade_repo = TradeRepository()
        self.active_positions: Dict[int, PositionState] = {}
        self.is_running = False
        
        logger.info(
            f"Profit Booking Engine initialized:\n"
            f"  Check Interval: {check_interval}s\n"
            f"  TP Levels: 1.5x, 3x, 5x stop distance\n"
            f"  Partial Closes: 33%, 33%, 34%"
        )
    
    async def start_monitoring(self):
        """Start the profit booking monitoring loop."""
        self.is_running = True
        logger.info("🎯 Profit Booking Engine started")
        
        while self.is_running:
            try:
                await self._monitor_positions()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in profit booking loop: {e}", exc_info=True)
                await asyncio.sleep(self.check_interval)
    
    def stop_monitoring(self):
        """Stop the profit booking monitoring loop."""
        self.is_running = False
        logger.info("Profit Booking Engine stopped")
    
    async def add_position(self, trade: Trade):
        """
        Add a new position to monitor.
        
        Args:
            trade: Trade object from database
        """
        # Calculate TP levels
        tp_levels = self.tp_manager.calculate_tp_levels(
            entry_price=trade.entry_price,
            stop_loss=trade.stop_loss,
            direction=trade.direction.value,
        )
        
        position = PositionState(
            trade_id=trade.id,
            symbol=trade.symbol,
            direction=trade.direction.value,
            entry_price=trade.entry_price,
            stop_loss=trade.stop_loss,
            current_sl=trade.stop_loss,
            quantity=trade.quantity,
            remaining_quantity=trade.quantity,
            tp_levels=tp_levels,
            breakeven_set=False,
            trailing_active=False,
            last_update=datetime.now(timezone.utc),
        )
        
        self.active_positions[trade.id] = position
        
        logger.info(
            f"📊 Position added to profit booking:\n"
            f"  Symbol: {trade.symbol}\n"
            f"  Direction: {trade.direction.value}\n"
            f"  Entry: {trade.entry_price:.5f}\n"
            f"  TP1: {tp_levels[0].price:.5f} (33%)\n"
            f"  TP2: {tp_levels[1].price:.5f} (33%)\n"
            f"  TP3: {tp_levels[2].price:.5f} (34%)"
        )
    
    async def remove_position(self, trade_id: int):
        """Remove a position from monitoring."""
        if trade_id in self.active_positions:
            position = self.active_positions.pop(trade_id)
            logger.info(f"Position {position.symbol} removed from profit booking")
    
    async def _monitor_positions(self):
        """Monitor all active positions for TP hits and trailing stops."""
        if not self.active_positions:
            return
        
        # Get current prices for all symbols
        symbols = list(set(p.symbol for p in self.active_positions.values()))
        current_prices = await self._get_current_prices(symbols)
        
        for trade_id, position in list(self.active_positions.items()):
            try:
                current_price = current_prices.get(position.symbol)
                if not current_price:
                    continue
                
                await self._process_position(position, current_price)
                
            except Exception as e:
                logger.error(
                    f"Error processing position {position.symbol}: {e}",
                    exc_info=True
                )
    
    async def _process_position(self, position: PositionState, current_price: float):
        """Process a single position for TP hits and trailing stops."""
        
        # Check TP levels
        for tp_level in position.tp_levels:
            if self.tp_manager.check_tp_hit(
                current_price=current_price,
                tp_level=tp_level,
                direction=position.direction,
            ):
                await self._execute_partial_close(position, tp_level, current_price)
        
        # Move to breakeven after TP1 hit
        if position.tp_levels[0].hit and not position.breakeven_set:
            if self.breakeven_manager.should_move_to_breakeven(
                current_price=current_price,
                entry_price=position.entry_price,
                tp1_price=position.tp_levels[0].price,
                direction=position.direction,
            ):
                await self._move_to_breakeven(position)
        
        # Activate trailing stop after TP1 hit
        if position.tp_levels[0].hit and position.breakeven_set:
            new_sl, moved = self.trailing_manager.calculate_trailing_stop(
                current_price=current_price,
                entry_price=position.entry_price,
                current_sl=position.current_sl,
                direction=position.direction,
                lock_in_pct=0.50,
            )
            
            if moved:
                await self._update_trailing_stop(position, new_sl)
    
    async def _execute_partial_close(
        self,
        position: PositionState,
        tp_level: TakeProfitLevel,
        current_price: float,
    ):
        """Execute partial position close at TP level."""
        # Calculate close quantity
        close_quantity = position.quantity * (tp_level.percentage / 100)
        
        # Mark TP as hit
        tp_level.hit = True
        
        # Update remaining quantity
        position.remaining_quantity -= close_quantity
        
        # Calculate PnL for this partial close
        is_buy = position.direction.upper() == "BUY"
        if is_buy:
            pnl = (current_price - position.entry_price) * close_quantity
        else:
            pnl = (position.entry_price - current_price) * close_quantity
        
        pnl_pct = ((current_price - position.entry_price) / position.entry_price * 100
                   if is_buy else
                   (position.entry_price - current_price) / position.entry_price * 100)
        
        logger.info(
            f"💰 TP{tp_level.level} HIT: {position.symbol}\n"
            f"  Price: {current_price:.5f}\n"
            f"  Closed: {tp_level.percentage:.0f}% ({close_quantity:.4f})\n"
            f"  PnL: ${pnl:,.2f} ({pnl_pct:+.2f}%)\n"
            f"  Remaining: {position.remaining_quantity:.4f}"
        )
        
        # Send Telegram notification
        if self.telegram_notifier:
            await self._send_tp_notification(
                position, tp_level, current_price, pnl, pnl_pct
            )
        
        # Update position in database (if needed)
        # This would require extending the Trade model to track partial closes
    
    async def _move_to_breakeven(self, position: PositionState):
        """Move stop loss to breakeven."""
        breakeven_sl = self.breakeven_manager.calculate_breakeven_sl(
            entry_price=position.entry_price,
            direction=position.direction,
            buffer_pct=0.001,
        )
        
        position.current_sl = breakeven_sl
        position.breakeven_set = True
        
        logger.info(
            f"🔒 Breakeven set: {position.symbol}\n"
            f"  Entry: {position.entry_price:.5f}\n"
            f"  New SL: {breakeven_sl:.5f}"
        )
        
        # Send Telegram notification
        if self.telegram_notifier:
            await self._send_breakeven_notification(position, breakeven_sl)
    
    async def _update_trailing_stop(self, position: PositionState, new_sl: float):
        """Update trailing stop loss."""
        old_sl = position.current_sl
        position.current_sl = new_sl
        position.trailing_active = True
        position.last_update = datetime.now(timezone.utc)
        
        logger.info(
            f"📈 Trailing stop updated: {position.symbol}\n"
            f"  Old SL: {old_sl:.5f}\n"
            f"  New SL: {new_sl:.5f}"
        )
        
        # Send Telegram notification (optional, can be noisy)
        # if self.telegram_notifier:
        #     await self._send_trailing_notification(position, old_sl, new_sl)
    
    async def _get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get current prices for symbols."""
        # This would integrate with exchange client or paper trader
        # For now, return empty dict - needs integration
        prices = {}
        
        try:
            # Get prices from order manager's exchange or paper trader
            if hasattr(self.order_manager, 'exchange'):
                for symbol in symbols:
                    ticker = await self.order_manager.exchange.fetch_ticker(symbol)
                    prices[symbol] = ticker.get('last', 0)
            elif hasattr(self.order_manager, 'paper_trader'):
                # Paper trader would need to expose current prices
                pass
        except Exception as e:
            logger.error(f"Error fetching prices: {e}")
        
        return prices
    
    async def _send_tp_notification(
        self,
        position: PositionState,
        tp_level: TakeProfitLevel,
        price: float,
        pnl: float,
        pnl_pct: float,
    ):
        """Send Telegram notification for TP hit."""
        message = (
            f"💰 <b>TP{tp_level.level} HIT</b>\n\n"
            f"Symbol: {position.symbol}\n"
            f"Direction: {position.direction}\n"
            f"Price: {price:.5f}\n"
            f"Closed: {tp_level.percentage:.0f}%\n"
            f"PnL: ${pnl:,.2f} ({pnl_pct:+.2f}%)\n"
            f"Remaining: {position.remaining_quantity:.4f}"
        )
        
        try:
            await self.telegram_notifier.send_message(message)
        except Exception as e:
            logger.error(f"Error sending TP notification: {e}")
    
    async def _send_breakeven_notification(
        self,
        position: PositionState,
        breakeven_sl: float,
    ):
        """Send Telegram notification for breakeven move."""
        message = (
            f"🔒 <b>Breakeven Set</b>\n\n"
            f"Symbol: {position.symbol}\n"
            f"Entry: {position.entry_price:.5f}\n"
            f"New SL: {breakeven_sl:.5f}\n"
            f"Risk eliminated!"
        )
        
        try:
            await self.telegram_notifier.send_message(message)
        except Exception as e:
            logger.error(f"Error sending breakeven notification: {e}")
