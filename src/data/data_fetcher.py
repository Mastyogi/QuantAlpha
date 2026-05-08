import pandas as pd
import numpy as np
from typing import Dict, Optional
from src.data.forex.broker_client import BrokerClient
from src.data.data_validator import DataValidator
from src.core.exceptions import DataError, InsufficientDataError
from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


class DataFetcher:
    """
    Fetches and caches OHLCV data from the exchange.
    Converts raw broker output into validated pandas DataFrames.
    """

    def __init__(self, broker_client: BrokerClient):
        self.exchange = broker_client
        self.validator = DataValidator()
        self._cache: Dict[str, pd.DataFrame] = {}

    async def get_dataframe(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
        use_cache: bool = False,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data and return as a validated DataFrame.
        Columns: open, high, low, close, volume — indexed by datetime.
        """
        cache_key = f"{symbol}_{timeframe}"

        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        raw = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

        if not raw or len(raw) < 50:
            raise InsufficientDataError(
                f"Insufficient data for {symbol} {timeframe}: got {len(raw) if raw else 0} candles"
            )

        df = self._raw_to_dataframe(raw)
        df = self.validator.validate_and_clean(df)

        if use_cache:
            self._cache[cache_key] = df

        logger.debug(f"Fetched {len(df)} candles for {symbol} {timeframe}")
        return df

    def _raw_to_dataframe(self, raw: list) -> pd.DataFrame:
        """Convert raw OHLCV list to DataFrame."""
        df = pd.DataFrame(
            raw, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.set_index("timestamp")
        df = df.astype(float)
        df = df.sort_index()
        # Remove duplicate timestamps
        df = df[~df.index.duplicated(keep="last")]
        return df

    async def get_multi_timeframe(
        self, symbol: str, timeframes: list, limit: int = 200
    ) -> Dict[str, pd.DataFrame]:
        """Fetch data for multiple timeframes concurrently."""
        import asyncio
        tasks = {tf: self.get_dataframe(symbol, tf, limit) for tf in timeframes}
        results = {}
        for tf, task in tasks.items():
            try:
                results[tf] = await task
            except Exception as e:
                logger.error(f"Failed to fetch {symbol} {tf}: {e}")
        return results

    def clear_cache(self):
        """Clear all cached data."""
        self._cache.clear()
