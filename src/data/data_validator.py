import pandas as pd
import numpy as np
from src.utils.logger import get_logger
from src.core.exceptions import DataValidationError

logger = get_logger(__name__)


class DataValidator:
    """Validates and cleans OHLCV DataFrames."""

    MIN_ROWS = 50
    MAX_PRICE_CHANGE_PCT = 50.0  # Flag if >50% single-candle change

    def validate_and_clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Full validation + cleaning pipeline."""
        df = self._check_required_columns(df)
        df = self._remove_zero_volume(df)
        df = self._fix_hloc_violations(df)
        df = self._remove_outliers(df)
        df = self._fill_gaps(df)

        if len(df) < self.MIN_ROWS:
            raise DataValidationError(
                f"After cleaning, only {len(df)} rows remain (min {self.MIN_ROWS})"
            )
        return df

    def _check_required_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        required = ["open", "high", "low", "close", "volume"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise DataValidationError(f"Missing columns: {missing}")
        return df[required]

    def _remove_zero_volume(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove candles with zero volume (often stale/missing data)."""
        before = len(df)
        df = df[df["volume"] > 0]
        removed = before - len(df)
        if removed > 0:
            logger.debug(f"Removed {removed} zero-volume candles")
        return df

    def _fix_hloc_violations(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fix or remove candles where high < low."""
        violations = df["high"] < df["low"]
        if violations.any():
            logger.warning(f"Fixing {violations.sum()} HLOC violations")
            df = df[~violations]
        # Ensure high >= open,close and low <= open,close
        df["high"] = df[["high", "open", "close"]].max(axis=1)
        df["low"] = df[["low", "open", "close"]].min(axis=1)
        return df

    def _remove_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove candles with extreme price changes."""
        pct_change = df["close"].pct_change().abs() * 100
        outliers = pct_change > self.MAX_PRICE_CHANGE_PCT
        if outliers.any():
            logger.warning(f"Removing {outliers.sum()} price outlier candles")
            df = df[~outliers]
        return df

    def _fill_gaps(self, df: pd.DataFrame) -> pd.DataFrame:
        """Forward-fill small NaN gaps."""
        if df.isnull().any().any():
            df = df.ffill().bfill()
        return df

    def detect_gaps(self, df: pd.DataFrame, timeframe: str) -> int:
        """Count missing candles based on expected frequency."""
        from src.utils.time_utils import timeframe_to_seconds
        expected_freq = pd.Timedelta(seconds=timeframe_to_seconds(timeframe))
        time_diffs = df.index.to_series().diff().dropna()
        gaps = (time_diffs > expected_freq * 1.5).sum()
        return int(gaps)
