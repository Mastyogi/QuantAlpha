"""
Market Structure Analysis
==========================
Smart Money Concepts (SMC) market structure detection.

Detects:
  - Break of Structure (BOS): Continuation signal
  - Change of Character (CHoCH): Reversal warning
  - Higher Highs (HH), Higher Lows (HL) → Uptrend confirmed
  - Lower Highs (LH), Lower Lows (LL)   → Downtrend confirmed
  - Swing Highs and Swing Lows (key levels)
  - Fair Value Gaps (FVG) — imbalance zones
  - Order Blocks — institutional buy/sell zones

This is the foundation of Smart Money Concepts trading.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SwingPoint:
    index:      int
    price:      float
    timestamp:  object
    swing_type: str     # "high" or "low"


@dataclass
class FairValueGap:
    """3-candle imbalance zone."""
    gap_high:  float
    gap_low:   float
    direction: str       # "bullish" or "bearish"
    candle_idx: int
    filled:    bool = False

    @property
    def midpoint(self) -> float:
        return (self.gap_high + self.gap_low) / 2

    @property
    def size_pct(self) -> float:
        return (self.gap_high - self.gap_low) / self.gap_low * 100


@dataclass
class OrderBlock:
    """Institutional order block zone."""
    zone_high:  float
    zone_low:   float
    direction:  str     # "bullish" (demand) or "bearish" (supply)
    candle_idx: int
    tested:     bool = False

    @property
    def midpoint(self) -> float:
        return (self.zone_high + self.zone_low) / 2


@dataclass
class MarketStructureResult:
    """Full market structure analysis."""
    trend:           str     # "uptrend" / "downtrend" / "ranging"
    bos_detected:    bool    # Break of Structure (continuation)
    choch_detected:  bool    # Change of Character (reversal)
    bos_direction:   str     # Direction of last BOS
    choch_direction: str     # Direction of CHoCH (new trend)

    # Swing points
    last_swing_high: Optional[SwingPoint]
    last_swing_low:  Optional[SwingPoint]
    swing_highs:     List[SwingPoint] = field(default_factory=list)
    swing_lows:      List[SwingPoint] = field(default_factory=list)

    # SMC levels
    fvgs:            List[FairValueGap]  = field(default_factory=list)
    order_blocks:    List[OrderBlock]    = field(default_factory=list)

    # Structure score (0–100)
    structure_score: float = 0.0
    trend_strength:  float = 0.0   # 0 = ranging, 1 = strong trend

    @property
    def is_trending(self) -> bool:
        return self.trend in ("uptrend", "downtrend")

    @property
    def near_fvg(self) -> Optional[FairValueGap]:
        """Returns nearest unfilled FVG if price is approaching it."""
        if not self.fvgs:
            return None
        unfilled = [f for f in self.fvgs if not f.filled]
        return unfilled[-1] if unfilled else None

    @property
    def nearest_ob(self) -> Optional[OrderBlock]:
        """Most recent untested order block."""
        untested = [o for o in self.order_blocks if not o.tested]
        return untested[-1] if untested else None


class MarketStructureAnalyzer:
    """
    Analyzes market structure using swing-point based logic.
    Detects BOS, CHoCH, FVGs, and Order Blocks.
    """

    def __init__(self, swing_lookback: int = 5):
        """
        Args:
            swing_lookback: Number of bars on each side to confirm a swing
        """
        self.swing_lookback = swing_lookback

    def analyze(self, df: pd.DataFrame) -> MarketStructureResult:
        """
        Full market structure analysis on OHLCV DataFrame.
        Requires at least 50 bars.
        """
        if len(df) < 20:
            return self._empty_result()

        df = df.copy().reset_index(drop=True)

        # 1. Find swing highs and lows
        swing_highs = self._find_swings(df, "high")
        swing_lows  = self._find_swings(df, "low")

        # 2. Determine trend from swing sequence
        trend, trend_strength = self._determine_trend(swing_highs, swing_lows)

        # 3. Detect BOS and CHoCH
        bos, bos_dir   = self._detect_bos(df, swing_highs, swing_lows, trend)
        choch, choch_dir = self._detect_choch(df, swing_highs, swing_lows, trend)

        # 4. Find Fair Value Gaps
        fvgs = self._find_fvgs(df)

        # 5. Find Order Blocks
        obs = self._find_order_blocks(df, swing_highs, swing_lows)

        # 6. Structure score
        score = self._score_structure(trend, bos, choch, trend_strength, fvgs)

        last_sh = swing_highs[-1] if swing_highs else None
        last_sl = swing_lows[-1]  if swing_lows  else None

        return MarketStructureResult(
            trend           = trend,
            bos_detected    = bos,
            choch_detected  = choch,
            bos_direction   = bos_dir,
            choch_direction = choch_dir,
            last_swing_high = last_sh,
            last_swing_low  = last_sl,
            swing_highs     = swing_highs[-10:],  # last 10
            swing_lows      = swing_lows[-10:],
            fvgs            = fvgs[-5:],           # last 5
            order_blocks    = obs[-3:],            # last 3
            structure_score = score,
            trend_strength  = trend_strength,
        )

    def add_to_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add market structure signals as columns."""
        result = self.analyze(df)
        df = df.copy()
        df["ms_trend"]    = result.trend
        df["ms_bos"]      = result.bos_detected
        df["ms_choch"]    = result.choch_detected
        df["ms_score"]    = result.structure_score
        df["ms_strength"] = result.trend_strength
        if result.last_swing_high:
            df["ms_last_sh"] = result.last_swing_high.price
        if result.last_swing_low:
            df["ms_last_sl"] = result.last_swing_low.price
        return df

    # ── Private ───────────────────────────────────────────────────────────────

    def _find_swings(self, df: pd.DataFrame, col: str) -> List[SwingPoint]:
        """Find swing highs or lows using local extrema."""
        lb    = self.swing_lookback
        swing_type = "high" if col == "high" else "low"
        points: List[SwingPoint] = []

        series = df[col].values
        for i in range(lb, len(series) - lb):
            window = series[i - lb: i + lb + 1]
            center = series[i]

            if swing_type == "high" and center == window.max() and center > series[i - 1] and center > series[i + 1]:
                ts = df.index[i] if hasattr(df.index, '__iter__') else i
                points.append(SwingPoint(index=i, price=float(center), timestamp=ts, swing_type="high"))
            elif swing_type == "low" and center == window.min() and center < series[i - 1] and center < series[i + 1]:
                ts = df.index[i] if hasattr(df.index, '__iter__') else i
                points.append(SwingPoint(index=i, price=float(center), timestamp=ts, swing_type="low"))

        return points

    def _determine_trend(
        self,
        swing_highs: List[SwingPoint],
        swing_lows:  List[SwingPoint],
    ) -> Tuple[str, float]:
        """Determine trend from last 3 swing highs and lows."""
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return "ranging", 0.0

        recent_sh = swing_highs[-3:]
        recent_sl = swing_lows[-3:]

        # Higher highs + higher lows = uptrend
        hh = all(recent_sh[i].price > recent_sh[i-1].price for i in range(1, len(recent_sh)))
        hl = all(recent_sl[i].price > recent_sl[i-1].price for i in range(1, len(recent_sl)))
        ll = all(recent_sl[i].price < recent_sl[i-1].price for i in range(1, len(recent_sl)))
        lh = all(recent_sh[i].price < recent_sh[i-1].price for i in range(1, len(recent_sh)))

        if hh and hl:
            strength = min(1.0, (sum(
                (recent_sh[i].price - recent_sh[i-1].price) / recent_sh[i-1].price
                for i in range(1, len(recent_sh))
            ) * 10))
            return "uptrend", max(0.0, strength)

        if ll and lh:
            strength = min(1.0, (sum(
                (recent_sl[i-1].price - recent_sl[i].price) / recent_sl[i-1].price
                for i in range(1, len(recent_sl))
            ) * 10))
            return "downtrend", max(0.0, strength)

        return "ranging", 0.0

    def _detect_bos(
        self,
        df: pd.DataFrame,
        swing_highs: List[SwingPoint],
        swing_lows:  List[SwingPoint],
        trend: str,
    ) -> Tuple[bool, str]:
        """BOS = price breaks above last swing high (uptrend) or below last swing low (downtrend)."""
        if not swing_highs or not swing_lows:
            return False, "NEUTRAL"

        current = float(df["close"].iloc[-1])

        if trend == "uptrend":
            last_sh = swing_highs[-1].price
            if current > last_sh:
                return True, "BUY"
        elif trend == "downtrend":
            last_sl = swing_lows[-1].price
            if current < last_sl:
                return True, "SELL"

        return False, "NEUTRAL"

    def _detect_choch(
        self,
        df: pd.DataFrame,
        swing_highs: List[SwingPoint],
        swing_lows:  List[SwingPoint],
        trend: str,
    ) -> Tuple[bool, str]:
        """CHoCH = price breaks key level IN OPPOSITE direction to trend."""
        if not swing_highs or not swing_lows:
            return False, "NEUTRAL"

        current = float(df["close"].iloc[-1])

        if trend == "uptrend":
            last_sl = swing_lows[-1].price
            if current < last_sl:
                return True, "SELL"
        elif trend == "downtrend":
            last_sh = swing_highs[-1].price
            if current > last_sh:
                return True, "BUY"

        return False, "NEUTRAL"

    def _find_fvgs(self, df: pd.DataFrame) -> List[FairValueGap]:
        """Find Fair Value Gaps (3-candle imbalance zones)."""
        fvgs: List[FairValueGap] = []
        if len(df) < 3:
            return fvgs

        for i in range(1, len(df) - 1):
            prev  = df.iloc[i - 1]
            curr  = df.iloc[i]
            nxt   = df.iloc[i + 1]

            # Bullish FVG: prev high < next low (gap up)
            if prev["high"] < nxt["low"]:
                fvgs.append(FairValueGap(
                    gap_high   = float(nxt["low"]),
                    gap_low    = float(prev["high"]),
                    direction  = "bullish",
                    candle_idx = i,
                ))

            # Bearish FVG: prev low > next high (gap down)
            elif prev["low"] > nxt["high"]:
                fvgs.append(FairValueGap(
                    gap_high   = float(prev["low"]),
                    gap_low    = float(nxt["high"]),
                    direction  = "bearish",
                    candle_idx = i,
                ))

        return fvgs

    def _find_order_blocks(
        self,
        df:          pd.DataFrame,
        swing_highs: List[SwingPoint],
        swing_lows:  List[SwingPoint],
    ) -> List[OrderBlock]:
        """Find order blocks — last opposing candle before a strong move."""
        obs: List[OrderBlock] = []
        if len(df) < 5:
            return obs

        # Bullish OB: last bearish candle before strong upward BOS
        for sh in swing_highs[-3:]:
            idx = sh.index
            if idx < 2:
                continue
            # Find last bearish candle before this swing high
            for j in range(idx - 1, max(0, idx - 5), -1):
                c = df.iloc[j]
                if c["close"] < c["open"]:  # bearish candle
                    obs.append(OrderBlock(
                        zone_high  = float(c["open"]),
                        zone_low   = float(c["close"]),
                        direction  = "bullish",
                        candle_idx = j,
                    ))
                    break

        # Bearish OB: last bullish candle before strong downward BOS
        for sl in swing_lows[-3:]:
            idx = sl.index
            if idx < 2:
                continue
            for j in range(idx - 1, max(0, idx - 5), -1):
                c = df.iloc[j]
                if c["close"] > c["open"]:  # bullish candle
                    obs.append(OrderBlock(
                        zone_high  = float(c["close"]),
                        zone_low   = float(c["open"]),
                        direction  = "bearish",
                        candle_idx = j,
                    ))
                    break

        return obs

    def _score_structure(
        self,
        trend:    str,
        bos:      bool,
        choch:    bool,
        strength: float,
        fvgs:     List[FairValueGap],
    ) -> float:
        """Score market structure quality 0–100."""
        score = 0.0
        if trend != "ranging":       score += 30
        if bos:                      score += 25
        if not choch:                score += 15   # No choch = clean structure
        score += strength * 20                     # Trend strength 0–20
        if fvgs:                     score += min(10, len(fvgs) * 2)
        return min(100, score)

    def _empty_result(self) -> MarketStructureResult:
        return MarketStructureResult(
            trend="ranging", bos_detected=False, choch_detected=False,
            bos_direction="NEUTRAL", choch_direction="NEUTRAL",
            last_swing_high=None, last_swing_low=None,
            structure_score=0.0, trend_strength=0.0,
        )
