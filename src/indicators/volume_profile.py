"""
Volume Profile Indicators
==========================
Volume Point of Control (POC), Value Area High (VAH), Value Area Low (VAL).
Volume Profile Visible Range (VPVR).

These are institutional-grade levels that act as major S/R zones.
Price tends to gravitate toward POC and rotate between VAH/VAL.

Usage:
  vp = VolumeProfile(n_bins=50)
  result = vp.calculate(df)
  print(result.poc, result.vah, result.val)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class VolumeProfileResult:
    poc:          float           # Point of Control — most traded price
    vah:          float           # Value Area High — 70% of volume above
    val:          float           # Value Area Low  — 70% of volume below
    value_area:   float           # VAH - VAL range
    poc_strength: float           # Volume at POC as % of total
    above_poc:    bool            # Is current price above POC?
    near_poc:     bool            # Within 0.5% of POC?
    near_vah:     bool            # Within 0.3% of VAH?
    near_val:     bool            # Within 0.3% of VAL?
    profile:      Dict[float, float] = field(default_factory=dict)  # price → volume

    @property
    def bias(self) -> str:
        """Directional bias based on price vs value area."""
        if self.above_poc:
            return "BULLISH"
        return "BEARISH"

    def nearest_level(self, price: float) -> Tuple[str, float]:
        """Return the name and distance % to nearest VP level."""
        levels = {"POC": self.poc, "VAH": self.vah, "VAL": self.val}
        nearest = min(levels.items(), key=lambda x: abs(x[1] - price))
        dist_pct = abs(nearest[1] - price) / price * 100
        return nearest[0], dist_pct


class VolumeProfile:
    """
    Calculates VPVR (Volume Profile Visible Range) from OHLCV data.
    Uses 50 bins by default — matches TradingView resolution.
    Value Area = 70% of total volume (industry standard).
    """

    VALUE_AREA_PCT = 0.70   # 70% of volume defines value area

    def __init__(self, n_bins: int = 50, lookback: int = 200):
        self.n_bins   = n_bins
        self.lookback = lookback

    def calculate(self, df: pd.DataFrame) -> VolumeProfileResult:
        """
        Calculate volume profile from recent OHLCV data.

        Args:
            df: DataFrame with open/high/low/close/volume columns
        Returns:
            VolumeProfileResult with POC, VAH, VAL
        """
        df = df.tail(self.lookback).copy()
        if len(df) < 10:
            logger.warning("Insufficient data for volume profile")
            mid = float(df["close"].iloc[-1]) if len(df) > 0 else 0.0
            return self._empty_result(mid)

        low  = float(df["low"].min())
        high = float(df["high"].max())

        if high <= low:
            mid = (high + low) / 2
            return self._empty_result(mid)

        # Create price bins
        bin_edges  = np.linspace(low, high, self.n_bins + 1)
        bin_prices = (bin_edges[:-1] + bin_edges[1:]) / 2  # bin midpoints
        bin_vol    = np.zeros(self.n_bins)

        # Distribute volume across the candle's price range
        for _, row in df.iterrows():
            candle_vol  = row["volume"]
            candle_low  = row["low"]
            candle_high = row["high"]

            # Find bins that overlap with this candle
            overlap_mask = (bin_edges[1:] >= candle_low) & (bin_edges[:-1] <= candle_high)
            n_overlap = overlap_mask.sum()

            if n_overlap > 0:
                vol_per_bin = candle_vol / n_overlap
                bin_vol[overlap_mask] += vol_per_bin

        # POC = bin with most volume
        poc_idx    = int(np.argmax(bin_vol))
        poc_price  = float(bin_prices[poc_idx])
        total_vol  = float(bin_vol.sum())
        poc_strength = float(bin_vol[poc_idx] / total_vol) if total_vol > 0 else 0.0

        # Value Area: expand from POC until we cover 70% of volume
        vah_idx, val_idx = self._calculate_value_area(bin_vol, poc_idx)
        vah = float(bin_prices[vah_idx])
        val = float(bin_prices[val_idx])

        current = float(df["close"].iloc[-1])

        return VolumeProfileResult(
            poc          = poc_price,
            vah          = vah,
            val          = val,
            value_area   = vah - val,
            poc_strength = poc_strength,
            above_poc    = current > poc_price,
            near_poc     = abs(current - poc_price) / poc_price < 0.005,
            near_vah     = abs(current - vah) / vah < 0.003,
            near_val     = abs(current - val) / val < 0.003,
            profile      = {float(bin_prices[i]): float(bin_vol[i]) for i in range(self.n_bins)},
        )

    def add_to_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add volume profile levels as columns to a DataFrame."""
        df = df.copy()
        result = self.calculate(df)
        df["vp_poc"]      = result.poc
        df["vp_vah"]      = result.vah
        df["vp_val"]      = result.val
        df["vp_above_poc"] = df["close"] > result.poc
        df["vp_dist_poc"] = (df["close"] - result.poc).abs() / result.poc
        return df

    def rolling_poc(self, df: pd.DataFrame, window: int = 50) -> pd.Series:
        """Compute rolling POC — tracks changing value areas over time."""
        pocs = []
        for i in range(len(df)):
            if i < window:
                pocs.append(np.nan)
                continue
            window_df = df.iloc[i - window:i]
            try:
                res = self.calculate(window_df)
                pocs.append(res.poc)
            except Exception:
                pocs.append(np.nan)
        return pd.Series(pocs, index=df.index, name="rolling_poc")

    # ── Private ───────────────────────────────────────────────────────────────

    def _calculate_value_area(
        self, bin_vol: np.ndarray, poc_idx: int
    ) -> Tuple[int, int]:
        """Expand outward from POC until 70% of volume is captured."""
        target  = bin_vol.sum() * self.VALUE_AREA_PCT
        covered = bin_vol[poc_idx]
        hi_idx  = poc_idx
        lo_idx  = poc_idx

        while covered < target:
            # Determine which side to expand
            can_go_up   = hi_idx < len(bin_vol) - 1
            can_go_down = lo_idx > 0

            if not can_go_up and not can_go_down:
                break

            vol_above = bin_vol[hi_idx + 1] if can_go_up   else 0
            vol_below = bin_vol[lo_idx - 1] if can_go_down else 0

            if vol_above >= vol_below and can_go_up:
                hi_idx  += 1
                covered += bin_vol[hi_idx]
            elif can_go_down:
                lo_idx  -= 1
                covered += bin_vol[lo_idx]
            else:
                break

        return hi_idx, lo_idx

    def _empty_result(self, price: float) -> VolumeProfileResult:
        return VolumeProfileResult(
            poc=price, vah=price, val=price,
            value_area=0.0, poc_strength=0.0,
            above_poc=False, near_poc=False,
            near_vah=False, near_val=False,
        )
