from datetime import datetime, timezone, timedelta
from typing import Optional


def utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


def timeframe_to_seconds(timeframe: str) -> int:
    """Convert timeframe string to seconds."""
    mapping = {
        "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
        "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "8h": 28800,
        "12h": 43200, "1d": 86400, "3d": 259200, "1w": 604800,
    }
    return mapping.get(timeframe, 3600)


def ms_to_datetime(ms: int) -> datetime:
    """Convert millisecond timestamp to UTC datetime."""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def datetime_to_ms(dt: datetime) -> int:
    """Convert datetime to millisecond timestamp."""
    return int(dt.timestamp() * 1000)


def format_duration(seconds: float) -> str:
    """Format duration in human-readable form."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}m"
    elif seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    else:
        return f"{seconds / 86400:.1f}d"


def get_candle_open_time(timeframe: str, dt: Optional[datetime] = None) -> datetime:
    """Get the open time of the current candle for a given timeframe."""
    if dt is None:
        dt = utcnow()
    seconds = timeframe_to_seconds(timeframe)
    ts = int(dt.timestamp())
    candle_ts = (ts // seconds) * seconds
    return datetime.fromtimestamp(candle_ts, tz=timezone.utc)
