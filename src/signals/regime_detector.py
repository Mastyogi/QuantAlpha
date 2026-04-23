"""
Market Regime Detector
========================
Identifies the CURRENT market regime before any signal fires.
Trading in the WRONG regime is the #1 cause of false signals.

4 Regimes:
  TRENDING   → Strong directional move, ADX high — BEST for trend following
  BREAKOUT   → Squeeze releasing, momentum building — BEST entry timing
  RANGING    → Sideways, ADX low — only mean-reversion works
  VOLATILE   → High ATR, news-driven — AVOID (random)
  DEAD       → No volume, no movement — AVOID

Regime Detection Methods:
  1. ADX strength + slope
  2. Bollinger Band width (squeeze detection)
  3. ATR percentile (volatility regime)
  4. Price efficiency ratio (trending vs choppy)
  5. Volume regime (institutional participation)
  6. Hurst exponent (mean-reverting vs trending)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
import redis.asyncio as redis

from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


class Regime:
    TRENDING  = "TRENDING"
    BREAKOUT  = "BREAKOUT"
    RANGING   = "RANGING"
    VOLATILE  = "VOLATILE"
    DEAD      = "DEAD"


# Which strategies work in which regime
REGIME_STRATEGY_MAP = {
    Regime.TRENDING:  ["trend_following", "momentum"],
    Regime.BREAKOUT:  ["trend_following", "breakout"],
    Regime.RANGING:   ["mean_reversion"],
    Regime.VOLATILE:  [],        # Avoid — unpredictable
    Regime.DEAD:      [],        # Avoid — no edge
}

# Signal precision multiplier per regime (empirical)
REGIME_PRECISION_BOOST = {
    Regime.TRENDING:  1.15,   # +15% precision boost
    Regime.BREAKOUT:  1.10,
    Regime.RANGING:   0.95,
    Regime.VOLATILE:  0.70,   # -30% — avoid
    Regime.DEAD:      0.50,
}


@dataclass
class RegimeResult:
    regime:           str
    confidence:       float       # 0–1 how sure we are
    adx:              float
    atr_percentile:   float       # 0–1, high = volatile
    bb_squeeze:       bool
    efficiency_ratio: float       # 0–1, high = trending
    hurst:            float       # >0.5 = trending
    volume_regime:    str         # "high" / "normal" / "low"
    strategy_allowed: bool        # Can we trade now?
    precision_mult:   float       # Expected precision multiplier
    reason:           str

    @property
    def trade_allowed(self) -> bool:
        return self.regime in (Regime.TRENDING, Regime.BREAKOUT)

    @property
    def grade(self) -> str:
        if self.regime == Regime.TRENDING:  return "🟢 TRENDING"
        if self.regime == Regime.BREAKOUT:  return "🔵 BREAKOUT"
        if self.regime == Regime.RANGING:   return "🟡 RANGING"
        if self.regime == Regime.VOLATILE:  return "🔴 VOLATILE"
        return                                     "⚫ DEAD"


class MarketRegimeDetector:
    """
    Detects current market regime from OHLCV data.
    Call before scoring signals — regime mismatch = skip trade.
    """

    def __init__(
        self,
        adx_trending_min: float = 25.0,    # ADX above this = trending
        adx_ranging_max:  float = 20.0,    # ADX below this = ranging
        atr_vol_pct:      float = 0.03,    # ATR > 3% = volatile
        atr_dead_pct:     float = 0.005,   # ATR < 0.5% = dead
        bb_squeeze_pct:   float = 0.015,   # BB width < 1.5% = squeeze
    ):
        self.adx_trending_min = adx_trending_min
        self.adx_ranging_max  = adx_ranging_max
        self.atr_vol_pct      = atr_vol_pct
        self.atr_dead_pct     = atr_dead_pct
        self.bb_squeeze_pct   = bb_squeeze_pct
        
        # Redis connection for caching
        self._redis_client: Optional[redis.Redis] = None
        self._cache_ttl = 900  # 15 minutes
    
    async def _get_redis(self) -> Optional[redis.Redis]:
        """Get or create Redis connection."""
        if self._redis_client is None:
            try:
                self._redis_client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True
                )
                await self._redis_client.ping()
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}")
                return None
        return self._redis_client
    
    async def detect_regime(self, df: pd.DataFrame, symbol: str = "UNKNOWN") -> str:
        """
        Public method to detect regime with Redis caching.
        
        Args:
            df: OHLCV DataFrame
            symbol: Trading symbol for cache key
        
        Returns:
            Regime string (TRENDING, RANGING, VOLATILE, DEAD, BREAKOUT)
        """
        # Try to get from cache
        redis_client = await self._get_redis()
        if redis_client:
            try:
                cache_key = f"regime:{symbol}"
                cached_regime = await redis_client.get(cache_key)
                if cached_regime:
                    logger.debug(f"Regime cache hit for {symbol}: {cached_regime}")
                    return cached_regime
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")
        
        # Detect regime
        result = self.detect(df)
        regime = result.regime
        
        # Cache result
        if redis_client:
            try:
                cache_key = f"regime:{symbol}"
                await redis_client.setex(cache_key, self._cache_ttl, regime)
                logger.debug(f"Cached regime for {symbol}: {regime} (TTL: {self._cache_ttl}s)")
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")
        
        # Log regime changes
        await self._log_regime_change(symbol, regime, redis_client)
        
        return regime
    
    async def _log_regime_change(
        self,
        symbol: str,
        new_regime: str,
        redis_client: Optional[redis.Redis]
    ):
        """Log regime changes at INFO level."""
        if not redis_client:
            return
        
        try:
            last_regime_key = f"regime:last:{symbol}"
            last_regime = await redis_client.get(last_regime_key)
            
            if last_regime and last_regime != new_regime:
                logger.info(
                    f"🔄 Regime change detected: {symbol} "
                    f"{last_regime} → {new_regime} "
                    f"at {pd.Timestamp.now(tz='UTC')}"
                )
            
            # Update last regime
            await redis_client.setex(last_regime_key, self._cache_ttl, new_regime)
        except Exception as e:
            logger.warning(f"Failed to log regime change: {e}")

    def detect(self, df: pd.DataFrame, lookback: int = 50) -> RegimeResult:
        """
        Detect regime from last N bars of OHLCV data.
        df must have: open, high, low, close, volume columns.
        """
        if len(df) < 30:
            return self._unknown(df)

        close  = df["close"]
        high   = df["high"]
        low    = df["low"]
        volume = df["volume"]

        # ── 1. ADX (trend strength) ───────────────────────────────────────────
        adx = self._adx(df, 14)
        adx_slope = adx - self._adx(df.iloc[:-5], 14) if len(df) > 20 else 0

        # ── 2. ATR percentile (volatility regime) ────────────────────────────
        atr      = self._atr(df, 14)
        atr_pct  = atr / close.iloc[-1]
        atr_hist = self._atr_series(df, 14)
        atr_q80  = atr_hist.quantile(0.80) if len(atr_hist.dropna()) > 5 else atr
        atr_q20  = atr_hist.quantile(0.20) if len(atr_hist.dropna()) > 5 else atr
        atr_percentile = (atr - atr_q20) / (atr_q80 - atr_q20 + 1e-8)
        atr_percentile = float(np.clip(atr_percentile, 0, 1))

        # ── 3. Bollinger Band squeeze ─────────────────────────────────────────
        bb_width_now  = self._bb_width(close, 20)
        bb_width_hist = pd.Series([self._bb_width(close.iloc[:i], 20) for i in range(25, len(close), 5)])
        bb_q20        = bb_width_hist.quantile(0.20) if len(bb_width_hist) > 3 else bb_width_now
        # BB squeeze: width < 1.5%
        bb_squeeze    = bb_width_now < self.bb_squeeze_pct

        # ── 4. Price efficiency ratio (trending vs choppy) ────────────────────
        n_eff    = min(lookback, len(close) - 1)
        net_move = abs(float(close.iloc[-1]) - float(close.iloc[-n_eff]))
        total_path = float(close.diff().abs().iloc[-n_eff:].sum()) + 1e-8
        er = net_move / total_path   # 1.0 = perfectly trending, ~0 = choppy

        # ── 5. Volume regime ──────────────────────────────────────────────────
        vol_avg_20 = float(volume.rolling(20).mean().iloc[-1])
        vol_avg_5  = float(volume.rolling(5).mean().iloc[-1])
        vol_ratio  = vol_avg_5 / (vol_avg_20 + 1)
        if vol_ratio >= 1.5:     vol_regime = "high"
        elif vol_ratio >= 0.7:   vol_regime = "normal"
        else:                    vol_regime = "low"

        # ── 6. Hurst exponent ─────────────────────────────────────────────────
        hurst = self._hurst(close.iloc[-min(40, len(close)):].values)

        # ── Classify regime ───────────────────────────────────────────────────
        regime, confidence, reason = self._classify(
            adx=adx, adx_slope=adx_slope,
            atr_pct=atr_pct, atr_percentile=atr_percentile,
            bb_squeeze=bb_squeeze, er=er,
            hurst=hurst, vol_regime=vol_regime,
        )

        return RegimeResult(
            regime=regime,
            confidence=round(confidence, 3),
            adx=round(adx, 1),
            atr_percentile=round(atr_percentile, 3),
            bb_squeeze=bb_squeeze,
            efficiency_ratio=round(er, 3),
            hurst=round(hurst, 3),
            volume_regime=vol_regime,
            strategy_allowed=regime in (Regime.TRENDING, Regime.BREAKOUT),
            precision_mult=REGIME_PRECISION_BOOST.get(regime, 1.0),
            reason=reason,
        )

    def _classify(
        self, adx, adx_slope, atr_pct, atr_percentile,
        bb_squeeze, er, hurst, vol_regime
    ) -> Tuple[str, float, str]:
        """
        Classify regime with priority order:
        VOLATILE > DEAD > TRENDING > BREAKOUT > RANGING
        """
        
        # Priority 1: VOLATILE — ATR > 3% OR sudden ATR spike > 2× avg
        if atr_pct > self.atr_vol_pct:
            return Regime.VOLATILE, 0.90, f"High ATR={atr_pct:.2%} > {self.atr_vol_pct:.2%}"
        
        if atr_percentile > 0.90:  # ATR spike > 2× average
            return Regime.VOLATILE, 0.85, f"ATR spike (percentile={atr_percentile:.2f})"
        
        # Priority 2: DEAD — Volume < 50% of 20-period avg AND ATR < 0.5%
        if vol_regime == "low" and atr_pct < self.atr_dead_pct:
            return Regime.DEAD, 0.90, f"Volume low + ATR={atr_pct:.3%} < {self.atr_dead_pct:.3%}"
        
        # Priority 3: TRENDING — ADX > 25 AND slope > 0 (rising)
        if adx > self.adx_trending_min and adx_slope > 0:
            conf = min(0.95, 0.70 + (adx - self.adx_trending_min) * 0.01 + adx_slope * 0.02)
            return Regime.TRENDING, conf, f"ADX={adx:.1f} > {self.adx_trending_min} + rising slope={adx_slope:+.1f}"
        
        # Priority 4: BREAKOUT — BB width < 1.5% AND ADX rising from below 20
        if bb_squeeze and adx < 20 and adx_slope > 1.0:
            conf = min(0.90, 0.65 + adx_slope * 0.05 + er * 0.20)
            return Regime.BREAKOUT, conf, f"BB squeeze + ADX rising from {adx:.1f} (slope={adx_slope:+.1f})"
        
        # Priority 5: RANGING — ADX < 20 AND BB width between 1.5%–3%
        if adx < self.adx_ranging_max and er < 0.35:
            conf = min(0.90, 0.65 + (self.adx_ranging_max - adx) * 0.02)
            return Regime.RANGING, conf, f"ADX={adx:.1f} < {self.adx_ranging_max} + low ER={er:.2f}"
        
        # Fallback: weak trending if ADX between 20-25
        if adx > self.adx_ranging_max and adx <= self.adx_trending_min:
            conf = 0.60 + (adx - self.adx_ranging_max) * 0.02
            return Regime.TRENDING, min(0.75, conf), f"Weak trend ADX={adx:.1f}"
        
        # Default: RANGING
        return Regime.RANGING, 0.55, f"Mixed: ADX={adx:.1f} ER={er:.2f}"

    # ── Technical helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _adx(df: pd.DataFrame, period: int = 14) -> float:
        try:
            high, low, close = df["high"], df["low"], df["close"]
            plus_dm  = high.diff().clip(lower=0)
            minus_dm = (-low.diff()).clip(lower=0)
            plus_dm  = plus_dm.where(plus_dm > minus_dm, 0)
            minus_dm = minus_dm.where(minus_dm > plus_dm, 0)
            prev_c   = close.shift(1)
            tr = pd.concat([high-low, (high-prev_c).abs(), (low-prev_c).abs()], axis=1).max(axis=1)
            atr14   = tr.rolling(period).mean()
            pdi     = 100 * plus_dm.rolling(period).mean() / (atr14 + 1e-8)
            mdi     = 100 * minus_dm.rolling(period).mean() / (atr14 + 1e-8)
            dx      = 100 * (pdi - mdi).abs() / (pdi + mdi + 1e-8)
            return float(dx.rolling(period).mean().iloc[-1])
        except Exception:
            return 20.0

    @staticmethod
    def _atr(df: pd.DataFrame, period: int = 14) -> float:
        try:
            if "atr_14" in df.columns:
                return float(df["atr_14"].iloc[-1])
            high, low, close = df["high"], df["low"], df["close"]
            tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
            return float(tr.rolling(period).mean().iloc[-1])
        except Exception:
            return 0.01

    @staticmethod
    def _atr_series(df: pd.DataFrame, period: int = 14) -> pd.Series:
        try:
            high, low, close = df["high"], df["low"], df["close"]
            tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
            return tr.rolling(period).mean().dropna()
        except Exception:
            return pd.Series([0.01])

    @staticmethod
    def _bb_width(close: pd.Series, period: int = 20) -> float:
        try:
            mid  = close.rolling(period).mean().iloc[-1]
            std  = close.rolling(period).std().iloc[-1]
            return float(4 * std / (mid + 1e-8))
        except Exception:
            return 0.04

    @staticmethod
    def _hurst(prices: np.ndarray) -> float:
        """Fast Hurst exponent. >0.5=trending, <0.5=mean-reverting."""
        try:
            n = len(prices)
            if n < 8:
                return 0.5
            lags  = [2, 4, 8, min(16, n//2)]
            stds  = [np.std(np.diff(prices, lag)) for lag in lags if lag < n]
            if len(stds) < 2:
                return 0.5
            log_lags = np.log([l for l in lags if l < n])
            log_stds = np.log(np.array(stds) + 1e-8)
            h = np.polyfit(log_lags, log_stds, 1)[0]
            return float(np.clip(h, 0, 1))
        except Exception:
            return 0.5

    def _unknown(self, df: pd.DataFrame) -> RegimeResult:
        return RegimeResult(
            regime=Regime.RANGING, confidence=0.4, adx=20.0,
            atr_percentile=0.5, bb_squeeze=False, efficiency_ratio=0.3,
            hurst=0.5, volume_regime="normal", strategy_allowed=False,
            precision_mult=1.0, reason="Insufficient data",
        )
