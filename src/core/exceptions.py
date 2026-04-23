"""Custom exception hierarchy for the trading bot."""


class TradingBotError(Exception):
    """Base exception for all bot errors."""
    pass


class ExchangeError(TradingBotError):
    """Exchange connectivity or API error."""
    pass


class ExchangeNotAvailableError(ExchangeError):
    """Exchange is temporarily unavailable."""
    pass


class InsufficientFundsError(ExchangeError):
    """Insufficient balance for the requested order."""
    pass


class OrderNotFoundError(ExchangeError):
    """Order ID not found on the exchange."""
    pass


class DataError(TradingBotError):
    """Data fetching or validation error."""
    pass


class DataValidationError(DataError):
    """OHLCV or market data failed quality checks."""
    pass


class InsufficientDataError(DataError):
    """Not enough historical data to compute indicators."""
    pass


class StrategyError(TradingBotError):
    """Strategy signal generation error."""
    pass


class RiskError(TradingBotError):
    """Risk management violation."""
    pass


class CircuitBreakerError(RiskError):
    """Circuit breaker has been triggered."""
    pass


class ModelError(TradingBotError):
    """ML model loading or inference error."""
    pass


class ModelNotTrainedError(ModelError):
    """Model has not been trained yet."""
    pass


class DatabaseError(TradingBotError):
    """Database operation failure."""
    pass


class TelegramError(TradingBotError):
    """Telegram notification failure."""
    pass


class ConfigurationError(TradingBotError):
    """Invalid configuration detected."""
    pass
