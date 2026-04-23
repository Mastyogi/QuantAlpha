"""
Data Normalizer
================
Normalizes OHLCV data across different exchanges and timeframes.

Problems it solves:
  - Different exchanges have different quote currencies (BTC/USD vs BTC/USDT)
  - Timestamps may be in different timezones or precisions
  - Prices may have different decimal representations
  - Volume units differ (BTC volume on Binance vs Coinbase)
  - Some exchanges report volume in quote currency, others in base
  - Gaps in data need interpolation or flagging
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger(__name__)


class DataNormalizer:
    """
    Normalizes OHLCV data to a standard internal format.
    Output: UTC-indexed DataFrame with float64 columns.
    """

    # Standard column names used throughout the bot
    REQUIRED_COLS = ["open", "high", "low", "close", "volume"]

    # Symbol aliases: map exchange-specific symbols to internal standard
    SYMBOL_ALIASES: Dict[str, str] = {
        "BTC/USD":   "BTC/USDT",
        "ETH/USD":   "ETH/USDT",
        "XBT/USD":   "BTC/USDT",   # Kraken convention
        "XBT/USDT":  "BTC/USDT",
        "BTCUSD":    "BTC/USDT",   # No separator
        "ETHUSD":    "ETH/USDT",
        "EURUSD=X":  "EURUSD",     # Yahoo Finance convention
        "XAUUSD=X":  "XAUUSD",
    }

    def __init__(self, fill_gaps: bool = True, max_gap_candles: int = 5):
        """
        Args:
            fill_gaps:       Interpolate small gaps in the data
            max_gap_candles: Max candles to interpolate (larger gaps get flagged)
        """
        self.fill_gaps       = fill_gaps
        self.max_gap_candles = max_gap_candles

    def normalize(
        self,
        df:       pd.DataFrame,
        symbol:   str,
        exchange: str = "unknown",
    ) -> pd.DataFrame:
        """
        Full normalization pipeline.
        Returns UTC-indexed, float64, validated DataFrame.
        """
        df = df.copy()

        # 1. Ensure UTC timezone-aware index
        df = self._normalize_index(df)

        # 2. Normalize column names
        df = self._normalize_columns(df)

        # 3. Cast to float64
        df = self._cast_to_float(df)

        # 4. Remove duplicates
        df = df[~df.index.duplicated(keep="last")]

        # 5. Sort by time
        df = df.sort_index()

        # 6. Fix OHLCV integrity (high >= low, etc.)
        df = self._fix_candle_integrity(df)

        # 7. Fill small gaps
        if self.fill_gaps:
            df, gaps_filled = self._fill_gaps(df, symbol, exchange)
            if gaps_filled > 0:
                logger.debug(f"{symbol}: filled {gaps_filled} candle gaps")

        # 8. Remove zero/negative prices
        df = self._remove_invalid_prices(df)

        # 9. Normalize volume (ensure positive)
        df["volume"] = df["volume"].clip(lower=0)

        logger.debug(f"Normalized {symbol} ({exchange}): {len(df)} candles")
        return df

    def normalize_symbol(self, symbol: str) -> str:
        """Standardize symbol string to internal format."""
        # Remove spaces
        symbol = symbol.replace(" ", "")
        # Check alias map
        if symbol in self.SYMBOL_ALIASES:
            return self.SYMBOL_ALIASES[symbol]
        # Convert BTCUSDT → BTC/USDT (common exchange format without /)
        if len(symbol) >= 6 and "/" not in symbol:
            for quote in ["USDT", "USD", "BTC", "ETH", "BUSD"]:
                if symbol.endswith(quote):
                    base = symbol[: -len(quote)]
                    if len(base) >= 2:
                        return f"{base}/{quote}"
        return symbol.upper()

    def align_timeframes(
        self,
        dfs: Dict[str, pd.DataFrame],
        reference_tf: str = "1h",
    ) -> Dict[str, pd.DataFrame]:
        """
        Align multiple timeframe DataFrames to share the same timestamps.
        Resamples higher TFs to match the reference TF's index.
        """
        if reference_tf not in dfs:
            logger.warning(f"Reference timeframe {reference_tf} not in provided DataFrames")
            return dfs

        ref_index = dfs[reference_tf].index
        aligned   = {reference_tf: dfs[reference_tf]}

        for tf, df in dfs.items():
            if tf == reference_tf:
                continue
            try:
                # Reindex: forward-fill from higher timeframe
                aligned[tf] = df.reindex(ref_index, method="ffill")
            except Exception as e:
                logger.warning(f"Could not align {tf}: {e}")
                aligned[tf] = df

        return aligned

    def compute_returns(
        self,
        df:      pd.DataFrame,
        periods: List[int] = [1, 3, 6, 12, 24],
    ) -> pd.DataFrame:
        """Add multi-period return columns (stationary features)."""
        df = df.copy()
        for p in periods:
            df[f"ret_{p}"]     = df["close"].pct_change(p)
            df[f"log_ret_{p}"] = np.log(df["close"] / df["close"].shift(p))
        return df

    # ── Private helpers ───────────────────────────────────────────────────────

    def _normalize_index(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure index is UTC-aware DatetimeIndex."""
        if not isinstance(df.index, pd.DatetimeIndex):
            # Try converting from various formats
            if "timestamp" in df.columns:
                df = df.set_index("timestamp")
            elif "date" in df.columns:
                df = df.set_index("date")

            try:
                df.index = pd.to_datetime(df.index)
            except Exception as e:
                logger.error(f"Cannot parse timestamp index: {e}")
                return df

        # Convert to UTC
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")

        return df

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Lowercase and rename columns to standard names."""
        df.columns = [c.lower().strip() for c in df.columns]

        # Rename common variations
        renames = {
            "o": "open", "h": "high", "l": "low", "c": "close",
            "v": "volume", "vol": "volume", "qty": "volume",
            "bid": "open", "ask": "close",   # L1 data fallback
        }
        df = df.rename(columns=renames)

        # Ensure all required columns exist
        for col in self.REQUIRED_COLS:
            if col not in df.columns:
                if col == "volume":
                    df["volume"] = 0.0
                    logger.debug("Added missing volume column (set to 0)")
                else:
                    raise ValueError(f"Required column '{col}' missing from DataFrame")

        return df[self.REQUIRED_COLS]

    def _cast_to_float(self, df: pd.DataFrame) -> pd.DataFrame:
        """Cast all OHLCV columns to float64."""
        for col in self.REQUIRED_COLS:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def _fix_candle_integrity(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure OHLCV candle integrity: high >= close/open >= low."""
        # High should be >= all other prices
        df["high"] = df[["high", "open", "close"]].max(axis=1)
        # Low should be <= all other prices
        df["low"]  = df[["low",  "open", "close"]].min(axis=1)
        return df

    def _fill_gaps(
        self, df: pd.DataFrame, symbol: str, exchange: str
    ) -> Tuple[pd.DataFrame, int]:
        """Fill small gaps using forward fill. Flag large gaps."""
        if len(df) < 2:
            return df, 0

        gaps_filled = 0
        # Infer frequency from first few rows
        diffs = df.index.to_series().diff().dropna()
        if len(diffs) == 0:
            return df, 0

        expected_freq = diffs.mode()[0]  # Most common interval

        # Create complete time range
        full_range = pd.date_range(
            start = df.index[0],
            end   = df.index[-1],
            freq  = expected_freq,
            tz    = "UTC",
        )

        if len(full_range) <= len(df):
            return df, 0

        original_len = len(df)
        df = df.reindex(full_range)

        # Only fill short gaps
        gap_sizes = df["close"].isna().astype(int)
        consec_gaps = gap_sizes.groupby((gap_sizes != gap_sizes.shift()).cumsum()).transform("sum")
        large_gaps  = consec_gaps > self.max_gap_candles

        if large_gaps.any():
            n_large = int(large_gaps.sum())
            logger.warning(
                f"{symbol} ({exchange}): {n_large} large gaps detected (>{self.max_gap_candles} candles)"
            )

        # Forward fill small gaps
        df = df.ffill()
        df = df.dropna(subset=["close"])

        gaps_filled = len(df) - original_len
        return df, max(0, gaps_filled)

    def _remove_invalid_prices(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove rows with zero or negative prices."""
        invalid = (df["close"] <= 0) | (df["open"] <= 0) | df["close"].isna()
        n_removed = invalid.sum()
        if n_removed > 0:
            logger.warning(f"Removed {n_removed} rows with invalid prices")
        return df[~invalid]
