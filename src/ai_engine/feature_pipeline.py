import pandas as pd
import numpy as np
from src.indicators.technical import TechnicalIndicators
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FeaturePipeline:
    """
    Extract 25+ ML features from raw OHLCV data.
    Features are stationary, normalized, and forward-looking leak-free.
    """

    FEATURE_COLUMNS = [
        # Price-derived (returns, not prices - stationary)
        "return_1", "return_3", "return_5", "return_10",
        # Momentum
        "rsi_14", "rsi_7", "macd_hist", "stoch_k",
        # Trend
        "adx", "ema_9_21_cross", "ema_21_50_cross", "trend_strength",
        # Volatility
        "atr_pct", "bb_bandwidth", "bb_pct",
        # Volume
        "volume_ratio", "obv_change",
        # Market structure
        "price_vs_vwap", "price_vs_bb_mid",
        # Time features
        "hour_sin", "hour_cos", "dow_sin", "dow_cos",
    ]

    def extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract ML-ready feature matrix from OHLCV DataFrame."""
        df = TechnicalIndicators.add_all_indicators(df)
        features = pd.DataFrame(index=df.index)

        # Returns (stationary price features)
        for n in [1, 3, 5, 10]:
            features[f"return_{n}"] = df["close"].pct_change(n)

        # Indicator features
        for col in [
            "rsi_14", "rsi_7", "macd_hist", "stoch_k", "adx",
            "atr_pct", "bb_bandwidth", "bb_pct", "volume_ratio",
        ]:
            features[col] = df[col]

        # Cross signals
        features["ema_9_21_cross"] = (df["ema_9"] - df["ema_21"]) / df["close"]
        features["ema_21_50_cross"] = (df["ema_21"] - df["ema_50"]) / df["close"]
        features["trend_strength"] = df["adx"] * np.sign(df["ema_9"] - df["ema_50"])

        # OBV normalized change
        features["obv_change"] = df["obv"].pct_change(3)

        # Price vs key levels
        features["price_vs_vwap"] = (df["close"] - df["vwap"]) / df["vwap"]
        features["price_vs_bb_mid"] = (df["close"] - df["bb_middle"]) / df["bb_middle"]

        # Cyclical time encoding (no data leakage)
        if df.index.dtype == "int64":
            timestamps = pd.to_datetime(df.index, unit="ms")
        else:
            timestamps = df.index

        try:
            hours = timestamps.hour
            dow = timestamps.dayofweek
        except AttributeError:
            hours = pd.Series(0, index=df.index)
            dow = pd.Series(0, index=df.index)

        features["hour_sin"] = np.sin(2 * np.pi * hours / 24)
        features["hour_cos"] = np.cos(2 * np.pi * hours / 24)
        features["dow_sin"] = np.sin(2 * np.pi * dow / 7)
        features["dow_cos"] = np.cos(2 * np.pi * dow / 7)

        return features.dropna()

    def create_labels(self, df: pd.DataFrame, forward_periods: int = 3) -> pd.Series:
        """
        Binary label: 1 = price UP by >0.5% in next N periods, 0 = DOWN/flat.
        CRITICAL: Shift forward to prevent lookahead bias.
        """
        future_return = df["close"].pct_change(forward_periods).shift(-forward_periods)
        labels = (future_return > 0.005).astype(int)
        return labels

    def prepare_training_data(self, df: pd.DataFrame):
        """Return (X, y) arrays ready for model training."""
        features = self.extract_features(df)
        labels = self.create_labels(df)

        # Align indices
        common_idx = features.index.intersection(labels.index)
        X = features.loc[common_idx].values
        y = labels.loc[common_idx].values

        # Remove any remaining NaNs
        mask = ~np.isnan(X).any(axis=1) & ~np.isnan(y)
        return X[mask], y[mask]
