"""
Adaptive Risk Manager
======================
ATR-based dynamic stop loss + take profit.
Per-asset-class R:R targets.
Trailing stop once in profit.
Win-rate based adaptive position sizing.
Correlation guard to prevent over-exposure.

Why this is better than fixed pips:
  - ATR adapts to current volatility (high vol = wider stop)
  - Trailing stop locks in profits
  - Per-asset R:R is realistic (crypto 2.5:1, forex 2:1)
  - Position size adapts to recent performance (win rate)
  - Correlation guard prevents correlated positions
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List
from collections import deque

import numpy as np
import pandas as pd
import redis.asyncio as redis

from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


@dataclass
class TradeSetup:
    """Complete trade setup with entry, SL, TP levels."""
    symbol:        str
    direction:     str          # BUY / SELL
    entry_price:   float
    stop_loss:     float
    take_profit_1: float        # 1:1 R:R — first target (partial exit 50%)
    take_profit_2: float        # Full R:R target (main target)
    take_profit_3: float        # Extended target (if very strong)
    risk_pct:      float        # % distance from entry to SL
    reward_pct:    float        # % distance from entry to TP2
    rr_ratio:      float        # Actual R:R = reward/risk
    atr_value:     float        # ATR used for calculation
    position_size_usd: float    # Recommended position size (USD)
    trailing_activation: float  # Price at which trailing stop activates
    invalidation:  float        # Trade invalid if price hits this level

    @property
    def risk_reward_ok(self) -> bool:
        return self.rr_ratio >= 1.5

    def display(self) -> str:
        arrow = "▲" if self.direction == "BUY" else "▼"
        return (
            f"\n{'='*42}\n"
            f"  {arrow} {self.direction} {self.symbol}\n"
            f"{'─'*42}\n"
            f"  Entry:      {self.entry_price:.5g}\n"
            f"  Stop Loss:  {self.stop_loss:.5g}  (-{self.risk_pct:.2f}%)\n"
            f"  Target 1:   {self.take_profit_1:.5g}  (1:1 R:R)\n"
            f"  Target 2:   {self.take_profit_2:.5g}  (+{self.reward_pct:.2f}%)\n"
            f"  Target 3:   {self.take_profit_3:.5g}  (extended)\n"
            f"  R:R Ratio:  {self.rr_ratio:.2f}:1  "
            f"{'✅' if self.risk_reward_ok else '❌ BLOCKED'}\n"
            f"  ATR:        {self.atr_value:.5g}\n"
            f"  Trail at:   {self.trailing_activation:.5g}\n"
            f"{'='*42}\n"
        )


@dataclass
class RiskCheckResult:
    """Result from risk check validation."""
    approved: bool
    reason: str
    position_size_adjustment: float = 1.0  # Multiplier for position size (0.5 = 50% reduction)


# ── R:R targets per asset class ───────────────────────────────────────────────
RR_TARGETS: Dict[str, Dict] = {
    "crypto": {
        "atr_sl_mult":     1.8,    # SL = 1.8 × ATR below entry
        "tp1_mult":        1.8,    # TP1 = 1.8 × ATR (1:1)
        "tp2_mult":        3.5,    # TP2 = 3.5 × ATR (main target)
        "tp3_mult":        5.0,    # TP3 extended
        "trail_mult":      1.5,    # Start trailing at 1.5 × ATR profit
        "min_rr":          1.8,
    },
    "forex": {
        "atr_sl_mult":     1.5,
        "tp1_mult":        1.5,
        "tp2_mult":        2.5,
        "tp3_mult":        4.0,
        "trail_mult":      1.2,
        "min_rr":          1.8,
    },
    "commodity": {
        "atr_sl_mult":     1.6,
        "tp1_mult":        1.6,
        "tp2_mult":        3.0,
        "tp3_mult":        4.5,
        "trail_mult":      1.3,
        "min_rr":          2.0,
    },
}

# Asset class detection
FOREX_SYMS = {"EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD"}
COMMODITY_SYMS = {"XAUUSD","XAGUSD","USOIL","UKOIL"}


def _asset_class(symbol: str) -> str:
    s = symbol.upper().replace("/","")
    if s in FOREX_SYMS:      return "forex"
    if s in COMMODITY_SYMS:  return "commodity"
    return "crypto"


class AdaptiveRiskManager:
    """
    Calculates ATR-based dynamic SL/TP for any instrument.
    Adapts to current volatility regime automatically.
    Adapts position sizing based on recent win rate performance.
    """

    def __init__(
        self, 
        max_risk_pct: float = 2.0, 
        account_equity: float = 10000.0,
        track_last_n_trades: int = 20
    ):
        self.max_risk_pct   = max_risk_pct
        self.account_equity = account_equity
        self.track_last_n_trades = track_last_n_trades
        
        # Track recent trade results for adaptive sizing
        self.recent_trades: deque = deque(maxlen=track_last_n_trades)
        self.consecutive_losses = 0
        
        # Redis client for correlation matrix
        self._redis_client: Optional[redis.Redis] = None
        
        logger.info(
            f"Adaptive Risk Manager initialized:\n"
            f"  Max Risk: {max_risk_pct}%\n"
            f"  Account Equity: ${account_equity:,.2f}\n"
            f"  Tracking last {track_last_n_trades} trades"
        )
    
    async def _get_redis(self) -> Optional[redis.Redis]:
        """Get or create Redis connection."""
        if self._redis_client is None:
            try:
                self._redis_client = redis.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
                # Test connection
                await self._redis_client.ping()
                logger.debug("Redis connection established")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}")
                return None
        return self._redis_client
    
    def record_trade_result(self, is_win: bool, pnl: float):
        """
        Record trade result for adaptive position sizing.
        
        Args:
            is_win: True if trade was profitable
            pnl: Profit/loss amount
        """
        self.recent_trades.append({
            "is_win": is_win,
            "pnl": pnl
        })
        
        if is_win:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
        
        win_rate = self.get_rolling_win_rate()
        logger.info(
            f"Trade recorded: {'WIN' if is_win else 'LOSS'} "
            f"(PnL: ${pnl:,.2f}) | "
            f"Rolling Win Rate: {win_rate:.1%} | "
            f"Consecutive Losses: {self.consecutive_losses}"
        )
    
    def get_rolling_win_rate(self) -> float:
        """Calculate rolling win rate from recent trades."""
        if not self.recent_trades:
            return 0.60  # Default baseline
        
        wins = sum(1 for t in self.recent_trades if t["is_win"])
        return wins / len(self.recent_trades)
    
    def get_position_size_multiplier(self) -> float:
        """
        Calculate position size multiplier based on recent performance.
        
        Rules:
        - Win rate > 70%: Increase size by up to 50%
        - Win rate < 55%: Decrease size by 50%
        - 5+ consecutive losses: Reduce to minimum (0.5x)
        - Formula: base_size × (1 + (win_rate - 0.60) × 2)
        - Clamped between 0.5x and 1.5x
        """
        # Emergency brake: 5+ consecutive losses
        if self.consecutive_losses >= 5:
            logger.warning(
                f"🚨 5+ consecutive losses detected! "
                f"Reducing position size to minimum (0.5x)"
            )
            return 0.5
        
        win_rate = self.get_rolling_win_rate()
        
        # Calculate multiplier: 1 + (win_rate - 0.60) × 2
        # Examples:
        #   win_rate = 0.70 → 1 + (0.10 × 2) = 1.20 (20% increase)
        #   win_rate = 0.50 → 1 + (-0.10 × 2) = 0.80 (20% decrease)
        multiplier = 1 + (win_rate - 0.60) * 2
        
        # Clamp between 0.5 and 1.5
        multiplier = max(0.5, min(1.5, multiplier))
        
        logger.debug(
            f"Position size multiplier: {multiplier:.2f}x "
            f"(win_rate: {win_rate:.1%})"
        )
        
        return multiplier
    
    def update_equity(self, new_equity: float):
        """Update account equity for position sizing."""
        old_equity = self.account_equity
        self.account_equity = new_equity
        
        pct_change = abs(new_equity - old_equity) / old_equity if old_equity > 0 else 0
        if pct_change >= 0.10:
            logger.info(
                f"📊 Equity updated: ${old_equity:,.2f} → ${new_equity:,.2f} "
                f"({pct_change:+.1%})"
            )
    
    def get_adaptive_position_size(
        self,
        base_position_size: float,
        min_size_pct: float = 0.005,  # 0.5% of equity
        max_size_pct: float = 0.05,   # 5% of equity
    ) -> float:
        """
        Calculate adaptive position size based on performance.
        
        Args:
            base_position_size: Base position size in USD
            min_size_pct: Minimum position size as % of equity
            max_size_pct: Maximum position size as % of equity
        
        Returns:
            Adjusted position size in USD
        """
        multiplier = self.get_position_size_multiplier()
        adjusted_size = base_position_size * multiplier
        
        # Enforce absolute limits
        min_size = self.account_equity * min_size_pct
        max_size = self.account_equity * max_size_pct
        
        adjusted_size = max(min_size, min(adjusted_size, max_size))
        
        logger.debug(
            f"Adaptive position size: ${adjusted_size:,.2f} "
            f"(base: ${base_position_size:,.2f}, multiplier: {multiplier:.2f}x)"
        )
        
        return adjusted_size

    async def check_correlation_guard(
        self,
        symbol: str,
        open_positions: List[Dict],
    ) -> RiskCheckResult:
        """
        Check correlation guard to prevent over-exposure to correlated assets.
        
        Args:
            symbol: Symbol to check
            open_positions: List of currently open positions
        
        Returns:
            RiskCheckResult with approval status and position size adjustment
        """
        if not open_positions:
            return RiskCheckResult(
                approved=True,
                reason="No open positions - correlation check passed",
                position_size_adjustment=1.0
            )
        
        try:
            # Get Redis client
            redis_client = await self._get_redis()
            
            if not redis_client:
                logger.warning("Redis unavailable - skipping correlation guard")
                return RiskCheckResult(
                    approved=True,
                    reason="Correlation matrix unavailable (Redis down)",
                    position_size_adjustment=1.0
                )
            
            # Fetch correlation matrix from Redis
            correlation_data = await redis_client.get("correlation_matrix")
            
            if not correlation_data:
                logger.warning("Correlation matrix not found in Redis - skipping correlation guard")
                return RiskCheckResult(
                    approved=True,
                    reason="Correlation matrix not populated",
                    position_size_adjustment=1.0
                )
            
            import json
            correlation_matrix = json.loads(correlation_data)
            
            # Check correlation with each open position
            max_correlation = 0.0
            correlated_symbol = None
            
            for position in open_positions:
                pos_symbol = position.get("symbol", "")
                
                # Get correlation between new symbol and open position symbol
                correlation = self._get_correlation(
                    symbol, pos_symbol, correlation_matrix
                )
                
                if correlation > max_correlation:
                    max_correlation = correlation
                    correlated_symbol = pos_symbol
            
            # Apply correlation rules
            if max_correlation > 0.90:
                # Block trade entirely
                logger.warning(
                    f"🚫 Trade BLOCKED: {symbol} has {max_correlation:.2%} "
                    f"correlation with open position {correlated_symbol} (>90%)"
                )
                return RiskCheckResult(
                    approved=False,
                    reason=f"High correlation ({max_correlation:.2%}) with {correlated_symbol}",
                    position_size_adjustment=0.0
                )
            
            elif max_correlation > 0.70:
                # Cap position size at 50%
                logger.info(
                    f"⚠️ Position size reduced: {symbol} has {max_correlation:.2%} "
                    f"correlation with {correlated_symbol} (>70%) - capping at 50%"
                )
                return RiskCheckResult(
                    approved=True,
                    reason=f"Moderate correlation ({max_correlation:.2%}) with {correlated_symbol} - size reduced",
                    position_size_adjustment=0.5
                )
            
            else:
                # No significant correlation
                logger.debug(
                    f"✅ Correlation check passed: {symbol} max correlation "
                    f"{max_correlation:.2%} with {correlated_symbol}"
                )
                return RiskCheckResult(
                    approved=True,
                    reason=f"Low correlation ({max_correlation:.2%})",
                    position_size_adjustment=1.0
                )
        
        except Exception as e:
            logger.error(f"Correlation guard check failed: {e}", exc_info=True)
            # Fail-safe: allow trade but log error
            return RiskCheckResult(
                approved=True,
                reason=f"Correlation check error: {str(e)}",
                position_size_adjustment=1.0
            )
    
    @staticmethod
    def _get_correlation(symbol1: str, symbol2: str, correlation_matrix: Dict) -> float:
        """
        Get correlation coefficient between two symbols from matrix.
        
        Args:
            symbol1: First symbol
            symbol2: Second symbol
            correlation_matrix: Correlation matrix dictionary
        
        Returns:
            Correlation coefficient (0.0 to 1.0)
        """
        # Normalize symbol names (remove slashes, convert to uppercase)
        s1 = symbol1.replace("/", "").replace("-", "").upper()
        s2 = symbol2.replace("/", "").replace("-", "").upper()
        
        # Same symbol = perfect correlation
        if s1 == s2:
            return 1.0
        
        # Try to find correlation in matrix
        # Matrix format: {"EURUSD": {"GBPUSD": 0.85, ...}, ...}
        try:
            if s1 in correlation_matrix and s2 in correlation_matrix[s1]:
                return abs(correlation_matrix[s1][s2])
            elif s2 in correlation_matrix and s1 in correlation_matrix[s2]:
                return abs(correlation_matrix[s2][s1])
            else:
                # No correlation data - assume low correlation
                return 0.0
        except (KeyError, TypeError):
            return 0.0

    def calculate_trade_setup(
        self,
        symbol: str,
        direction: str,
        df: pd.DataFrame,
        confluence_score: float = 75.0,
        custom_rr_mult: Optional[float] = None,
        use_adaptive_sizing: bool = True,
    ) -> TradeSetup:
        """
        Calculate complete trade setup with adaptive SL/TP.

        Args:
            symbol:           Trading instrument
            direction:        "BUY" or "SELL"
            df:               OHLCV DataFrame with indicators
            confluence_score: 0–100 score (higher = wider TP allowed)
            custom_rr_mult:   Override R:R multiplier
            use_adaptive_sizing: Apply win-rate based position sizing
        """
        asset_class = _asset_class(symbol)
        params = RR_TARGETS[asset_class].copy()

        # High confluence → reward more aggressive target
        if confluence_score >= 85:
            params["tp2_mult"] *= 1.2
            params["tp3_mult"] *= 1.3

        entry = df["close"].iloc[-1]
        atr   = self._get_atr(df)
        is_buy = direction.upper() == "BUY"

        # ATR multiplier scales with confluence score
        atr_mult = params["atr_sl_mult"]
        if atr_mult <= 0:
            atr_mult = 1.5

        if is_buy:
            sl   = entry - atr * atr_mult
            tp1  = entry + atr * params["tp1_mult"]
            tp2  = entry + atr * params["tp2_mult"]
            tp3  = entry + atr * params["tp3_mult"]
            trail_activation = entry + atr * params["trail_mult"]
            invalidation = entry - atr * (atr_mult + 0.5)
        else:
            sl   = entry + atr * atr_mult
            tp1  = entry - atr * params["tp1_mult"]
            tp2  = entry - atr * params["tp2_mult"]
            tp3  = entry - atr * params["tp3_mult"]
            trail_activation = entry - atr * params["trail_mult"]
            invalidation = entry + atr * (atr_mult + 0.5)

        risk_dist   = abs(entry - sl)
        reward_dist = abs(entry - tp2)
        rr_ratio    = reward_dist / risk_dist if risk_dist > 0 else 0

        risk_pct    = risk_dist / entry * 100
        reward_pct  = reward_dist / entry * 100

        # Base position sizing: risk exactly max_risk_pct of equity
        base_position_size = (self.account_equity * self.max_risk_pct / 100) / (risk_pct / 100)
        base_position_size = min(base_position_size, self.account_equity * 0.20)  # max 20% of account
        
        # Apply adaptive sizing based on win rate
        if use_adaptive_sizing:
            position_size_usd = self.get_adaptive_position_size(
                base_position_size=base_position_size,
                min_size_pct=0.005,  # 0.5% of equity
                max_size_pct=0.05,   # 5% of equity
            )
        else:
            position_size_usd = base_position_size

        logger.debug(
            f"{symbol} {direction}: entry={entry:.5g} SL={sl:.5g} "
            f"TP2={tp2:.5g} R:R={rr_ratio:.2f} ATR={atr:.5g} "
            f"Size=${position_size_usd:,.2f}"
        )

        return TradeSetup(
            symbol=symbol, direction=direction,
            entry_price=round(entry, 6),
            stop_loss=round(sl, 6),
            take_profit_1=round(tp1, 6),
            take_profit_2=round(tp2, 6),
            take_profit_3=round(tp3, 6),
            risk_pct=round(risk_pct, 3),
            reward_pct=round(reward_pct, 3),
            rr_ratio=round(rr_ratio, 2),
            atr_value=round(atr, 6),
            position_size_usd=round(position_size_usd, 2),
            trailing_activation=round(trail_activation, 6),
            invalidation=round(invalidation, 6),
        )

    def update_trailing_stop(
        self,
        setup: TradeSetup,
        current_price: float,
        current_sl: float,
        atr: float,
    ) -> Tuple[float, bool]:
        """
        Update trailing stop as trade moves in profit.

        Returns:
            (new_sl, sl_moved) — new stop loss price and whether it moved
        """
        is_buy = setup.direction == "BUY"
        asset  = _asset_class(setup.symbol)
        trail_offset = atr * RR_TARGETS[asset]["atr_sl_mult"]

        if is_buy:
            # Only trail up, never down
            if current_price >= setup.trailing_activation:
                new_sl = max(current_sl, current_price - trail_offset)
                return new_sl, new_sl > current_sl
        else:
            if current_price <= setup.trailing_activation:
                new_sl = min(current_sl, current_price + trail_offset)
                return new_sl, new_sl < current_sl

        return current_sl, False

    def validate_setup(self, setup: TradeSetup) -> Tuple[bool, str]:
        """Final validation of the trade setup before execution."""
        asset = _asset_class(setup.symbol)
        min_rr = RR_TARGETS[asset]["min_rr"]

        if setup.rr_ratio < min_rr:
            return False, f"R:R {setup.rr_ratio:.2f} < minimum {min_rr} for {asset}"
        if setup.risk_pct > self.max_risk_pct * 1.5:
            return False, f"Risk {setup.risk_pct:.2f}% exceeds max {self.max_risk_pct}%"
        if setup.position_size_usd <= 0:
            return False, "Invalid position size"
        return True, "OK"

    @staticmethod
    def _get_atr(df: pd.DataFrame, period: int = 14) -> float:
        """Get current ATR value, compute if not present."""
        if "atr_14" in df.columns:
            atr = df["atr_14"].iloc[-1]
            if atr > 0:
                return atr
        # Compute ATR
        high, low, close = df["high"], df["low"], df["close"]
        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        return tr.rolling(period).mean().iloc[-1]
