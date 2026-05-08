import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


class PaperTrader:
    """
    Simulated order execution engine for paper trading.
    Tracks positions, applies slippage, and calculates P&L.
    """

    def __init__(self):
        self.equity: float = 10000.0
        self.open_positions: Dict[str, dict] = {}
        self.closed_trades: List[dict] = []
        self.total_fees: float = 0.0
        self._fee_rate: float = 0.001  # 0.1% taker fee

    def execute_order(
        self,
        symbol: str,
        side: str,
        size_usd: float,
        price: float,
        stop_loss: float,
        take_profit: float,
        confidence: float = 0.0,
        strategy_name: str = "unknown",
    ) -> dict:
        """Simulate order execution with slippage."""
        # Apply slippage
        slippage = settings.slippage_pct / 100
        if side == "buy":
            fill_price = price * (1 + slippage)
        else:
            fill_price = price * (1 - slippage)

        quantity = size_usd / fill_price
        fee = size_usd * self._fee_rate
        self.total_fees += fee
        self.equity -= fee

        order_id = f"paper_{uuid.uuid4().hex[:12]}"

        position = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "entry_price": fill_price,
            "quantity": quantity,
            "size_usd": size_usd,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "confidence": confidence,
            "strategy_name": strategy_name,
            "opened_at": datetime.now(timezone.utc),
            "is_paper": True,
        }

        self.open_positions[order_id] = position
        logger.info(
            f"[PAPER] {side.upper()} {symbol} qty={quantity:.6f} @ {fill_price:.4f} "
            f"SL={stop_loss:.4f} TP={take_profit:.4f}"
        )

        return {
            "id": order_id,
            "symbol": symbol,
            "side": side,
            "amount": quantity,
            "price": fill_price,
            "status": "open",
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
        }

    def update_positions(self, current_prices: Dict[str, float]) -> List[dict]:
        """Check all open positions for SL/TP hits. Returns list of closed trades."""
        closed = []
        for order_id, pos in list(self.open_positions.items()):
            symbol = pos["symbol"]
            price = current_prices.get(symbol)
            if price is None:
                continue

            closed_trade = None

            if pos["side"] == "buy":
                if price <= pos["stop_loss"]:
                    closed_trade = self._close_position(order_id, price, "STOP_LOSS")
                elif price >= pos["take_profit"]:
                    closed_trade = self._close_position(order_id, price, "TAKE_PROFIT")

            elif pos["side"] == "sell":
                if price >= pos["stop_loss"]:
                    closed_trade = self._close_position(order_id, price, "STOP_LOSS")
                elif price <= pos["take_profit"]:
                    closed_trade = self._close_position(order_id, price, "TAKE_PROFIT")

            if closed_trade:
                closed.append(closed_trade)

        return closed

    def _close_position(self, order_id: str, exit_price: float, reason: str) -> dict:
        """Close a position and calculate P&L."""
        pos = self.open_positions.pop(order_id)
        fee = pos["size_usd"] * self._fee_rate
        self.total_fees += fee

        if pos["side"] == "buy":
            pnl = (exit_price - pos["entry_price"]) * pos["quantity"] - fee
        else:
            pnl = (pos["entry_price"] - exit_price) * pos["quantity"] - fee

        pnl_pct = pnl / pos["size_usd"] * 100
        self.equity += pos["size_usd"] + pnl

        trade = {
            **pos,
            "exit_price": exit_price,
            "exit_reason": reason,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "closed_at": datetime.now(timezone.utc),
        }
        self.closed_trades.append(trade)

        emoji = "✅" if pnl > 0 else "❌"
        logger.info(
            f"{emoji} [PAPER] CLOSED {pos['symbol']} @ {exit_price:.4f} "
            f"Reason={reason} PnL={pnl:+.2f} ({pnl_pct:+.2f}%)"
        )
        return trade

    def get_stats(self) -> dict:
        """Return current paper trading statistics."""
        total = len(self.closed_trades)
        wins = [t for t in self.closed_trades if t["pnl"] > 0]
        losses = [t for t in self.closed_trades if t["pnl"] <= 0]

        return {
            "equity": self.equity,
            "open_positions": len(self.open_positions),
            "total_trades": total,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": len(wins) / max(total, 1) * 100,
            "total_pnl": sum(t["pnl"] for t in self.closed_trades),
            "total_fees": self.total_fees,
        }

    @property
    def trade_history(self) -> List[dict]:
        """Alias for closed_trades — used by performance tracker."""
        return self.closed_trades
