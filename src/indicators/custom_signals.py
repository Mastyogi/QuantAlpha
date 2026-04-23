"""
Custom Composite Signals
=========================
Proprietary indicators combining multiple signals into a single score.

Indicators:
  1. Alpha Signal:      Combined momentum + trend + volume score
  2. Smart Money Index: Approximates institutional activity
  3. Liquidity Sweep Detector: Detects stop hunts before reversal
  4. Market Regime Composite: Quantified regime strength
  5. Exhaustion Signal: Detects overextension / trend exhaustion
  6. Confluence Score (fast): Quick-compute version for scanning

These are the "secret sauce" layer on top of standard indicators.
"""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger(__name__)


class CustomSignals:
    """
    Proprietary composite signal indicators.
    All methods are vectorized and operate on DataFrames.
    """

    @staticmethod
    def add_all_custom(df: pd.DataFrame) -> pd.DataFrame:
        """Add all custom composite signals to DataFrame."""
        df = df.copy()
        df = CustomSignals._add_alpha_signal(df)
        df = CustomSignals._add_smart_money_index(df)
        df = CustomSignals._add_exhaustion_signal(df)
        df = CustomSignals._add_liquidity_sweep(df)
        df = CustomSignals._add_composite_score(df)
        return df

    # ── 1. Alpha Signal ───────────────────────────────────────────────────────

    @staticmethod
    def _add_alpha_signal(df: pd.DataFrame) -> pd.DataFrame:
        """
        Alpha Signal: Combined momentum + trend + volume.
        Range: -100 to +100.
        +100 = maximum bullish confluence
        -100 = maximum bearish confluence
        """
        alpha = pd.Series(0.0, index=df.index)

        # Momentum component (RSI-based)
        if "rsi_14" in df.columns:
            rsi_signal = (df["rsi_14"] - 50) / 50 * 40  # ±40 pts from RSI
            alpha += rsi_signal

        # Trend component (EMA alignment)
        if all(c in df.columns for c in ["ema_9", "ema_21", "ema_50"]):
            bull = (df["ema_9"] > df["ema_21"]) & (df["ema_21"] > df["ema_50"])
            bear = (df["ema_9"] < df["ema_21"]) & (df["ema_21"] < df["ema_50"])
            trend_pts = pd.Series(0.0, index=df.index)
            trend_pts[bull] =  35.0
            trend_pts[bear] = -35.0
            alpha += trend_pts

        # Volume confirmation component
        if "volume_ratio" in df.columns:
            vol_signal = (df["volume_ratio"].clip(0, 3) - 1) * 12.5  # ±25 pts at 3x vol
            alpha += vol_signal

        df["alpha_signal"] = alpha.clip(-100, 100)
        return df

    # ── 2. Smart Money Index ──────────────────────────────────────────────────

    @staticmethod
    def _add_smart_money_index(df: pd.DataFrame) -> pd.DataFrame:
        """
        Smart Money Index (SMI) approximation.
        Institutional money tends to trade at open and close of sessions.
        Dumb money trades after news / emotional reactions.

        SMI = (Last 30min activity) - (First 30min activity)
        For hourly data: last candle close action vs first candle reaction.

        Result: Positive = institutions accumulating, Negative = distributing.
        """
        # Approximate with: (close - open range position) trend
        # Strong closes at highs = smart money buying
        hl = (df["high"] - df["low"]).replace(0, np.nan)
        close_pos = (df["close"] - df["low"]) / hl  # 0=close at low, 1=close at high

        # Smooth over 5 periods
        smi = close_pos.rolling(5).mean() * 200 - 100  # scale to ±100
        df["smart_money_index"] = smi.fillna(0).clip(-100, 100)
        return df

    # ── 3. Exhaustion Signal ─────────────────────────────────────────────────

    @staticmethod
    def _add_exhaustion_signal(df: pd.DataFrame) -> pd.DataFrame:
        """
        Trend Exhaustion: Detects when a trend is running out of momentum.
        Combines RSI overbought/oversold + volume declining + ATR shrinking.

        0 = no exhaustion
        1 = mild exhaustion
        2 = strong exhaustion (trend likely to reverse or pause)
        """
        exhaustion = pd.Series(0.0, index=df.index)

        # RSI extremes
        if "rsi_14" in df.columns:
            overbought  = (df["rsi_14"] > 70).astype(float)
            oversold    = (df["rsi_14"] < 30).astype(float)
            rsi_extreme = overbought + oversold
            exhaustion += rsi_extreme

        # Volume declining (last 3 periods vs prior 3)
        vol_recent = df["volume"].rolling(3).mean()
        vol_prior  = df["volume"].rolling(3).mean().shift(3)
        vol_decline = (vol_recent < vol_prior * 0.7).astype(float)
        exhaustion += vol_decline

        # ATR shrinking (momentum losing)
        if "atr_14" in df.columns:
            atr_recent = df["atr_14"]
            atr_prior  = df["atr_14"].shift(5)
            atr_shrink = (atr_recent < atr_prior * 0.7).astype(float)
            exhaustion += atr_shrink

        df["exhaustion"] = exhaustion.clip(0, 3)
        df["exhaustion_warning"] = exhaustion >= 2
        return df

    # ── 4. Liquidity Sweep ───────────────────────────────────────────────────

    @staticmethod
    def _add_liquidity_sweep(df: pd.DataFrame) -> pd.DataFrame:
        """
        Liquidity Sweep (Stop Hunt) Detector.
        Price spikes below recent lows then reverses = stop hunt (bullish).
        Price spikes above recent highs then reverses = stop hunt (bearish).

        These are high-probability reversal setups used by Smart Money.
        """
        lookback = 20

        recent_high = df["high"].rolling(lookback).max().shift(1)
        recent_low  = df["low"].rolling(lookback).min().shift(1)

        # Bullish sweep: low broke below recent_low but close is back above
        bull_sweep = (df["low"] < recent_low) & (df["close"] > recent_low)

        # Bearish sweep: high broke above recent_high but close is back below
        bear_sweep = (df["high"] > recent_high) & (df["close"] < recent_high)

        df["liq_sweep_bullish"] = bull_sweep
        df["liq_sweep_bearish"] = bear_sweep
        df["liq_sweep_signal"]  = pd.Series(0, index=df.index)
        df.loc[bull_sweep, "liq_sweep_signal"] = 1
        df.loc[bear_sweep, "liq_sweep_signal"] = -1

        return df

    # ── 5. Composite Score ────────────────────────────────────────────────────

    @staticmethod
    def _add_composite_score(df: pd.DataFrame) -> pd.DataFrame:
        """
        Master composite score combining all custom signals.
        Range: -100 to +100.
        Used as the final signal strength indicator.
        """
        composite = pd.Series(0.0, index=df.index)
        weights   = 0

        if "alpha_signal" in df.columns:
            composite += df["alpha_signal"] * 0.40
            weights   += 0.40

        if "smart_money_index" in df.columns:
            composite += df["smart_money_index"] * 0.30
            weights   += 0.30

        if "liq_sweep_signal" in df.columns:
            composite += df["liq_sweep_signal"] * 50 * 0.15  # Convert -1/0/1 to score
            weights   += 0.15

        # Exhaustion penalty: subtract from composite when trend exhausted
        if "exhaustion" in df.columns:
            exhaustion_penalty = df["exhaustion"] * 10  # up to -30 penalty
            composite -= exhaustion_penalty
            weights   += 0.15

        if weights > 0:
            composite = composite / weights if weights != 1.0 else composite

        df["custom_composite"] = composite.clip(-100, 100)

        # Direction signal from composite
        df["custom_direction"] = "NEUTRAL"
        df.loc[df["custom_composite"] > 30, "custom_direction"] = "BUY"
        df.loc[df["custom_composite"] < -30, "custom_direction"] = "SELL"

        return df

    @staticmethod
    def get_signal_summary(df: pd.DataFrame, idx: int = -1) -> dict:
        """Get a summary of all custom signals for a specific bar."""
        row = df.iloc[idx]
        return {
            "alpha_signal":      float(row.get("alpha_signal", 0)),
            "smart_money_index": float(row.get("smart_money_index", 0)),
            "exhaustion":        float(row.get("exhaustion", 0)),
            "liq_sweep":         int(row.get("liq_sweep_signal", 0)),
            "composite":         float(row.get("custom_composite", 0)),
            "direction":         str(row.get("custom_direction", "NEUTRAL")),
            "exhaustion_warn":   bool(row.get("exhaustion_warning", False)),
        }
